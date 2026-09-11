import time
import logging
from typing import Optional, Dict, Any, List, Union
from sqlalchemy.orm import Session

from app.config import settings
from app.rag.retriever import rag_retriever, RAGRetriever
from app.rag.hybrid_retriever import hybrid_retriever, HybridRetriever
from app.rag.relevance import relevance_filter, RelevanceFilter
from app.rag.context_builder import context_builder, ContextBuilder
from app.rag.schemas import RAGRetrievalResponse, SourceCitation, MetadataFilter
from app.llm.service import llm_service, LLMService

logger = logging.getLogger("enterprise_rag.rag.service")


class RAGService:
    """
    Main RAG orchestration service coordinating query embedding, hybrid retrieval,
    relevance threshold filtering, deduplication, context construction, and local LLM generation.
    """

    def __init__(
        self,
        retriever: Optional[RAGRetriever] = None,
        hybrid_ret: Optional[HybridRetriever] = None,
        filter_layer: Optional[RelevanceFilter] = None,
        builder: Optional[ContextBuilder] = None,
        llm_svc: Optional[LLMService] = None,
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
        self.llm_service = llm_svc or llm_service

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
        Execute full Phase 9 Hybrid RAG retrieval pipeline and construct grounded context for local LLM.
        Applies semantic + keyword hybrid search, RRF merging, metadata filtering, and number/date boosts.
        """
        t_start = time.perf_counter()
        logger.info(f"RAG query received: '{query[:80]}' (doc_id={document_id})")

        # 1. Hybrid candidate retrieval (Semantic + Keyword + RRF)
        t_ret_start = time.perf_counter()
        candidates, diagnostics = self.hybrid_retriever.retrieve(
            query=query,
            top_k=top_k,
            db=db,
            document_id=document_id,
            filters=filters,
            min_score=min_score,
            return_diagnostics=True,
        )
        hybrid_time_ms = round((time.perf_counter() - t_ret_start) * 1000, 2)
        sem_time_ms = diagnostics.get("latencies_ms", {}).get("semantic_time_ms", 0.0)

        # 2. Relevance threshold filtering
        accepted_chunks, filter_stats = self.filter_layer.filter_candidates(
            candidates=candidates,
            min_score=min_score,
        )

        should_debug = bool(debug or settings.RAG_DEBUG)

        # 3. Handle low-confidence / insufficient context
        if not accepted_chunks:
            total_time_ms = round((time.perf_counter() - t_start) * 1000, 2)
            debug_info = None
            if should_debug:
                debug_info = {
                    **filter_stats,
                    "faiss_time_ms": sem_time_ms,
                    **diagnostics["latencies_ms"],
                    "hybrid_time_ms": hybrid_time_ms,
                    "total_time_ms": total_time_ms,
                    "diagnostics": diagnostics,
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
        if should_debug:
            debug_info = {
                **filter_stats,
                "faiss_time_ms": sem_time_ms,
                **diagnostics["latencies_ms"],
                "hybrid_time_ms": hybrid_time_ms,
                "context_build_time_ms": context_build_time_ms,
                "total_time_ms": total_time_ms,
                "context_characters": len(grounded_context),
                "diagnostics": diagnostics,
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
        document_id: Optional[str] = None,
        original_query: Optional[str] = None,
        filters: Optional[Union[MetadataFilter, Dict[str, Any]]] = None,
        allowed_document_ids: Optional[List[str]] = None,
        language: Optional[str] = "en",
    ) -> Dict[str, Any]:
        """
        Complete Phase 6 & 7 RAG pipeline:
        Retrieves grounded context using retrieval query -> validates sufficiency ->
        generates LLM answer using original user question -> parses citations.
        Enforces RBAC fine-grained document access permissions before retrieval.
        """
        t_start = time.perf_counter()
        prompt_query = original_query if original_query is not None else query

        # Prepare active filters
        active_filters = filters or {}
        if isinstance(active_filters, dict):
            active_filters = active_filters.copy()
            if allowed_document_ids is not None:
                active_filters["allowed_document_ids"] = allowed_document_ids
        elif isinstance(active_filters, MetadataFilter):
            if allowed_document_ids is not None:
                active_filters.allowed_document_ids = allowed_document_ids

        # Step 1 & 2: RAG retrieval & relevance filtering
        retrieval_res = self.retrieve_context(
            query=query,
            top_k=top_k,
            min_score=min_score,
            db=db,
            document_id=document_id,
            filters=active_filters,
        )
        retrieval_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # Step 3: No-Context Safety Check (Refuse immediately without calling LLM)
        if retrieval_res.status == "insufficient_context":
            logger.info("RAG retrieval yielded insufficient context. Refusing to generate ungrounded answer.")
            return {
                "success": True,
                "status": "insufficient_context",
                "query": prompt_query.strip(),
                "retrieval_query": query.strip(),
                "answer": "I couldn't find that information in the uploaded documents. I could not find sufficient information in the provided enterprise documents to answer this question.",
                "context": "",
                "sources": [],
                "total_sources": 0,
                "retrieval_duration_ms": retrieval_duration_ms,
                "llm_duration_ms": 0.0,
                "total_duration_ms": retrieval_duration_ms,
                "guardrail_status": "NO_ANSWER_REFUSAL",
                "grounding_warning": False,
                "grounding_classification": "UNSUPPORTED",
                "confidence": "None",
                "language": language or "en",
                "message": "No sufficiently relevant information was found in the enterprise knowledge base.",
            }

        # Step 4: Invoke Local Ollama LLM with original user question
        t_llm_start = time.perf_counter()
        llm_gen = self.llm_service.generate_grounded_answer(
            query=prompt_query,
            context=retrieval_res.context,
            sources=retrieval_res.sources,
            language=language,
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
                "guardrail_status": "ERROR",
                "grounding_warning": True,
                "grounding_classification": "UNSUPPORTED",
                "confidence": "None",
                "language": language or "en",
                "message": llm_gen.get("message", "Local LLM answer generation failed."),
            }

        raw_answer = llm_gen.get("answer", "")
        raw_sources = llm_gen.get("sources", retrieval_res.sources)

        # Step 5: Post-Generation Guardrails Check (Sensitive data scrub, length limit, citation verify, grounding warning)
        from app.rag.guardrails import guardrails_service
        guardrail_res = guardrails_service.apply_all_guardrails(
            answer=raw_answer,
            retrieved_context=retrieval_res.context,
            retrieved_sources=raw_sources,
            has_retrieval_chunks=len(retrieval_res.sources) > 0,
        )

        final_answer = guardrail_res["answer"]
        final_sources = guardrail_res["sources"]

        serialized_sources = [
            s.model_dump() if isinstance(s, SourceCitation) else s
            for s in final_sources
        ]

        # Calculate confidence based on top retrieval score and grounding
        top_score = 0.0
        if serialized_sources and len(serialized_sources) > 0:
            top_score = serialized_sources[0].get("score", 0.0)

        if guardrail_res.get("grounding_warning"):
            confidence = "Low"
        elif top_score >= 0.60:
            confidence = "High"
        elif top_score >= 0.40:
            confidence = "Medium"
        else:
            confidence = "Low"

        logger.info(
            f"RAG answer generated successfully: retrieval={retrieval_duration_ms}ms, "
            f"llm={llm_duration_ms}ms, total={total_duration_ms}ms, guardrail={guardrail_res['guardrail_status']}"
        )

        return {
            "success": True,
            "status": "success",
            "query": query.strip(),
            "answer": final_answer,
            "context": retrieval_res.context,
            "sources": serialized_sources,
            "total_sources": len(serialized_sources),
            "retrieval_duration_ms": retrieval_duration_ms,
            "llm_duration_ms": llm_duration_ms,
            "total_duration_ms": total_duration_ms,
            "guardrail_status": guardrail_res["guardrail_status"],
            "grounding_warning": guardrail_res["grounding_warning"],
            "grounding_classification": guardrail_res.get("grounding_classification", "SUPPORTED"),
            "confidence": confidence,
            "language": language or "en",
            "sensitive_data_redacted": guardrail_res["sensitive_data_redacted"],
            "truncated": guardrail_res["truncated"],
            "message": None,
        }


# Global singleton instance
rag_service = RAGService()
