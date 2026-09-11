"""
VectorService module wrapping FAISS CPU IndexFlatIP vector operations.
Implements the standardized service interface:
- initialize(dimension=384)
- load()
- save()
- add_vectors(embeddings, metadata_list)
- search(query_vector, top_k=5, min_score=0.35)
- rebuild(embeddings, metadata_list)
- count()
- clear()
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np

from app.rag.vector_store import vector_store, FAISSVectorStore
from services.vectorstore_service import vectorstore_service, VectorStoreService


class VectorService:
    """
    Standardized service layer for FAISS vector operations.
    Delegates to the FAISSVectorStore singleton.
    """

    def __init__(self, store: Optional[FAISSVectorStore] = None):
        self._store = store or vector_store

    def initialize(self, dimension: int = 384):
        return self._store.initialize(dimension=dimension)

    def load(self, directory: Optional[Path] = None) -> bool:
        return self._store.load(directory=directory)

    def save(self, directory: Optional[Path] = None):
        return self._store.save(directory=directory)

    def add_vectors(self, embeddings: np.ndarray, metadata_list: List[Dict[str, Any]]):
        return self._store.add_vectors(embeddings=embeddings, metadata_list=metadata_list)

    def search(self, query_vector: np.ndarray, top_k: int = 5, min_score: float = 0.35) -> List[Dict[str, Any]]:
        return self._store.search(query_vector=query_vector, top_k=top_k, min_score=min_score)

    def rebuild(self, embeddings: np.ndarray, metadata_list: List[Dict[str, Any]], directory: Optional[Path] = None):
        return self._store.rebuild(embeddings=embeddings, metadata_list=metadata_list, directory=directory)

    def count(self) -> int:
        return self._store.count()

    def clear(self):
        return self._store.clear()

    @property
    def is_built(self) -> bool:
        return self._store.is_built

    @property
    def total_vectors(self) -> int:
        return self._store.total_vectors

    def get_index_stats(self) -> Dict[str, Any]:
        return self._store.get_index_stats()


# Global singleton instance
vector_service = VectorService()

__all__ = [
    "VectorService",
    "vector_service",
    "VectorStoreService",
    "vectorstore_service",
]
