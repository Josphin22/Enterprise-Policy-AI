import logging
from typing import Optional, List, Dict, Any

from app.config import settings
from app.llm.ollama_client import ollama_client, OllamaClient
from app.llm.prompt_builder import prompt_builder, PromptBuilder
from app.llm.response_parser import response_parser, ResponseParser

logger = logging.getLogger("enterprise_rag.llm.service")


class LLMService:
    """
    High-level LLM orchestration service managing prompt assembly, local inference,
    and grounded response parsing.
    """

    def __init__(
        self,
        client: Optional[OllamaClient] = None,
        p_builder: Optional[PromptBuilder] = None,
        r_parser: Optional[ResponseParser] = None,
    ):
        self.client = client or ollama_client
        self.prompt_builder = p_builder or prompt_builder
        self.response_parser = r_parser or response_parser

    def get_status(self) -> Dict[str, Any]:
        """
        Check connectivity with the local Ollama daemon and verify model installation.
        """
        is_connected = self.client.check_connection()
        installed_models = self.client.list_models() if is_connected else []
        is_model_ready = self.client.check_model_available(settings.OLLAMA_MODEL) if is_connected else False

        is_available = is_connected and is_model_ready

        if not is_connected:
            status = "llm_unavailable"
            message = f"Local Ollama daemon unreachable at {settings.OLLAMA_BASE_URL}."
        elif not is_model_ready:
            status = "model_not_found"
            message = f"Configured model '{settings.OLLAMA_MODEL}' not found. Installed: {installed_models}"
        else:
            status = "available"
            message = f"Local model '{settings.OLLAMA_MODEL}' is ready for inference."

        return {
            "provider": "ollama",
            "endpoint": settings.OLLAMA_BASE_URL,
            "model": settings.OLLAMA_MODEL,
            "available": is_available,
            "status": status,
            "base_url": settings.OLLAMA_BASE_URL,
            "installed_models": installed_models,
            "message": message,
        }

    def generate_grounded_answer(
        self,
        query: str,
        context: str,
        sources: List[Any],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        language: Optional[str] = "en",
    ) -> Dict[str, Any]:
        """
        Builds grounded RAG prompt, invokes local Ollama LLM, validates answer,
        and ensures citation authenticity.
        """
        system_prompt, user_prompt = self.prompt_builder.build_rag_prompt(
            query=query,
            context=context,
            language=language,
        )

        gen_result = self.client.generate(
            prompt=user_prompt,
            system=system_prompt,
            model=model or settings.OLLAMA_MODEL,
            temperature=temperature,
        )

        if not gen_result.get("success"):
            return {
                "success": False,
                "status": gen_result.get("status", "generation_error"),
                "answer": "",
                "sources": sources,
                "duration_ms": gen_result.get("total_duration_ms", 0.0),
                "message": gen_result.get("message", "LLM generation failed."),
            }

        raw_answer = gen_result.get("response", "")
        sanitized_answer, final_sources = self.response_parser.validate_and_filter_citations(
            raw_answer=raw_answer,
            retrieved_sources=sources,
        )

        return {
            "success": True,
            "status": "success",
            "answer": sanitized_answer,
            "sources": final_sources,
            "duration_ms": gen_result.get("total_duration_ms", 0.0),
            "prompt_eval_count": gen_result.get("prompt_eval_count"),
            "eval_count": gen_result.get("eval_count"),
            "message": None,
        }


# Global singleton instance
llm_service = LLMService()
