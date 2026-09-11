"""
EmbeddingService export in backend/app/services/
Provides standardized embedding generation interface using SentenceTransformers.
"""
from services.embedding_service import (
    embedding_service,
    EmbeddingService,
    get_embedding_model,
    embed_text,
    embed_texts,
    get_dimension,
)

__all__ = [
    "embedding_service",
    "EmbeddingService",
    "get_embedding_model",
    "embed_text",
    "embed_texts",
    "get_dimension",
]
