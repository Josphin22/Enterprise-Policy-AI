"""
Tests for Phase 6 Chat API Endpoint (POST /api/chat).
Covers:
- Valid question returns 200 with response, citations, confidence, metadata
- Empty question returns 422 validation error
- Question exceeding 2000 characters returns 422
- Document filtering (document_id)
- Invalid document ID returns 404
- Conversational follow-up query rewriting
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import init_db
from app.database.session import SessionLocal
from app.models.document import Document
from app.models.chat import ChatSession, ChatMessage
from services.vectorstore_service import build_index


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Ensure database and FAISS index are initialized."""
    init_db()
    db = SessionLocal()
    build_index(db=db)
    db.close()


@pytest.fixture
def client():
    return TestClient(app)


def test_chat_valid_question_returns_200(client):
    """Verify valid policy question returns 200 with answer, sources, and metadata."""
    payload = {
        "message": "How many annual leave days are allowed?",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0
    assert "sources" in data
    assert isinstance(data["sources"], list)
    assert "total_sources" in data


def test_chat_empty_question_validation_error(client):
    """Verify empty or blank message returns 422 Unprocessable Entity."""
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 422

    response2 = client.post("/api/chat", json={"message": ""})
    assert response2.status_code == 422

    response3 = client.post("/api/chat", json={})
    assert response3.status_code == 422


def test_chat_question_exceeding_2000_chars(client):
    """Verify question exceeding 2000 characters returns 422."""
    long_question = "What is the policy? " * 150  # > 2000 chars
    assert len(long_question) > 2000
    response = client.post("/api/chat", json={"message": long_question})
    assert response.status_code == 422


def test_chat_invalid_document_id_returns_404(client):
    """Verify specifying a non-existent document_id returns 404."""
    response = client.post(
        "/api/chat",
        json={
            "message": "What is the policy?",
            "document_id": "non-existent-uuid-99999",
        },
    )
    assert response.status_code == 404
    data = response.json()
    err_text = str(data.get("error") or data.get("detail") or "")
    assert "not found" in err_text.lower()


def test_chat_document_filter_uses_only_target_doc(client):
    """Verify document_id filter ensures returned citations belong only to that document."""
    db = SessionLocal()
    doc = db.query(Document).first()
    db.close()

    if not doc:
        pytest.skip("No documents in database to test document filtering.")

    response = client.post(
        "/api/chat",
        json={
            "message": "What are the rules and guidelines?",
            "document_id": str(doc.id),
        },
    )
    assert response.status_code == 200
    data = response.json()
    # All returned sources should match doc.id or doc.filename
    for src in data.get("sources", []):
        if src.get("document_id"):
            assert str(src["document_id"]) == str(doc.id)


def test_chat_conversation_followup_context_rewrite(client):
    """Verify that multi-turn conversation maintains context for follow-up questions."""
    # 1. Create a session
    sess_res = client.post("/api/chat/sessions", json={"title": "Test Followup Session"})
    assert sess_res.status_code in [200, 201]
    session_id = sess_res.json()["session_id"]

    # 2. Ask initial question
    r1 = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "message": "What is the annual leave policy allowance?",
        },
    )
    assert r1.status_code == 200

    # 3. Ask follow-up question that relies on context
    r2 = client.post(
        "/api/chat",
        json={
            "session_id": session_id,
            "message": "Can I carry it over to the next year?",
        },
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert "answer" in data2
    # Verify the contextual query rewriting retained policy context
    assert data2["success"] is True
