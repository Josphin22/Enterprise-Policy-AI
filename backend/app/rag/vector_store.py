import json
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import faiss
import numpy as np

from app.config import settings

logger = logging.getLogger("enterprise_rag.rag.vector_store")


class FAISSVectorStore:
    """
    Local persistent vector store using FAISS CPU IndexFlatIP with L2-normalized vectors.
    Provides exact cosine similarity retrieval and maps vector IDs to PostgreSQL chunk metadata.
    """

    def __init__(self, vectorstore_dir: Optional[Path] = None):
        self.vectorstore_dir = vectorstore_dir or settings.VECTORSTORE_DIR
        self.index_file = self.vectorstore_dir / "index.faiss"
        self.metadata_file = self.vectorstore_dir / "metadata.json"
        self.info_file = self.vectorstore_dir / "index_info.json"

        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata_map: Dict[int, Dict[str, Any]] = {}
        self.index_info: Dict[str, Any] = {}

    @property
    def is_built(self) -> bool:
        return self.index is not None and self.index.ntotal > 0

    @property
    def total_vectors(self) -> int:
        return self.index.ntotal if self.index is not None else 0

    def create_index(self, dimension: int):
        """
        Create a new in-memory FAISS IndexFlatIP.
        Inner product with L2-normalized vectors mathematically equals Cosine Similarity.
        """
        logger.info(f"Creating new FAISS IndexFlatIP (dimension={dimension})")
        self.index = faiss.IndexFlatIP(dimension)
        self.metadata_map = {}
        self.index_info = {
            "index_type": "IndexFlatIP",
            "metric": "Cosine Similarity (Normalized Inner Product)",
            "dimension": dimension,
            "vectors": 0,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def add_vectors(self, embeddings: np.ndarray, metadata_list: List[Dict[str, Any]]):
        """
        Add a matrix of normalized vector embeddings and their corresponding metadata dictionaries.
        """
        if embeddings.size == 0 or len(metadata_list) == 0:
            logger.warning("add_vectors called with empty embeddings or metadata")
            return

        if embeddings.shape[0] != len(metadata_list):
            raise ValueError(
                f"Embeddings count ({embeddings.shape[0]}) does not match metadata count ({len(metadata_list)})"
            )

        dimension = embeddings.shape[1]
        if self.index is None:
            self.create_index(dimension)
        elif self.index.d != dimension:
            raise ValueError(
                f"Embedding dimension {dimension} does not match index dimension {self.index.d}"
            )

        start_id = self.index.ntotal

        # Ensure float32 contiguous array
        vectors = np.ascontiguousarray(embeddings, dtype=np.float32)

        # L2-normalize vectors to enforce unit length for cosine similarity
        faiss.normalize_L2(vectors)

        # Add to FAISS index
        self.index.add(vectors)

        # Record metadata mapping for each added vector
        for idx, meta in enumerate(metadata_list):
            vector_id = start_id + idx
            self.metadata_map[vector_id] = meta

        self.index_info["vectors"] = self.index.ntotal
        self.index_info["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        logger.info(f"Added {len(metadata_list)} vectors to FAISS index. Total count: {self.index.ntotal}")

    def save_index(self, directory: Optional[Path] = None):
        """
        Serialize FAISS index binary, metadata mapping, and index summary info to disk.
        """
        target_dir = directory or self.vectorstore_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        idx_path = target_dir / "index.faiss"
        meta_path = target_dir / "metadata.json"
        info_path = target_dir / "index_info.json"

        if self.index is None:
            raise RuntimeError("Cannot save uninitialized FAISS index.")

        # Save FAISS binary
        faiss.write_index(self.index, str(idx_path))

        # Save metadata JSON (keys serialized as strings)
        serialized_meta = {str(k): v for k, v in self.metadata_map.items()}
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(serialized_meta, f, indent=2)

        # Save info JSON
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(self.index_info, f, indent=2)

        logger.info(f"FAISS index and metadata successfully saved to: {target_dir}")

    def load_index(self, directory: Optional[Path] = None) -> bool:
        """
        Load persistent FAISS index and metadata mapping from disk.
        Returns True if loaded successfully, False if index files do not exist or are corrupted.
        """
        target_dir = directory or self.vectorstore_dir
        idx_path = target_dir / "index.faiss"
        meta_path = target_dir / "metadata.json"
        info_path = target_dir / "index_info.json"

        if not (idx_path.exists() and meta_path.exists()):
            logger.info(f"No existing FAISS index found at {target_dir}")
            return False

        try:
            logger.info(f"Loading persistent FAISS index from {idx_path}")
            self.index = faiss.read_index(str(idx_path))

            with open(meta_path, "r", encoding="utf-8") as f:
                raw_meta = json.load(f)
                self.metadata_map = {int(k): v for k, v in raw_meta.items()}

            if info_path.exists():
                with open(info_path, "r", encoding="utf-8") as f:
                    self.index_info = json.load(f)
            else:
                self.index_info = {
                    "index_type": "IndexFlatIP",
                    "dimension": self.index.d,
                    "vectors": self.index.ntotal,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }

            logger.info(f"FAISS index loaded successfully with {self.index.ntotal} vectors (dimension={self.index.d})")
            return True

        except Exception as exc:
            logger.error(f"Failed to load FAISS index from {target_dir}: {exc}", exc_info=True)
            self.index = None
            self.metadata_map = {}
            self.index_info = {}
            return False

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Execute cosine similarity search with query vector and return ranked results with metadata.
        """
        if not self.is_built:
            logger.warning("Search failed: FAISS index is not built or empty")
            return []

        # Ensure query is 2D float32 contiguous array
        q_vec = np.ascontiguousarray(query_vector, dtype=np.float32)
        if q_vec.ndim == 1:
            q_vec = q_vec.reshape(1, -1)

        # L2-normalize query vector for cosine similarity
        faiss.normalize_L2(q_vec)

        # Clamp top_k to total vectors available
        k = max(1, min(top_k, self.index.ntotal))

        # Perform search (returns distances/inner-products and vector indices)
        scores, indices = self.index.search(q_vec, k)

        results: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            meta = self.metadata_map.get(int(idx), {})
            results.append({
                "vector_id": int(idx),
                "score": float(score),
                "chunk_id": meta.get("chunk_id"),
                "document_id": meta.get("document_id"),
                "filename": meta.get("filename"),
                "page": meta.get("page"),
                "section": meta.get("section"),
                "text": meta.get("text"),
                "character_count": meta.get("character_count"),
            })

        logger.info(f"FAISS search returned {len(results)} matches for top_k={k}")
        return results

    def clear(self):
        """Reset in-memory vector store."""
        self.index = None
        self.metadata_map = {}
        self.index_info = {}

    def get_index_stats(self) -> Dict[str, Any]:
        """Return diagnostic vector store statistics."""
        return {
            "status": "ready" if self.is_built else "not_built",
            "vectors": self.total_vectors,
            "dimension": self.index.d if self.index is not None else 0,
            "index_type": self.index_info.get("index_type", "IndexFlatIP"),
            "metric": self.index_info.get("metric", "Cosine Similarity"),
            "last_built": self.index_info.get("updated_at"),
        }


# Global singleton instance
vector_store = FAISSVectorStore()
