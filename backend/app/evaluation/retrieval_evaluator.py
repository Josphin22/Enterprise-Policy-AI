import logging
from typing import List, Dict, Any, Set
from app.evaluation.dataset import EvaluationQuestion
from app.rag.schemas import CandidateChunk

logger = logging.getLogger("enterprise_rag.evaluation.retrieval")


class RetrievalEvaluator:
    """
    Evaluates RAG retrieval engine performance on:
    - Precision@1, Precision@3, Precision@5
    - Recall@1, Recall@3, Recall@5
    - Hit Rate@1, Hit Rate@3, Hit Rate@5 (Top-1, Top-3, Top-5 accuracy)
    - Semantic Context Relevance
    """

    @staticmethod
    def evaluate_query_retrieval(
        question: EvaluationQuestion,
        retrieved_chunks: List[CandidateChunk],
        k_values: List[int] = [1, 3, 5],
    ) -> Dict[str, Any]:
        """
        Evaluate a single query's retrieved candidate chunks against expected sources.
        """
        expected_docs: Set[str] = {doc.lower().strip() for doc in question.expected_sources}
        if not expected_docs:
            # Unanswerable / out-of-domain query
            return {
                "question_id": question.id,
                "is_unanswerable": True,
                "retrieved_count": len(retrieved_chunks),
                "hit_rate_at_k": {f"hit@{k}": 0.0 for k in k_values},
                "precision_at_k": {f"p@{k}": 0.0 for k in k_values},
                "recall_at_k": {f"r@{k}": 0.0 for k in k_values},
                "context_relevance": "N/A",
                "retrieved_documents": [getattr(c, "filename", getattr(c, "document", "")) for c in retrieved_chunks],
            }

        retrieved_docs_ordered = [
            getattr(c, "filename", getattr(c, "document", "")).lower().strip() for c in retrieved_chunks
        ]

        metrics = {
            "question_id": question.id,
            "is_unanswerable": False,
            "expected_documents": list(expected_docs),
            "retrieved_documents": [getattr(c, "filename", getattr(c, "document", "")) for c in retrieved_chunks],
            "retrieved_count": len(retrieved_chunks),
            "hit_rate_at_k": {},
            "precision_at_k": {},
            "recall_at_k": {},
        }

        # Calculate Hit Rate, Precision, Recall at each K, and reciprocal rank
        first_relevant_rank = None
        reciprocal_rank = 0.0

        for idx, doc_name in enumerate(retrieved_docs_ordered, start=1):
            if doc_name in expected_docs and first_relevant_rank is None:
                first_relevant_rank = idx
                reciprocal_rank = round(1.0 / idx, 4)

        metrics["reciprocal_rank"] = reciprocal_rank
        metrics["first_relevant_rank"] = first_relevant_rank

        # Optional chunk-level matching
        expected_chunk = getattr(question, "expected_chunk", None)
        expected_chunk_idx = getattr(question, "expected_chunk_index", None)
        chunk_hit = False
        if expected_chunk or expected_chunk_idx is not None:
            for c in retrieved_chunks:
                c_id = getattr(c, "chunk_id", None)
                c_idx = getattr(c, "chunk_index", None)
                if (expected_chunk and c_id == expected_chunk) or (expected_chunk_idx is not None and c_idx == expected_chunk_idx):
                    chunk_hit = True
                    break
        metrics["chunk_hit"] = chunk_hit

        # Calculate Hit Rate, Precision, and Recall at each K
        for k in k_values:
            top_k_docs = retrieved_docs_ordered[:k]
            unique_top_k = set(top_k_docs)
            relevant_retrieved = unique_top_k.intersection(expected_docs)

            # Hit Rate @ K (1 if at least 1 expected doc is in top-K, else 0)
            hit = 1.0 if len(relevant_retrieved) > 0 else 0.0
            metrics["hit_rate_at_k"][f"hit@{k}"] = hit

            # Precision @ K (fraction of top-K chunks that belong to expected documents)
            matching_chunks_count = sum(1 for d in top_k_docs if d in expected_docs)
            p_at_k = matching_chunks_count / k if k > 0 else 0.0
            metrics["precision_at_k"][f"p@{k}"] = round(p_at_k, 4)

            # Recall @ K (fraction of expected documents retrieved in top-K)
            r_at_k = len(relevant_retrieved) / len(expected_docs) if len(expected_docs) > 0 else 0.0
            metrics["recall_at_k"][f"r@{k}"] = round(r_at_k, 4)

        # Context relevance categorization
        hit_at_5 = metrics["hit_rate_at_k"].get("hit@5", 0.0)
        p_at_5 = metrics["precision_at_k"].get("p@5", 0.0)

        if hit_at_5 == 1.0 and p_at_5 >= 0.5:
            context_relevance = "Relevant"
        elif hit_at_5 == 1.0:
            context_relevance = "Partially Relevant"
        else:
            context_relevance = "Irrelevant"

        metrics["context_relevance"] = context_relevance
        return metrics

    @staticmethod
    def aggregate_retrieval_metrics(query_eval_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate individual query metrics into dataset-wide precision, recall, hit rate, MRR, and accuracy.
        """
        answerable_evals = [r for r in query_eval_results if not r.get("is_unanswerable", False)]
        total_answerable = len(answerable_evals)

        if total_answerable == 0:
            return {
                "total_queries_evaluated": len(query_eval_results),
                "answerable_queries": 0,
                "hit_rate_1": 0.0,
                "hit_rate_3": 0.0,
                "hit_rate_5": 0.0,
                "precision_1": 0.0,
                "precision_3": 0.0,
                "precision_5": 0.0,
                "recall_1": 0.0,
                "recall_3": 0.0,
                "recall_5": 0.0,
                "mrr": 0.0,
                "mrr_at_5": 0.0,
                "context_relevance_score": 0.0,
            }

        hit_1 = sum(r["hit_rate_at_k"]["hit@1"] for r in answerable_evals) / total_answerable
        hit_3 = sum(r["hit_rate_at_k"]["hit@3"] for r in answerable_evals) / total_answerable
        hit_5 = sum(r["hit_rate_at_k"]["hit@5"] for r in answerable_evals) / total_answerable

        p_1 = sum(r["precision_at_k"]["p@1"] for r in answerable_evals) / total_answerable
        p_3 = sum(r["precision_at_k"]["p@3"] for r in answerable_evals) / total_answerable
        p_5 = sum(r["precision_at_k"]["p@5"] for r in answerable_evals) / total_answerable

        r_1 = sum(r["recall_at_k"]["r@1"] for r in answerable_evals) / total_answerable
        r_3 = sum(r["recall_at_k"]["r@3"] for r in answerable_evals) / total_answerable
        r_5 = sum(r["recall_at_k"]["r@5"] for r in answerable_evals) / total_answerable

        # Mean Reciprocal Rank (MRR)
        mrr = sum(r.get("reciprocal_rank", 0.0) for r in answerable_evals) / total_answerable
        mrr_5 = sum(
            r.get("reciprocal_rank", 0.0)
            if (r.get("first_relevant_rank") and r["first_relevant_rank"] <= 5)
            else 0.0
            for r in answerable_evals
        ) / total_answerable

        relevant_count = sum(1 for r in answerable_evals if r["context_relevance"] in ("Relevant", "Partially Relevant"))
        context_relevance_score = relevant_count / total_answerable

        return {
            "total_queries_evaluated": len(query_eval_results),
            "answerable_queries": total_answerable,
            "hit_rate_1": round(hit_1 * 100, 2),
            "hit_rate_3": round(hit_3 * 100, 2),
            "hit_rate_5": round(hit_5 * 100, 2),
            "precision_1": round(p_1, 4),
            "precision_3": round(p_3, 4),
            "precision_5": round(p_5, 4),
            "recall_1": round(r_1, 4),
            "recall_3": round(r_3, 4),
            "recall_5": round(r_5, 4),
            "mrr": round(mrr, 4),
            "mrr_at_5": round(mrr_5, 4),
            "context_relevance_score": round(context_relevance_score * 100, 2),
        }


retrieval_evaluator = RetrievalEvaluator()
