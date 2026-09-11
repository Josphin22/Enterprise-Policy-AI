"""
Phase 7 - Advanced Enterprise RAG Chatbot Comprehensive Test Suite
Validates all 28 required test scenarios from Phase 7:
1. test_create_conversation
2. test_list_conversations
3. test_search_conversations_by_title
4. test_get_conversation_messages
5. test_rename_conversation
6. test_delete_conversation
7. test_delete_conversation_cascades_messages
8. test_chat_stores_user_message
9. test_chat_stores_assistant_message
10. test_assistant_message_stores_sources
11. test_conversation_title_auto_generated
12. test_custom_conversation_title_preserved
13. test_followup_question_detection
14. test_standalone_question_not_detected_as_followup
15. test_contextual_query_generation
16. test_contextual_query_used_for_retrieval_only
17. test_top_k_retrieval_configurable
18. test_source_diversity_balancing
19. test_source_citation_validation
20. test_source_card_preview_generation
21. test_similarity_score_labeling
22. test_feedback_endpoint_positive
23. test_feedback_endpoint_negative
24. test_feedback_with_optional_comment
25. test_chat_rate_limiting
26. test_empty_question_validation
27. test_oversized_question_handling
28. test_nonexistent_conversation_returns_404
"""

import json
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database.connection import init_db
from app.database.session import SessionLocal
from app.models.chat import ChatSession, ChatMessage, Feedback
from app.models.document import Document
from app.services.query_context_service import query_context_service
from app.rag.context_builder import context_builder
from app.rag.schemas import SourceCitation
from services.vectorstore_service import build_index


@pytest.fixture(scope="module", autouse=True)
def setup_phase7_db():
    """Ensure database and vector index are initialized for Phase 7."""
    init_db()
    db = SessionLocal()
    build_index(db=db)
    db.close()


@pytest.fixture
def client():
    return TestClient(app)


# =========================================================================
# 1-7: Conversation CRUD & Cascading Deletion
# =========================================================================

def test_create_conversation(client):
    """Scenario 1: Create a new conversation via POST /api/conversations."""
    payload = {"title": "Leave Policy Inquiry"}
    response = client.post("/api/conversations", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data or "session_id" in data
    c_id = data.get("id") or data.get("session_id")
    assert c_id is not None
    assert data.get("title") == "Leave Policy Inquiry"


def test_list_conversations(client):
    """Scenario 2: List all conversations via GET /api/conversations."""
    # Ensure at least one exists
    client.post("/api/conversations", json={"title": "Test Listing Session"})
    response = client.get("/api/conversations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Verify session items have required fields
    item = data[0]
    assert "id" in item or "session_id" in item
    assert "title" in item
    assert "updated_at" in item or "created_at" in item


def test_search_conversations_by_title(client):
    """Scenario 3: Filter conversations by search term."""
    unique_keyword = f"RemoteGuidelines_{uuid.uuid4().hex[:6]}"
    client.post("/api/conversations", json={"title": f"Policy on {unique_keyword}"})
    client.post("/api/conversations", json={"title": "Unrelated Healthcare Discussion"})

    response = client.get(f"/api/conversations?search={unique_keyword}")
    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert any(unique_keyword in s.get("title", "") for s in results)
    assert not any("Healthcare Discussion" in s.get("title", "") for s in results)


def test_get_conversation_messages(client):
    """Scenario 4: Retrieve conversation details and full message history."""
    # Create conversation and ask a question
    c_res = client.post("/api/conversations", json={"title": "Detailed History Thread"})
    session_id = c_res.json().get("id") or c_res.json().get("session_id")

    chat_res = client.post("/api/chat", json={
        "message": "What is the annual leave quota?",
        "conversation_id": session_id,
    })
    assert chat_res.status_code == 200

    # Retrieve conversation details
    detail_res = client.get(f"/api/conversations/{session_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail.get("id") == session_id
    assert "messages" in detail
    assert len(detail["messages"]) >= 2  # user message and assistant answer


def test_rename_conversation(client):
    """Scenario 5: Update conversation title via PATCH /api/conversations/{id}."""
    c_res = client.post("/api/conversations", json={"title": "Original Title"})
    session_id = c_res.json().get("id") or c_res.json().get("session_id")

    patch_res = client.patch(f"/api/conversations/{session_id}", json={"title": "Renamed Policy Discussion"})
    assert patch_res.status_code == 200
    assert patch_res.json().get("title") == "Renamed Policy Discussion"

    # Verify persistence
    get_res = client.get(f"/api/conversations/{session_id}")
    assert get_res.json().get("title") == "Renamed Policy Discussion"


def test_delete_conversation(client):
    """Scenario 6: Delete conversation via DELETE /api/conversations/{id}."""
    c_res = client.post("/api/conversations", json={"title": "Session to Delete"})
    session_id = c_res.json().get("id") or c_res.json().get("session_id")

    del_res = client.delete(f"/api/conversations/{session_id}")
    assert del_res.status_code == 200
    assert del_res.json().get("success") is True

    # Subsequent fetch must return 404
    fetch_res = client.get(f"/api/conversations/{session_id}")
    assert fetch_res.status_code == 404


def test_delete_conversation_cascades_messages(client):
    """Scenario 7: Ensure deleting a session cascades to its messages and feedback."""
    c_res = client.post("/api/conversations", json={"title": "Cascade Verification Session"})
    session_id = c_res.json().get("id") or c_res.json().get("session_id")

    # Post message
    chat_res = client.post("/api/chat", json={
        "message": "What are core office hours?",
        "conversation_id": session_id,
    })
    asst_msg_id = chat_res.json().get("assistant_message_id") or chat_res.json().get("message_id")

    # Leave feedback
    if asst_msg_id:
        client.post(f"/api/chat/messages/{asst_msg_id}/feedback", json={"rating": "positive"})

    # Verify messages exist in DB
    db = SessionLocal()
    try:
        msg_count = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()
        assert msg_count >= 1

        # Delete conversation
        del_res = client.delete(f"/api/conversations/{session_id}")
        assert del_res.status_code == 200

        # Verify messages and feedbacks are gone
        msg_count_post = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()
        assert msg_count_post == 0

        if asst_msg_id:
            fb_count = db.query(Feedback).filter(Feedback.message_id == asst_msg_id).count()
            assert fb_count == 0
    finally:
        db.close()


# =========================================================================
# 8-12: Message Persistence & Title Auto-Generation
# =========================================================================

def test_chat_stores_user_message(client):
    """Scenario 8: Chat endpoint persists user question as a role='user' message."""
    c_res = client.post("/api/conversations", json={})
    session_id = c_res.json().get("id") or c_res.json().get("session_id")

    client.post("/api/chat", json={
        "message": "How many sick days per year?",
        "conversation_id": session_id,
    })

    db = SessionLocal()
    try:
        user_msg = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user"
        ).first()
        assert user_msg is not None
        assert "sick days" in user_msg.content.lower()
    finally:
        db.close()


def test_chat_stores_assistant_message(client):
    """Scenario 9: Chat endpoint persists assistant response as role='assistant'."""
    c_res = client.post("/api/conversations", json={})
    session_id = c_res.json().get("id") or c_res.json().get("session_id")

    client.post("/api/chat", json={
        "message": "What is the annual leave quota?",
        "conversation_id": session_id,
    })

    db = SessionLocal()
    try:
        asst_msg = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "assistant"
        ).first()
        assert asst_msg is not None
        assert len(asst_msg.content) > 0
    finally:
        db.close()


def test_assistant_message_stores_sources(client):
    """Scenario 10: Assistant message record contains serialized sources_json."""
    c_res = client.post("/api/conversations", json={})
    session_id = c_res.json().get("id") or c_res.json().get("session_id")

    client.post("/api/chat", json={
        "message": "How many annual leave days are allowed?",
        "conversation_id": session_id,
    })

    db = SessionLocal()
    try:
        asst_msg = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "assistant"
        ).first()
        assert asst_msg is not None
        assert asst_msg.sources_json is not None
        parsed_sources = json.loads(asst_msg.sources_json)
        assert isinstance(parsed_sources, list)
    finally:
        db.close()


def test_conversation_title_auto_generated(client):
    """Scenario 11: First message in default session auto-generates title."""
    c_res = client.post("/api/conversations", json={})
    session_id = c_res.json().get("id") or c_res.json().get("session_id")

    client.post("/api/chat", json={
        "message": "What is the remote work policy for engineers?",
        "conversation_id": session_id,
    })

    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        assert session is not None
        # Title should not be the generic placeholder
        assert session.title != "Policy Discussion Session"
        assert "remote work policy" in session.title.lower()
    finally:
        db.close()


def test_custom_conversation_title_preserved(client):
    """Scenario 12: Custom conversation title is NOT overwritten by first question."""
    custom_title = "Executive Q3 Policy Alignment"
    c_res = client.post("/api/conversations", json={"title": custom_title})
    session_id = c_res.json().get("id") or c_res.json().get("session_id")

    client.post("/api/chat", json={
        "message": "How many days of sick leave are allowed?",
        "conversation_id": session_id,
    })

    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        assert session.title == custom_title
    finally:
        db.close()


# =========================================================================
# 13-16: Follow-up Detection & Smart Contextual Queries
# =========================================================================

def test_followup_question_detection():
    """Scenario 13: Detect follow-up questions containing pronouns or short queries."""
    recent_history = [
        {"role": "user", "content": "What is the remote work policy?"},
        {"role": "assistant", "content": "Employees are allowed 2 remote days per week."}
    ]

    assert query_context_service.is_followup_question("how many days?", recent_history) is True
    assert query_context_service.is_followup_question("can I take them on Friday?", recent_history) is True
    assert query_context_service.is_followup_question("what about it?", recent_history) is True
    assert query_context_service.is_followup_question("who approves this?", recent_history) is True


def test_standalone_question_not_detected_as_followup():
    """Scenario 14: Comprehensive standalone questions are not treated as follow-ups."""
    # When there is no prior history
    assert query_context_service.is_followup_question("What is the annual leave policy?") is False

    # When query is long, self-contained, and contains no pronouns
    recent_history = [
        {"role": "user", "content": "Tell me about dental benefits."},
    ]
    standalone = "Explain the standard enterprise data retention schedule for international customer records"
    assert query_context_service.is_followup_question(standalone, recent_history) is False


def test_contextual_query_generation():
    """Scenario 15: Contextual query combines previous topic with follow-up."""
    recent_history = [
        {"role": "user", "content": "What is the maternity leave entitlement?"},
        {"role": "assistant", "content": "Maternity leave is 16 weeks fully paid."}
    ]
    composed = query_context_service.build_contextual_retrieval_query("can it be extended?", recent_history)
    assert "maternity leave" in composed.lower()
    assert "extended" in composed.lower()


def test_contextual_query_used_for_retrieval_only():
    """Scenario 16: Retrieval query is used for FAISS search while user query is passed to LLM."""
    from app.rag.service import rag_service
    with patch.object(rag_service, "retrieve_context") as mock_retrieve, \
         patch.object(rag_service.llm_service, "generate_grounded_answer") as mock_llm_gen:

        mock_retrieve.return_value = MagicMock(
            status="success",
            context="Policy passage on leave",
            sources=[SourceCitation(source_id="S1", document="doc.pdf", score=0.85, preview="Text", text="Text")]
        )
        mock_llm_gen.return_value = {"success": True, "answer": "Mock answer", "sources": []}

        rag_service.generate_rag_answer(
            query="Maternity Leave Policy. can it be extended?",
            original_query="can it be extended?"
        )

        # Retrieval must use contextual query
        mock_retrieve.assert_called_once()
        retrieval_arg = mock_retrieve.call_args[1].get("query") or mock_retrieve.call_args[0][0]
        assert "maternity leave" in retrieval_arg.lower()

        # LLM generation must receive original user query
        mock_llm_gen.assert_called_once()
        llm_query_arg = mock_llm_gen.call_args[1].get("query") or mock_llm_gen.call_args[0][0]
        assert llm_query_arg == "can it be extended?"


# =========================================================================
# 17-21: Retrieval Quality & Citations
# =========================================================================

def test_top_k_retrieval_configurable():
    """Scenario 17: TOP_K setting defaults to 8 and can be configured."""
    assert settings.RETRIEVAL_TOP_K == 8

    from app.rag.retriever import rag_retriever
    with patch.object(rag_retriever.vector_store, "search") as mock_search:
        mock_search.return_value = []
        rag_retriever.retrieve("leave policy", top_k=6)
        assert mock_search.call_args[1]["top_k"] == 6


def test_source_diversity_balancing():
    """Scenario 18: Context builder ensures passages from distinct documents are balanced."""
    from app.rag.schemas import CandidateChunk

    mock_chunks = [
        CandidateChunk(chunk_id="c1", document_id="docA", filename="LeavePolicy.pdf", chunk_index=1, text="Leave A", score=0.9),
        CandidateChunk(chunk_id="c2", document_id="docA", filename="LeavePolicy.pdf", chunk_index=2, text="Leave B", score=0.88),
        CandidateChunk(chunk_id="c3", document_id="docA", filename="LeavePolicy.pdf", chunk_index=3, text="Leave C", score=0.85),
        CandidateChunk(chunk_id="c4", document_id="docB", filename="AttendancePolicy.pdf", chunk_index=1, text="Attendance A", score=0.84),
        CandidateChunk(chunk_id="c5", document_id="docB", filename="AttendancePolicy.pdf", chunk_index=2, text="Attendance B", score=0.82),
        CandidateChunk(chunk_id="c6", document_id="docC", filename="RemotePolicy.pdf", chunk_index=1, text="Remote A", score=0.80),
    ]

    _, sources = context_builder.build_context(mock_chunks, max_chunks=3)
    doc_names = {s.document for s in sources}
    assert len(doc_names) >= 2


def test_source_citation_validation():
    """Scenario 19: Citations contain required source_id, document, and score fields."""
    citation = SourceCitation(
        source_id="S1",
        document="Employee_Handbook.pdf",
        page=3,
        chunk_index=2,
        score=0.78,
        preview="Core hours are 9am to 5pm."
    )
    assert citation.source_id == "S1"
    assert citation.document == "Employee_Handbook.pdf"
    assert citation.page == 3
    assert citation.score == 0.78


def test_source_card_preview_generation():
    """Scenario 20: Source citations include concise text excerpt preview."""
    long_chunk_text = "This is a comprehensive enterprise policy document detailing the specific vacation entitlement schedule." * 5
    citation = SourceCitation(
        source_id="S1",
        document="Policy.pdf",
        text=long_chunk_text,
        score=0.82
    )
    assert citation.preview is not None
    assert len(citation.preview) <= 255
    assert "..." in citation.preview or len(citation.preview) < len(long_chunk_text)


def test_similarity_score_labeling(client):
    """Scenario 21: Similarity score in chat response is a normalized float."""
    res = client.post("/api/chat", json={"message": "How many annual leave days are allowed?"})
    assert res.status_code == 200
    data = res.json()
    if data.get("sources"):
        first_source = data["sources"][0]
        assert "score" in first_source
        score = first_source["score"]
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0


# =========================================================================
# 22-25: Feedback System & Rate Limiting
# =========================================================================

def test_feedback_endpoint_positive(client):
    """Scenario 22: Thumbs up feedback on assistant message returns 200 or 201."""
    chat_res = client.post("/api/chat", json={"message": "What is the sick leave policy?"})
    msg_id = chat_res.json().get("assistant_message_id") or chat_res.json().get("message_id")

    fb_res = client.post(f"/api/chat/messages/{msg_id}/feedback", json={"rating": "positive"})
    assert fb_res.status_code in (200, 201)
    assert fb_res.json().get("success") is True


def test_feedback_endpoint_negative(client):
    """Scenario 23: Thumbs down feedback on assistant message returns 200 or 201."""
    chat_res = client.post("/api/chat", json={"message": "What is the remote work policy?"})
    msg_id = chat_res.json().get("assistant_message_id") or chat_res.json().get("message_id")

    fb_res = client.post(f"/api/chat/messages/{msg_id}/feedback", json={"rating": "negative"})
    assert fb_res.status_code in (200, 201)
    assert fb_res.json().get("success") is True


def test_feedback_with_optional_comment(client):
    """Scenario 24: Feedback with optional comment stores comment in database."""
    chat_res = client.post("/api/chat", json={"message": "What is the core working hours schedule?"})
    msg_id = chat_res.json().get("assistant_message_id") or chat_res.json().get("message_id")
    test_comment = "Extremely clear citation and accurate answer."

    fb_res = client.post(f"/api/chat/messages/{msg_id}/feedback", json={
        "rating": "positive",
        "comment": test_comment,
    })
    assert fb_res.status_code in (200, 201)

    db = SessionLocal()
    try:
        fb_record = db.query(Feedback).filter(Feedback.message_id == msg_id).first()
        assert fb_record is not None
        assert fb_record.comment == test_comment
    finally:
        db.close()

    db = SessionLocal()
    try:
        fb_record = db.query(Feedback).filter(Feedback.message_id == msg_id).first()
        assert fb_record is not None
        assert fb_record.comment == test_comment
    finally:
        db.close()


def test_chat_rate_limiting():
    """Scenario 25: Verify rate limiting configuration for enterprise chat."""
    assert settings.CHAT_RATE_LIMIT == "30/minute"


# =========================================================================
# 26-28: Edge Cases & Error Handling
# =========================================================================

def test_empty_question_validation(client):
    """Scenario 26: Empty or whitespace-only question returns 422."""
    res_blank = client.post("/api/chat", json={"message": "   "})
    assert res_blank.status_code == 422

    res_empty = client.post("/api/chat", json={"message": ""})
    assert res_empty.status_code == 422


def test_oversized_question_handling(client):
    """Scenario 27: Question exceeding 2000 characters returns 422."""
    giant_message = "What is the policy? " * 150  # > 2500 characters
    res = client.post("/api/chat", json={"message": giant_message})
    assert res.status_code == 422


def test_nonexistent_conversation_returns_404(client):
    """Scenario 28: Fetching, renaming, or deleting a non-existent conversation returns 404."""
    dummy_id = "00000000-0000-0000-0000-000000000000"

    get_res = client.get(f"/api/conversations/{dummy_id}")
    assert get_res.status_code == 404

    patch_res = client.patch(f"/api/conversations/{dummy_id}", json={"title": "New Title"})
    assert patch_res.status_code == 404

    del_res = client.delete(f"/api/conversations/{dummy_id}")
    assert del_res.status_code == 404
