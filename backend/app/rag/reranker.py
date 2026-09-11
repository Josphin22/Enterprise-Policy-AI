"""
Enterprise Policy AI - Optional Reranker Service (Phase 9)
Provides optional CrossEncoder / Neural Reranking on candidate chunks.
Configurable via ENABLE_RERANKING=false (default). Gracefully falls back
to initial ranking if disabled or if model loading fails.
"""

import time
import logging
from typing import List, Optional
from app.config import settings
from app.rag.schemas import CandidateChunk

logger = logging.getLogger("enterprise_rag.rag.reranker")


class RerankerService:
    """
    Reranks candidate chunks using a neural cross-encoder model
    when ENABLE_RERANKING is enabled.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or "cross-encoder/ms-marco-MiniLM-L-6-v2"
        self._model = None
        self._model_loaded = False

    @property
    def is_enabled(self) -> bool:
        return bool(getattr(settings, "ENABLE_RERANKING", False))

    def _get_model(self):
        """Lazy loader for CrossEncoder."""
        if not self._model_loaded and self.is_enabled:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading reranker model: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                self._model_loaded = True
            except Exception as exc:
                logger.warning(
                    f"Could not load CrossEncoder '{self.model_name}': {exc}. "
                    "Falling back to original hybrid ranking."
                )
                self._model = None
                self._model_loaded = True
        return self._model

    def rerank(
        self,
        query: str,
        candidates: List[CandidateChunk],
        top_k: int = 5,
    ) -> List[CandidateChunk]:
        """
        Rerank top-N candidates down to top_k.
        If ENABLE_RERANKING is False or model is unavailable, passes candidates through.
        """
        if not candidates or not query or not self.is_enabled:
            return candidates[:top_k]

        t_start = time.perf_counter()
        model = self._get_model()

        if model is None:
            # Graceful fallback: return top_k candidates as-is
            return candidates[:top_k]

        try:
            pairs = [[query, c.text] for c in candidates]
            scores = model.predict(pairs)

            # Assign reranked scores and sort
            reranked: List[CandidateChunk] = []
            for c, sc in zip(candidates, scores):
                reranked_score = float(sc)
                # Map to [0.0, 1.0] sigmoid/min-max or normalized float
                norm_score = max(0.0, min(1.0, (reranked_score + 10.0) / 20.0))
                c_copy = c.model_copy()
                c_copy.score = round(norm_score, 4)
                c_copy.match_reasons.append("cross_encoder_reranked")
                reranked.append(c_copy)

            reranked.sort(key=lambda x: x.score, reverse=True)
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.info(f"Reranking complete in {elapsed_ms}ms ({len(candidates)} -> {min(top_k, len(reranked))})")
            return reranked[:top_k]

        except Exception as exc:
            logger.warning(f"Reranking execution failed: {exc}. Falling back to original ranking.")
            return candidates[:top_k]


# Global singleton instance
reranker_service = RerankerService()
