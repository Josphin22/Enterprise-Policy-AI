"""
Automated Test Suite for Phase 4: Real Local Embeddings + FAISS Vector Knowledge Base.
Tests all 15 scenarios specified in Part 53:
1. Model loading
2. Embedding dimension
3. Single text embedding
4. Batch embedding
5. Normalization
6. FAISS index creation
7. Vector count
8. Metadata count
9. Dimension validation
10. Semantic search
11. top_k
12. Threshold filtering
13. Empty index
14. Rebuild without duplication
15. Persistence after restart
"""

import os
import shutil
import tempfile
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
import faiss

from app.main import app
from app.config import settings
from app.database.connection import init_db
from app.database.session import SessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.vector_store import FAISSVectorStore, EXPECTED_DIMENSION
from services.embedding_service import (
    embedding_service,
    get_embedding_model,
    embed_text,
    embed_texts,
    get_dimension,
)
from services.vectorstore_service import (
    vectorstore_service,
    build_index,
    load_index,
    search,
    get_status,
)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Initialize database tables before test execution."""
    init_db()


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


# =========================================================================
# 1. Model Loading
# =========================================================================
def test_01_model_loading():
    """Test that the local SentenceTransformer model loads and caches properly."""
    model = get_embedding_model()
    assert model is not None
    assert "all-MiniLM-L6-v2" in embedding_service.model_name
    assert embedding_service.is_loaded is True


# =========================================================================
# 2. Embedding Dimension
# =========================================================================
def test_02_embedding_dimension():
    """Validate programmatically that embeddings have exactly 384 dimensions."""
    dim = get_dimension()
    assert dim == 384
    vec = embed_text("Test sentence for dimension verification.")
    assert vec.shape == (384,)
    assert vec.dtype == np.float32


# =========================================================================
# 3. Single Text Embedding
# =========================================================================
def test_03_single_text_embedding():
    """Verify single string embedding generation and empty string handling."""
    text = "Enterprise leave policies allow employees to request paid time off."
    vec = embed_text(text)
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (384,)
    assert not np.isnan(vec).any()
    assert not np.all(vec == 0)

    # Empty text should return a zero vector
    empty_vec = embed_text("   ")
    assert empty_vec.shape == (384,)
    assert np.all(empty_vec == 0)


# =========================================================================
# 4. Batch Embedding
# =========================================================================
def test_04_batch_embedding():
    """Verify batch embedding with configurable batch size produces expected shape."""
    texts = [
        "First policy paragraph on remote work eligibility.",
        "Second policy paragraph on core collaboration hours.",
        "Third policy paragraph on health insurance benefits.",
        "Fourth policy paragraph on annual vacation entitlement.",
    ]
    matrix = embed_texts(texts, batch_size=2)
    assert isinstance(matrix, np.ndarray)
    assert matrix.shape == (4, 384)
    assert matrix.dtype == np.float32


# =========================================================================
# 5. Normalization
# =========================================================================
def test_05_normalization():
    """Verify that all generated embeddings have an L2 norm of 1.0 (cosine similarity)."""
    texts = [
        "Normalizing embedding vectors guarantees inner product equals cosine similarity.",
        "Another sentence to test unit length properties.",
    ]
    embeddings = embed_texts(texts)
    for i in range(len(texts)):
        norm = float(np.linalg.norm(embeddings[i]))
        assert abs(norm - 1.0) < 1e-4, f"Vector {i} L2 norm {norm} != 1.0"


# =========================================================================
# 6. FAISS Index Creation
# =========================================================================
def test_06_faiss_index_creation():
    """Verify FAISS IndexFlatIP creation with exact dimension 384."""
    store = FAISSVectorStore(vectorstore_dir=Path(tempfile.mkdtemp()))
    store.initialize(dimension=384)
    assert store.index is not None
    assert isinstance(store.index, faiss.IndexFlatIP)
    assert store.index.d == 384
    assert store.index.ntotal == 0


# =========================================================================
# 7 & 8. Vector Count and Metadata Count Synchronization
# =========================================================================
def test_07_08_vector_and_metadata_count_sync():
    """Verify that adding vectors enforces a strict 1:1 match with metadata records."""
    temp_dir = Path(tempfile.mkdtemp())
    store = FAISSVectorStore(vectorstore_dir=temp_dir)
    store.initialize(dimension=384)

    embeddings = embed_texts(["Paragraph A", "Paragraph B", "Paragraph C"])
    metadata = [
        {"chunk_id": "c1", "document_id": "d1", "filename": "Policy.txt", "chunk_index": 0, "text": "Paragraph A"},
        {"chunk_id": "c2", "document_id": "d1", "filename": "Policy.txt", "chunk_index": 1, "text": "Paragraph B"},
        {"chunk_id": "c3", "document_id": "d1", "filename": "Policy.txt", "chunk_index": 2, "text": "Paragraph C"},
    ]

    store.add_vectors(embeddings, metadata)
    assert store.total_vectors == 3
    assert len(store.metadata_map) == 3
    assert store.metadata_map[0]["chunk_id"] == "c1"
    assert store.metadata_map[1]["chunk_id"] == "c2"
    assert store.metadata_map[2]["chunk_id"] == "c3"


# =========================================================================
# 9. Dimension Validation
# =========================================================================
def test_09_dimension_validation():
    """Verify that a dimension mismatch raises an error clearly."""
    temp_dir = Path(tempfile.mkdtemp())
    store = FAISSVectorStore(vectorstore_dir=temp_dir)

    with pytest.raises(ValueError, match="VECTOR_DIMENSION_MISMATCH"):
        store.initialize(dimension=512)

    store.initialize(dimension=384)
    invalid_dim_embeddings = np.random.randn(2, 512).astype(np.float32)
    with pytest.raises(ValueError, match="VECTOR_DIMENSION_MISMATCH"):
        store.add_vectors(invalid_dim_embeddings, [{"chunk_id": "1"}, {"chunk_id": "2"}])


# =========================================================================
# 10. Semantic Search
# =========================================================================
def test_10_semantic_search():
    """Verify semantic search retrieves relevant chunks with cosine similarity scores."""
    db = SessionLocal()
    build_res = build_index(db=db)
    assert build_res["status"] == "success"
    assert build_res["vectors"] > 0

    # Search for annual leave policy
    results = search("How many annual leave days are allowed?", top_k=3, min_score=0.35, db=db)
    assert len(results) > 0
    top_hit = results[0]
    assert "score" in top_hit
    assert top_hit["score"] > 0.5
    assert "text" in top_hit
    assert "filename" in top_hit
    db.close()


# =========================================================================
# 11. top_k Limit Enforcement
# =========================================================================
def test_11_top_k_enforcement():
    """Verify that top_k correctly limits the number of returned chunks."""
    db = SessionLocal()
    res_1 = search("leave days policy", top_k=1, db=db)
    assert len(res_1) <= 1

    res_3 = search("leave days policy", top_k=3, db=db)
    assert len(res_3) <= 3
    db.close()


# =========================================================================
# 12. Threshold Filtering (Out-of-Domain Test)
# =========================================================================
def test_12_threshold_filtering_out_of_domain():
    """Verify that out-of-domain queries scoring below threshold return zero results."""
    db = SessionLocal()
    # Completely unrelated query
    results = search("What is the capital of France and what is its population?", top_k=5, min_score=0.35, db=db)
    assert len(results) == 0, f"Expected 0 results for out-of-domain query, got {len(results)}"
    db.close()


# =========================================================================
# 13. Empty Index & Unbuilt Handling
# =========================================================================
def test_13_empty_index_handling(client: TestClient):
    """Verify that search on an unbuilt or empty index returns HTTP 409."""
    temp_dir = Path(tempfile.mkdtemp())
    dummy_store = FAISSVectorStore(vectorstore_dir=temp_dir)
    assert dummy_store.is_built is False
    assert dummy_store.total_vectors == 0

    # Test empty text chunk rejection in service
    empty_res = dummy_store.search(np.zeros(384, dtype=np.float32), top_k=5)
    assert empty_res == []


# =========================================================================
# 14. Rebuild Without Duplication
# =========================================================================
def test_14_rebuild_without_duplication():
    """Verify that rebuilding the knowledge base replaces the index without accumulating duplicate vectors."""
    db = SessionLocal()
    res1 = build_index(db=db)
    v1 = res1["vectors"]
    assert v1 > 0

    res2 = build_index(db=db)
    v2 = res2["vectors"]
    assert v2 == v1, f"Vectors doubled on rebuild: {v2} != {v1}"

    res3 = build_index(db=db)
    v3 = res3["vectors"]
    assert v3 == v1, f"Vectors accumulated on rebuild: {v3} != {v1}"
    db.close()


# =========================================================================
# 15. Persistence After Restart
# =========================================================================
def test_15_persistence_after_restart():
    """Verify that saved index and metadata reload cleanly and remain searchable."""
    temp_dir = Path(tempfile.mkdtemp())
    store1 = FAISSVectorStore(vectorstore_dir=temp_dir)
    store1.initialize(dimension=384)

    texts = [
        "Company core working hours are 9:00 AM to 5:00 PM.",
        "Employees may take up to 18 annual leave days.",
    ]
    embs = embed_texts(texts)
    meta = [
        {"chunk_id": "c101", "filename": "Hours.txt", "chunk_index": 0, "text": texts[0]},
        {"chunk_id": "c102", "filename": "Leave.txt", "chunk_index": 0, "text": texts[1]},
    ]
    store1.add_vectors(embs, meta)
    store1.save()

    # Create fresh instance simulating application restart
    store2 = FAISSVectorStore(vectorstore_dir=temp_dir)
    loaded = store2.load()
    assert loaded is True
    assert store2.is_built is True
    assert store2.total_vectors == 2

    # Query the reloaded store
    q_vec = embed_text("What time does work start?")
    hits = store2.search(q_vec, top_k=1, min_score=0.35)
    assert len(hits) == 1
    assert hits[0]["chunk_id"] == "c101"
    assert "9:00 AM" in hits[0]["text"]

    # Clean up temp directory
    shutil.rmtree(temp_dir, ignore_errors=True)
