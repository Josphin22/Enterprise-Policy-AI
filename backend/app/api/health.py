from fastapi import APIRouter
from app.schemas.system import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Check operational availability of the Enterprise Policy RAG backend.",
)
async def get_health():
    """
    Returns standard healthy status and service descriptor.
    """
    return HealthResponse(
        status="healthy",
        service="Enterprise Policy RAG"
    )
