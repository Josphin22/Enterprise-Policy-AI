import logging
import threading
from typing import List, Optional, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import settings

logger = logging.getLogger("enterprise_rag.rag.embeddings")

# Process-level model cache to ensure single load across requests
_GLOBAL_MODEL_CACHE: Dict[str, SentenceTransformer] = {}
_GLOBAL_LOCK = threading.Lock()
EXPECTED_DIMENSION: int = 384


class EmbeddingService:
    """
    Thread-safe local embedding service using SentenceTransformers.
    Generates L2-normalized 384-dimensional dense vectors for document chunks and user queries.
    Loaded ONCE at application startup and cached for all subsequent requests.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._dimension: Optional[int] = None

    @property
    def is_loaded(self) -> bool:
        return self.model_name in _GLOBAL_MODEL_CACHE

    def load_model(self) -> SentenceTransformer:
        """
        Load the SentenceTransformer model ONCE into memory.
        Uses process-level singleton caching and local-first loading.
        Verifies that model vector dimension is exactly 384.
        """
        global _GLOBAL_MODEL_CACHE
        if self.model_name not in _GLOBAL_MODEL_CACHE:
            with _GLOBAL_LOCK:
                if self.model_name not in _GLOBAL_MODEL_CACHE:
                    logger.info(f"Loading SentenceTransformer model: '{self.model_name}'")
                    model = None
                    # Try local files first for instant offline startup
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
                    logger.info(f"Model '{self.model_name}' successfully loaded and cached.")

        model = _GLOBAL_MODEL_CACHE[self.model_name]

        # Determine and verify vector dimension
        if self._dimension is None:
            if hasattr(model, "get_embedding_dimension"):
                self._dimension = model.get_embedding_dimension()
            elif hasattr(model, "get_sentence_embedding_dimension"):
                self._dimension = model.get_sentence_embedding_dimension()
            else:
                sample_vec = model.encode(["probe"])
                self._dimension = sample_vec.shape[-1]

            if self._dimension != EXPECTED_DIMENSION:
                error_msg = f"EMBEDDING_MODEL_ERROR: Expected vector dimension {EXPECTED_DIMENSION}, but model '{self.model_name}' has dimension {self._dimension}."
                logger.error(error_msg)
                raise ValueError(error_msg)

        return model

    def get_dimension(self) -> int:
        """Return and verify the vector dimension (must be 384)."""
        if self._dimension is None:
            self.load_model()
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
        Verified to return a vector of exact dimension 384.
        """
        if not text or not text.strip():
            dim = self.get_dimension()
            return np.zeros(dim, dtype=np.float32)

        model = self.load_model()
        embedding = model.encode(
            text.strip(),
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        vec = np.asarray(embedding, dtype=np.float32)

        if vec.shape[-1] != EXPECTED_DIMENSION:
            raise ValueError(
                f"EMBEDDING_MODEL_ERROR: Expected embedding dimension {EXPECTED_DIMENSION}, got {vec.shape[-1]}"
            )

        return vec

    def embed_texts(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """
        Generate normalized 2D float32 embeddings for a list/batch of texts.
        Verified to return shape (len(texts), 384).
        """
        if not texts:
            dim = self.get_dimension()
            return np.empty((0, dim), dtype=np.float32)

        bs = batch_size or settings.EMBEDDING_BATCH_SIZE
        model = self.load_model()

        # Sanitize empty strings to spaces so encoder handles cleanly
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
                f"EMBEDDING_MODEL_ERROR: Expected vector dimension {EXPECTED_DIMENSION}, got {matrix.shape[-1]}"
            )

        return matrix

    def embed_documents(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """Alias for embed_texts to preserve backward compatibility."""
        return self.embed_texts(texts, batch_size=batch_size)


# Global singleton instance
embedding_service = EmbeddingService()
