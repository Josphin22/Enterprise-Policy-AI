import os
import io
import pytest
from unittest.mock import patch
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.base import Base
from app.database.session import get_db
from app.models.user import User
from app.models.document import Document
from app.models.document_metadata import DocumentMetadata
from app.models.chat import ChatSession, ChatMessage
from app.models.feedback import Feedback
from app.main import app

# Isolated in-memory SQLite database with StaticPool for thread-safe test execution
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh tables for every test."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    """Provide a clean database session for unit tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """FastAPI TestClient with overridden get_db dependency."""
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


# ==========================================
# 1. Database Connection & Table Creation Tests
# ==========================================
def test_table_creation(db_session: Session):
    """Verify that all Phase 4 tables are created successfully."""
    tables = Base.metadata.tables.keys()
    expected_tables = {
        "users",
        "documents",
        "document_metadata",
        "document_chunks",
        "chat_sessions",
        "chat_messages",
        "feedback",
    }
    for table in expected_tables:
        assert table in tables, f"Expected table '{table}' in metadata"


# ==========================================
# 2. User Model Tests
# ==========================================
def test_user_creation_and_query(db_session: Session):
    """Verify creating and retrieving a User."""
    user = User(
        username="john_doe",
        email="john.doe@enterprise.local",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    retrieved = db_session.scalar(select(User).where(User.email == "john.doe@enterprise.local"))
    assert retrieved is not None
    assert retrieved.username == "john_doe"
    assert retrieved.is_active is True
    assert retrieved.id is not None
    assert retrieved.created_at is not None


# ==========================================
# 3. Document & DocumentMetadata Model Tests
# ==========================================
def test_document_and_metadata_models(db_session: Session):
    """Verify Document and DocumentMetadata creation and relationships."""
    doc = Document(
        filename="12345_Test_Policy.pdf",
        original_filename="Test_Policy.pdf",
        file_type="pdf",
        file_size=1024,
        file_path="/tmp/12345_Test_Policy.pdf",
        processing_status="uploaded",
        chunk_count=0,
    )
    db_session.add(doc)
    db_session.commit()

    meta = DocumentMetadata(
        document_id=doc.id,
        title="Corporate Leave Policy",
        description="Official annual and sick leave guidelines",
        author="HR Department",
    )
    db_session.add(meta)
    db_session.commit()

    # Query back
    retrieved_doc = db_session.get(Document, doc.id)
    assert retrieved_doc is not None
    assert retrieved_doc.original_filename == "Test_Policy.pdf"
    assert retrieved_doc.processing_status == "uploaded"
    assert retrieved_doc.metadata_rel is not None
    assert retrieved_doc.metadata_rel.title == "Corporate Leave Policy"


# ==========================================
# 4. ChatSession, ChatMessage, Feedback Tests
# ==========================================
def test_chat_session_message_and_feedback(db_session: Session):
    """Verify ChatSession, ChatMessage, and Feedback relationships."""
    session = ChatSession(title="Leave Policy Q&A")
    db_session.add(session)
    db_session.commit()

    msg = ChatMessage(
        session_id=session.id,
        role="user",
        content="How many vacation days do full-time employees get?",
    )
    db_session.add(msg)
    db_session.commit()

    fb = Feedback(
        message_id=msg.id,
        rating="positive",
        comment="Helpful query",
    )
    db_session.add(fb)
    db_session.commit()

    retrieved_session = db_session.get(ChatSession, session.id)
    assert len(retrieved_session.messages) == 1
    assert retrieved_session.messages[0].content == "How many vacation days do full-time employees get?"
    assert len(retrieved_session.messages[0].feedbacks) == 1
    assert retrieved_session.messages[0].feedbacks[0].rating == "positive"


# ==========================================
# 5. API Endpoints Integration Tests (PostgreSQL persistence)
# ==========================================
def test_document_upload_list_detail_and_delete(client: TestClient):
    """
    Test complete lifecycle:
    Upload document -> saved in DB -> listed from DB -> get details -> delete from DB and filesystem.
    """
    sample_content = b"Enterprise standard leave policy: 20 days annual vacation."
    file_payload = ("Leave_Policy_2026.txt", io.BytesIO(sample_content), "text/plain")

    # 1. Upload
    upload_res = client.post("/api/documents/upload", files={"file": file_payload})
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    doc_id = doc_data["document_id"]
    assert doc_data["status"] == "uploaded"
    assert doc_data["filename"] == "Leave_Policy_2026.txt"

    # 2. List documents (must contain our uploaded document)
    list_res = client.get("/api/documents")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    matching = [d for d in list_data["documents"] if d["document_id"] == doc_id]
    assert len(matching) == 1
    assert matching[0]["filename"] == "Leave_Policy_2026.txt"

    # 3. Get document details
    detail_res = client.get(f"/api/documents/{doc_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["document_id"] == doc_id
    assert detail_res.json()["status"] == "uploaded"

    # 4. Knowledge base status reflects actual document count
    kb_res = client.get("/api/knowledge-base/status")
    assert kb_res.status_code == 200
    assert kb_res.json()["status"] in ("ready", "not_built")
    assert kb_res.json()["documents"] >= 1

    # 5. Process endpoint (Phase 5 Active Extraction and Chunking)
    proc_res = client.post(f"/api/documents/{doc_id}/process")
    assert proc_res.status_code == 200
    assert proc_res.json()["status"] == "processed"
    assert proc_res.json()["chunk_count"] >= 1

    # 6. Delete document
    del_res = client.delete(f"/api/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # 7. Document should now return 404
    get_after_del = client.get(f"/api/documents/{doc_id}")
    assert get_after_del.status_code == 404


def test_chat_session_and_message_api(client: TestClient):
    """Test creating chat session, sending user query, and reading history."""
    # 1. Create chat session
    session_res = client.post("/api/chat/sessions", json={"title": "HR Benefit Questions"})
    assert session_res.status_code == 201
    session_id = session_res.json()["session_id"]
    assert session_res.json()["title"] == "HR Benefit Questions"

    # 2. Send user message associated with session
    chat_res = client.post(
        "/api/chat",
        json={"question": "What is the standard health insurance policy?", "session_id": session_id},
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["status"] in ("success", "retrieval_ready", "insufficient_context", "llm_not_configured", "llm_unavailable", "model_not_found")
    msg_id = chat_data["message_id"]
    assert msg_id is not None

    # 3. Read chat history for the session
    hist_res = client.get(f"/api/chat/history?session_id={session_id}")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert len(hist_data["history"]) >= 1
    assert hist_data["history"][0]["content"] == "What is the standard health insurance policy?"
    assert hist_data["history"][0]["role"] == "user"

    # 4. Submit feedback for the message
    fb_res = client.post(
        "/api/chat/feedback",
        json={"message_id": msg_id, "rating": "positive", "comment": "Clear query log"},
    )
    assert fb_res.status_code == 201
    assert fb_res.json()["success"] is True


def test_feedback_nonexistent_message_returns_404(client: TestClient):
    """Submitting feedback for an unknown message ID must return 404."""
    res = client.post(
        "/api/chat/feedback",
        json={"message_id": "00000000-0000-0000-0000-000000000000", "rating": "positive"},
    )
    assert res.status_code == 404


def test_system_status_api_healthy(client: TestClient):
    """System status when database check is healthy."""
    with patch("app.services.system_service.check_db_connection", return_value=True):
        res = client.get("/api/system/status")
        assert res.status_code == 200
        data = res.json()
        assert data["backend"]["status"] == "healthy"
        assert data["database"]["status"] == "healthy"
        assert data["vector_database"]["status"] in ("healthy", "not_configured")
        assert data["embedding_model"]["status"] in ("loaded", "not_loaded")
        assert data["llm"]["status"] in ("healthy", "unavailable", "not_configured")


def test_system_status_api_unavailable(client: TestClient):
    """System status when database check is unavailable."""
    with patch("app.services.system_service.check_db_connection", return_value=False):
        res = client.get("/api/system/status")
        assert res.status_code == 200
        data = res.json()
        assert data["backend"]["status"] == "healthy"
        assert data["database"]["status"] == "unavailable"
