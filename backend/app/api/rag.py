import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.core.auth import get_optional_user
from app.models.user import User
from app.rag.schemas import (
    RAGRetrievalRequest,
    RAGRetrievalResponse,
    SearchDiagnosticsResponse,
)
from app.rag.service import rag_service
from app.rag.hybrid_retriever import hybrid_retriever

router = APIRouter(prefix="/rag", tags=["RAG Retrieval"])


@router.post(
    "/retrieve",
    response_model=RAGRetrievalResponse,
    summary="Hybrid RAG Context Retrieval",
    description="Executes Phase 9 Hybrid Retrieval (FAISS semantic + full-text keyword search, RRF merging, metadata filtering, number/date preservation) and returns grounded context block with citations [S1], [S2].",
)
async def retrieve_rag_context(
    request: RAGRetrievalRequest,
    db: Session = Depends(get_db),
):
    """
    Executes Phase 9 Hybrid RAG retrieval engine pipeline.
    """
    return rag_service.retrieve_context(
        query=request.query,
        top_k=request.top_k,
        min_score=request.min_score,
        db=db,
        document_id=request.document_id,
        filters=request.filters,
        debug=request.debug,
    )


@router.post(
    "/debug-search",
    response_model=SearchDiagnosticsResponse,
    summary="Internal Retrieval Diagnostics",
    description="Internal developer and administrator search diagnostic endpoint exposing semantic, keyword, merged, and final candidate chunks with latencies and exact term matches.",
)
async def debug_retrieval_search(
    request: RAGRetrievalRequest,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Developer / Admin diagnostics endpoint:
    Returns query, semantic candidates, keyword candidates, merged candidates,
    final candidates, component latencies, and entity extractions.
    Does not expose debug details to normal unprivileged users in production.
    """
    is_admin = current_user is not None and getattr(current_user, "role", None) == "ADMIN"
    if not (settings.DEBUG or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Retrieval diagnostics are restricted to administrators.",
        )

    clean_query = hybrid_retriever.semantic_retriever.normalize_query(request.query)

    _, diagnostics = hybrid_retriever.retrieve(
        query=clean_query,
        top_k=request.top_k,
        db=db,
        document_id=request.document_id,
        filters=request.filters,
        min_score=request.min_score,
        return_diagnostics=True,
    )

    return SearchDiagnosticsResponse(
        query=request.query,
        normalized_query=clean_query,
        detected_numbers=diagnostics.get("detected_numbers", []),
        detected_dates=diagnostics.get("detected_dates", []),
        detected_keywords=diagnostics.get("detected_keywords", []),
        semantic_count=diagnostics.get("semantic_count", 0),
        keyword_count=diagnostics.get("keyword_count", 0),
        merged_count=diagnostics.get("merged_count", 0),
        final_count=diagnostics.get("final_count", 0),
        latencies_ms=diagnostics.get("latencies_ms", {}),
        semantic_candidates=diagnostics.get("semantic_candidates", []),
        keyword_candidates=diagnostics.get("keyword_candidates", []),
        merged_candidates=diagnostics.get("semantic_candidates", []) + diagnostics.get("keyword_candidates", []),
        final_candidates=diagnostics.get("final_candidates", []),
    )
