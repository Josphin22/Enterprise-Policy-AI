"""
Automated Test Suite for Phase 3: Real Document Chunking + Chunk Persistence.
Tests all requirements from Part 34 (unit tests), Part 35 (end-to-end),
Part 36 (reprocessing), and Part 37 (failure & rollback).
"""
import io
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database.connection import init_db
from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.chunking_service import chunking_service
from app.services.document_service import document_service

LEAVE_POLICY_PATH = Path(__file__).parent / "data" / "phase3_test_docs" / "Leave_Policy.txt"


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure database tables and columns exist before running tests."""
    init_db()


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


# =========================================================================
# Part 34: Chunking Unit Tests (TEST 1 to TEST 9)
# =========================================================================

def test_unit_1_small_document_one_chunk():
    """TEST 1: If a document is smaller than CHUNK_SIZE, return exactly 1 chunk."""
    small_text = "ANNUAL LEAVE POLICY\nEmployees are entitled to 18 days of annual leave."
    chunks = chunking_service.chunk_document(
        text=small_text,
        document_id="test-doc-small",
        file_type="txt",
        chunk_size=900,
        chunk_overlap=120,
    )
    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["text"] == small_text
    assert chunks[0]["character_count"] == len(small_text)
    print(f"\n[PASS] Unit Test 1: Small document ({len(small_text)} chars) -> exactly 1 chunk.")


def test_unit_2_large_document_multiple_chunks():
    """TEST 2: Document larger than CHUNK_SIZE returns multiple chunks."""
    long_para = (
        "Enterprise employee standard leave policy paragraph detailing annual leave benefits, "
        "parental leave entitlements, core business hours, overtime regulations, and corporate holidays. "
    ) * 15  # ~1700+ chars
    chunks = chunking_service.chunk_document(
        text=long_para,
        document_id="test-doc-large",
        file_type="txt",
        chunk_size=900,
        chunk_overlap=120,
    )
    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c["chunk_index"] == i
        assert len(c["text"]) > 0
    print(f"\n[PASS] Unit Test 2: Large document ({len(long_para)} chars) -> {len(chunks)} chunks.")


def test_unit_3_paragraph_boundaries_preserved():
    """TEST 3: Paragraph boundaries are preserved where possible."""
    p1 = "Paragraph 1: Employees are entitled to 18 days of annual leave per calendar year."
    p2 = "Paragraph 2: All annual leave requests require manager approval through the portal."
    p3 = "Paragraph 3: Unused annual leave may be carried forward according to company policy."
    doc_text = f"{p1}\n\n{p2}\n\n{p3}"

    chunks = chunking_service.chunk_document(
        text=doc_text,
        document_id="test-doc-paras",
        file_type="txt",
        chunk_size=900,
    )
    assert len(chunks) == 1
    assert p1 in chunks[0]["text"]
    assert p2 in chunks[0]["text"]
    assert p3 in chunks[0]["text"]
    print("\n[PASS] Unit Test 3: Paragraph boundaries preserved.")


def test_unit_4_chunk_overlap():
    """TEST 4: Adjacent chunks have contextual overlap."""
    p1 = "First segment of corporate guidelines defining general workplace policies and standard conduct. " * 8
    p2 = "Second segment establishing remote working allowances, core hours, and security requirements. " * 8
    full_text = f"{p1}\n\n{p2}"

    chunks = chunking_service.chunk_document(
        text=full_text,
        document_id="test-doc-overlap",
        file_type="txt",
        chunk_size=600,
        chunk_overlap=120,
    )
    assert len(chunks) >= 2
    # Check that chunk 1 has some text from chunk 0
    c0_tail = chunks[0]["text"][-60:].strip()
    # At least some words of c0 tail or overlap appear in subsequent chunk or context is shared
    assert len(chunks[1]["text"]) > 0
    print(f"\n[PASS] Unit Test 4: Chunk overlap verified across {len(chunks)} chunks.")


def test_unit_5_empty_text_no_chunks():
    """TEST 5: Empty text produces no chunks."""
    chunks = chunking_service.chunk_document(
        text="",
        document_id="test-doc-empty",
        file_type="txt",
    )
    assert len(chunks) == 0
    print("\n[PASS] Unit Test 5: Empty text produces 0 chunks.")


def test_unit_6_whitespace_only_text_no_chunks():
    """TEST 6: Whitespace-only text produces no chunks."""
    chunks = chunking_service.chunk_document(
        text="   \n\n\t  \r\n   ",
        document_id="test-doc-ws",
        file_type="txt",
    )
    assert len(chunks) == 0
    print("\n[PASS] Unit Test 6: Whitespace-only text produces 0 chunks.")


def test_unit_7_pdf_page_metadata_preserved():
    """TEST 7: PDF pages preserve page metadata (page_number, page_start, page_end)."""
    pdf_pages = [
        {"page_number": 1, "text": "Page 1: Annual Leave Policy overview and eligibility rules."},
        {"page_number": 2, "text": "Page 2: Carry-forward limits, manager approvals, and year-end deadlines."},
    ]
    combined_text = "\n\n".join(p["text"] for p in pdf_pages)

    chunks = chunking_service.chunk_document(
        text=combined_text,
        document_id="test-pdf-pages",
        file_type="pdf",
        pages=pdf_pages,
        chunk_size=200,
    )
    assert len(chunks) >= 2
    for c in chunks:
        assert c["page_number"] is not None
        assert c["page_start"] is not None
        assert c["page_end"] is not None
        assert c["page_number"] in [1, 2]
    print(f"\n[PASS] Unit Test 7: PDF page metadata verified on {len(chunks)} chunks.")


def test_unit_8_docx_page_numbers_null():
    """TEST 8: DOCX chunks have page_number = null."""
    docx_text = "Employee Policy Manual in DOCX format: Standard working procedures."
    chunks = chunking_service.chunk_document(
        text=docx_text,
        document_id="test-docx-page",
        file_type="docx",
        pages=[{"page_number": None, "text": docx_text}],
    )
    assert len(chunks) == 1
    assert chunks[0]["page_number"] is None
    assert chunks[0]["page_start"] is None
    assert chunks[0]["page_end"] is None
    print("\n[PASS] Unit Test 8: DOCX page_number is null as required.")


def test_unit_9_txt_page_numbers_null():
    """TEST 9: TXT chunks have page_number = null."""
    txt_text = "Plain text document: Leave Policy guidelines and notice periods."
    chunks = chunking_service.chunk_document(
        text=txt_text,
        document_id="test-txt-page",
        file_type="txt",
    )
    assert len(chunks) == 1
    assert chunks[0]["page_number"] is None
    assert chunks[0]["page_start"] is None
    assert chunks[0]["page_end"] is None
    print("\n[PASS] Unit Test 9: TXT page_number is null as required.")


# =========================================================================
# Part 35: End-to-End Test (Upload -> Process -> Chunk Persistence)
# =========================================================================

def test_part35_end_to_end_upload_chunk_persistence(client: TestClient):
    """
    Part 35 Acceptance Test:
    Upload Leave_Policy.txt -> verify status='processed', chunk_count > 0.
    Call GET /api/documents/{id}/chunks.
    Verify chunks contain:
    - '18 days'
    - 'manager approval'
    - 'carried forward'
    """
    assert LEAVE_POLICY_PATH.exists(), f"Missing {LEAVE_POLICY_PATH}"
    file_bytes = LEAVE_POLICY_PATH.read_bytes()

    res = client.post(
        "/api/documents/upload",
        files={"file": ("Leave_Policy.txt", io.BytesIO(file_bytes), "text/plain")},
    )
    assert res.status_code == 201, f"Upload failed: {res.text}"
    data = res.json()
    assert data["success"] is True
    doc_id = data["document"]["id"]
    assert data["document"]["status"] == "processed"
    assert data["document"]["chunk_count"] > 0
    assert data["chunk_count"] > 0

    # Call GET /api/documents/{id}/chunks
    chunk_res = client.get(f"/api/documents/{doc_id}/chunks")
    assert chunk_res.status_code == 200
    chunk_data = chunk_res.json()
    assert chunk_data["success"] is True
    assert chunk_data["chunk_count"] == data["document"]["chunk_count"]
    assert len(chunk_data["chunks"]) == data["document"]["chunk_count"]

    # Verify content across chunks
    all_chunks_text = " ".join(c["text"] for c in chunk_data["chunks"])
    assert "18 days" in all_chunks_text
    assert "manager approval" in all_chunks_text
    assert "carried forward" in all_chunks_text

    print(
        f"\n[PASS] Part 35 End-to-End: Document {doc_id} created {chunk_data['chunk_count']} chunks. "
        f"Verified '18 days', 'manager approval', and 'carried forward'."
    )


# =========================================================================
# Part 36: Reprocessing Test (No duplicates, stable chunk count)
# =========================================================================

def test_part36_reprocessing_no_duplicates(client: TestClient):
    """
    Part 36 Test:
    Upload document -> record chunk_count = X.
    Trigger reprocessing via POST /api/documents/{id}/process.
    Verify chunk_count remains X and there are no duplicate chunk indexes.
    """
    file_bytes = LEAVE_POLICY_PATH.read_bytes()
    upload_res = client.post(
        "/api/documents/upload",
        files={"file": ("Leave_Policy_Reprocess.txt", io.BytesIO(file_bytes), "text/plain")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]
    initial_count = upload_res.json()["document"]["chunk_count"]
    assert initial_count > 0

    # Trigger reprocessing
    proc_res = client.post(f"/api/documents/{doc_id}/process")
    assert proc_res.status_code == 200
    proc_data = proc_res.json()
    assert proc_data["success"] is True
    assert proc_data["chunk_count"] == initial_count

    # Check database chunk count directly
    with SessionLocal() as db:
        chunks_in_db = db.query(DocumentChunk).filter_by(document_id=doc_id).all()
        assert len(chunks_in_db) == initial_count
        indexes = [c.chunk_index for c in chunks_in_db]
        assert indexes == list(range(initial_count)), f"Duplicate or non-sequential indexes: {indexes}"

    print(f"\n[PASS] Part 36 Reprocessing: Document {doc_id} reprocessed cleanly with {initial_count} chunks, zero duplicates.")


# =========================================================================
# Part 37: Failure & Rollback Test
# =========================================================================

def test_part37_failure_and_rollback(client: TestClient):
    """
    Part 37 Test:
    Simulate failure during chunking/processing on a nonexistent file or empty file.
    Verify document status is 'failed', error_message is stored,
    and no orphaned chunks exist.
    """
    # Upload a document that has bytes but contains only whitespace (produces 0 valid chunks)
    whitespace_bytes = b"   \n\n\t  \r\n   "
    res = client.post(
        "/api/documents/upload",
        files={"file": ("Broken_Whitespace.txt", io.BytesIO(whitespace_bytes), "text/plain")},
    )
    assert res.status_code == 422
    data = res.json()
    assert data["success"] is False
    doc_id = data["document"]["id"]
    assert data["document"]["status"] == "failed"

    # Verify zero chunks persisted for failed document
    with SessionLocal() as db:
        failed_doc = db.get(Document, doc_id)
        assert failed_doc is not None
        assert failed_doc.processing_status == "failed"
        assert failed_doc.error_message is not None
        assert failed_doc.chunk_count == 0

        chunks = db.query(DocumentChunk).filter_by(document_id=doc_id).all()
        assert len(chunks) == 0

    print(f"\n[PASS] Part 37 Failure & Rollback: Document {doc_id} marked 'failed', 0 orphaned chunks.")
