import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.evaluation.dataset import EvaluationDataset, EvaluationQuestion
from app.evaluation.retrieval_evaluator import RetrievalEvaluator
from app.evaluation.answer_evaluator import AnswerEvaluator
from app.evaluation.hallucination_evaluator import HallucinationEvaluator
from app.evaluation.performance import PerformanceProfiler
from app.evaluation.metrics import MetricsAggregator
from app.evaluation.runner import EvaluationRunner
from app.rag.schemas import CandidateChunk


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def sample_question():
    return EvaluationQuestion(
        id="Q001",
        question="How many annual leave days are allowed?",
        expected_answer="Employees are entitled to 15 days of annual paid vacation leave.",
        expected_sources=["Leave_Policy.pdf"],
        expected_keywords=["15 days", "annual", "vacation"],
        expected_numbers=[15],
        expected_dates=[],
        answerable=True,
        category="direct",
    )


@pytest.fixture
def sample_unanswerable_question():
    return EvaluationQuestion(
        id="Q022",
        question="What is the population of Mars?",
        expected_answer="I could not find sufficient information in the provided enterprise documents.",
        expected_sources=[],
        expected_keywords=["not find sufficient information"],
        expected_numbers=[],
        expected_dates=[],
        answerable=False,
        category="unanswerable",
    )


# =========================================================================
# 1. Dataset Loader Tests
# =========================================================================

def test_evaluation_dataset_loading():
    """Verify loading and structure of 35-question evaluation benchmark."""
    ds = EvaluationDataset()
    assert ds.total >= 30
    assert len(ds.get_answerable()) >= 20
    assert len(ds.get_unanswerable()) >= 10

    # Verify key categories exist
    categories = {q.category for q in ds.questions}
    assert "direct" in categories
    assert "paraphrased" in categories
    assert "multi_document" in categories
    assert "numerical" in categories
    assert "date" in categories
    assert "unanswerable" in categories
    assert "prompt_injection" in categories


# =========================================================================
# 2. Retrieval Evaluator Tests
# =========================================================================

def test_retrieval_evaluator_precision_recall(sample_question):
    """Test Hit Rate, Precision@K, and Recall@K calculation."""
    evaluator = RetrievalEvaluator()
    mock_chunks = [
        CandidateChunk(
            chunk_id="c1",
            document_id="d1",
            filename="Leave_Policy.pdf",
            page=1,
            section="Annual Leave",
            text="Employees get 15 days annual vacation leave.",
            character_count=45,
            score=0.88,
        ),
        CandidateChunk(
            chunk_id="c2",
            document_id="d2",
            filename="Attendance_Policy.txt",
            page=None,
            section="Hours",
            text="Core hours are 10:00 to 4:00.",
            character_count=30,
            score=0.45,
        ),
    ]

    res = evaluator.evaluate_query_retrieval(sample_question, mock_chunks, [1, 3, 5])
    assert res["hit_rate_at_k"]["hit@1"] == 1.0
    assert res["precision_at_k"]["p@1"] == 1.0
    assert res["recall_at_k"]["r@1"] == 1.0
    assert res["context_relevance"] in ("Relevant", "Partially Relevant")


def test_retrieval_evaluator_unanswerable(sample_unanswerable_question):
    """Test unanswerable query evaluation behavior."""
    evaluator = RetrievalEvaluator()
    res = evaluator.evaluate_query_retrieval(sample_unanswerable_question, [], [1, 3, 5])
    assert res["is_unanswerable"] is True
    assert res["context_relevance"] == "N/A"


# =========================================================================
# 3. Answer Evaluator Tests
# =========================================================================

def test_answer_evaluator_correct_answer(sample_question):
    """Test factual answer matching, numbers, and source check."""
    evaluator = AnswerEvaluator()
    actual_ans = "All full-time employees are entitled to 15 days of annual paid vacation leave [S1]."
    actual_sources = [{"source_id": "S1", "document": "Leave_Policy.pdf", "page": 1}]

    res = evaluator.evaluate_answer(sample_question, actual_ans, actual_sources, "success")
    assert res["answer_correct"] is True
    assert res["source_correct"] is True
    assert res["numerical_correct"] is True
    assert res["completeness"] == "Complete"
    assert res["failure_type"] is None


def test_answer_evaluator_numerical_error(sample_question):
    """Test detection of numerical discrepancies (e.g. 20 days instead of 15 days)."""
    evaluator = AnswerEvaluator()
    actual_ans = "Employees are entitled to 20 days of annual vacation leave [S1]."
    actual_sources = [{"source_id": "S1", "document": "Leave_Policy.pdf", "page": 1}]

    res = evaluator.evaluate_answer(sample_question, actual_ans, actual_sources, "success")
    assert res["numerical_correct"] is False
    assert res["failure_type"] == "Numerical Error"


def test_answer_evaluator_refusal_correctness(sample_unanswerable_question):
    """Test refusal verification on unanswerable query."""
    evaluator = AnswerEvaluator()
    res = evaluator.evaluate_answer(
        sample_unanswerable_question,
        "I could not find sufficient information in the provided enterprise documents.",
        [],
        "insufficient_context",
    )
    assert res["refusal_correct"] is True
    assert res["answer_correct"] is True
    assert res["failure_type"] is None


# =========================================================================
# 4. Hallucination Evaluator Tests
# =========================================================================

def test_hallucination_evaluator_supported():
    """Test grounded answer support detection."""
    evaluator = HallucinationEvaluator()
    context = "Section 1: Annual Leave. All full-time employees receive 15 days of annual paid leave."
    answer = "Employees receive 15 days of annual paid leave according to Section 1."

    res = evaluator.evaluate_faithfulness(answer, context, "success")
    assert res["classification"] == "SUPPORTED"
    assert res["is_hallucination"] is False
    assert res["faithfulness_score"] >= 0.8


def test_hallucination_evaluator_unsupported():
    """Test ungrounded/hallucinated claim detection."""
    evaluator = HallucinationEvaluator()
    context = "Section 1: Standard enterprise working hours are 9:00 AM to 5:00 PM."
    answer = "Employees receive an international travel bonus of $50,000 every December."

    res = evaluator.evaluate_faithfulness(answer, context, "success")
    assert res["classification"] == "UNSUPPORTED"
    assert res["is_hallucination"] is True


# =========================================================================
# 5. Performance Profiler Tests
# =========================================================================

def test_performance_profiler_statistics():
    """Test Mean, Median, Min, Max, and P95 calculation."""
    profiler = PerformanceProfiler()
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]

    stats = profiler.calculate_statistics(latencies)
    assert stats["count"] == 10
    assert stats["mean_ms"] == 55.0
    assert stats["median_ms"] == 55.0
    assert stats["min_ms"] == 10.0
    assert stats["max_ms"] == 100.0
    assert stats["p95_ms"] == 100.0


# =========================================================================
# 6. Evaluation Reports & Runner Tests
# =========================================================================

def test_metrics_aggregator_export(tmp_path):
    """Test JSON and CSV report export."""
    aggregator = MetricsAggregator()
    summary = {"title": "Test Evaluation", "accuracy": 95.0}
    records = [{
        "question_id": "Q001",
        "question": "Leave days?",
        "category": "direct",
        "expected_answer": "15 days",
        "actual_answer": "15 days",
        "expected_sources": ["Leave_Policy.pdf"],
        "actual_sources": [{"document": "Leave_Policy.pdf"}],
        "retrieval_passed": True,
        "answer_passed": True,
        "source_passed": True,
        "faithfulness_classification": "SUPPORTED",
        "refusal_correct": None,
        "latency_ms": 120.5,
    }]

    exported = aggregator.export_reports(
        summary=summary,
        full_records=records,
        retrieval_metrics={"hit_rate_1": 100.0},
        answer_metrics={"answer_accuracy": 100.0},
        performance_metrics={"total": {"mean_ms": 120.5}},
        output_dir=tmp_path,
    )

    assert Path(exported["summary_json"]).exists()
    assert Path(exported["results_json"]).exists()
    assert Path(exported["csv"]).exists()


# =========================================================================
# 7. Evaluation & Health API Endpoints Tests
# =========================================================================

def test_api_evaluation_summary_endpoint(test_client):
    """Test GET /api/evaluation/summary endpoint."""
    with patch.object(
        EvaluationRunner,
        "run_evaluation",
        return_value={
            "summary": {
                "evaluation_timestamp": "2026-09-04 00:00:00",
                "dataset_info": {"total_questions": 35, "answerable_questions": 23, "unanswerable_questions": 12},
                "retrieval_metrics": {"top_1_accuracy": 95.0, "top_5_accuracy": 100.0},
                "answer_metrics": {"answer_accuracy": 95.0, "source_accuracy": 95.0, "refusal_accuracy": 100.0},
                "hallucination_metrics": {"faithfulness_rate": 96.0, "hallucination_rate": 0.0},
                "performance_metrics": {"average_total_ms": 150.0, "p95_total_ms": 280.0},
            },
            "records": [],
            "failed_cases": [],
        },
    ):
        resp = test_client.get("/api/evaluation/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "retrieval_metrics" in data
        assert "answer_metrics" in data


def test_api_system_health_endpoint(test_client):
    """Test GET /api/system/health endpoint."""
    resp = test_client.get("/api/system/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["backend"] == "operational"
    assert "vector_store" in data
    assert "embedding_model" in data
    assert "llm_engine" in data
