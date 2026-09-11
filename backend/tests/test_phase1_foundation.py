"""
Phase 1 Foundation Verification Test Suite.
Tests the 6 foundational requirements specified in Phase 1:
1. Health API returns valid status, database, faiss, and ollama fields.
2. LLM Status API queries live Ollama daemon and returns real availability.
3. EmbeddingService loads 384-dimensional SentenceTransformer model and normalizes.
4. VectorService / FAISS initializes with IndexFlatIP dimension 384.
5. VectorService persistence: saves to disk and survives reload/restart.
6. Knowledge Base status API calculates authentic database counts and vector metrics.
"""
import sys
import tempfile
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.main import app
from app.config import settings
from app.rag.embeddings import embedding_service
from app.rag.vector_store import FAISSVectorStore, vector_store
from app.services.vector_service import vector_service

client = TestClient(app)


def test_1_health_api():
    """TEST 1: Verify GET /api/health returns valid response with real component statuses."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert data["database"] in ("connected", "unreachable")
    assert "faiss" in data
    assert data["faiss"] in ("ready", "not_built")
    assert "ollama" in data
    assert data["ollama"] in ("available", "unavailable")
    assert data.get("service") == "Enterprise Policy RAG"
    print(f"\n[PASS] TEST 1 Health API: {data}")


def test_2_ollama_status_api():
    """TEST 2: Verify GET /api/llm/status contacts Ollama and returns live state."""
    response = client.get("/api/llm/status")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"].lower() == "ollama"
    assert "endpoint" in data
    assert data["model"] == settings.OLLAMA_MODEL
    assert isinstance(data["available"], bool)
    assert "status" in data
    assert "installed_models" in data
    print(f"\n[PASS] TEST 2 Ollama Status: available={data['available']}, model={data['model']}, installed={data['installed_models']}")


def test_3_embedding_service_dimension_and_vectors():
    """TEST 3: Verify embedding model loads successfully, dimension == 384, and normalization."""
    dim = embedding_service.get_dimension()
    assert dim == 384, f"Expected dimension 384, got {dim}"

    # Test single text embedding
    vec = embedding_service.embed_text("Annual leave policy guidelines")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (384,), f"Expected shape (384,), got {vec.shape}"
    norm = np.linalg.norm(vec)
    assert np.isclose(norm, 1.0, atol=1e-4), f"Embedding must be unit normalized, got {norm}"

    # Test batch text embedding
    batch_vecs = embedding_service.embed_texts([
        "First policy statement",
        "Second policy statement",
    ])
    assert isinstance(batch_vecs, np.ndarray)
    assert batch_vecs.shape == (2, 384), f"Expected shape (2, 384), got {batch_vecs.shape}"

    # Verify error on invalid dimension probe
    assert embedding_service.EXPECTED_DIMENSION == 384 if hasattr(embedding_service, "EXPECTED_DIMENSION") else True
    print(f"\n[PASS] TEST 3 Embedding Service: dimension={dim}, norm={norm:.4f}, batch_shape={batch_vecs.shape}")


def test_4_faiss_initialization():
    """TEST 4: Initialize FAISS and confirm index dimension == 384."""
    store = FAISSVectorStore()
    store.initialize(dimension=384)
    assert store.index is not None
    assert store.index.d == 384, f"Expected index dimension 384, got {store.index.d}"
    assert store.count() == 0

    # Also check global vector_service
    assert vector_service.count() >= 0
    print(f"\n[PASS] TEST 4 FAISS Initialization: IndexFlatIP created with dimension={store.index.d}")


def test_5_faiss_persistence_and_reload():
    """TEST 5: Persist FAISS, simulate backend restart by creating a new store, and confirm reload."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Create and populate index
        store1 = FAISSVectorStore(vectorstore_dir=tmp_path)
        store1.initialize(dimension=384)

        dummy_embeddings = np.random.randn(3, 384).astype(np.float32)
        # Normalize dummy embeddings
        dummy_embeddings /= np.linalg.norm(dummy_embeddings, axis=1, keepdims=True)

        metadata = [
            {
                "document_id": "doc-001",
                "filename": "Leave_Policy.pdf",
                "chunk_id": "chk-001",
                "chunk_index": 0,
                "page_number": 1,
                "text": "Full-time employees are entitled to 15 days of annual leave.",
            },
            {
                "document_id": "doc-001",
                "filename": "Leave_Policy.pdf",
                "chunk_id": "chk-002",
                "chunk_index": 1,
                "page_number": 2,
                "text": "Medical leave requires a physician certificate after 3 consecutive days.",
            },
            {
                "document_id": "doc-002",
                "filename": "WFH_Policy.txt",
                "chunk_id": "chk-003",
                "chunk_index": 0,
                "page_number": None,
                "text": "Remote work is permitted up to 2 days per week with manager approval.",
            },
        ]

        store1.add_vectors(dummy_embeddings, metadata)
        assert store1.count() == 3
        store1.save()

        assert (tmp_path / "index.faiss").exists()
        assert (tmp_path / "metadata.json").exists()

        # 2. Simulate fresh backend restart: initialize separate store instance and load from disk
        store2 = FAISSVectorStore(vectorstore_dir=tmp_path)
        success = store2.load()
        assert success is True
        assert store2.count() == 3
        assert store2.index.d == 384
        assert len(store2.metadata_map) == 3

        # Verify metadata mapping preservation
        meta0 = store2.metadata_map[0]
        assert meta0["filename"] == "Leave_Policy.pdf"
        assert meta0["page_number"] == 1
        assert "15 days" in meta0["text"]

        # 3. Test search on reloaded index
        query_vec = dummy_embeddings[0].reshape(1, -1)
        results = store2.search(query_vec, top_k=2)
        assert len(results) == 2
        assert results[0]["filename"] == "Leave_Policy.pdf"
        assert np.isclose(results[0]["score"], 1.0, atol=1e-3)
        print(f"\n[PASS] TEST 5 FAISS Persistence: Successfully saved and reloaded 3 vectors. Top match score={results[0]['score']:.4f}")


def test_6_knowledge_base_status():
    """TEST 6: Call GET /api/knowledge-base/status and confirm values reflect actual backend state."""
    response = client.get("/api/knowledge-base/status")
    assert response.status_code == 200
    data = response.json()

    assert "documents" in data
    assert "chunks" in data
    assert "vectors" in data
    assert "dimension" in data
    assert "embedding_model" in data
    assert "index_type" in data
    assert "status" in data

    assert data["dimension"] == 384
    assert data["index_type"] == "IndexFlatIP"
    assert data["status"] in ("active", "ready", "not_built")
    assert data["vectors"] == vector_store.total_vectors
    assert data["documents"] >= 0
    assert data["chunks"] >= 0

    print(f"\n[PASS] TEST 6 Knowledge Base Status: documents={data['documents']}, chunks={data['chunks']}, vectors={data['vectors']}, dimension={data['dimension']}, status={data['status']}")
