"""
RetrievalService export in backend/app/services/
Provides semantic Top-K retrieval, relevance filtering, and context building against FAISS.
"""
from services.retrieval_service import (
    retrieval_service,
    RetrievalService,
    retrieve_context,
    build_grounded_context,
    filter_relevance,
)

__all__ = [
    "retrieval_service",
    "RetrievalService",
    "retrieve_context",
    "build_grounded_context",
    "filter_relevance",
]
