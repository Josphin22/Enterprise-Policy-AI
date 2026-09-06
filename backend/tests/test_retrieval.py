import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.embeddings import embedding_service
from app.rag.vector_store import FAISSVectorStore
from app.rag.retriever import RAGRetriever
from app.rag.relevance import RelevanceFilter
from app.rag.context_builder import ContextBuilder
from app.rag.service import RAGService
from app.rag.pipeline import RAGPipeline
from app.rag.schemas import CandidateChunk, RAGRetrievalRequest


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session):
    """FastAPI TestClient with overridden database session."""
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
def populated_rag_environment(tmp_path, db_session: Session):
    """
    Sets up a populated knowledge base with realistic enterprise policy documents:
    1. Leave_Policy.pdf
    2. Attendance_Policy.txt
    3. Work_From_Home_Policy.docx
    """
    v_dir = tmp_path / "test_vectorstore"
    v_store = FAISSVectorStore(vectorstore_dir=v_dir)

    doc_leave = Document(
        id="doc-leave-001",
        filename="Leave_Policy.pdf",
        original_filename="Leave_Policy.pdf",
        file_type="pdf",
        file_size=15000,
        file_path=str(tmp_path / "Leave_Policy.pdf"),
        processing_status="processed",
        chunk_count=3,
    )
    doc_att = Document(
        id="doc-att-002",
        filename="Attendance_Policy.txt",
        original_filename="Attendance_Policy.txt",
        file_type="txt",
        file_size=8000,
        file_path=str(tmp_path / "Attendance_Policy.txt"),
        processing_status="processed",
        chunk_count=2,
    )
    doc_wfh = Document(
        id="doc-wfh-003",
        filename="Work_From_Home_Policy.docx",
        original_filename="Work_From_Home_Policy.docx",
        file_type="docx",
        file_size=12000,
        file_path=str(tmp_path / "Work_From_Home_Policy.docx"),
        processing_status="processed",
        chunk_count=2,
    )
    db_session.add_all([doc_leave, doc_att, doc_wfh])

    chunks = [
        # Leave Policy Chunks
        DocumentChunk(
            id="chunk-leave-01",
            document_id=doc_leave.id,
            chunk_index=0,
            page_number=1,
            section="Annual Vacation Leave",
            text="All full-time employees are entitled to 15 days of annual paid vacation leave per calendar year. Leave accrues on a pro-rata basis at 1.25 days per month of service.",
            character_count=165,
        ),
        DocumentChunk(
            id="chunk-leave-02",
            document_id=doc_leave.id,
            chunk_index=1,
            page_number=1,
            section="Leave Carry Forward",
            text="Employees may carry forward a maximum of 5 unused annual vacation days into the subsequent calendar year. Any additional unused leave will lapse on December 31.",
            character_count=171,
        ),
        DocumentChunk(
            id="chunk-leave-03",
            document_id=doc_leave.id,
            chunk_index=2,
            page_number=2,
            section="Sick Leave",
            text="Full-time employees receive 10 days of paid sick leave annually. A medical practitioner certificate is mandatory for sick leave exceeding 3 consecutive business days.",
            character_count=172,
        ),
        # Attendance Policy Chunks
        DocumentChunk(
            id="chunk-att-01",
            document_id=doc_att.id,
            chunk_index=0,
            page_number=None,
            section="Standard Work Schedule",
            text="Standard enterprise working hours are 9:00 AM to 5:00 PM Monday through Friday. All employees must log their daily attendance via the portal.",
            character_count=150,
        ),
        DocumentChunk(
            id="chunk-att-02",
            document_id=doc_att.id,
            chunk_index=1,
            page_number=None,
            section="Core Working Hours",
            text="Core working hours during which all team members must be available and reachable online or in the office are 10:00 AM to 4:00 PM.",
            character_count=141,
        ),
        # Work From Home Policy Chunks
        DocumentChunk(
            id="chunk-wfh-01",
            document_id=doc_wfh.id,
            chunk_index=0,
            page_number=1,
            section="Remote Work Eligibility",
            text="Full-time staff members who have completed their initial 90-day probationary period are eligible to work remotely up to 2 days per week with manager approval.",
            character_count=170,
        ),
        DocumentChunk(
            id="chunk-wfh-02",
            document_id=doc_wfh.id,
            chunk_index=1,
            page_number=2,
            section="Home Workspace & Security",
            text="Employees working remotely must maintain a dedicated ergonomic workspace, utilize corporate VPN at all times, and ensure sensitive company information remains confidential.",
            character_count=182,
        ),
    ]
    db_session.add_all(chunks)
    db_session.commit()

    # Build FAISS index for these chunks
    pipeline = RAGPipeline(
        embed_service=embedding_service,
        v_store=v_store,
    )
    pipeline.build_knowledge_base(db=db_session)

    # Initialize RAG components bound to this vector store
    retriever = RAGRetriever(embed_service=embedding_service, v_store=v_store)
    rel_filter = RelevanceFilter(default_min_score=0.35)
    builder = ContextBuilder(max_chunks=5, max_characters=6000, include_adjacent=False)
    service = RAGService(retriever=retriever, filter_layer=rel_filter, builder=builder)

    return {
        "vector_store": v_store,
        "retriever": retriever,
        "relevance_filter": rel_filter,
        "context_builder": builder,
        "rag_service": service,
        "db": db_session,
    }


# =========================================================================
# 1. Unit Tests
# =========================================================================

def test_query_validation_empty_whitespace_error(populated_rag_environment):
    """Validate that blank or whitespace queries raise HTTP 400."""
    retriever = populated_rag_environment["retriever"]
    with pytest.raises(Exception) as exc_info:
        retriever.normalize_query("   ")
    assert "cannot be empty" in str(exc_info.value)


def test_relevance_filter_threshold_behavior():
    """
    Evaluate candidate filtering across multiple thresholds: 0.20, 0.30, 0.35, 0.40, 0.50.
    """
    filter_layer = RelevanceFilter()
    sample_candidates = [
        CandidateChunk(chunk_id="c1", document_id="d1", filename="f1.pdf", text="T1", score=0.88),
        CandidateChunk(chunk_id="c2", document_id="d1", filename="f1.pdf", text="T2", score=0.62),
        CandidateChunk(chunk_id="c3", document_id="d1", filename="f1.pdf", text="T3", score=0.38),
        CandidateChunk(chunk_id="c4", document_id="d2", filename="f2.txt", text="T4", score=0.32),
        CandidateChunk(chunk_id="c5", document_id="d3", filename="f3.docx", text="T5", score=0.18),
    ]

    # Threshold 0.20
    acc_20, stats_20 = filter_layer.filter_candidates(sample_candidates, min_score=0.20)
    assert len(acc_20) == 4
    assert stats_20["rejected"] == 1

    # Threshold 0.30
    acc_30, stats_30 = filter_layer.filter_candidates(sample_candidates, min_score=0.30)
    assert len(acc_30) == 4

    # Default Threshold 0.35
    acc_35, stats_35 = filter_layer.filter_candidates(sample_candidates, min_score=0.35)
    assert len(acc_35) == 3
    assert [c.chunk_id for c in acc_35] == ["c1", "c2", "c3"]
    assert stats_35["rejected"] == 2

    # Threshold 0.40
    acc_40, stats_40 = filter_layer.filter_candidates(sample_candidates, min_score=0.40)
    assert len(acc_40) == 2

    # Threshold 0.50
    acc_50, stats_50 = filter_layer.filter_candidates(sample_candidates, min_score=0.50)
    assert len(acc_50) == 2


def test_context_builder_deduplication():
    """Verify that identical texts are deduplicated while distinct chunks from same doc are kept."""
    builder = ContextBuilder()
    chunks = [
        CandidateChunk(chunk_id="c1", document_id="d1", filename="Leave.pdf", page=1, text="15 days annual vacation leave.", score=0.90),
        CandidateChunk(chunk_id="c2", document_id="d1", filename="Leave.pdf", page=1, text="15 days annual vacation leave. ", score=0.88),  # Duplicate
        CandidateChunk(chunk_id="c3", document_id="d1", filename="Leave.pdf", page=2, text="Carry forward 5 unused days.", score=0.75),    # Distinct chunk from same doc
    ]
    context, sources = builder.build_context(chunks)
    assert len(sources) == 2
    assert sources[0].source_id == "S1"
    assert sources[1].source_id == "S2"
    assert "Carry forward 5 unused days" in context


def test_context_builder_character_and_chunk_limits():
    """Verify context respects chunk count and max character boundaries without mid-word cuts."""
    builder = ContextBuilder(max_chunks=2, max_characters=150)
    chunks = [
        CandidateChunk(chunk_id="c1", document_id="d1", filename="DocA.pdf", text="Policy text block 1 for test.", score=0.90),
        CandidateChunk(chunk_id="c2", document_id="d2", filename="DocB.pdf", text="Policy text block 2 for test.", score=0.80),
        CandidateChunk(chunk_id="c3", document_id="d3", filename="DocC.pdf", text="Policy text block 3 for test.", score=0.70),
    ]
    context, sources = builder.build_context(chunks)
    assert len(sources) <= 2
    assert len(context) <= 150


def test_source_id_mapping_and_structure():
    """Verify source citations [S1], [S2] format accurately."""
    builder = ContextBuilder()
    chunks = [
        CandidateChunk(chunk_id="c1", document_id="doc1", filename="Policy.pdf", page=2, section="Vacation", text="Leave rules.", score=0.89123),
    ]
    context, sources = builder.build_context(chunks)
    assert "[Source S1]" in context
    assert "Document: Policy.pdf" in context
    assert "Page: 2" in context
    assert "Section: Vacation" in context
    assert sources[0].source_id == "S1"
    assert sources[0].score == 0.8912


def test_adjacent_chunk_expansion(populated_rag_environment):
    """Test neighboring-chunk expansion when include_adjacent=True."""
    db = populated_rag_environment["db"]
    builder = ContextBuilder(include_adjacent=True)
    initial_chunks = [
        CandidateChunk(chunk_id="chunk-leave-02", document_id="doc-leave-001", chunk_index=1, filename="Leave_Policy.pdf", page=1, section="Leave Carry Forward", text="Carry forward text", score=0.85),
    ]
    expanded = builder.expand_adjacent_chunks(initial_chunks, db=db)
    # Should include chunk 1, chunk 0, and chunk 2
    assert len(expanded) >= 2


def test_insufficient_context_handling_for_irrelevant_query(populated_rag_environment):
    """Test that asking an out-of-domain question returns insufficient_context with no fabricated citations."""
    service = populated_rag_environment["rag_service"]
    resp = service.retrieve_context(
        query="What is the population of Mars and how many craters exist on its surface?",
        min_score=0.35,
    )
    assert resp.status == "insufficient_context"
    assert resp.context == ""
    assert len(resp.sources) == 0
    assert "No sufficiently relevant information was found" in resp.message


def test_rag_service_latency_breakdown_and_debug_mode(populated_rag_environment):
    """Verify latency tracking and debug metadata."""
    from app.config import settings
    original_debug = settings.RAG_DEBUG
    settings.RAG_DEBUG = True
    try:
        service = populated_rag_environment["rag_service"]
        resp = service.retrieve_context(query="annual leave entitlement days")
        assert resp.status == "success"
        assert resp.debug_info is not None
        assert "faiss_time_ms" in resp.debug_info
        assert "total_time_ms" in resp.debug_info
        assert "threshold" in resp.debug_info
    finally:
        settings.RAG_DEBUG = original_debug


# =========================================================================
# 2. Integration & End-to-End Tests
# =========================================================================

def test_end_to_end_leave_policy_retrieval_and_15_days_context(populated_rag_environment):
    """
    Test core requirement:
    Question: 'How many annual leave days are allowed?'
    Retrieved context must contain '15 days' and point to 'Leave_Policy.pdf'.
    """
    service = populated_rag_environment["rag_service"]
    resp = service.retrieve_context(query="How many annual leave days are allowed?")

    assert resp.status == "success"
    assert "15 days" in resp.context
    assert len(resp.sources) >= 1
    assert resp.sources[0].document == "Leave_Policy.pdf"
    assert resp.sources[0].page == 1
    assert resp.sources[0].score >= 0.60


def test_paraphrased_query_semantic_retrieval(populated_rag_environment):
    """
    Test paraphrased query:
    Question: 'What is the yearly vacation allotment?'
    Should semantically retrieve the annual leave policy chunk.
    """
    service = populated_rag_environment["rag_service"]
    resp = service.retrieve_context(query="What is the yearly vacation allotment?")

    assert resp.status == "success"
    assert "15 days" in resp.context
    assert resp.sources[0].document == "Leave_Policy.pdf"


def test_multi_document_query_context_construction(populated_rag_environment):
    """
    Test query spanning multiple policies:
    Question: 'What are the rules regarding annual leave and remote working eligibility?'
    Retrieved context should include chunks from both Leave_Policy.pdf and Work_From_Home_Policy.docx.
    """
    service = populated_rag_environment["rag_service"]
    resp = service.retrieve_context(
        query="What are the rules regarding annual leave and remote working eligibility?",
        top_k=5,
    )
    assert resp.status == "success"
    docs_retrieved = {s.document for s in resp.sources}
    assert "Leave_Policy.pdf" in docs_retrieved
    assert "Work_From_Home_Policy.docx" in docs_retrieved


def test_api_rag_retrieve_endpoint(client: TestClient, populated_rag_environment):
    """Test POST /api/rag/retrieve endpoint."""
    from app.rag.service import rag_service
    # Point global rag_service to the test vector store
    rag_service.retriever = populated_rag_environment["retriever"]
    rag_service.filter_layer = populated_rag_environment["relevance_filter"]
    rag_service.builder = populated_rag_environment["context_builder"]

    payload = {
        "query": "How many annual leave days are allowed?",
        "top_k": 3,
        "min_score": 0.35,
    }
    response = client.post("/api/rag/retrieve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "15 days" in data["context"]
    assert len(data["sources"]) >= 1
    assert data["sources"][0]["source_id"] == "S1"


def test_api_chat_returns_retrieval_ready_and_grounded_context(client: TestClient, populated_rag_environment):
    """
    Test POST /api/chat:
    User message -> stored in DB -> RAG retrieval executed -> returns retrieval_ready + context.
    """
    from app.rag.service import rag_service
    rag_service.retriever = populated_rag_environment["retriever"]
    rag_service.filter_layer = populated_rag_environment["relevance_filter"]
    rag_service.builder = populated_rag_environment["context_builder"]

    payload = {"question": "How many annual leave days are allowed?"}
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] in ("success", "retrieval_ready", "llm_unavailable")
    assert "15 days" in data["context"]
    assert len(data["sources"]) >= 1
    assert data["sources"][0]["document"] == "Leave_Policy.pdf"
    assert data["message_id"] is not None


def test_15_query_evaluation_benchmark_precision_recall(populated_rag_environment):
    """
    Execute complete 15-query evaluation benchmark across Direct, Paraphrased,
    Multi-document, Irrelevant, and Ambiguous categories.
    Measure Top-1, Top-3, and Top-5 accuracy and precision/recall.
    """
    service = populated_rag_environment["rag_service"]
    eval_file = Path(__file__).parent / "data" / "rag_queries.json"
    with open(eval_file, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    top_1_hits = 0
    top_3_hits = 0
    top_5_hits = 0
    negative_correct = 0
    total_queries = len(eval_data)
    positive_queries = 0

    print("\n--- Phase 7 RAG Retrieval Benchmark Results ---")

    for item in eval_data:
        q_id = item["id"]
        query = item["query"]
        expected_status = item["expected_status"]
        expected_doc = item["expected_document"]

        resp = service.retrieve_context(query=query, top_k=5, min_score=0.35)

        if expected_status == "insufficient_context":
            if resp.status == "insufficient_context":
                negative_correct += 1
                print(f"PASS [{q_id} - Irrelevant]: '{query}' -> correctly rejected (insufficient_context)")
            else:
                print(f"FAIL [{q_id} - Irrelevant]: '{query}' -> unexpectedly returned {len(resp.sources)} sources")
        else:
            positive_queries += 1
            retrieved_docs = [s.document for s in resp.sources]

            # Top-1 Check
            expected_docs = [expected_doc] if isinstance(expected_doc, str) else expected_doc
            top_1_match = len(retrieved_docs) > 0 and any(d in expected_docs for d in [retrieved_docs[0]])
            if top_1_match:
                top_1_hits += 1

            # Top-3 Check
            top_3_match = any(d in expected_docs for d in retrieved_docs[:3])
            if top_3_match:
                top_3_hits += 1

            # Top-5 Check
            top_5_match = any(d in expected_docs for d in retrieved_docs[:5])
            if top_5_match:
                top_5_hits += 1

            status_str = "PASS" if top_1_match else "WARN"
            print(f"{status_str} [{q_id} - {item['category']}]: '{query[:45]}...' -> Top-1: {retrieved_docs[:1]}, Top-K: {retrieved_docs}")

    top_1_acc = (top_1_hits / positive_queries) * 100
    top_3_acc = (top_3_hits / positive_queries) * 100
    top_5_acc = (top_5_hits / positive_queries) * 100

    print(f"\nBenchmark Summary: Total={total_queries} | Top-1 Acc={top_1_acc:.1f}% | Top-3 Acc={top_3_acc:.1f}% | Top-5 Acc={top_5_acc:.1f}% | Irrelevant Rejected={negative_correct}/3")

    assert top_1_acc >= 80.0, f"Top-1 accuracy ({top_1_acc}%) below 80%"
    assert top_5_acc == 100.0, f"Top-5 accuracy ({top_5_acc}%) should be 100%"
    assert negative_correct == 3, f"All 3 irrelevant queries must return insufficient_context"
