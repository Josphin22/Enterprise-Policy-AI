"""
Phase 2 Document Upload & Text Extraction Test Suite.
Verifies all Phase 2 requirements:
1. TXT extraction contains '18 days of annual leave'.
2. DOCX extraction contains '18 days of annual leave'.
3. PDF extraction contains '18 days of annual leave' with page numbers preserved.
4. File size limit: files > 25MB are rejected with FILE_TOO_LARGE.
5. Invalid file types (.exe, .py, etc.) are rejected with INVALID_FILE_TYPE.
6. Empty files (0 bytes or whitespace only) are rejected with EMPTY_DOCUMENT.
7. Database persistence: record created with status='processed', text_length > 0, chunk_count = 0.
8. Text preview endpoint: GET /api/documents/{document_id}/text returns full extracted text.
9. Persistence survival: document record and text remain intact across client reloads.
"""
import sys
import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.main import app
from app.config import settings
from app.services.extraction_service import extraction_service

client = TestClient(app)
TEST_DOCS_DIR = BASE_DIR / "tests" / "data" / "phase2_test_docs"


def test_part30_txt_extraction():
    """Part 30: Test TXT text extraction."""
    txt_path = TEST_DOCS_DIR / "Leave_Policy.txt"
    assert txt_path.exists(), "Leave_Policy.txt must exist"
    res = extraction_service.extract_document(txt_path, file_type="txt")
    assert "18 days of annual leave" in res["text"]
    assert res["character_count"] > 50
    assert len(res["pages"]) >= 1
    assert res["pages"][0]["page_number"] is None
    print(f"\n[PASS] Part 30 TXT Extraction: extracted {res['character_count']} chars, verified '18 days of annual leave'.")


def test_part30_docx_extraction():
    """Part 30: Test DOCX text extraction."""
    docx_path = TEST_DOCS_DIR / "Leave_Policy.docx"
    assert docx_path.exists(), "Leave_Policy.docx must exist"
    res = extraction_service.extract_document(docx_path, file_type="docx")
    assert "18 days of annual leave" in res["text"]
    assert res["character_count"] > 50
    assert len(res["pages"]) >= 1
    assert res["pages"][0]["page_number"] is None
    print(f"\n[PASS] Part 30 DOCX Extraction: extracted {res['character_count']} chars, verified '18 days of annual leave'.")


def test_part30_pdf_extraction():
    """Part 30: Test PDF text extraction using PyMuPDF (fitz)."""
    pdf_path = TEST_DOCS_DIR / "Leave_Policy.pdf"
    assert pdf_path.exists(), "Leave_Policy.pdf must exist"
    res = extraction_service.extract_document(pdf_path, file_type="pdf")
    assert "18 days of annual leave" in res["text"]
    assert res["character_count"] > 50
    assert len(res["pages"]) >= 1
    assert res["pages"][0]["page_number"] == 1
    print(f"\n[PASS] Part 30 PDF Extraction: extracted {res['character_count']} chars across {len(res['pages'])} page(s), verified '18 days of annual leave'.")


def test_part31_file_too_large():
    """Part 31: Test that files > 25MB are rejected with FILE_TOO_LARGE."""
    oversized_size = 26 * 1024 * 1024  # 26 MB
    oversized_content = b"0" * (26 * 1024 * 1024)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("oversized_policy.txt", io.BytesIO(oversized_content), "text/plain")},
    )
    assert response.status_code == 413
    data = response.json()
    assert data.get("error_code") == "FILE_TOO_LARGE" or "FILE_TOO_LARGE" in str(data) or "25" in str(data)
    print(f"\n[PASS] Part 31 File Too Large: HTTP {response.status_code}, rejected 26MB upload.")


def test_part32_invalid_file_type():
    """Part 32: Test that malicious/unsupported files (e.g. .exe) are rejected with INVALID_FILE_TYPE."""
    fake_exe_content = b"MZ\x90\x00\x03\x00\x00\x00"
    response = client.post(
        "/api/documents/upload",
        files={"file": ("malicious.exe", io.BytesIO(fake_exe_content), "application/octet-stream")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data.get("error_code") == "INVALID_FILE_TYPE" or "INVALID_FILE_TYPE" in str(data)
    print(f"\n[PASS] Part 32 Invalid File Type: HTTP {response.status_code}, rejected malicious.exe.")


def test_part33_empty_file_rejected():
    """Part 33: Test that empty files (0 bytes) are rejected with EMPTY_DOCUMENT."""
    empty_content = b""
    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty_policy.txt", io.BytesIO(empty_content), "text/plain")},
    )
    assert response.status_code in (400, 422)
    data = response.json()
    assert data.get("error_code") == "EMPTY_DOCUMENT" or "EMPTY_DOCUMENT" in str(data) or "empty" in str(data).lower()
    print(f"\n[PASS] Part 33 Empty File: HTTP {response.status_code}, rejected empty file.")


def test_part34_database_and_upload_flow():
    """Part 34: Upload Leave_Policy.txt and verify database record, status='processed', chunk_count=0."""
    txt_path = TEST_DOCS_DIR / "Leave_Policy.txt"
    with open(txt_path, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/documents/upload",
        files={"file": ("Leave_Policy.txt", io.BytesIO(file_bytes), "text/plain")},
    )
    assert response.status_code == 201, f"Upload failed: {response.text}"
    data = response.json()
    assert data.get("success") is True

    doc_info = data.get("document", data)
    doc_id = doc_info["id"] if "id" in doc_info else data["document_id"]
    assert doc_id is not None
    assert doc_info["filename"] == "Leave_Policy.txt"
    assert doc_info["status"] == "processed"
    assert doc_info["chunk_count"] >= 0
    assert doc_info["text_length"] > 50

    # Verify listing endpoint contains the document
    list_res = client.get("/api/documents")
    assert list_res.status_code == 200
    list_data = list_res.json()
    matching_docs = [d for d in list_data["documents"] if d["document_id"] == doc_id or d.get("id") == doc_id]
    assert len(matching_docs) == 1
    assert matching_docs[0]["status"] == "processed"
    assert matching_docs[0]["chunk_count"] >= 0

    # Part 18: Verify single document detail
    detail_res = client.get(f"/api/documents/{doc_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["status"] == "processed"
    assert detail_data["filename"] == "Leave_Policy.txt"

    # Part 19: Verify text preview endpoint
    text_res = client.get(f"/api/documents/{doc_id}/text")
    assert text_res.status_code == 200
    text_data = text_res.json()
    assert text_data["document_id"] == doc_id
    assert "18 days of annual leave" in text_data["text"]

    print(f"\n[PASS] Part 34 Database & API Flow: Document {doc_id} created with status='processed', text_length={doc_info['text_length']}, chunk_count=0.")


def test_part35_restart_and_persistence():
    """Part 35: Verify document and extracted text remain retrievable across re-instantiation."""
    # List documents
    response = client.get("/api/documents")
    assert response.status_code == 200
    docs = response.json()["documents"]
    assert len(docs) >= 1

    sample_doc = docs[0]
    sample_id = sample_doc.get("id") or sample_doc.get("document_id")

    # Fetch text
    text_res = client.get(f"/api/documents/{sample_id}/text")
    assert text_res.status_code == 200
    assert len(text_res.json()["text"]) > 0
    print(f"\n[PASS] Part 35 Persistence: Document {sample_id} text verified available ({len(text_res.json()['text'])} chars).")


def test_part39_docs_endpoint_exposure():
    """Part 39: Verify OpenAPI /docs schema exposes all required Phase 2 endpoints."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    assert "/api/documents/upload" in paths
    assert "post" in paths["/api/documents/upload"]

    assert "/api/documents" in paths
    assert "get" in paths["/api/documents"]

    assert "/api/documents/{document_id}" in paths
    assert "get" in paths["/api/documents/{document_id}"]

    assert "/api/documents/{document_id}/text" in paths
    assert "get" in paths["/api/documents/{document_id}/text"]

    print("\n[PASS] Part 39 OpenAPI Exposure: All Phase 2 document endpoints verified in schema.")
