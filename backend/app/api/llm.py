from typing import List
from fastapi import APIRouter
from app.llm.schemas import LLMStatusResponse
from app.llm.service import llm_service
from app.llm.ollama_client import ollama_client

router = APIRouter(prefix="/llm", tags=["LLM Inference"])


@router.get(
    "/status",
    response_model=LLMStatusResponse,
    summary="Get Local LLM Status",
    description="Check local Ollama daemon connectivity, active model configuration, and model availability.",
)
async def get_llm_status():
    """
    Returns live operational status of the local Ollama LLM subsystem.
    """
    status_data = llm_service.get_status()
    return LLMStatusResponse(
        provider=status_data.get("provider", "ollama"),
        endpoint=status_data.get("endpoint", "http://127.0.0.1:11434"),
        model=status_data["model"],
        available=status_data.get("available", False),
        status=status_data["status"],
        base_url=status_data.get("base_url", "http://127.0.0.1:11434"),
        installed_models=status_data.get("installed_models", []),
        message=status_data.get("message"),
    )


@router.get(
    "/models",
    response_model=List[str],
    summary="List Installed Ollama Models",
    description="List all local LLM models currently installed and pulled in the Ollama instance.",
)
async def list_installed_models():
    """
    Returns list of locally available Ollama model tags.
    """
    return ollama_client.list_models()
