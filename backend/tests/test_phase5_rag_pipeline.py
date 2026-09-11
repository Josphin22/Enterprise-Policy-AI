"""
Automated Test Suite for Phase 5: Real RAG Retrieval Pipeline + Context Builder.
Tests the complete pipeline:
User Question -> Query Embedding -> FAISS Semantic Search -> Top-K Relevant Chunks
-> Relevance Filtering -> Context Builder -> Grounded Context (READY FOR OLLAMA IN PHASE 6)
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import numpy as np

from app.main import app
from app.config import settings
from app.database.connection import init_db
from app.database.session import SessionLocal
from app.rag.schemas import (
    CandidateChunk,
    SourceCitation,
    RAGRetrievalRequest,
    RAGRetrievalResponse,
)
from services.embedding_service import embedding_service, embed_text
from services.vectorstore_service import vectorstore_service, build_index, search
from services.retrieval_service import (
    retrieval_service,
    retrieve_context,
    build_grounded_context,
    filter_relevance,
)


@pytest.fixture(scope="module", autouse=True)
def setup_knowledge_base():
    """Ensure database initialized and knowledge base built for tests."""
    init_db()
    db = SessionLocal()
    build_index(db=db)
    db.close()


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


# =========================================================================
# 1. User Question Validation & Normalization
# =========================================================================
def test_01_user_question_validation():
    """Verify that empty, blank, or whitespace queries are strictly rejected."""
    with pytest.raises(Exception):
        retrieve_context("   ")

    with pytest.raises(Exception):
        retrieve_context("")

    # Normalization collapses multiple spaces without altering semantics
    norm = retrieval_service.retriever.normalize_query("   How   many   annual leave   days?   ")
    assert norm == "How many annual leave days?"


# =========================================================================
# 2. Query Embedding
# =========================================================================
def test_02_query_embedding():
    """Verify that query embedding uses local all-MiniLM-L6-v2 and produces normalized 384-dim vector."""
    query = "How many annual leave days are allowed?"
    query_vec = embedding_service.embed_text(query)

    assert isinstance(query_vec, np.ndarray)
    assert query_vec.shape == (384,)
    assert query_vec.dtype == np.float32
    norm = float(np.linalg.norm(query_vec))
    assert abs(norm - 1.0) < 1e-4


# =========================================================================
# 3 & 4. FAISS Semantic Search & Top-K Relevant Chunks
# =========================================================================
def test_03_04_faiss_semantic_search_and_candidates():
    """Verify FAISS semantic search retrieves candidate chunks with authentic metadata."""
    query = "How many annual leave days are allowed?"
    candidates = retrieval_service.retriever.retrieve(query=query, top_k=3)

    assert len(candidates) > 0
    assert len(candidates) <= 3

    top = candidates[0]
    assert isinstance(top, CandidateChunk)
    assert top.chunk_id is not None
    assert top.document_id is not None
    assert top.filename is not None
    assert top.text is not None
    assert len(top.text) > 0
    assert top.score >= -1.0 and top.score <= 1.0


# =========================================================================
# 5. Relevance Filtering (Thresholding)
# =========================================================================
def test_05_relevance_filtering():
    """Verify that chunks below min_score threshold are rejected while accepted ones are sorted descending."""
    dummy_candidates = [
        CandidateChunk(chunk_id="c1", document_id="d1", filename="f1.pdf", text="High relevance", score=0.82),
        CandidateChunk(chunk_id="c2", document_id="d1", filename="f1.pdf", text="Medium relevance", score=0.45),
        CandidateChunk(chunk_id="c3", document_id="d2", filename="f2.txt", text="Low relevance", score=0.25),
    ]

    accepted, stats = filter_relevance(dummy_candidates, min_score=0.35)
    assert len(accepted) == 2
    assert stats["rejected"] == 1
    assert stats["threshold"] == 0.35
    assert accepted[0].score >= accepted[1].score
    assert accepted[0].chunk_id == "c1"
    assert accepted[1].chunk_id == "c2"


# =========================================================================
# 6. Out-of-Domain Query Handling (insufficient_context)
# =========================================================================
def test_06_out_of_domain_insufficient_context():
    """Verify that out-of-domain questions yield insufficient_context status and empty context."""
    out_of_domain_query = "What is the capital city of France?"
    res = retrieve_context(out_of_domain_query, top_k=5, min_score=0.35)

    assert res.status == "insufficient_context"
    assert res.context == ""
    assert res.sources == []
    assert res.total_sources == 0
    assert "No sufficiently relevant information" in (res.message or "")


# =========================================================================
# 7. Context Builder & Deduplication
# =========================================================================
def test_07_context_builder_deduplication():
    """Verify that duplicated chunk texts from multiple uploads are consolidated."""
    chunks = [
        CandidateChunk(chunk_id="c1", document_id="d1", filename="Leave.txt", text="Employees receive 18 days leave.", score=0.85),
        CandidateChunk(chunk_id="c2", document_id="d2", filename="Leave_copy.txt", text="Employees receive 18 days leave.", score=0.84),
        CandidateChunk(chunk_id="c3", document_id="d3", filename="Hours.txt", text="Standard hours are 9 to 5.", score=0.75),
    ]

    context, sources = build_grounded_context(chunks)
    assert len(sources) == 2
    assert "[Source S1]" in context
    assert "[Source S2]" in context
    assert "[Source S3]" not in context


# =========================================================================
# 8. Bounded Context (Character & Chunk Limits)
# =========================================================================
def test_08_bounded_context_limits():
    """Verify that context builder enforces max_chunks and max_characters boundaries."""
    chunks = [
        CandidateChunk(chunk_id=f"c{i}", document_id="d1", filename="P.txt", text=f"Section {i} policy rule text.", score=0.80 - (i * 0.05))
        for i in range(10)
    ]

    # Limit to 2 chunks
    context_2, sources_2 = build_grounded_context(chunks, max_chunks=2)
    assert len(sources_2) == 2

    # Limit by character count (e.g. 150 characters max should truncate at 1 or 2 chunks)
    context_bounded, sources_bounded = build_grounded_context(chunks, max_characters=150)
    assert len(sources_bounded) <= 2
    assert len(sources_bounded) < len(chunks)


# =========================================================================
# 9 & 10. Grounded Context Format & Source Citations
# =========================================================================
def test_09_10_grounded_context_format_and_citations():
    """Verify that context blocks include proper [Source S1] headers and citations."""
    query = "How many annual leave days are allowed?"
    res = retrieve_context(query, top_k=3, min_score=0.35)

    assert res.status == "success"
    assert len(res.sources) >= 1
    assert "[Source S1]" in res.context
    assert "Document:" in res.context

    first_source = res.sources[0]
    assert isinstance(first_source, SourceCitation)
    assert first_source.source_id == "S1"
    assert first_source.document is not None
    assert first_source.chunk_id is not None
    assert first_source.score >= 0.35


# =========================================================================
# 11. API Endpoint: POST /api/rag/retrieve
# =========================================================================
def test_11_api_rag_retrieve_endpoint(client: TestClient):
    """Verify POST /api/rag/retrieve HTTP endpoint contract."""
    payload = {
        "query": "How many annual leave days are allowed?",
        "top_k": 3,
        "min_score": 0.35,
    }
    response = client.post("/api/rag/retrieve", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["query"] == "How many annual leave days are allowed?"
    assert len(data["context"]) > 0
    assert len(data["sources"]) >= 1
    assert data["total_sources"] == len(data["sources"])


# =========================================================================
# 12. End-to-End Grounded Context Ready for Phase 6
# =========================================================================
def test_12_ready_for_ollama_in_phase6():
    """Verify that retrieved grounded context contains accurate enterprise policy facts ready for LLM."""
    query = "What are the rules for working from home?"
    res = retrieve_context(query, top_k=3, min_score=0.35)

    assert res.status == "success"
    assert "Remote" in res.context or "Work" in res.context or "home" in res.context.lower()
    assert len(res.sources) >= 1
    # Confirms no answer generation or Ollama call was triggered
    assert not hasattr(res, "answer")
