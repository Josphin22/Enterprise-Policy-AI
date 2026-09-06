import time
import math
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("enterprise_rag.evaluation.performance")


class PerformanceProfiler:
    """
    Sub-millisecond latency profiler for RAG stages:
    - Embedding generation latency
    - FAISS similarity retrieval latency
    - Database query latency
    - Context construction latency
    - LLM generation latency
    - Total pipeline latency
    """

    @staticmethod
    def calculate_statistics(latencies: List[float]) -> Dict[str, float]:
        """
        Calculate Mean, Median, Min, Max, and P95 from an array of millisecond latencies.
        """
        if not latencies:
            return {
                "mean_ms": 0.0,
                "median_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p95_ms": 0.0,
                "count": 0,
            }

        sorted_vals = sorted(latencies)
        count = len(sorted_vals)
        mean_val = sum(sorted_vals) / count

        # Median
        if count % 2 == 1:
            median_val = sorted_vals[count // 2]
        else:
            median_val = (sorted_vals[(count // 2) - 1] + sorted_vals[count // 2]) / 2.0

        min_val = sorted_vals[0]
        max_val = sorted_vals[-1]

        # P95 (95th percentile)
        p95_idx = int(math.ceil(0.95 * count)) - 1
        p95_idx = max(0, min(p95_idx, count - 1))
        p95_val = sorted_vals[p95_idx]

        return {
            "mean_ms": round(mean_val, 2),
            "median_ms": round(median_val, 2),
            "min_ms": round(min_val, 2),
            "max_ms": round(max_val, 2),
            "p95_ms": round(p95_val, 2),
            "count": count,
        }

    @staticmethod
    def aggregate_performance_metrics(query_latencies: List[Dict[str, float]]) -> Dict[str, Any]:
        """
        Aggregate timing records across all evaluated queries.
        """
        retrieval_latencies = [q.get("retrieval_ms", 0.0) for q in query_latencies if "retrieval_ms" in q]
        llm_latencies = [q.get("llm_ms", 0.0) for q in query_latencies if "llm_ms" in q]
        total_latencies = [q.get("total_ms", 0.0) for q in query_latencies if "total_ms" in q]

        return {
            "retrieval": PerformanceProfiler.calculate_statistics(retrieval_latencies),
            "llm_generation": PerformanceProfiler.calculate_statistics(llm_latencies),
            "total_pipeline": PerformanceProfiler.calculate_statistics(total_latencies),
        }


performance_profiler = PerformanceProfiler()
