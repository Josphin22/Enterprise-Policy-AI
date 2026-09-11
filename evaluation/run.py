"""
Evaluation Runner CLI for Enterprise Policy AI (Phase 12)
Supports:
    python -m evaluation.run
    python backend/evaluation/run.py

Outputs empirical evaluation metrics across the dataset:
    Questions: <N>
    Recall@1: <value>
    Recall@3: <value>
    Recall@5: <value>
    MRR: <value>
    Grounded answers: <value>
    Citation accuracy: <value>
    No-answer rate: <value>
"""

import sys
import os
from pathlib import Path

# Ensure root and backend paths are in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent if CURRENT_DIR.name == "evaluation" else CURRENT_DIR.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

for p in [str(PROJECT_ROOT), str(BACKEND_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app.evaluation.runner import EvaluationRunner


def main():
    runner = EvaluationRunner()
    results = runner.run_evaluation()
    summary = results["summary"]
    
    ret_metrics = summary.get("retrieval_metrics", {})
    ans_metrics = summary.get("answer_metrics", {})
    halluc_metrics = summary.get("hallucination_metrics", {})
    dataset_info = summary.get("dataset_info", {})
    
    total_q = dataset_info.get("total_questions", 0)
    unanswerable_q = dataset_info.get("unanswerable_questions", 0)
    no_answer_rate = round((unanswerable_q / total_q) * 100, 2) if total_q > 0 else 0.0

    print("\n" + "=" * 55)
    print("      PHASE 12 — ENTERPRISE RAG EVALUATION REPORT")
    print("=" * 55)
    print(f"Questions: {total_q}")
    print(f"Recall@1: {ret_metrics.get('recall_at_1', 0.0)}")
    print(f"Recall@3: {ret_metrics.get('recall_at_3', 0.0)}")
    print(f"Recall@5: {ret_metrics.get('recall_at_5', 0.0)}")
    print(f"MRR: {ret_metrics.get('mrr', 0.0)}")
    print(f"Grounded answers: {halluc_metrics.get('faithfulness_rate', 0.0)}%")
    print(f"Citation accuracy: {ans_metrics.get('source_accuracy', 0.0)}%")
    print(f"No-answer rate: {no_answer_rate}%")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
