import os
import time
import json
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import faiss
import numpy as np

from app.config import settings

logger = logging.getLogger("enterprise_rag.rag.vector_store")
EXPECTED_DIMENSION: int = 384


class FAISSVectorStore:
    """
    Local persistent vector store using FAISS CPU IndexFlatIP with L2-normalized vectors.
    Inner product on normalized vectors represents exact Cosine Similarity.
    Maps every vector ID strictly 1:1 to chunk metadata.
    Provides atomic persistence and dimension/integrity validation.
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

    @property
    def dimension(self) -> int:
        return self.index.d if self.index is not None else EXPECTED_DIMENSION

    def count(self) -> int:
        """Return the current number of indexed vectors."""
        return self.total_vectors

    def initialize(self, dimension: int = EXPECTED_DIMENSION):
        """
        Create a new in-memory FAISS IndexFlatIP.
        Inner product with L2-normalized vectors mathematically equals Cosine Similarity.
        """
        if dimension != EXPECTED_DIMENSION:
            raise ValueError(
                f"VECTOR_DIMENSION_MISMATCH: Expected dimension {EXPECTED_DIMENSION}, got {dimension}"
            )

        logger.info(f"Initializing FAISS IndexFlatIP (dimension={dimension})")
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

    def create_index(self, dimension: int = EXPECTED_DIMENSION):
        """Alias for initialize() to maintain backward-compatibility."""
        self.initialize(dimension=dimension)

    def add_vectors(self, embeddings: np.ndarray, metadata_list: List[Dict[str, Any]]):
        """
        Add normalized vector embeddings and their corresponding metadata.
        Strict invariant: Every vector MUST map to a metadata object, and vice versa.
        """
        if embeddings.size == 0 or len(metadata_list) == 0:
            logger.warning("add_vectors called with empty embeddings or metadata")
            return

        if embeddings.shape[0] != len(metadata_list):
            raise ValueError(
                f"METADATA_MISMATCH: Embeddings count ({embeddings.shape[0]}) does not match metadata count ({len(metadata_list)})"
            )

        dimension = embeddings.shape[1]
        if self.index is None:
            self.initialize(dimension)
        elif self.index.d != dimension:
            raise ValueError(
                f"VECTOR_DIMENSION_MISMATCH: Embedding dimension {dimension} does not match index dimension {self.index.d}"
            )

        start_id = self.index.ntotal

        # Ensure float32 contiguous array
        vectors = np.ascontiguousarray(embeddings, dtype=np.float32)

        # L2-normalize vectors to enforce unit length for cosine similarity
        faiss.normalize_L2(vectors)

        # Add to FAISS index
        self.index.add(vectors)

        # Record metadata mapping for each added vector (Part 11 structure)
        for idx, meta in enumerate(metadata_list):
            vector_id = start_id + idx
            normalized_meta = {
                "vector_index": vector_id,
                "document_id": meta.get("document_id"),
                "filename": meta.get("filename"),
                "chunk_id": meta.get("chunk_id"),
                "chunk_index": meta.get("chunk_index", idx),
                "page_number": meta.get("page_number", meta.get("page")),
                "page": meta.get("page", meta.get("page_number")),
                "section": meta.get("section"),
                "text": meta.get("text", ""),
                "character_count": meta.get("character_count", len(meta.get("text", ""))),
            }
            self.metadata_map[vector_id] = normalized_meta

        # Strict index validation (Part 18)
        if self.index.ntotal != len(self.metadata_map):
            raise ValueError(
                f"INDEX_VALIDATION_ERROR: FAISS total vectors ({self.index.ntotal}) does not match metadata records ({len(self.metadata_map)})"
            )

        self.index_info["vectors"] = self.index.ntotal
        self.index_info["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        logger.info(f"Added {len(metadata_list)} vectors to FAISS index. Total count: {self.index.ntotal}")

    def save(self, directory: Optional[Path] = None):
        """
        Serialize FAISS index binary, metadata mapping, and index summary info to disk atomically.
        Uses temporary files (.tmp) followed by atomic replacement to prevent corruption.
        """
        target_dir = directory or self.vectorstore_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        if self.index is None:
            raise RuntimeError("FAISS_ERROR: Cannot save uninitialized FAISS index.")

        # Strict validation before saving (Part 18 & 19)
        if self.index.d != EXPECTED_DIMENSION:
            raise ValueError(
                f"VECTOR_DIMENSION_MISMATCH: Index dimension is {self.index.d}, expected {EXPECTED_DIMENSION}"
            )
        if self.index.ntotal != len(self.metadata_map):
            raise ValueError(
                f"INDEX_VALIDATION_ERROR: Vector count ({self.index.ntotal}) != metadata records ({len(self.metadata_map)})"
            )

        idx_path = target_dir / "index.faiss"
        meta_path = target_dir / "metadata.json"
        info_path = target_dir / "index_info.json"

        idx_tmp = target_dir / "index.faiss.tmp"
        meta_tmp = target_dir / "metadata.json.tmp"
        info_tmp = target_dir / "index_info.json.tmp"

        try:
            # 1. Save FAISS binary to temp file
            faiss.write_index(self.index, str(idx_tmp))

            # 2. Save metadata JSON as a list of chunk metadata records (Part 11 format)
            metadata_list = [self.metadata_map[i] for i in sorted(self.metadata_map.keys())]
            with open(meta_tmp, "w", encoding="utf-8") as f:
                json.dump(metadata_list, f, indent=2)

            # 3. Save info JSON to temp file
            with open(info_tmp, "w", encoding="utf-8") as f:
                json.dump(self.index_info, f, indent=2)

            # 4. Atomically replace active files with temporary files (Part 17 atomic persistence)
            # On Windows, open handles or rapid rebuilds require retry with backoff
            def _safe_replace(src: Path, dst: Path):
                import shutil
                for attempt in range(5):
                    try:
                        os.replace(src, dst)
                        return
                    except PermissionError:
                        time.sleep(0.05 * (attempt + 1))
                try:
                    shutil.copyfile(src, dst)
                    src.unlink(missing_ok=True)
                except Exception as cp_err:
                    logger.warning(f"File copy fallback notice: {cp_err}")

            _safe_replace(idx_tmp, idx_path)
            _safe_replace(meta_tmp, meta_path)
            _safe_replace(info_tmp, info_path)

            logger.info(f"FAISS index and metadata successfully persisted atomically to: {target_dir}")

        except Exception as exc:
            # Clean up temp files on error
            for tmp in (idx_tmp, meta_tmp, info_tmp):
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except Exception:
                        pass
            logger.error(f"Failed to persist FAISS index atomically: {exc}", exc_info=True)
            raise exc

    def save_index(self, directory: Optional[Path] = None):
        """Alias for save() to maintain backward-compatibility."""
        self.save(directory=directory)

    def load(self, directory: Optional[Path] = None) -> bool:
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
            loaded_index = faiss.read_index(str(idx_path))

            with open(meta_path, "r", encoding="utf-8") as f:
                raw_meta = json.load(f)

            # Support both list format and dict format
            new_metadata_map: Dict[int, Dict[str, Any]] = {}
            if isinstance(raw_meta, list):
                for idx, item in enumerate(raw_meta):
                    v_idx = item.get("vector_index", idx)
                    new_metadata_map[int(v_idx)] = item
            elif isinstance(raw_meta, dict):
                for k, v in raw_meta.items():
                    new_metadata_map[int(k)] = v
            else:
                raise ValueError("Corrupted metadata.json: must be JSON list or object")

            # Validate loaded index (Part 18 & 19)
            if loaded_index.d != EXPECTED_DIMENSION:
                raise ValueError(
                    f"VECTOR_DIMENSION_MISMATCH: Loaded index dimension {loaded_index.d} != {EXPECTED_DIMENSION}"
                )
            if loaded_index.ntotal != len(new_metadata_map):
                raise ValueError(
                    f"INDEX_VALIDATION_ERROR: FAISS vectors ({loaded_index.ntotal}) != metadata records ({len(new_metadata_map)})"
                )

            self.index = loaded_index
            self.metadata_map = new_metadata_map

            if info_path.exists():
                with open(info_path, "r", encoding="utf-8") as f:
                    self.index_info = json.load(f)
            else:
                self.index_info = {
                    "index_type": "IndexFlatIP",
                    "metric": "Cosine Similarity (Normalized Inner Product)",
                    "dimension": self.index.d,
                    "vectors": self.index.ntotal,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }

            logger.info(
                f"FAISS index loaded successfully with {self.index.ntotal} vectors (dimension={self.index.d})"
            )
            return True

        except Exception as exc:
            logger.error(f"FAISS_ERROR: Failed to load FAISS index from {target_dir}: {exc}", exc_info=True)
            self.index = None
            self.metadata_map = {}
            self.index_info = {}
            return False

    def load_index(self, directory: Optional[Path] = None) -> bool:
        """Alias for load() to maintain backward-compatibility."""
        return self.load(directory=directory)

    def rebuild(self, embeddings: np.ndarray, metadata_list: List[Dict[str, Any]], directory: Optional[Path] = None):
        """
        Completely reset and rebuild the FAISS index with new embeddings and metadata, then save to disk.
        """
        dimension = embeddings.shape[1] if embeddings.size > 0 else EXPECTED_DIMENSION
        self.initialize(dimension=dimension)
        if embeddings.size > 0:
            self.add_vectors(embeddings, metadata_list)
        self.save(directory=directory)
        logger.info(f"FAISS index rebuilt and persisted with {self.count()} vectors.")

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        min_score: Optional[float] = None,
        document_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute cosine similarity search with normalized query vector and return ranked results.
        Filters out any chunks with similarity score < min_score if specified (Part 24).
        If document_id is provided, filters results to only chunks belonging to that document.
        """
        if not self.is_built:
            logger.warning("Search failed: FAISS index is not built or empty")
            return []

        # Ensure query is 2D float32 contiguous array
        q_vec = np.ascontiguousarray(query_vector, dtype=np.float32)
        if q_vec.ndim == 1:
            q_vec = q_vec.reshape(1, -1)

        # L2-normalize query vector for exact cosine similarity
        faiss.normalize_L2(q_vec)

        # Determine search depth k (full depth if filtering by document_id to find document's best chunks)
        if document_id:
            k = max(1, self.index.ntotal)
        else:
            k = max(1, min(top_k, self.index.ntotal))

        # Perform search
        scores, indices = self.index.search(q_vec, k)

        results: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue

            similarity_score = float(score)

            # Threshold filtering (Part 24 requirement when min_score is provided)
            if min_score is not None and similarity_score < min_score:
                logger.debug(
                    f"Filtered out chunk index {idx} with score {similarity_score:.4f} < min_score {min_score}"
                )
                continue

            meta = self.metadata_map.get(int(idx), {})

            # Document ID filter
            if document_id and str(meta.get("document_id")) != str(document_id):
                continue

            results.append({
                "vector_id": int(idx),
                "score": round(similarity_score, 4),
                "chunk_id": meta.get("chunk_id"),
                "document_id": meta.get("document_id"),
                "filename": meta.get("filename"),
                "chunk_index": meta.get("chunk_index"),
                "page": meta.get("page_number") or meta.get("page"),
                "page_number": meta.get("page_number") or meta.get("page"),
                "section": meta.get("section"),
                "text": meta.get("text"),
                "character_count": meta.get("character_count"),
            })

            if len(results) >= top_k:
                break

        logger.info(
            f"FAISS search returned {len(results)} matches for top_k={top_k} (doc_id={document_id}, min_score={min_score})"
        )
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
            "index_path": str(self.index_file.as_posix()),
            "metadata_path": str(self.metadata_file.as_posix()),
        }


# Global singleton instance
vector_store = FAISSVectorStore()
# Global service alias
vector_service = vector_store
