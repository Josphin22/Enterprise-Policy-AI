import logging
from fastapi import APIRouter
from app.schemas.system import HealthResponse
from app.database.connection import check_db_connection
from app.rag.vector_store import vector_store
from app.llm.ollama_client import ollama_client
from app.config import settings

logger = logging.getLogger("enterprise_rag.health")
router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health Check",
    description="Actively probes PostgreSQL/SQLite database connection, FAISS vector index readiness, and local Ollama daemon status.",
)
async def get_health():
    """
    Returns live operational status of all core dependencies:
    - database: connected / unreachable
    - faiss: ready / not_built
    - ollama: available / unavailable
    - status: healthy (if all OK) / degraded
    """
    # 1. Probe database
    db_connected = check_db_connection()
    db_status = "connected" if db_connected else "unreachable"

    # 2. Probe FAISS vector index
    faiss_ready = vector_store.is_built or vector_store.load()
    faiss_status = "ready" if faiss_ready else "not_built"

    # 3. Probe Ollama daemon and model
    ollama_conn = ollama_client.check_connection()
    ollama_model_ready = (
        ollama_client.check_model_available(settings.OLLAMA_MODEL)
        if ollama_conn
        else False
    )
    ollama_available = ollama_conn and ollama_model_ready
    ollama_status = "available" if ollama_available else "unavailable"

    # Determine overall status
    is_overall_healthy = db_connected and faiss_ready and ollama_available
    overall_status = "healthy" if is_overall_healthy else "degraded"

    return HealthResponse(
        status=overall_status,
        database=db_status,
        faiss=faiss_status,
        ollama=ollama_status,
        service="Enterprise Policy RAG",
    )


@router.get(
    "/health/ollama",
    summary="Ollama Health Check",
    description="Check whether the local Ollama daemon is reachable and whether the configured model exists.",
)
async def get_ollama_health():
    """
    Returns Ollama health and model status:
    {
      "available": true,
      "model": "llama3.2:3b"
    }
    or if unavailable:
    {
      "available": false,
      "model": "llama3.2:3b",
      "error": "Ollama is not reachable"
    }
    """
    from services.ollama_service import ollama_service
    return ollama_service.health_check()

