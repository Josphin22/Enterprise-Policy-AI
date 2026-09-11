import os
import json
import pytest
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.base import Base
from app.database.session import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import FAISSVectorStore
from app.rag.pipeline import RAGPipeline
from app.main import app

# In-memory SQLite engine for isolated test runs
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def temp_vector_dir(tmp_path):
    v_dir = tmp_path / "vectorstore"
    v_dir.mkdir(parents=True, exist_ok=True)
    return v_dir


@pytest.fixture
def embedding_svc():
    return EmbeddingService(model_name="all-MiniLM-L6-v2")


@pytest.fixture
def vector_st(temp_vector_dir):
    return FAISSVectorStore(vectorstore_dir=temp_vector_dir)


@pytest.fixture
def pipeline(embedding_svc, vector_st):
    return RAGPipeline(embed_service=embedding_svc, v_store=vector_st)


# ============================================================================
# 1. Embedding Service Tests
# ============================================================================

def test_embedding_service_loads_model_and_detects_dimension(embedding_svc):
    dim = embedding_svc.get_dimension()
    assert dim == 384
    assert embedding_svc.is_loaded is True


def test_embedding_service_embed_text_normalized(embedding_svc):
    query = "How many annual leave days are allowed?"
    vec = embedding_svc.embed_text(query)
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (384,)
    assert vec.dtype == np.float32

    # Verify L2 norm is ~1.0
    norm = np.linalg.norm(vec)
    assert np.isclose(norm, 1.0, atol=1e-4)


def test_embedding_service_empty_text_returns_zero_vector(embedding_svc):
    vec_empty = embedding_svc.embed_text("")
    assert vec_empty.shape == (384,)
    assert np.all(vec_empty == 0.0)

    vec_spaces = embedding_svc.embed_text("   \n\t  ")
    assert np.all(vec_spaces == 0.0)


def test_embedding_service_batch_documents(embedding_svc):
    texts = [
        "Employees are entitled to 15 days of annual leave.",
        "Standard core working hours are 9:00 AM to 5:00 PM.",
        "Remote work subsidy allows up to $500 for home office setup.",
    ]
    embeddings = embedding_svc.embed_documents(texts, batch_size=2)
    assert embeddings.shape == (3, 384)
    assert embeddings.dtype == np.float32

    for i in range(3):
        norm = np.linalg.norm(embeddings[i])
        assert np.isclose(norm, 1.0, atol=1e-4)


# ============================================================================
# 2. FAISS Vector Store Tests (IndexFlatIP & Cosine Similarity)
# ============================================================================

def test_faiss_vector_store_lifecycle(vector_st, embedding_svc, temp_vector_dir):
    texts = [
        "Employees receive 15 days of paid vacation per year.",
        "Working hours are 9 AM to 5 PM Monday through Friday.",
    ]
    meta = [
        {"chunk_id": "c1", "document_id": "d1", "filename": "Leave_Policy.pdf", "page": 1, "section": "Leave", "text": texts[0]},
        {"chunk_id": "c2", "document_id": "d2", "filename": "Attendance_Policy.txt", "page": None, "section": "Hours", "text": texts[1]},
    ]

    embeddings = embedding_svc.embed_documents(texts)
    vector_st.create_index(384)
    vector_st.add_vectors(embeddings, meta)

    assert vector_st.is_built is True
    assert vector_st.total_vectors == 2

    # Save to disk
    vector_st.save_index()
    assert (temp_vector_dir / "index.faiss").exists()
    assert (temp_vector_dir / "metadata.json").exists()
    assert (temp_vector_dir / "index_info.json").exists()

    # Load in new instance
    new_store = FAISSVectorStore(vectorstore_dir=temp_vector_dir)
    assert new_store.is_built is False
    loaded = new_store.load_index()
    assert loaded is True
    assert new_store.is_built is True
    assert new_store.total_vectors == 2
    assert new_store.metadata_map[0]["chunk_id"] == "c1"
    assert new_store.metadata_map[1]["chunk_id"] == "c2"


def test_faiss_similarity_search_ranking(vector_st, embedding_svc):
    texts = [
        "Employees are entitled to 15 days of annual paid vacation leave per calendar year.",
        "All staff must clock in between 8:00 AM and 10:00 AM for flexible arrival.",
        "Eligible employees may work remotely up to 2 days per week under the hybrid model.",
    ]
    meta = [
        {"chunk_id": "chunk-leave", "document_id": "d-leave", "filename": "Leave_Policy.txt", "page": 1, "section": "Vacation", "text": texts[0]},
        {"chunk_id": "chunk-att", "document_id": "d-att", "filename": "Attendance_Policy.txt", "page": 1, "section": "Arrival", "text": texts[1]},
        {"chunk_id": "chunk-wfh", "document_id": "d-wfh", "filename": "WFH_Policy.txt", "page": 1, "section": "Hybrid", "text": texts[2]},
    ]

    embeddings = embedding_svc.embed_documents(texts)
    vector_st.create_index(384)
    vector_st.add_vectors(embeddings, meta)

    # Search for annual leave
    query_vec = embedding_svc.embed_text("How many annual vacation days are permitted?")
    results = vector_st.search(query_vec, top_k=2)

    assert len(results) == 2
    # Top-1 result MUST be Leave Policy
    assert results[0]["chunk_id"] == "chunk-leave"
    assert results[0]["filename"] == "Leave_Policy.txt"
    assert "15 days" in results[0]["text"]
    assert results[0]["score"] > results[1]["score"]
    assert results[0]["score"] > 0.60


def test_corrupted_index_handling(tmp_path):
    corrupt_dir = tmp_path / "corrupt_store"
    corrupt_dir.mkdir(parents=True, exist_ok=True)
    # Write garbage into index.faiss
    (corrupt_dir / "index.faiss").write_bytes(b"NOT_A_VALID_FAISS_INDEX")
    (corrupt_dir / "metadata.json").write_text("{}", encoding="utf-8")

    store = FAISSVectorStore(vectorstore_dir=corrupt_dir)
    loaded = store.load_index()
    assert loaded is False
    assert store.is_built is False


# ============================================================================
# 3. RAG Pipeline Integration & Database Workflow Tests
# ============================================================================

def test_rag_pipeline_empty_db_returns_no_processed_chunks(pipeline, db_session):
    result = pipeline.build_knowledge_base(db_session)
    assert result["success"] is False
    assert result["status"] == "no_processed_chunks"
    assert result["vectors"] == 0


def test_rag_pipeline_end_to_end_build_and_search(pipeline, db_session):
    # 1. Create a processed document in DB with chunks
    doc = Document(
        filename="123_Leave_Policy.txt",
        original_filename="Leave_Policy.txt",
        file_type="txt",
        file_size=1024,
        file_path="E:/GEN AI/backend/documents/sample.txt",
        processing_status="processed",
        chunk_count=2,
    )
    db_session.add(doc)
    db_session.flush()

    chunk1 = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        text="Employees are entitled to 15 days of annual leave per year. Unused leave up to 5 days can carry forward.",
        page_number=1,
        section="Annual Leave",
        character_count=107,
    )
    chunk2 = DocumentChunk(
        document_id=doc.id,
        chunk_index=1,
        text="Sick leave of 10 days per year is provided. Medical certificate is needed for absences exceeding 3 days.",
        page_number=1,
        section="Sick Leave",
        character_count=106,
    )
    db_session.add_all([chunk1, chunk2])
    db_session.commit()

    # 2. Build Knowledge Base
    build_res = pipeline.build_knowledge_base(db_session)
    assert build_res["success"] is True
    assert build_res["status"] == "built"
    assert build_res["documents"] == 1
    assert build_res["chunks"] == 2
    assert build_res["vectors"] == 2
    assert build_res["embedding_dimension"] == 384

    # 3. Search: "How many annual leave days are allowed?"
    search_res = pipeline.search_knowledge_base("How many annual leave days are allowed?", top_k=2)
    assert len(search_res["results"]) == 2
    top_result = search_res["results"][0]
    assert top_result["filename"] == "Leave_Policy.txt"
    assert top_result["section"] == "Annual Leave"
    assert "15 days" in top_result["text"]
    assert top_result["score"] > 0.65

    # 4. Rebuild Idempotency: Rebuilding should NOT create duplicate vectors
    rebuild_res = pipeline.build_knowledge_base(db_session)
    assert rebuild_res["vectors"] == 2


# ============================================================================
# 4. REST API Endpoint Tests
# ============================================================================

def test_api_knowledge_base_build_and_search(client: TestClient, db_session):
    # Seed DB with processed policy
    doc = Document(
        filename="123_Work_From_Home_Policy.txt",
        original_filename="Work_From_Home_Policy.txt",
        file_type="txt",
        file_size=800,
        file_path="sample.txt",
        processing_status="processed",
        chunk_count=1,
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        text="Full-time employees receive a $500 home office equipment subsidy and may work remotely 2 days per week.",
        page_number=1,
        section="WFH Stipend",
        character_count=106,
    )
    db_session.add(chunk)
    db_session.commit()

    # 1. Build Knowledge Base
    build_res = client.post("/api/knowledge-base/build")
    assert build_res.status_code == 200
    build_data = build_res.json()
    assert build_data["success"] is True
    assert build_data["status"] == "built"
    assert build_data["vectors"] >= 1

    # 2. Check Status
    status_res = client.get("/api/knowledge-base/status")
    assert status_res.status_code == 200
    assert status_res.json()["status"] in ("ready", "active")
    assert status_res.json()["vectors"] >= 1
    assert status_res.json()["vector_database"] == "FAISS"

    # 3. Search
    search_res = client.post("/api/knowledge-base/search", json={
        "query": "Is there a financial allowance or subsidy for home office?",
        "top_k": 3,
    })
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data["results"]) >= 1
    assert "$500" in search_data["results"][0]["text"]

    # 4. Search Validation (Empty Query)
    invalid_search = client.post("/api/knowledge-base/search", json={
        "query": "   ",
        "top_k": 3,
    })
    assert invalid_search.status_code == 422 or invalid_search.status_code == 400


def test_api_reindex_document(client: TestClient, db_session):
    doc = Document(
        filename="123_Attendance_Policy.txt",
        original_filename="Attendance_Policy.txt",
        file_type="txt",
        file_size=600,
        file_path="sample.txt",
        processing_status="processed",
        chunk_count=1,
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        text="Employees must maintain at least 95% punctuality.",
        page_number=1,
        section="Attendance",
        character_count=49,
    )
    db_session.add(chunk)
    db_session.commit()

    reindex_res = client.post(f"/api/documents/{doc.id}/reindex")
    assert reindex_res.status_code == 200
    assert reindex_res.json()["success"] is True


# ============================================================================
# 5. Semantic Search Evaluation Benchmark (10 Queries)
# ============================================================================

def test_semantic_search_evaluation_benchmark(pipeline, db_session):
    """
    Evaluates 10 benchmark queries against indexed policy documents
    to measure Top-1 and Top-5 retrieval precision.
    """
    # Ingest 3 realistic policy documents
    policies = [
        {
            "filename": "Leave_Policy.txt",
            "chunks": [
                ("Employees are entitled to 15 days of annual paid vacation leave per calendar year. Leave accrues at 1.25 days per month.", "Annual Vacation Leave"),
                ("Employees may carry forward a maximum of 5 unused vacation days into the subsequent calendar year.", "Carry Forward"),
                ("Full-time employees receive 10 days of paid sick leave annually. A medical certificate is required for absences over 3 consecutive days.", "Sick Leave"),
                ("Eligible employees are entitled to 12 weeks of paid parental leave for the birth or adoption of a child.", "Parental Leave"),
            ]
        },
        {
            "filename": "Attendance_Policy.txt",
            "chunks": [
                ("Standard company working hours are 9:00 AM to 5:00 PM, Monday through Friday, comprising a 40-hour work week.", "Standard Working Hours"),
                ("Flexible schedule allows employees to arrive between 8:00 AM and 10:00 AM, completing 8 hours daily.", "Flexible Arrival"),
                ("Unexcused absence without notifying manager within 2 hours of shift start is subject to disciplinary review.", "Unexcused Absence"),
            ]
        },
        {
            "filename": "Work_From_Home_Policy.txt",
            "chunks": [
                ("Employees in eligible roles may work remotely up to 2 days per week with manager approval under hybrid work.", "Hybrid Eligibility"),
                ("The company provides a one-time $500 home office equipment stipend for ergonomic setup and monitors.", "Home Office Stipend"),
                ("All remote workers must connect via corporate VPN and maintain two-factor authentication for data security.", "Data Security Protocols"),
            ]
        },
    ]

    for p in policies:
        doc = Document(
            filename=f"sample_{p['filename']}",
            original_filename=p["filename"],
            file_type="txt",
            file_size=2048,
            file_path=p["filename"],
            processing_status="processed",
            chunk_count=len(p["chunks"]),
        )
        db_session.add(doc)
        db_session.flush()

        for idx, (text, section) in enumerate(p["chunks"]):
            c = DocumentChunk(
                document_id=doc.id,
                chunk_index=idx,
                text=text,
                page_number=None,
                section=section,
                character_count=len(text),
            )
            db_session.add(c)
    db_session.commit()

    # Build KB
    build_result = pipeline.build_knowledge_base(db_session)
    assert build_result["success"] is True
    assert build_result["vectors"] == 10

    # Load 10 benchmark queries from eval dataset
    eval_file = Path(__file__).resolve().parent.parent.parent / "data" / "evaluation" / "semantic_search_eval.json"
    assert eval_file.exists()
    eval_items = json.loads(eval_file.read_text(encoding="utf-8"))

    passed_top1 = 0
    passed_top5 = 0
    evaluated_count = 0

    for item in eval_items:
        expected_doc = item["expected_document"]
        if expected_doc is None:
            continue  # Negative control query

        evaluated_count += 1
        query = item["query"]
        search_res = pipeline.search_knowledge_base(query, top_k=5)
        results = search_res["results"]

        assert len(results) > 0

        # Check Top-1
        top1_doc = results[0]["filename"]
        if top1_doc == expected_doc:
            passed_top1 += 1

        # Check Top-5
        top5_docs = [r["filename"] for r in results]
        if expected_doc in top5_docs:
            passed_top5 += 1

    top1_accuracy = passed_top1 / evaluated_count
    top5_accuracy = passed_top5 / evaluated_count

    print(f"\n[Semantic Search Benchmark] Top-1 Accuracy: {top1_accuracy * 100:.1f}%, Top-5 Accuracy: {top5_accuracy * 100:.1f}%")
    assert top1_accuracy >= 0.80, f"Top-1 accuracy ({top1_accuracy}) fell below 80%"
    assert top5_accuracy == 1.00, f"Top-5 accuracy ({top5_accuracy}) must be 100%"
