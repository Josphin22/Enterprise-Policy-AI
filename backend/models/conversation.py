"""
Conversation Model module (Phase 6)
Maps to ChatSession in app.models.chat.
"""
from app.models.chat import ChatSession

Conversation = ChatSession
__all__ = ["Conversation", "ChatSession"]
