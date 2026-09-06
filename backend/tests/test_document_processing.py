import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.base import Base
from app.database.session import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.main import app
from app.services.document_processing.pdf_loader import PDFLoader
from app.services.document_processing.docx_loader import DocxLoader
from app.services.document_processing.txt_loader import TxtLoader
from app.services.document_processing.text_cleaner import TextCleaner
from app.services.document_processing.chunker import DocumentChunker, ProcessedChunk
from app.services.document_processing.base_loader import ExtractedBlock
from app.services.document_processing.processor import DocumentProcessor
from app.services.system_service import system_service


# Isolated in-memory SQLite database engine for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create fresh in-memory schema for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Test client with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================================================================
# 1. Text Cleaner Tests
# ============================================================================

def test_text_cleaner_normalizes_whitespace_and_preserves_policy_numbers():
    raw_text = "   All   full-time employees   are entitled to   15 days  \r\n\r\n  of annual leave.  \n\n\n\nMax carry-over: 5 days.   "
    cleaned = TextCleaner.clean(raw_text)

    # Must preserve exact numbers and terminology
    assert "15 days" in cleaned
    assert "5 days" in cleaned
    assert "annual leave" in cleaned
    # Must collapse excessive line breaks and whitespace
    assert "   " not in cleaned
    assert "\r" not in cleaned
    assert "\n\n\n" not in cleaned


def test_text_cleaner_handles_empty_and_special_chars():
    assert TextCleaner.clean("") == ""
    assert TextCleaner.clean("   ") == ""
    # Control character stripping while preserving standard text
    text_with_control = "Policy text\x00\x08with hidden control chars"
    cleaned = TextCleaner.clean(text_with_control)
    assert "\x00" not in cleaned
    assert "Policy text with hidden control chars" == cleaned


# ============================================================================
# 2. Loader Tests (TXT, PDF, DOCX)
# ============================================================================

def test_txt_loader_utf8_and_fallback(tmp_path):
    txt_file = tmp_path / "sample_policy.txt"
    txt_file.write_text("Company standard working hours: 09:00 AM to 05:00 PM.", encoding="utf-8")

    loader = TxtLoader()
    blocks = loader.load(txt_file)

    assert len(blocks) == 1
    assert "09:00 AM to 05:00 PM" in blocks[0].text
    assert blocks[0].page_number is None
    assert blocks[0].metadata["file_type"] == "txt"


def test_pdf_loader_with_sample_document():
    pdf_path = Path("e:/GEN AI/data/sample_documents/Leave_Policy.pdf")
    if not pdf_path.exists():
        pytest.skip("Sample Leave_Policy.pdf not found")

    loader = PDFLoader()
    blocks = loader.load(pdf_path)

    assert len(blocks) >= 1
    # Check page preservation
    assert blocks[0].page_number == 1
    assert "15 days" in blocks[0].text or "Leave Policy" in blocks[0].text


def test_docx_loader_with_sample_document():
    docx_path = Path("e:/GEN AI/data/sample_documents/Leave_Policy.docx")
    if not docx_path.exists():
        pytest.skip("Sample Leave_Policy.docx not found")

    loader = DocxLoader()
    blocks = loader.load(docx_path)

    assert len(blocks) >= 1
    # Check that DOCX sets page_number to None
    for b in blocks:
        assert b.page_number is None

    full_text = " ".join(b.text for b in blocks)
    assert "15 days" in full_text
    assert "Annual Vacation" in full_text


# ============================================================================
# 3. Document Chunker Tests
# ============================================================================

def test_chunker_splits_text_and_preserves_policy_numbers():
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    blocks = [
        ExtractedBlock(
            text="Employees are entitled to 15 days of annual paid vacation leave per calendar year. Leave accrues on a pro-rata basis at 1.25 days per month.",
            page_number=1,
            section="Leave Entitlement",
        )
    ]

    chunks = chunker.create_chunks(
        document_id="doc-123",
        filename="leave.pdf",
        file_type="pdf",
        extracted_blocks=blocks,
    )

    assert len(chunks) >= 1
    # Verify sequential index and page preservation
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 1
    assert chunks[0].section == "Leave Entitlement"
    assert chunks[0].document_id == "doc-123"

    combined_text = " ".join(c.text for c in chunks)
    assert "15 days" in combined_text


def test_chunker_does_not_discard_short_critical_rules():
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=100)
    blocks = [
        ExtractedBlock(
            text="Maximum leave: 15 days.",
            page_number=2,
            section="Limits",
        )
    ]

    chunks = chunker.create_chunks(
        document_id="doc-short",
        filename="rules.txt",
        file_type="txt",
        extracted_blocks=blocks,
    )

    assert len(chunks) == 1
    assert chunks[0].text == "Maximum leave: 15 days."
    assert chunks[0].character_count == len("Maximum leave: 15 days.")


# ============================================================================
# 4. Processor Pipeline & Reprocessing Tests
# ============================================================================

def test_process_document_success(db_session, tmp_path):
    # Create sample physical file
    test_file = tmp_path / "Leave_Policy.txt"
    test_file.write_text(
        "Enterprise Leave Policy\n\nAll employees are entitled to 15 days of annual leave.",
        encoding="utf-8",
    )

    # Register document in database
    doc = Document(
        id="test-proc-doc-1",
        filename="test_leave.txt",
        original_filename="Leave_Policy.txt",
        file_type="txt",
        file_size=len(test_file.read_bytes()),
        file_path=str(test_file),
        processing_status="uploaded",
        chunk_count=0,
    )
    db_session.add(doc)
    db_session.commit()

    # Run processing
    res = DocumentProcessor.process_document(doc.id, db_session)

    assert res["success"] is True
    assert res["status"] == "processed"
    assert res["chunk_count"] > 0

    # Verify document in DB
    refreshed_doc = db_session.get(Document, doc.id)
    assert refreshed_doc.processing_status == "processed"
    assert refreshed_doc.chunk_count == res["chunk_count"]

    # Verify chunks in DB
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
    assert len(chunks) == res["chunk_count"]
    assert any("15 days" in c.text for c in chunks)


def test_reprocessing_deletes_old_chunks_without_duplicates(db_session, tmp_path):
    test_file = tmp_path / "Reprocess_Policy.txt"
    test_file.write_text("Version 1: 15 days of leave.", encoding="utf-8")

    doc = Document(
        id="test-reproc-doc",
        filename="reproc.txt",
        original_filename="Reprocess_Policy.txt",
        file_type="txt",
        file_size=len(test_file.read_bytes()),
        file_path=str(test_file),
        processing_status="uploaded",
        chunk_count=0,
    )
    db_session.add(doc)
    db_session.commit()

    # First processing
    res1 = DocumentProcessor.process_document(doc.id, db_session)
    count1 = res1["chunk_count"]

    # Update file content and re-process
    test_file.write_text("Version 2: Updated leave policy to 18 days of annual leave.", encoding="utf-8")
    res2 = DocumentProcessor.process_document(doc.id, db_session)
    count2 = res2["chunk_count"]

    # Chunks in DB should match new count only (no duplicates)
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
    assert len(chunks) == count2
    assert all("Version 2" in c.text for c in chunks)


def test_process_missing_physical_file_marks_failed(db_session):
    doc = Document(
        id="missing-file-doc",
        filename="nonexistent.txt",
        original_filename="nonexistent.txt",
        file_type="txt",
        file_size=100,
        file_path="e:/GEN AI/documents/nonexistent_file_path.txt",
        processing_status="uploaded",
        chunk_count=0,
    )
    db_session.add(doc)
    db_session.commit()

    with pytest.raises(Exception):
        DocumentProcessor.process_document(doc.id, db_session)

    refreshed = db_session.get(Document, doc.id)
    assert refreshed.processing_status == "failed"


# ============================================================================
# 5. API Endpoint Tests
# ============================================================================

def test_api_process_and_get_chunks(client, db_session, tmp_path):
    test_file = tmp_path / "Sample.txt"
    test_file.write_text(
        "Remote Work Policy: Eligible employees may work from home 2 days per week. "
        "Equipment reimbursement up to $500.",
        encoding="utf-8",
    )

    doc = Document(
        id="api-chunk-doc-1",
        filename="sample.txt",
        original_filename="Sample.txt",
        file_type="txt",
        file_size=len(test_file.read_bytes()),
        file_path=str(test_file),
        processing_status="uploaded",
        chunk_count=0,
    )
    db_session.add(doc)
    db_session.commit()

    # Process via API
    proc_resp = client.post(f"/api/documents/{doc.id}/process")
    assert proc_resp.status_code == 200
    proc_data = proc_resp.json()
    assert proc_data["success"] is True
    assert proc_data["status"] == "processed"
    assert proc_data["chunk_count"] >= 1

    # Fetch chunks via API
    chunks_resp = client.get(f"/api/documents/{doc.id}/chunks")
    assert chunks_resp.status_code == 200
    chunks_data = chunks_resp.json()
    assert chunks_data["success"] is True
    assert chunks_data["chunk_count"] == proc_data["chunk_count"]
    assert len(chunks_data["chunks"]) == proc_data["chunk_count"]
    assert "$500" in chunks_data["chunks"][0]["text"]


def test_api_knowledge_base_status_reflects_processed_documents_and_chunks(client, db_session, tmp_path):
    test_file = tmp_path / "KB_Test.txt"
    test_file.write_text("Knowledge base test document with sample text for chunking.", encoding="utf-8")

    doc = Document(
        id="kb-test-doc",
        filename="kb.txt",
        original_filename="KB_Test.txt",
        file_type="txt",
        file_size=len(test_file.read_bytes()),
        file_path=str(test_file),
        processing_status="uploaded",
        chunk_count=0,
    )
    db_session.add(doc)
    db_session.commit()

    # Process doc
    client.post(f"/api/documents/{doc.id}/process")

    # Query KB status
    kb_resp = client.get("/api/knowledge-base/status")
    assert kb_resp.status_code == 200
    kb_data = kb_resp.json()

    assert kb_data["documents"] == 1
    assert kb_data["processed_documents"] == 1
    assert kb_data["chunks"] >= 1
    assert "vectors" in kb_data
    assert kb_data["vector_database"] == "FAISS"
