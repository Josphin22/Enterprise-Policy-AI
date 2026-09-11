"""
Enterprise Policy AI - Centralized Local Embedding Service (Phase 4)
Provides 100% local embedding generation using sentence-transformers/all-MiniLM-L6-v2.
Model is loaded once, cached locally, and generates L2-normalized 384-dimensional dense vectors.
"""

import logging
import threading
from typing import List, Optional, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger("enterprise_rag.services.embedding")

# Process-level model cache to guarantee single model load across all requests and threads
_GLOBAL_MODEL_CACHE: Dict[str, SentenceTransformer] = {}
_GLOBAL_LOCK = threading.Lock()
EXPECTED_DIMENSION: int = 384


class EmbeddingService:
    """
    Centralized local embedding service using SentenceTransformers.
    Generates normalized 384-dimensional dense vectors for document chunks and user queries.
    Loaded ONCE at application startup and cached for all subsequent requests.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name: str = model_name or settings.EMBEDDING_MODEL
        self._dimension: Optional[int] = None

    @property
    def is_loaded(self) -> bool:
        """Check if the model is currently cached in memory."""
        return self.model_name in _GLOBAL_MODEL_CACHE

    def get_embedding_model(self) -> SentenceTransformer:
        """
        Load the SentenceTransformer model ONCE into memory.
        Uses process-level singleton caching and local-first loading.
        Verifies that model vector dimension is exactly 384.
        """
        global _GLOBAL_MODEL_CACHE
        if self.model_name not in _GLOBAL_MODEL_CACHE:
            with _GLOBAL_LOCK:
                if self.model_name not in _GLOBAL_MODEL_CACHE:
                    logger.info(f"Loading local SentenceTransformer model: '{self.model_name}'")
                    model = None
                    # Try local files first for fast offline startup
                    try:
                        model = SentenceTransformer(self.model_name, local_files_only=True)
                    except Exception:
                        pass

                    if model is None:
                        try:
                            model = SentenceTransformer(self.model_name)
                        except Exception as exc:
                            logger.error(f"Failed to load embedding model '{self.model_name}': {exc}", exc_info=True)
                            raise RuntimeError(f"EMBEDDING_MODEL_ERROR: Could not load '{self.model_name}': {exc}") from exc

                    _GLOBAL_MODEL_CACHE[self.model_name] = model
                    logger.info(f"Embedding model '{self.model_name}' successfully loaded into memory.")

        model = _GLOBAL_MODEL_CACHE[self.model_name]

        # Programmatically verify embedding dimension (Part 3 requirement)
        if self._dimension is None:
            if hasattr(model, "get_embedding_dimension"):
                self._dimension = model.get_embedding_dimension()
            elif hasattr(model, "get_sentence_embedding_dimension"):
                self._dimension = model.get_sentence_embedding_dimension()
            else:
                sample_vec = model.encode(["probe"], convert_to_numpy=True)
                self._dimension = int(sample_vec.shape[-1])

            if self._dimension != EXPECTED_DIMENSION:
                error_msg = (
                    f"VECTOR_DIMENSION_MISMATCH: Expected vector dimension {EXPECTED_DIMENSION}, "
                    f"but model '{self.model_name}' produced dimension {self._dimension}."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

        return model

    # Alias for get_embedding_model() to preserve backward compatibility
    def load_model(self) -> SentenceTransformer:
        return self.get_embedding_model()

    def get_dimension(self) -> int:
        """Return and programmatically verify vector dimension (must be 384)."""
        if self._dimension is None:
            self.get_embedding_model()
        return self._dimension or EXPECTED_DIMENSION

    @staticmethod
    def normalize_vector(vec: np.ndarray) -> np.ndarray:
        """Enforce L2 unit normalization on an embedding vector or matrix."""
        norm = np.linalg.norm(vec, axis=-1, keepdims=True)
        norm = np.where(norm == 0, 1.0, norm)
        return (vec / norm).astype(np.float32)

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate a normalized 1D float32 embedding vector for a single string.
        Verified programmatically to return a vector of exact dimension 384.
        """
        if not text or not text.strip():
            dim = self.get_dimension()
            return np.zeros(dim, dtype=np.float32)

        model = self.get_embedding_model()
        embedding = model.encode(
            text.strip(),
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        vec = np.asarray(embedding, dtype=np.float32)

        # Dimension validation check (Part 3 & 19)
        if vec.shape[-1] != EXPECTED_DIMENSION:
            raise ValueError(
                f"VECTOR_DIMENSION_MISMATCH: Expected embedding dimension {EXPECTED_DIMENSION}, got {vec.shape[-1]}"
            )

        return vec

    def embed_texts(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """
        Generate normalized 2D float32 embeddings for a batch of texts.
        Uses batch encoding (default 32) and normalize_embeddings=True.
        Verified programmatically to return shape (len(texts), 384).
        """
        if not texts:
            dim = self.get_dimension()
            return np.empty((0, dim), dtype=np.float32)

        bs = batch_size or settings.EMBEDDING_BATCH_SIZE
        model = self.get_embedding_model()

        # Sanitize empty strings to a space so encoder handles cleanly
        cleaned_texts = [t.strip() if (t and t.strip()) else " " for t in texts]

        embeddings = model.encode(
            cleaned_texts,
            batch_size=bs,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        matrix = np.asarray(embeddings, dtype=np.float32)

        if matrix.shape[-1] != EXPECTED_DIMENSION:
            raise ValueError(
                f"VECTOR_DIMENSION_MISMATCH: Expected vector dimension {EXPECTED_DIMENSION}, got {matrix.shape[-1]}"
            )

        return matrix

    def embed_documents(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """Alias for embed_texts to preserve backward compatibility."""
        return self.embed_texts(texts, batch_size=batch_size)


# Global singleton instance
embedding_service = EmbeddingService()


# Top-level module convenience functions matching Part 4 interface
def get_embedding_model() -> SentenceTransformer:
    return embedding_service.get_embedding_model()


def embed_text(text: str) -> np.ndarray:
    return embedding_service.embed_text(text)


def embed_texts(texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
    return embedding_service.embed_texts(texts, batch_size=batch_size)


def get_dimension() -> int:
    return embedding_service.get_dimension()
