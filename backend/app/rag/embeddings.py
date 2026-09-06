import logging
import threading
from typing import List, Optional, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import settings

logger = logging.getLogger("enterprise_rag.rag.embeddings")

# Process-level model cache to avoid repeated network checks and weight loading
_GLOBAL_MODEL_CACHE: Dict[str, SentenceTransformer] = {}
_GLOBAL_LOCK = threading.Lock()


class EmbeddingService:
    """
    Thread-safe, lazy-loading local embedding service using SentenceTransformers.
    Generates normalized dense numerical vectors for document chunks and user queries.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._dimension: Optional[int] = None

    @property
    def is_loaded(self) -> bool:
        return self.model_name in _GLOBAL_MODEL_CACHE

    def load_model(self) -> SentenceTransformer:
        """
        Load the SentenceTransformer model if not already loaded into memory.
        Uses process-level singleton caching and local-first loading.
        """
        global _GLOBAL_MODEL_CACHE
        if self.model_name not in _GLOBAL_MODEL_CACHE:
            with _GLOBAL_LOCK:
                if self.model_name not in _GLOBAL_MODEL_CACHE:
                    logger.info(f"Loading local SentenceTransformer model: '{self.model_name}'")
                    model = None
                    # Try local cache first for instant, offline execution
                    try:
                        model = SentenceTransformer(self.model_name, local_files_only=True)
                    except Exception:
                        pass

                    if model is None:
                        try:
                            model = SentenceTransformer(self.model_name)
                        except Exception as exc:
                            logger.error(f"Failed to load embedding model '{self.model_name}': {exc}", exc_info=True)
                            raise RuntimeError(f"Could not load embedding model '{self.model_name}': {exc}") from exc

                    _GLOBAL_MODEL_CACHE[self.model_name] = model
                    logger.info(f"Model '{self.model_name}' successfully loaded and cached in memory.")

        model = _GLOBAL_MODEL_CACHE[self.model_name]
        if self._dimension is None:
            if hasattr(model, "get_embedding_dimension"):
                self._dimension = model.get_embedding_dimension()
            elif hasattr(model, "get_sentence_embedding_dimension"):
                self._dimension = model.get_sentence_embedding_dimension()
            else:
                sample_vec = model.encode(["dimension probe"])
                self._dimension = sample_vec.shape[-1]
        return model

    def get_dimension(self) -> int:
        """
        Return the exact embedding vector dimension of the loaded model.
        """
        if self._dimension is None:
            self.load_model()
        return self._dimension

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate a normalized 1D float32 embedding vector for a single text query or string.
        """
        if not text or not text.strip():
            dim = self.get_dimension()
            return np.zeros(dim, dtype=np.float32)

        model = self.load_model()
        # normalize_embeddings=True ensures L2 norm equals 1 for exact Cosine Similarity with FAISS IndexFlatIP
        embedding = model.encode(
            text.strip(),
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return np.asarray(embedding, dtype=np.float32)

    def embed_documents(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """
        Generate normalized 2D float32 embeddings for a batch of document chunk texts.
        """
        if not texts:
            dim = self.get_dimension()
            return np.empty((0, dim), dtype=np.float32)

        bs = batch_size or settings.EMBEDDING_BATCH_SIZE
        model = self.load_model()

        # Sanitize texts
        cleaned_texts = [t if (t and t.strip()) else " " for t in texts]

        logger.info(f"Generating embeddings for {len(cleaned_texts)} document chunks (batch_size={bs})...")
        embeddings = model.encode(
            cleaned_texts,
            batch_size=bs,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return np.asarray(embeddings, dtype=np.float32)


# Global singleton instance
embedding_service = EmbeddingService()
