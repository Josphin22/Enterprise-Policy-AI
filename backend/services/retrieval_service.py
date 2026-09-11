"""
Enterprise Policy AI - Centralized RAG Retrieval & Context Pipeline Service (Phase 5)
Orchestrates:
User Question -> Query Embedding -> FAISS Semantic Search -> Top-K Relevant Chunks
-> Relevance Filtering -> Context Builder -> Grounded Context (READY FOR OLLAMA IN PHASE 6)
"""

import time
import logging
from typing import Optional, Dict, Any, List, Tuple, Union
from sqlalchemy.orm import Session

from app.config import settings
from app.rag.retriever import rag_retriever, RAGRetriever
from app.rag.hybrid_retriever import hybrid_retriever, HybridRetriever
from app.rag.relevance import relevance_filter, RelevanceFilter
from app.rag.context_builder import context_builder, ContextBuilder
from app.rag.schemas import (
    CandidateChunk,
    SourceCitation,
    RAGRetrievalResponse,
    MetadataFilter,
)

logger = logging.getLogger("enterprise_rag.services.retrieval")


class RetrievalService:
    """
    Service coordinating natural language query embedding, hybrid retrieval,
    relevance score filtering, deduplication, and grounded context construction.
    Strictly prepares grounded context with zero hallucination risk for local LLMs.
    """

    def __init__(
        self,
        retriever: Optional[RAGRetriever] = None,
        hybrid_ret: Optional[HybridRetriever] = None,
        filter_layer: Optional[RelevanceFilter] = None,
        builder: Optional[ContextBuilder] = None,
    ):
        self.retriever = retriever or rag_retriever
        if hybrid_ret is not None:
            self.hybrid_retriever = hybrid_ret
        elif retriever is not None:
            self.hybrid_retriever = HybridRetriever(semantic_retriever=retriever)
        else:
            self.hybrid_retriever = hybrid_retriever
        self.filter_layer = filter_layer or relevance_filter
        self.builder = builder or context_builder

    def retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        db: Optional[Session] = None,
        document_id: Optional[str] = None,
        filters: Optional[Union[MetadataFilter, Dict[str, Any]]] = None,
        debug: Optional[bool] = False,
    ) -> RAGRetrievalResponse:
        """
        Execute full Phase 9 Hybrid RAG retrieval pipeline:
        1. Validate and normalize user question
        2. Semantic FAISS + Keyword search with RRF merging
        3. Exact number, date, currency preservation boosts
        4. Metadata filtering across both streams
        5. Relevance filtering against min_score threshold
        6. Deduplicate and format grounded context with citations [Source 1], [Source 2]
        """
        t_start = time.perf_counter()
        clean_query = self.retriever.normalize_query(query)
        logger.info(f"Retrieval pipeline invoked for query: '{clean_query[:75]}...' (doc_id={document_id})")

        # 1. Hybrid candidate retrieval (Semantic + Keyword + RRF)
        t_ret_start = time.perf_counter()
        candidates, diagnostics = self.hybrid_retriever.retrieve(
            query=clean_query,
            top_k=top_k,
            db=db,
            document_id=document_id,
            filters=filters,
            min_score=min_score,
            return_diagnostics=True,
        )
        hybrid_time_ms = round((time.perf_counter() - t_ret_start) * 1000, 2)

        # 2. Relevance threshold filtering (default 0.35)
        effective_min_score = min_score if min_score is not None else settings.RAG_MIN_SCORE
        accepted_chunks, filter_stats = self.filter_layer.filter_candidates(
            candidates=candidates,
            min_score=effective_min_score,
        )

        should_debug = bool(debug or settings.RAG_DEBUG)

        # 3. Handle low-confidence / out-of-domain queries
        if not accepted_chunks:
            total_time_ms = round((time.perf_counter() - t_start) * 1000, 2)
            debug_info = None
            if should_debug:
                debug_info = {
                    **filter_stats,
                    **diagnostics["latencies_ms"],
                    "hybrid_time_ms": hybrid_time_ms,
                    "total_time_ms": total_time_ms,
                    "diagnostics": diagnostics,
                }

            logger.warning(
                f"Insufficient context: all {len(candidates)} candidates fell below threshold {filter_stats['threshold']}."
            )

            return RAGRetrievalResponse(
                status="insufficient_context",
                query=clean_query,
                context="",
                sources=[],
                total_sources=0,
                message="No sufficiently relevant information was found in the enterprise knowledge base.",
                debug_info=debug_info,
            )

        # 4. Context construction, deduplication, and sequential citation mapping
        t_build_start = time.perf_counter()
        grounded_context, sources = self.builder.build_context(
            chunks=accepted_chunks,
            db=db,
        )
        context_build_time_ms = round((time.perf_counter() - t_build_start) * 1000, 2)

        total_time_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # 5. Diagnostic debug metadata
        debug_info = None
        if should_debug:
            debug_info = {
                **filter_stats,
                **diagnostics["latencies_ms"],
                "hybrid_time_ms": hybrid_time_ms,
                "context_build_time_ms": context_build_time_ms,
                "total_time_ms": total_time_ms,
                "context_characters": len(grounded_context),
                "diagnostics": diagnostics,
            }

        logger.info(
            f"Retrieval complete in {total_time_ms}ms: {len(sources)} sources, "
            f"{len(grounded_context)} chars grounded context."
        )

        return RAGRetrievalResponse(
            status="success",
            query=clean_query,
            context=grounded_context,
            sources=sources,
            total_sources=len(sources),
            message=None,
            debug_info=debug_info,
        )

    def filter_relevance(
        self,
        candidates: List[CandidateChunk],
        min_score: Optional[float] = None,
    ) -> Tuple[List[CandidateChunk], Dict[str, Any]]:
        """Filter candidate chunks by cosine similarity score."""
        return self.filter_layer.filter_candidates(candidates=candidates, min_score=min_score)

    def build_grounded_context(
        self,
        chunks: List[CandidateChunk],
        max_chunks: Optional[int] = None,
        max_characters: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> Tuple[str, List[SourceCitation]]:
        """Build formatted grounded context block with [Source S1] citations."""
        return self.builder.build_context(
            chunks=chunks,
            max_chunks=max_chunks,
            max_characters=max_characters,
            db=db,
        )


# Global singleton instance
retrieval_service = RetrievalService()


# Top-level module convenience functions
def retrieve_context(
    query: str,
    top_k: Optional[int] = None,
    min_score: Optional[float] = None,
    db: Optional[Session] = None,
    document_id: Optional[str] = None,
) -> RAGRetrievalResponse:
    return retrieval_service.retrieve_context(
        query=query,
        top_k=top_k,
        min_score=min_score,
        db=db,
        document_id=document_id,
    )


def build_grounded_context(
    chunks: List[CandidateChunk],
    max_chunks: Optional[int] = None,
    max_characters: Optional[int] = None,
    db: Optional[Session] = None,
) -> Tuple[str, List[SourceCitation]]:
    return retrieval_service.build_grounded_context(
        chunks=chunks, max_chunks=max_chunks, max_characters=max_characters, db=db
    )


def filter_relevance(
    candidates: List[CandidateChunk],
    min_score: Optional[float] = None,
) -> Tuple[List[CandidateChunk], Dict[str, Any]]:
    return retrieval_service.filter_relevance(candidates=candidates, min_score=min_score)
