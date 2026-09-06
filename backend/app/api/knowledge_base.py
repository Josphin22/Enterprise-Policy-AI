from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.system import (
    KnowledgeBaseStatusResponse,
    KnowledgeBaseBuildResponse,
    KnowledgeBaseSearchRequest,
    KnowledgeBaseSearchResponse,
)
from app.services.system_service import system_service
from app.rag.pipeline import rag_pipeline

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])


@router.get(
    "/status",
    response_model=KnowledgeBaseStatusResponse,
    summary="Get Knowledge Base Vector Status",
    description="Retrieve live counts of PostgreSQL documents, chunks, and FAISS vectors.",
)
async def get_knowledge_base_status(db: Session = Depends(get_db)):
    """
    Returns authentic knowledge base metrics including FAISS index status, dimensions, and vector count.
    """
    return system_service.get_knowledge_base_status(db)


@router.post(
    "/build",
    response_model=KnowledgeBaseBuildResponse,
    summary="Build / Rebuild FAISS Vector Index",
    description="Extract all processed PostgreSQL chunks, generate SentenceTransformers embeddings, and build the FAISS index.",
)
async def build_knowledge_base(db: Session = Depends(get_db)):
    """
    Triggers Phase 6 embedding pipeline and saves the resulting FAISS index to disk.
    """
    result = rag_pipeline.build_knowledge_base(db)
    return KnowledgeBaseBuildResponse(
        success=result["success"],
        status=result["status"],
        documents=result.get("documents", 0),
        chunks=result.get("chunks", 0),
        vectors=result.get("vectors", 0),
        embedding_model=result.get("embedding_model"),
        embedding_dimension=result.get("embedding_dimension"),
        message=result["message"],
    )


@router.post(
    "/search",
    response_model=KnowledgeBaseSearchResponse,
    summary="Semantic Vector Search",
    description="Embed a natural language query with SentenceTransformers and retrieve top-K most similar document chunks from FAISS.",
)
async def search_knowledge_base(
    request: KnowledgeBaseSearchRequest,
    db: Session = Depends(get_db),
):
    """
    Performs cosine similarity search against the persistent local FAISS vector store.
    """
    result = rag_pipeline.search_knowledge_base(
        query=request.query,
        top_k=request.top_k,
        db=db,
    )
    return KnowledgeBaseSearchResponse(
        query=result["query"],
        results=result["results"],
        total_matches=result["total_matches"],
    )
