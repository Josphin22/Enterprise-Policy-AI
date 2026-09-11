"""
Enterprise Policy AI - Centralized Ollama LLM Service (Phase 6)
Responsible exclusively for local Ollama daemon communication, health probing,
model availability verification, and conservative text generation.
Enforces 100% local execution without third-party or paid cloud inference APIs.
"""

import time
import logging
from typing import List, Optional, Dict, Any
import httpx

from app.config import settings

logger = logging.getLogger("enterprise_rag.services.ollama")


class OllamaService:
    """
    Dedicated local LLM service communicating exclusively with local Ollama HTTP API.
    Supports health checks, model enumeration, and grounded completion inference.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.default_model = (model or settings.OLLAMA_MODEL).strip()
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """Cached HTTP client with connection pool for fast local inference."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=5.0),
            )
        return self._client

    def is_reachable(self) -> bool:
        """Check if local Ollama daemon is active and responding on HTTP."""
        try:
            resp = self.client.get("/api/tags", timeout=1.5)
            return resp.status_code == 200
        except Exception as exc:
            logger.debug(f"Ollama daemon unreachable at {self.base_url}: {exc}")
            return False

    def list_installed_models(self) -> List[str]:
        """Fetch all model tags currently installed in the local Ollama instance."""
        try:
            resp = self.client.get("/api/tags", timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [
                    m.get("name")
                    for m in data.get("models", [])
                    if m.get("name")
                ]
                return models
            return []
        except Exception as exc:
            logger.warning(f"Failed to query installed Ollama models: {exc}")
            return []

    def check_model_available(self, model_name: Optional[str] = None) -> bool:
        """
        Verify whether the requested model is installed locally.
        Supports exact match and prefix/tag variations (e.g. 'llama3.2:3b' vs 'llama3.2:latest').
        """
        target = (model_name or self.default_model).strip()
        models = self.list_installed_models()
        if not models:
            return False

        target_base = target.split(":")[0]
        for m in models:
            if m == target or m.startswith(f"{target}:") or m.split(":")[0] == target_base:
                return True
        return False

    def health_check(self) -> Dict[str, Any]:
        """
        Comprehensive Ollama health status check for /api/health/ollama.
        Returns clear structured status without internal stack traces.
        """
        target_model = self.default_model
        reachable = self.is_reachable()

        if not reachable:
            logger.warning(f"Ollama health check: daemon unreachable at {self.base_url}")
            return {
                "available": False,
                "model": target_model,
                "error": "Ollama is not reachable",
            }

        installed = self.list_installed_models()
        model_exists = self.check_model_available(target_model)

        if not model_exists:
            logger.warning(
                f"Ollama health check: model '{target_model}' not installed (available: {installed})"
            )
            return {
                "available": False,
                "model": target_model,
                "error": f"Configured model '{target_model}' is not installed",
            }

        return {
            "available": True,
            "model": target_model,
        }

    def generate_response(
        self,
        prompt: str,
        system: Optional[str] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        num_ctx: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate grounded answer text using local Ollama model.
        1. Validates daemon reachability.
        2. Validates configured model presence.
        3. Enforces conservative parameters (low temp, max_tokens).
        4. Handles connection errors, timeouts, and invalid responses cleanly.
        """
        effective_system = system or system_prompt
        target_model = model or self.default_model
        t_start = time.perf_counter()

        # Step 1: Reachability check
        if not self.is_reachable():
            return {
                "success": False,
                "status": "llm_unavailable",
                "model": target_model,
                "response": "",
                "total_duration_ms": 0.0,
                "error": "Ollama is not reachable",
                "message": f"Local Ollama service is unavailable at {self.base_url}.",
            }

        # Step 2: Model presence check
        if not self.check_model_available(target_model):
            return {
                "success": False,
                "status": "model_not_found",
                "model": target_model,
                "response": "",
                "total_duration_ms": 0.0,
                "error": f"Configured Ollama model '{target_model}' is not installed",
                "message": (
                    f"Configured Ollama model '{target_model}' is not installed locally. "
                    f"Please run 'ollama pull {target_model}' in your terminal."
                ),
            }

        # Step 3: Configure generation options
        effective_temp = temperature if temperature is not None else settings.OLLAMA_TEMPERATURE
        effective_top_p = top_p if top_p is not None else settings.OLLAMA_TOP_P
        effective_ctx = num_ctx if num_ctx is not None else settings.OLLAMA_NUM_CTX
        effective_predict = max_tokens if max_tokens is not None else settings.OLLAMA_MAX_TOKENS

        options: Dict[str, Any] = {
            "temperature": effective_temp,
            "top_p": effective_top_p,
            "num_ctx": effective_ctx,
            "num_predict": effective_predict,
        }

        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        if effective_system:
            payload["system"] = effective_system

        logger.info(
            f"Dispatching prompt to Ollama '{target_model}' (temp={effective_temp}, num_predict={effective_predict})..."
        )

        # Step 4: Execute HTTP request to local Ollama daemon
        try:
            resp = self.client.post(
                "/api/generate",
                json=payload,
                timeout=float(self.timeout),
            )
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

            if resp.status_code == 200:
                data = resp.json()
                raw_response = data.get("response", "").strip()

                if not raw_response:
                    logger.warning("Ollama returned 200 OK but response text was empty.")
                    return {
                        "success": False,
                        "status": "empty_response",
                        "model": target_model,
                        "response": "",
                        "total_duration_ms": elapsed_ms,
                        "error": "Ollama generated an empty response",
                        "message": "Local model generated an empty response.",
                    }

                logger.info(
                    f"Ollama generation completed in {elapsed_ms}ms ({len(raw_response)} chars)."
                )
                return {
                    "success": True,
                    "status": "success",
                    "model": target_model,
                    "response": raw_response,
                    "total_duration_ms": elapsed_ms,
                    "prompt_eval_count": data.get("prompt_eval_count"),
                    "eval_count": data.get("eval_count"),
                    "error": None,
                    "message": None,
                }
            else:
                logger.error(f"Ollama returned HTTP {resp.status_code}: {resp.text}")
                return {
                    "success": False,
                    "status": "generation_error",
                    "model": target_model,
                    "response": "",
                    "total_duration_ms": elapsed_ms,
                    "error": f"Ollama HTTP error {resp.status_code}",
                    "message": f"Ollama generation failed with status code {resp.status_code}.",
                }

        except httpx.TimeoutException:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.warning(f"Ollama generation timed out after {self.timeout}s.")
            return {
                "success": False,
                "status": "generation_timeout",
                "model": target_model,
                "response": "",
                "total_duration_ms": elapsed_ms,
                "error": "Ollama generation timed out",
                "message": f"The local AI model took too long to respond (timeout: {self.timeout}s).",
            }
        except httpx.ConnectError:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.error(f"Connection to Ollama failed at {self.base_url}")
            return {
                "success": False,
                "status": "llm_unavailable",
                "model": target_model,
                "response": "",
                "total_duration_ms": elapsed_ms,
                "error": "Ollama connection refused",
                "message": f"Could not connect to Ollama daemon at {self.base_url}.",
            }
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.error(f"Unexpected error communicating with Ollama: {exc}")
            return {
                "success": False,
                "status": "generation_error",
                "model": target_model,
                "response": "",
                "total_duration_ms": elapsed_ms,
                "error": str(exc),
                "message": f"Local LLM inference error: {str(exc)}",
            }

    def close(self):
        """Close cached HTTP client sessions."""
        if self._client and not self._client.is_closed:
            self._client.close()


# Centralized global singleton instance
ollama_service = OllamaService()
