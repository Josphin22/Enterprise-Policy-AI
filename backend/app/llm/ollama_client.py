import time
import logging
from typing import List, Optional, Dict, Any
import httpx

from app.config import settings

logger = logging.getLogger("enterprise_rag.llm.ollama_client")


class OllamaClient:
    """
    Reusable HTTP client communicating directly with the local Ollama daemon.
    Enforces local-only inference without any third-party or cloud dependencies.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.default_model = default_model or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=5.0),
            )
        return self._client

    def check_connection(self) -> bool:
        """
        Check if the local Ollama daemon is reachable on OLLAMA_BASE_URL.
        """
        try:
            resp = self.client.get("/api/tags", timeout=1.0)
            return resp.status_code == 200
        except Exception as exc:
            logger.debug(f"Ollama connection check failed: {exc}")
            return False

    def list_models(self) -> List[str]:
        """
        Query Ollama for all installed local models.
        """
        try:
            resp = self.client.get("/api/tags", timeout=1.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                return models
            return []
        except Exception as exc:
            logger.warning(f"Failed to list Ollama models: {exc}")
            return []

    def check_model_available(self, model_name: Optional[str] = None) -> bool:
        """
        Check whether the target model (or tag variation) is installed locally.
        """
        target = (model_name or self.default_model).strip()
        models = self.list_models()
        if not models:
            return False

        # Exact match or prefix match (e.g. 'llama3.2:3b' vs 'llama3.2:3b' or 'llama3.2:latest')
        target_base = target.split(":")[0]
        for m in models:
            if m == target or m.startswith(f"{target}:") or m.split(":")[0] == target_base:
                return True
        return False

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        num_ctx: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate answer from the local Ollama model.
        Returns a structured dictionary with status and timing.
        """
        target_model = model or self.default_model
        t_start = time.perf_counter()

        # 1. Connection check
        if not self.check_connection():
            return {
                "success": False,
                "status": "llm_unavailable",
                "model": target_model,
                "response": "",
                "total_duration_ms": 0.0,
                "message": f"Local Ollama service is unavailable at {self.base_url}.",
            }

        # 2. Model presence check
        if not self.check_model_available(target_model):
            return {
                "success": False,
                "status": "model_not_found",
                "model": target_model,
                "response": "",
                "total_duration_ms": 0.0,
                "message": (
                    f"Configured Ollama model '{target_model}' is not installed locally. "
                    f"Please run 'ollama pull {target_model}' in your terminal."
                ),
            }

        # 3. Build payload
        options = {
            "temperature": temperature if temperature is not None else settings.OLLAMA_TEMPERATURE,
            "top_p": top_p if top_p is not None else settings.OLLAMA_TOP_P,
            "num_ctx": num_ctx if num_ctx is not None else settings.OLLAMA_NUM_CTX,
        }

        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        if system:
            payload["system"] = system

        logger.info(f"Sending prompt to Ollama model '{target_model}' (temp={options['temperature']})...")

        # 4. Execute request
        try:
            resp = self.client.post("/api/generate", json=payload, timeout=float(self.timeout))
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

            if resp.status_code == 200:
                data = resp.json()
                raw_response = data.get("response", "").strip()
                logger.info(f"Ollama generation succeeded in {elapsed_ms}ms ({len(raw_response)} chars).")
                return {
                    "success": True,
                    "status": "success",
                    "model": target_model,
                    "response": raw_response,
                    "total_duration_ms": elapsed_ms,
                    "prompt_eval_count": data.get("prompt_eval_count"),
                    "eval_count": data.get("eval_count"),
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
                "message": f"The local AI model took too long to respond (timeout: {self.timeout}s).",
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
                "message": f"Local LLM inference error: {str(exc)}",
            }

    def close(self):
        if self._client and not self._client.is_closed:
            self._client.close()


# Global singleton instance
ollama_client = OllamaClient()
