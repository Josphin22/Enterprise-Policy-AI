import sys
import io
import pytest
from unittest.mock import patch
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database.base import Base
from app.database.session import get_db
from app.main import app

# Isolated in-memory SQLite database with StaticPool
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# 1. Health Endpoint
def test_health_endpoint(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Enterprise Policy RAG"


# 2. System Status Endpoint
def test_system_status_endpoint(client: TestClient):
    with patch("app.services.system_service.check_db_connection", return_value=True):
        response = client.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["backend"]["status"] == "healthy"
        assert data["database"]["status"] == "healthy"
        assert data["vector_database"]["status"] in ("healthy", "not_configured")
        assert data["embedding_model"]["status"] in ("loaded", "not_loaded")
        assert data["llm"]["status"] in ("healthy", "unavailable", "not_configured")


# 3. Document Listing
def test_get_documents_list(client: TestClient):
    response = client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert isinstance(data["documents"], list)
    assert "total" in data


# 4. Upload Valid TXT File & Lifecycle
def test_upload_valid_txt_file(client: TestClient):
    file_content = b"Enterprise standard leave policy guidelines: All full-time employees receive 20 days annual leave."
    file_obj = io.BytesIO(file_content)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("Sample_Leave_Policy.txt", file_obj, "text/plain")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "document_id" in data
    assert data["filename"] == "Sample_Leave_Policy.txt"
    assert data["file_type"] == "txt"
    assert data["status"] in ("uploaded", "processed")

    doc_id = data["document_id"]

    # Retrieve Document by ID
    get_res = client.get(f"/api/documents/{doc_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["document_id"] == doc_id
    assert get_data["filename"] == "Sample_Leave_Policy.txt"

    # Process Document (Phase 5 Active Processing)
    proc_res = client.post(f"/api/documents/{doc_id}/process")
    assert proc_res.status_code == 200
    proc_data = proc_res.json()
    assert proc_data["status"] == "processed"
    assert proc_data["chunk_count"] >= 1

    # Delete Document
    del_res = client.delete(f"/api/documents/{doc_id}")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["success"] is True
    assert del_data["document_id"] == doc_id

    # Verify document no longer exists in DB
    get_after_del = client.get(f"/api/documents/{doc_id}")
    assert get_after_del.status_code == 404


# 5. Reject Unsupported File Extension
def test_reject_unsupported_file(client: TestClient):
    bad_file = io.BytesIO(b"binary executable data")
    response = client.post(
        "/api/documents/upload",
        files={"file": ("malicious_script.exe", bad_file, "application/octet-stream")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file format" in data.get("error", "") or "detail" in str(data)


# 6. Request Nonexistent Document
def test_get_nonexistent_document(client: TestClient):
    response = client.get("/api/documents/non-existent-uuid-99999")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False


def test_delete_nonexistent_document(client: TestClient):
    response = client.delete("/api/documents/non-existent-uuid-99999")
    assert response.status_code == 404


# 7. Validate Empty / Whitespace Chat Question
def test_chat_empty_question_validation(client: TestClient):
    response = client.post("/api/chat", json={"question": "   "})
    assert response.status_code == 422


def test_chat_valid_question_persisted(client: TestClient):
    response = client.post(
        "/api/chat",
        json={"question": "How many annual leave days are allowed?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("success", "retrieval_ready", "insufficient_context", "llm_not_configured", "llm_unavailable", "model_not_found")
    assert "message_id" in data
    assert data["message_id"] is not None



def test_chat_history(client: TestClient):
    response = client.get("/api/chat/history")
    assert response.status_code == 200
    data = response.json()
    assert "history" in data
    assert isinstance(data["history"], list)


def test_chat_feedback_invalid_rating(client: TestClient):
    response = client.post(
        "/api/chat/feedback",
        json={"message_id": "msg_001", "rating": "super_good"},
    )
    assert response.status_code == 422


# 8. Knowledge Base Status & Build Endpoints
def test_knowledge_base_status(client: TestClient):
    response = client.get("/api/knowledge-base/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ready", "active", "not_built")
    assert "documents" in data
    assert "chunks" in data
    assert "vectors" in data
    assert data["vector_database"] == "FAISS"


def test_knowledge_base_build_stub(client: TestClient):
    response = client.post("/api/knowledge-base/build")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("built", "no_processed_chunks")

