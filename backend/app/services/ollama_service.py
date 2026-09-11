"""
OllamaService module in backend/app/services/
Provides local LLM inference client connectivity, health probing, and text generation.
"""
from services.ollama_service import ollama_service, OllamaService

__all__ = ["ollama_service", "OllamaService"]

