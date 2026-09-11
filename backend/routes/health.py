"""
Health Router module in backend/routes/
Re-exports health router from app.api.health.
"""
from app.api.health import router

__all__ = ["router"]
