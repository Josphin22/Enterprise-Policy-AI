import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("enterprise_rag.evaluation.metrics")

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation_results"


class MetricsAggregator:
    """
    Coordinates aggregation of retrieval, answer generation, hallucination, and performance metrics.
    Exports JSON and CSV reports into backend/evaluation_results/.
    """

    @staticmethod
    def build_category_breakdown(evaluation_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Group evaluation results by category (Direct, Paraphrased, Multi-doc, etc.)
        and calculate accuracy per category.
        """
        categories: Dict[str, List[Dict[str, Any]]] = {}
        for rec in evaluation_records:
            cat = rec.get("category", "other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(rec)

        breakdown = {}
        for cat, items in categories.items():
            total = len(items)
            passed = sum(1 for it in items if it.get("answer_passed", False))
            breakdown[cat] = {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "accuracy": round((passed / total * 100), 2) if total > 0 else 0.0,
            }

        return breakdown

    @staticmethod
    def build_failed_cases_table(evaluation_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract all failed test cases with their failure classification and diagnostics.
        """
        failed_cases = []
        for rec in evaluation_records:
            if not rec.get("answer_passed", False) or not rec.get("source_passed", False):
                failed_cases.append({
                    "question_id": rec.get("question_id"),
                    "question": rec.get("question"),
                    "category": rec.get("category"),
                    "expected_answer": rec.get("expected_answer"),
                    "actual_answer": rec.get("actual_answer"),
                    "expected_source": rec.get("expected_sources"),
                    "actual_source": [s.get("document") for s in rec.get("actual_sources", [])],
                    "failure_type": rec.get("failure_type") or "General Failure",
                    "latency_ms": rec.get("latency_ms", 0.0),
                })
        return failed_cases

    @staticmethod
    def export_reports(
        summary: Dict[str, Any],
        full_records: List[Dict[str, Any]],
        retrieval_metrics: Dict[str, Any],
        answer_metrics: Dict[str, Any],
        performance_metrics: Dict[str, Any],
        output_dir: Optional[Path] = None,
    ) -> Dict[str, str]:
        """
        Save all evaluation metrics as structured JSON files and CSV table.
        """
        target_dir = output_dir or RESULTS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        exported_paths = {}

        # 1. evaluation_summary.json
        summary_path = target_dir / "evaluation_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        exported_paths["summary_json"] = str(summary_path)

        # 2. evaluation_results.json
        results_path = target_dir / "evaluation_results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(full_records, f, indent=2)
        exported_paths["results_json"] = str(results_path)

        # 3. retrieval_metrics.json
        retrieval_path = target_dir / "retrieval_metrics.json"
        with open(retrieval_path, "w", encoding="utf-8") as f:
            json.dump(retrieval_metrics, f, indent=2)
        exported_paths["retrieval_json"] = str(retrieval_path)

        # 4. answer_metrics.json
        answer_path = target_dir / "answer_metrics.json"
        with open(answer_path, "w", encoding="utf-8") as f:
            json.dump(answer_metrics, f, indent=2)
        exported_paths["answer_json"] = str(answer_path)

        # 5. performance_metrics.json
        perf_path = target_dir / "performance_metrics.json"
        with open(perf_path, "w", encoding="utf-8") as f:
            json.dump(performance_metrics, f, indent=2)
        exported_paths["performance_json"] = str(perf_path)

        # 6. evaluation_results.csv
        csv_path = target_dir / "evaluation_results.csv"
        fieldnames = [
            "Question ID",
            "Question",
            "Category",
            "Expected Answer",
            "Actual Answer",
            "Expected Source",
            "Actual Source",
            "Retrieval Pass",
            "Answer Pass",
            "Source Pass",
            "Faithfulness",
            "Refusal Correct",
            "Latency (ms)",
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for rec in full_records:
                writer.writerow({
                    "Question ID": rec.get("question_id"),
                    "Question": rec.get("question"),
                    "Category": rec.get("category"),
                    "Expected Answer": rec.get("expected_answer"),
                    "Actual Answer": rec.get("actual_answer"),
                    "Expected Source": ", ".join(rec.get("expected_sources", [])),
                    "Actual Source": ", ".join([s.get("document", "") for s in rec.get("actual_sources", [])]),
                    "Retrieval Pass": "PASS" if rec.get("retrieval_passed") else "FAIL",
                    "Answer Pass": "PASS" if rec.get("answer_passed") else "FAIL",
                    "Source Pass": "PASS" if rec.get("source_passed") else "FAIL",
                    "Faithfulness": rec.get("faithfulness_classification", "N/A"),
                    "Refusal Correct": "YES" if rec.get("refusal_correct") else ("N/A" if rec.get("answerable") else "NO"),
                    "Latency (ms)": round(rec.get("latency_ms", 0.0), 1),
                })
        exported_paths["csv"] = str(csv_path)

        logger.info(f"Successfully exported evaluation reports to {target_dir}")
        return exported_paths


metrics_aggregator = MetricsAggregator()
