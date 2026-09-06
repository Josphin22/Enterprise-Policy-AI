import time
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.config import settings
from app.rag.retriever import rag_retriever, RAGRetriever
from app.rag.relevance import relevance_filter, RelevanceFilter
from app.rag.context_builder import context_builder, ContextBuilder
from app.rag.schemas import RAGRetrievalResponse, SourceCitation
from app.llm.service import llm_service, LLMService

logger = logging.getLogger("enterprise_rag.rag.service")


class RAGService:
    """
    Main RAG orchestration service coordinating query embedding, FAISS retrieval,
    relevance threshold filtering, deduplication, context construction, and local LLM generation.
    """

    def __init__(
        self,
        retriever: Optional[RAGRetriever] = None,
        filter_layer: Optional[RelevanceFilter] = None,
        builder: Optional[ContextBuilder] = None,
        llm_svc: Optional[LLMService] = None,
    ):
        self.retriever = retriever or rag_retriever
        self.filter_layer = filter_layer or relevance_filter
        self.builder = builder or context_builder
        self.llm_service = llm_svc or llm_service

    def retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        db: Optional[Session] = None,
    ) -> RAGRetrievalResponse:
        """
        Execute full RAG retrieval pipeline and construct grounded context for local LLM.
        """
        t_start = time.perf_counter()
        logger.info(f"RAG query received: '{query[:80]}'")

        # 1. FAISS candidate retrieval
        t_faiss_start = time.perf_counter()
        candidates = self.retriever.retrieve(query=query, top_k=top_k, db=db)
        faiss_time_ms = round((time.perf_counter() - t_faiss_start) * 1000, 2)

        # 2. Relevance threshold filtering
        accepted_chunks, filter_stats = self.filter_layer.filter_candidates(
            candidates=candidates,
            min_score=min_score,
        )

        # 3. Handle low-confidence / insufficient context
        if not accepted_chunks:
            total_time_ms = round((time.perf_counter() - t_start) * 1000, 2)
            debug_info = None
            if settings.RAG_DEBUG:
                debug_info = {
                    **filter_stats,
                    "faiss_time_ms": faiss_time_ms,
                    "total_time_ms": total_time_ms,
                }

            logger.warning(
                f"Insufficient context for query '{query[:50]}'. "
                f"All {len(candidates)} candidates fell below threshold {filter_stats['threshold']}."
            )

            return RAGRetrievalResponse(
                status="insufficient_context",
                query=query.strip(),
                context="",
                sources=[],
                total_sources=0,
                message="No sufficiently relevant information was found in the enterprise knowledge base.",
                debug_info=debug_info,
            )

        # 4. Context construction, deduplication, and citation mapping
        t_build_start = time.perf_counter()
        grounded_context, sources = self.builder.build_context(
            chunks=accepted_chunks,
            db=db,
        )
        context_build_time_ms = round((time.perf_counter() - t_build_start) * 1000, 2)

        total_time_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # 5. Debug metadata
        debug_info = None
        if settings.RAG_DEBUG:
            debug_info = {
                **filter_stats,
                "faiss_time_ms": faiss_time_ms,
                "context_build_time_ms": context_build_time_ms,
                "total_time_ms": total_time_ms,
                "context_characters": len(grounded_context),
            }

        logger.info(
            f"RAG retrieval succeeded in {total_time_ms}ms ({len(sources)} sources, "
            f"{len(grounded_context)} chars context)."
        )

        return RAGRetrievalResponse(
            status="success",
            query=query.strip(),
            context=grounded_context,
            sources=sources,
            total_sources=len(sources),
            message=None,
            debug_info=debug_info,
        )

    def generate_rag_answer(
        self,
        query: str,
        top_k: Optional[int] = None,
        min_score: Optional[float] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Complete Phase 8 RAG pipeline:
        Retrieves grounded context -> validates sufficiency -> generates LLM answer -> parses citations.
        """
        t_start = time.perf_counter()

        # Step 1 & 2: RAG retrieval & relevance filtering
        retrieval_res = self.retrieve_context(
            query=query,
            top_k=top_k,
            min_score=min_score,
            db=db,
        )
        retrieval_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # Step 3: No-Context Safety Check (Refuse immediately without calling LLM)
        if retrieval_res.status == "insufficient_context":
            logger.info("RAG retrieval yielded insufficient context. Refusing to generate ungrounded answer.")
            return {
                "success": True,
                "status": "insufficient_context",
                "query": query.strip(),
                "answer": "I could not find sufficient information in the provided enterprise documents to answer this question.",
                "context": "",
                "sources": [],
                "total_sources": 0,
                "retrieval_duration_ms": retrieval_duration_ms,
                "llm_duration_ms": 0.0,
                "total_duration_ms": retrieval_duration_ms,
                "message": "No sufficiently relevant information was found in the enterprise knowledge base.",
            }

        # Step 4: Invoke Local Ollama LLM
        t_llm_start = time.perf_counter()
        llm_gen = self.llm_service.generate_grounded_answer(
            query=query,
            context=retrieval_res.context,
            sources=retrieval_res.sources,
        )
        llm_duration_ms = round((time.perf_counter() - t_llm_start) * 1000, 2)
        total_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

        if not llm_gen.get("success"):
            return {
                "success": False,
                "status": llm_gen.get("status", "generation_error"),
                "query": query.strip(),
                "answer": None,
                "context": retrieval_res.context,
                "sources": [s.model_dump() for s in retrieval_res.sources],
                "total_sources": len(retrieval_res.sources),
                "retrieval_duration_ms": retrieval_duration_ms,
                "llm_duration_ms": llm_duration_ms,
                "total_duration_ms": total_duration_ms,
                "message": llm_gen.get("message", "Local LLM answer generation failed."),
            }

        serialized_sources = [
            s.model_dump() if isinstance(s, SourceCitation) else s
            for s in llm_gen.get("sources", retrieval_res.sources)
        ]

        logger.info(
            f"RAG answer generated successfully: retrieval={retrieval_duration_ms}ms, "
            f"llm={llm_duration_ms}ms, total={total_duration_ms}ms"
        )

        return {
            "success": True,
            "status": "success",
            "query": query.strip(),
            "answer": llm_gen.get("answer", ""),
            "context": retrieval_res.context,
            "sources": serialized_sources,
            "total_sources": len(serialized_sources),
            "retrieval_duration_ms": retrieval_duration_ms,
            "llm_duration_ms": llm_duration_ms,
            "total_duration_ms": total_duration_ms,
            "message": None,
        }


# Global singleton instance
rag_service = RAGService()
