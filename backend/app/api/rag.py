from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.rag.schemas import RAGRetrievalRequest, RAGRetrievalResponse
from app.rag.service import rag_service

router = APIRouter(prefix="/rag", tags=["RAG Retrieval"])


@router.post(
    "/retrieve",
    response_model=RAGRetrievalResponse,
    summary="RAG Context Retrieval",
    description="Embeds natural language query, performs FAISS vector search, filters by relevance threshold (min_score), deduplicates, and returns grounded context block with source citations [S1], [S2] ready for local LLM.",
)
async def retrieve_rag_context(
    request: RAGRetrievalRequest,
    db: Session = Depends(get_db),
):
    """
    Executes Phase 7 RAG retrieval engine pipeline.
    """
    return rag_service.retrieve_context(
        query=request.query,
        top_k=request.top_k,
        min_score=request.min_score,
        db=db,
    )
