"""
Tests for Ollama service reachability, model checking, and health endpoint.
Phase 6: Real Ollama Integration
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx
from fastapi.testclient import TestClient

from app.main import app
from services.ollama_service import ollama_service, OllamaService
from app.config import settings


@pytest.fixture
def client():
    return TestClient(app)


def test_ollama_service_health_check_live_or_mocked():
    """Verify health_check() responds correctly with status dictionary."""
    is_live = ollama_service.health_check()
    assert isinstance(is_live, dict)
    assert "available" in is_live
    assert isinstance(is_live["available"], bool)


def test_ollama_service_model_available():
    """Verify check_model_available correctly identifies the configured model."""
    target_model = settings.OLLAMA_MODEL
    available = ollama_service.check_model_available(target_model)
    assert isinstance(available, bool)


def test_ollama_health_endpoint(client):
    """Verify GET /api/health/ollama returns 200 with available and model fields."""
    response = client.get("/api/health/ollama")
    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "model" in data
    assert data["model"] == settings.OLLAMA_MODEL


def test_ollama_service_offline_handling(client):
    """Verify graceful handling when Ollama daemon is offline/unreachable."""
    with patch.object(
        ollama_service,
        "health_check",
        return_value={"available": False, "model": settings.OLLAMA_MODEL, "error": "Ollama is not reachable"},
    ):
        response = client.get("/api/health/ollama")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert "not reachable" in data.get("error", "").lower() or "offline" in data.get("error", "").lower()


def test_ollama_service_client_timeout_handling():
    """Verify timeout exception is handled cleanly without crashing."""
    service = OllamaService(base_url="http://127.0.0.1:11434", timeout=0.0001)
    with patch.object(httpx.Client, "get", side_effect=httpx.TimeoutException("Timeout")):
        res = service.health_check()
        assert res["available"] is False
        assert service.check_model_available("llama3.2:3b") is False


def test_ollama_generate_response_mocked():
    """Verify prompt formatting and payload passed to Ollama generate endpoint."""
    service = OllamaService()
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "response": "According to company policy [Source 1], annual leave is 25 days."
    }

    with patch.object(service.client, "post", return_value=mock_resp) as mock_post:
        result = service.generate_response(
            prompt="How many leave days?",
            system_prompt="You are a helpful assistant.",
            temperature=0.1,
            max_tokens=200,
        )
        assert result["success"] is True
        assert "annual leave is 25 days" in result["response"]
        mock_post.assert_called_once()
        call_json = mock_post.call_args[1]["json"]
        assert call_json["model"] == settings.OLLAMA_MODEL
        assert call_json["stream"] is False
        assert call_json["options"]["temperature"] == 0.1
        assert call_json["options"]["num_predict"] == 200
