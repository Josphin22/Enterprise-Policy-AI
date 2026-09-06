import logging
from typing import List, Tuple, Dict, Any, Optional
from app.config import settings
from app.rag.schemas import CandidateChunk

logger = logging.getLogger("enterprise_rag.rag.relevance")


class RelevanceFilter:
    """
    Relevance filtering layer for RAG retrieval.
    Evaluates candidate cosine similarity scores against a configurable threshold,
    rejecting noisy or irrelevant document chunks to prevent LLM hallucinations.
    """

    def __init__(self, default_min_score: Optional[float] = None):
        self.default_min_score = default_min_score or settings.RAG_MIN_SCORE

    def filter_candidates(
        self,
        candidates: List[CandidateChunk],
        min_score: Optional[float] = None,
    ) -> Tuple[List[CandidateChunk], Dict[str, Any]]:
        """
        Filter candidate chunks by minimum cosine similarity threshold.
        Returns accepted chunks sorted by score (descending) and diagnostic stats.
        """
        threshold = min_score if min_score is not None else self.default_min_score
        accepted: List[CandidateChunk] = []
        rejected: List[CandidateChunk] = []

        for chunk in candidates:
            if chunk.score >= threshold:
                accepted.append(chunk)
            else:
                rejected.append(chunk)

        # Ensure descending sort by relevance score
        accepted.sort(key=lambda c: c.score, reverse=True)

        stats = {
            "candidates": len(candidates),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "threshold": threshold,
        }

        logger.info(
            f"Relevance filter: {len(accepted)} accepted, {len(rejected)} rejected "
            f"(threshold={threshold:.2f})"
        )

        return accepted, stats


# Global singleton instance
relevance_filter = RelevanceFilter()
