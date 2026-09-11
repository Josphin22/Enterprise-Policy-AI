"""
Phase 9 — Advanced RAG Quality, Hybrid Search & Retrieval Optimization
Comprehensive Test Suite covering:
1. Semantic vector search (FAISS + SentenceTransformers)
2. Keyword search (exact terms, terminology, numbers, dates, currencies)
3. Hybrid search & Reciprocal Rank Fusion (RRF) result merging
4. Deduplication of chunks
5. Number and date preservation & confidence boosts
6. Metadata filtering (document_id, file_type, owner_id, status, department)
7. Source diversity balancing across multi-document queries
8. Optional reranking toggle (graceful fallback)
9. Retrieval diagnostics API endpoint (/api/rag/debug-search)
10. Scientific retrieval evaluation & MRR (Mean Reciprocal Rank) metrics
11. Out-of-domain query safe refusal
12. End-to-end chat integration with zero regressions
"""

import os
import json
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.config import settings
from app.database.connection import init_db
from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_metadata import DocumentMetadata
from app.models.user import User
from app.core.security import create_access_token
from app.rag.schemas import CandidateChunk, MetadataFilter, RAGRetrievalRequest
from app.rag.keyword_search import keyword_search_engine, KeywordSearchEngine
from app.rag.hybrid_retriever import hybrid_retriever, HybridRetriever
from app.rag.reranker import reranker_service, RerankerService
from app.rag.service import rag_service
from app.evaluation.dataset import EvaluationQuestion
from app.evaluation.retrieval_evaluator import retrieval_evaluator
from services.vectorstore_service import build_index

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_phase9_environment():
    """Ensure database schema is up-to-date and populated for Phase 9 tests."""
    init_db()
    db = SessionLocal()

    # Seed test documents and chunks if not present
    doc1 = db.query(Document).filter(Document.filename == "Leave_Policy.pdf").first()
    if not doc1:
        doc1 = Document(
            id=str(uuid.uuid4()),
            filename="Leave_Policy.pdf",
            original_filename="Leave_Policy.pdf",
            file_type=".pdf",
            file_size=1024,
            file_path="documents/Leave_Policy.pdf",
            processing_status="processed",
            chunk_count=3,
        )
        db.add(doc1)
        db.flush()

        # Add chunks with specific numbers and dates
        c1 = DocumentChunk(
            id=str(uuid.uuid4()),
            document_id=doc1.id,
            chunk_index=0,
            text="All full-time employees are entitled to 15 days of annual paid vacation leave per calendar year. Leave accrues on a pro-rata basis at 1.25 days per month.",
            character_count=145,
            page_number=1,
            section="Annual Vacation Leave",
        )
        c2 = DocumentChunk(
            id=str(uuid.uuid4()),
            document_id=doc1.id,
            chunk_index=1,
            text="Employees may carry forward a maximum of 5 unused annual vacation days into the subsequent calendar year 2026. Any remaining leave expires strictly on December 31.",
            character_count=168,
            page_number=1,
            section="Carry Forward",
        )
        c3 = DocumentChunk(
            id=str(uuid.uuid4()),
            document_id=doc1.id,
            chunk_index=2,
            text="Employees receive 10 days of paid sick leave annually. A doctor medical certificate is mandatory for sick leave exceeding 3 consecutive business days.",
            character_count=160,
            page_number=2,
            section="Sick Leave",
        )
        db.add_all([c1, c2, c3])

    doc2 = db.query(Document).filter(Document.filename == "Work_From_Home_Policy.docx").first()
    if not doc2:
        doc2 = Document(
            id=str(uuid.uuid4()),
            filename="Work_From_Home_Policy.docx",
            original_filename="Work_From_Home_Policy.docx",
            file_type=".docx",
            file_size=2048,
            file_path="documents/Work_From_Home_Policy.docx",
            processing_status="processed",
            chunk_count=2,
        )
        db.add(doc2)
        db.flush()

        w1 = DocumentChunk(
            id=str(uuid.uuid4()),
            document_id=doc2.id,
            chunk_index=0,
            text="Under the telecommuting framework, staff may work remotely up to 2 days per week with manager approval. Staff must complete a 90-day probationary period.",
            character_count=162,
            page_number=1,
            section="Remote Work Eligibility",
        )
        w2 = DocumentChunk(
            id=str(uuid.uuid4()),
            document_id=doc2.id,
            chunk_index=1,
            text="Remote employees must utilize the corporate VPN at all times. A work-from-home equipment stipend of ₹50,000 is reimbursed after 5 years of continuous service.",
            character_count=170,
            page_number=2,
            section="Security and Equipment",
        )
        db.add_all([w1, w2])

    db.commit()

    # Rebuild vector index so FAISS contains these vectors
    build_index(db=db)
    db.close()


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_auth_header(db_session: Session):
    admin = db_session.query(User).filter(User.role == "ADMIN").first()
    if not admin:
        admin = User(
            id=str(uuid.uuid4()),
            username="admin_test",
            email="admin_phase9@enterprise.com",
            hashed_password="hashed_test_pw",
            role="ADMIN",
            is_active=True,
        )
        db_session.add(admin)
        db_session.commit()
    token = create_access_token({"sub": admin.id, "email": admin.email, "role": admin.role})
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. Semantic Retrieval (Paraphrased query)
# =====================================================================

def test_semantic_retrieval_paraphrased_query(db_session: Session):
    """
    Verify semantic retrieval finds correct policy chunks even when
    user wording differs from exact text in the policy document.
    """
    paraphrased = "How much annual paid time off can full-time workers take each year?"
    candidates = hybrid_retriever.semantic_retriever.retrieve(
        query=paraphrased,
        top_k=5,
        db=db_session,
    )
    assert len(candidates) > 0
    top_doc = candidates[0].filename
    assert "Leave_Policy" in top_doc or candidates[0].score >= 0.35


# =====================================================================
# 2. Keyword Retrieval (Exact Terminology & Acronyms)
# =====================================================================

def test_keyword_retrieval_exact_terminology(db_session: Session):
    """
    Verify keyword search finds chunks matching exact terminology, acronyms (VPN),
    and domain phrases.
    """
    query = "corporate VPN"
    results = keyword_search_engine.search(
        query=query,
        db=db_session,
        top_k=5,
    )
    assert len(results) > 0
    assert any("vpn" in r.text.lower() for r in results)
    assert results[0].source_type == "keyword"


# =====================================================================
# 3. Hybrid Search & Reciprocal Rank Fusion (RRF)
# =====================================================================

def test_hybrid_search_fuses_candidates(db_session: Session):
    """
    Verify hybrid retrieval combines semantic vector search and keyword search
    using Reciprocal Rank Fusion.
    """
    query = "How many days of annual vacation leave do employees get?"
    candidates, diagnostics = hybrid_retriever.retrieve(
        query=query,
        top_k=5,
        db=db_session,
        return_diagnostics=True,
    )
    assert len(candidates) > 0
    assert diagnostics["semantic_count"] > 0
    assert diagnostics["final_count"] > 0
    assert "Leave_Policy.pdf" in [c.filename for c in candidates]


# =====================================================================
# 4. Duplicate Results Elimination
# =====================================================================

def test_duplicate_chunk_elimination():
    """
    Verify identical/duplicate chunks from semantic and keyword pipelines
    are merged and eliminated without creating duplicate entries.
    """
    c_sem = CandidateChunk(
        chunk_id="chunk-123",
        document_id="doc-1",
        filename="Test_Policy.pdf",
        chunk_index=0,
        text="All employees must complete safety compliance training annually.",
        character_count=65,
        score=0.82,
        source_type="semantic",
    )
    c_kw = CandidateChunk(
        chunk_id="chunk-123",
        document_id="doc-1",
        filename="Test_Policy.pdf",
        chunk_index=0,
        text="All employees must complete safety compliance training annually.",
        character_count=65,
        score=0.75,
        source_type="keyword",
        match_reasons=["compliance"],
    )

    entities = {"numbers": [], "dates": [], "currencies": [], "keywords": ["compliance"]}
    merged = hybrid_retriever._merge_and_fuse_candidates(
        query="compliance training",
        semantic_candidates=[c_sem],
        keyword_candidates=[c_kw],
        entities=entities,
        top_k=5,
    )

    # Must be deduplicated down to exactly 1 candidate
    assert len(merged) == 1
    assert merged[0].chunk_id == "chunk-123"
    assert merged[0].source_type == "hybrid"


# =====================================================================
# 5. Number and Currency Preservation & Boosts
# =====================================================================

def test_number_preservation_and_boost(db_session: Session):
    """
    Verify queries with exact numbers and currency (15 days, 90-day, ₹50,000, 5 years)
    prioritize chunks containing those figures with confidence boosts.
    """
    # 1. Test 1.25 days per month accrual
    res_accrual = hybrid_retriever.retrieve(
        query="1.25 days per month accrual rate",
        top_k=3,
        db=db_session,
    )
    assert len(res_accrual) > 0
    assert "1.25" in res_accrual[0].text

    # 2. Test 90-day probation period
    res_probation = hybrid_retriever.retrieve(
        query="What is the 90-day probationary period?",
        top_k=3,
        db=db_session,
    )
    assert len(res_probation) > 0
    assert "90-day" in res_probation[0].text or "90" in res_probation[0].text

    # 3. Test currency and years: ₹50,000 after 5 years
    res_currency = hybrid_retriever.retrieve(
        query="equipment stipend of ₹50,000 after 5 years",
        top_k=3,
        db=db_session,
    )
    assert len(res_currency) > 0
    assert "50,000" in res_currency[0].text or "5 years" in res_currency[0].text


# =====================================================================
# 6. Date Preservation & Boosts
# =====================================================================

def test_date_preservation_and_boost(db_session: Session):
    """
    Verify queries with dates ('December 31', '2026') boost date-matched chunks.
    """
    res_date = hybrid_retriever.retrieve(
        query="carry forward unused vacation days into 2026 before December 31",
        top_k=3,
        db=db_session,
    )
    assert len(res_date) > 0
    top_text = res_date[0].text
    assert "December 31" in top_text or "2026" in top_text


# =====================================================================
# 7. Metadata Filtering (document_id, file_type, status)
# =====================================================================

def test_metadata_filtering_document_id(db_session: Session):
    """
    Verify filtering by document_id limits results strictly to that document.
    """
    leave_doc = db_session.query(Document).filter(Document.filename == "Leave_Policy.pdf").first()
    assert leave_doc is not None

    candidates = hybrid_retriever.retrieve(
        query="annual vacation leave entitlement and carry forward",
        top_k=5,
        db=db_session,
        filters=MetadataFilter(document_id=leave_doc.id),
    )
    assert len(candidates) > 0
    for c in candidates:
        assert c.document_id == leave_doc.id


def test_metadata_filtering_file_type(db_session: Session):
    """
    Verify filtering by file_type (e.g. 'docx') excludes other file formats.
    """
    candidates = hybrid_retriever.retrieve(
        query="remote telecommuting probationary period",
        top_k=5,
        db=db_session,
        filters=MetadataFilter(file_type="docx"),
    )
    assert len(candidates) > 0
    for c in candidates:
        assert c.filename.endswith(".docx")


# =====================================================================
# 8. Source Diversity Balancing
# =====================================================================

def test_source_diversity_balancing():
    """
    Verify source diversity balancing prevents a single document from crowding out
    other relevant documents for multi-concept queries.
    """
    c1 = CandidateChunk(
        chunk_id="c1", document_id="doc-A", filename="Policy_A.pdf",
        chunk_index=0, text="Doc A chunk 1 text", character_count=20, score=0.95
    )
    c2 = CandidateChunk(
        chunk_id="c2", document_id="doc-A", filename="Policy_A.pdf",
        chunk_index=1, text="Doc A chunk 2 text", character_count=20, score=0.94
    )
    c3 = CandidateChunk(
        chunk_id="c3", document_id="doc-A", filename="Policy_A.pdf",
        chunk_index=2, text="Doc A chunk 3 text", character_count=20, score=0.93
    )
    c4 = CandidateChunk(
        chunk_id="c4", document_id="doc-B", filename="Policy_B.pdf",
        chunk_index=0, text="Doc B chunk 1 text", character_count=20, score=0.90
    )

    all_candidates = [c1, c2, c3, c4]
    diverse = hybrid_retriever._apply_source_diversity(all_candidates, max_k=2)

    # In top 2, both Doc A and Doc B must be represented
    doc_ids_represented = {c.document_id for c in diverse}
    assert "doc-A" in doc_ids_represented
    assert "doc-B" in doc_ids_represented


# =====================================================================
# 9. Configurable Reranking
# =====================================================================

def test_reranker_optional_toggle():
    """
    Verify reranking operates safely without raising errors when disabled,
    and falls back cleanly if enabled.
    """
    assert reranker_service.is_enabled is False

    c1 = CandidateChunk(
        chunk_id="c1", document_id="doc-1", filename="Doc1.pdf",
        chunk_index=0, text="Sample text for chunk 1", character_count=25, score=0.8
    )
    reranked = reranker_service.rerank("query", [c1], top_k=5)
    assert len(reranked) == 1
    assert reranked[0].chunk_id == "c1"


# =====================================================================
# 10. Retrieval Diagnostics API Endpoint
# =====================================================================

def test_retrieval_diagnostics_endpoint(admin_auth_header):
    """
    Verify POST /api/rag/debug-search returns candidate breakdown, latencies,
    and detected entities for authorized users.
    """
    resp = client.post(
        "/api/rag/debug-search",
        json={"query": "15 days annual vacation leave in 2026", "top_k": 5},
        headers=admin_auth_header,
    )
    assert resp.status_code == 200, f"Diagnostics failed: {resp.text}"
    data = resp.json()

    assert data["query"] == "15 days annual vacation leave in 2026"
    assert "15 days" in data["detected_numbers"] or "15" in data["detected_numbers"]
    assert "2026" in data["detected_dates"]
    assert "latencies_ms" in data
    assert "semantic_time_ms" in data["latencies_ms"]
    assert "keyword_time_ms" in data["latencies_ms"]
    assert len(data["final_candidates"]) > 0


# =====================================================================
# 11. Scientific Retrieval Evaluation & MRR
# =====================================================================

def test_retrieval_evaluator_mrr_calculation():
    """
    Verify scientific calculation of Precision@K, Recall@K, Hit Rate@K,
    and Mean Reciprocal Rank (MRR).
    """
    q1 = EvaluationQuestion(
        id="Q1",
        question="What is the leave entitlement?",
        expected_answer="15 days",
        expected_sources=["Leave_Policy.pdf"],
        expected_chunk_index=0,
    )

    c_match = CandidateChunk(
        chunk_id="chk-1", document_id="doc-1", filename="Leave_Policy.pdf",
        chunk_index=0, text="15 days annual leave", character_count=20, score=0.9
    )
    c_other = CandidateChunk(
        chunk_id="chk-2", document_id="doc-2", filename="Other.pdf",
        chunk_index=0, text="Other policy", character_count=12, score=0.5
    )

    eval_result = retrieval_evaluator.evaluate_query_retrieval(
        question=q1,
        retrieved_chunks=[c_match, c_other],
        k_values=[1, 3, 5],
    )

    assert eval_result["reciprocal_rank"] == 1.0
    assert eval_result["hit_rate_at_k"]["hit@1"] == 1.0
    assert eval_result["precision_at_k"]["p@1"] == 1.0
    assert eval_result["recall_at_k"]["r@1"] == 1.0
    assert eval_result["chunk_hit"] is True

    # Aggregate check
    agg = retrieval_evaluator.aggregate_retrieval_metrics([eval_result])
    assert agg["mrr"] == 1.0
    assert agg["hit_rate_1"] == 100.0


# =====================================================================
# 12. Out-of-Domain Safe Refusal
# =====================================================================

def test_out_of_domain_query_safe_refusal(db_session: Session):
    """
    Verify out-of-domain queries properly return insufficient context
    with zero hallucination.
    """
    response = rag_service.retrieve_context(
        query="What is the maintenance protocol for quantum teleportation engines?",
        min_score=0.45,
        db=db_session,
    )
    assert response.status == "insufficient_context"
    assert response.context == ""
    assert len(response.sources) == 0


# =====================================================================
# 13. End-to-End Chat Integration with Hybrid Retrieval
# =====================================================================

def test_chat_service_hybrid_retrieval_integration(db_session: Session):
    """
    Verify existing chat service generates answers using Phase 9 hybrid retrieval.
    """
    from app.services.chat_service import chat_service

    with patch.object(rag_service.llm_service, "generate_grounded_answer") as mock_llm:
        mock_llm.return_value = {
            "success": True,
            "answer": "All full-time employees receive 15 days of annual vacation leave. [Source S1]",
        }

        resp = chat_service.handle_chat_message(
            question="How many annual vacation days are allowed?",
            session_id=None,
            db=db_session,
        )
        assert resp.success is True
        assert len(resp.sources) > 0
        assert "Leave_Policy.pdf" in [s.get("filename") or s.get("document") for s in resp.sources]
