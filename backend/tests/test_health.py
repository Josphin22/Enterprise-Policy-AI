import sys
from pathlib import Path

# Ensure backend directory is in sys.path for test execution
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_status_code():
    """Verify that GET /api/health returns HTTP 200 OK."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_check_payload():
    """Verify that GET /api/health returns the expected JSON payload."""
    response = client.get("/api/health")
    data = response.json()
    assert data.get("status") == "healthy"
    assert data.get("service") == "Enterprise Policy RAG"


def test_cors_headers():
    """Verify CORS preflight or response headers are correctly configured."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    # FastAPI CORS middleware returns 200 for preflight
    assert response.status_code == 200
