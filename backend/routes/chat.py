"""
Chat Router module in backend/routes/
Re-exports chat router from app.api.chat.
"""
from app.api.chat import router

__all__ = ["router"]
