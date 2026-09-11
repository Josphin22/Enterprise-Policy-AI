from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import JSONResponse
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
    description="Retrieve live counts of PostgreSQL/SQLite documents, chunks, and FAISS vectors.",
)
async def get_knowledge_base_status(db: Session = Depends(get_db)):
    """
    Returns authentic knowledge base metrics including FAISS index status, dimensions, and vector count.
    """
    return system_service.get_knowledge_base_status(db)


@router.post(
    "/rebuild",
    response_model=KnowledgeBaseBuildResponse,
    summary="Rebuild FAISS Vector Index",
    description="Completely rebuild the FAISS index from current database chunks without duplicating vectors.",
)
async def rebuild_knowledge_base(db: Session = Depends(get_db)):
    """
    Triggers local embedding pipeline and atomically persists the resulting FAISS index to disk (Part 26).
    """
    result = rag_pipeline.build_knowledge_base(db)

    # Concurrency check (Part 34)
    if result.get("status") == "in_progress":
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "status": "in_progress",
                "message": "Build already in progress.",
                "documents": result.get("documents", 0),
                "chunks": result.get("chunks", 0),
                "vectors": result.get("vectors", 0),
                "dimension": result.get("dimension", 384),
            },
        )

    return KnowledgeBaseBuildResponse(
        success=result["success"],
        status=result["status"],
        documents=result.get("documents", 0),
        chunks=result.get("chunks", 0),
        vectors=result.get("vectors", 0),
        dimension=result.get("dimension", 384),
        embedding_model=result.get("embedding_model"),
        embedding_dimension=result.get("embedding_dimension", 384),
        message=result["message"],
    )


@router.post(
    "/build",
    response_model=KnowledgeBaseBuildResponse,
    summary="Build FAISS Vector Index (Alias)",
    description="Alias for /rebuild to maintain backward compatibility.",
)
async def build_knowledge_base(db: Session = Depends(get_db)):
    """Alias for /rebuild endpoint."""
    return await rebuild_knowledge_base(db=db)


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
    Returns HTTP 409 if knowledge base has not been built yet (Part 29).
    """
    try:
        min_score = request.min_score if request.min_score is not None else 0.35
        result = rag_pipeline.search_knowledge_base(
            query=request.query,
            top_k=request.top_k,
            min_score=min_score,
            db=db,
        )
        return KnowledgeBaseSearchResponse(
            query=result["query"],
            results=result["results"],
            total_matches=result["total_matches"],
        )
    except HTTPException as http_exc:
        if http_exc.status_code == status.HTTP_409_CONFLICT:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"error": "KNOWLEDGE_BASE_NOT_BUILT", "detail": "KNOWLEDGE_BASE_NOT_BUILT"},
            )
        raise http_exc
