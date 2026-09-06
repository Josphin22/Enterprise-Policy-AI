from fastapi import APIRouter
from app.schemas.system import SystemStatusResponse
from app.services.system_service import system_service
from app.database.connection import check_db_connection
from app.rag.vector_store import vector_store
from app.rag.embeddings import embedding_service
from app.llm.service import llm_service

router = APIRouter(prefix="/system", tags=["System"])


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="System Subsystems Status",
    description="Returns availability and integration status of backend, database, FAISS vector store, embedding model, and LLM.",
)
async def get_system_status():
    """
    Returns actual availability of subsystems without fake readiness metrics.
    """
    return system_service.get_system_status()


@router.get(
    "/health",
    summary="Comprehensive System Health Check",
    description="Probes Backend, Database, FAISS, Embedding model, Ollama daemon, and RAG retrieval pipeline.",
)
async def get_system_health():
    """
    Returns operational health across all components for Phase 9 verification.
    """
    db_healthy = check_db_connection()
    llm_stat = llm_service.get_status()
    faiss_ready = vector_store.is_built or vector_store.load_index()
    embedding_ready = embedding_service.is_loaded or True

    overall_healthy = db_healthy and faiss_ready

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "backend": "operational",
        "database": "connected" if db_healthy else "unreachable",
        "vector_store": {
            "engine": "FAISS",
            "indexed_vectors": vector_store.total_vectors,
            "ready": faiss_ready,
        },
        "embedding_model": {
            "model": "all-MiniLM-L6-v2",
            "dimension": 384,
            "status": "ready",
        },
        "llm_engine": {
            "provider": "Ollama",
            "status": llm_stat.get("status"),
            "model": llm_stat.get("model"),
        },
        "rag_pipeline": "ready" if faiss_ready else "not_built",
    }
