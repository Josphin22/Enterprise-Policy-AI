"""
RAGService module in backend/app/services/
Orchestrates context retrieval, relevance thresholding, and source citation packaging.
"""
from app.rag.service import rag_service, RAGService

__all__ = ["rag_service", "RAGService"]
