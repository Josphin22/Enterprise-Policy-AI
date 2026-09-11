"""
Enterprise Policy AI - VectorStore Build & Retrieval Service (Phase 4)
Orchestrates reading real chunks from PostgreSQL/SQLite, local embedding generation,
FAISS IndexFlatIP construction, atomic persistence, status monitoring, and semantic search.
"""

import logging
import threading
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.database.session import SessionLocal
from app.rag.vector_store import vector_store, FAISSVectorStore, EXPECTED_DIMENSION
from services.embedding_service import embedding_service, EmbeddingService

logger = logging.getLogger("enterprise_rag.services.vectorstore")

# Concurrency lock to prevent simultaneous duplicate rebuilds (Part 34)
_BUILD_LOCK = threading.Lock()


class VectorStoreService:
    """
    Centralized vector store service managing FAISS IndexFlatIP lifecycle,
    chunk ingestion, vector search, and status reporting.
    """

    def __init__(
        self,
        v_store: Optional[FAISSVectorStore] = None,
        embed_service: Optional[EmbeddingService] = None,
    ):
        self.vector_store = v_store or vector_store
        self.embedding_service = embed_service or embedding_service

    def is_building(self) -> bool:
        """Check if an index build is currently in progress."""
        return _BUILD_LOCK.locked()

    def build_index(self, db: Optional[Session] = None, force: bool = False) -> Dict[str, Any]:
        """
        Extract valid chunks from PostgreSQL/SQLite, generate batch embeddings,
        create a fresh FAISS IndexFlatIP index, and persist atomically to disk.
        Guarantees zero duplicate vectors across rebuilds (Part 15 & 16).
        """
        # Concurrency check (Part 34)
        if not _BUILD_LOCK.acquire(blocking=False):
            logger.warning("Build rejected: Index build is already in progress.")
            return {
                "status": "in_progress",
                "message": "Build already in progress.",
                "documents": 0,
                "chunks": 0,
                "vectors": self.vector_store.total_vectors,
                "dimension": EXPECTED_DIMENSION,
            }

        close_session = False
        session = db
        if session is None:
            session = SessionLocal()
            close_session = True

        try:
            logger.info("Starting knowledge base index build...")

            # 1. Query all chunks ordered by document_id and chunk_index (Part 6)
            chunks_stmt = (
                select(DocumentChunk, Document.original_filename, Document.processing_status)
                .join(Document, DocumentChunk.document_id == Document.id)
                .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index.asc())
            )
            chunk_rows = session.execute(chunks_stmt).all()

            # 2. Filter and validate chunks (Part 6 requirement)
            # Only embed valid chunks; skip NULL text, empty text, whitespace-only text
            valid_texts: List[str] = []
            valid_metadata: List[Dict[str, Any]] = []
            distinct_doc_ids = set()

            for chunk_model, orig_filename, proc_status in chunk_rows:
                raw_text = chunk_model.text
                if not raw_text or not raw_text.strip():
                    logger.debug(f"Skipping empty or whitespace chunk ID {chunk_model.id}")
                    continue

                cleaned_text = raw_text.strip()
                valid_texts.append(cleaned_text)
                distinct_doc_ids.add(chunk_model.document_id)

                valid_metadata.append({
                    "chunk_id": chunk_model.id,
                    "document_id": chunk_model.document_id,
                    "filename": orig_filename,
                    "chunk_index": chunk_model.chunk_index,
                    "page_number": chunk_model.page_number,
                    "page": chunk_model.page_number,
                    "section": chunk_model.section,
                    "text": cleaned_text,
                    "character_count": len(cleaned_text),
                })

            total_valid_chunks = len(valid_texts)
            total_docs = len(distinct_doc_ids)

            # 3. Empty database handling (Part 14)
            if total_valid_chunks == 0:
                logger.info("No valid document chunks available in database to index.")
                # Clear existing in-memory index
                self.vector_store.clear()
                return {
                    "status": "empty",
                    "message": "No vectors available. No valid processed document chunks found.",
                    "documents": 0,
                    "chunks": 0,
                    "vectors": 0,
                    "dimension": EXPECTED_DIMENSION,
                }

            logger.info(
                f"Generating real local embeddings for {total_valid_chunks} chunks across {total_docs} documents..."
            )

            # 4. Generate real batch embeddings locally via SentenceTransformers (Part 7)
            embeddings = self.embedding_service.embed_texts(
                valid_texts,
                batch_size=settings.EMBEDDING_BATCH_SIZE,
            )

            # 5. Programmatic dimension check (Part 3 & 19)
            emb_dim = embeddings.shape[1]
            if emb_dim != EXPECTED_DIMENSION:
                raise ValueError(
                    f"VECTOR_DIMENSION_MISMATCH: Embedding dimension {emb_dim} != expected {EXPECTED_DIMENSION}"
                )

            logger.info(f"Generated embeddings matrix: shape={embeddings.shape}")

            # 6. Create brand NEW FAISS IndexFlatIP (Part 9 & 15)
            # Completely resets in-memory index to ensure no vector duplication
            self.vector_store.initialize(dimension=emb_dim)

            # 7. Add vectors and metadata
            self.vector_store.add_vectors(embeddings, valid_metadata)

            # 8. Strict index validation (Part 18)
            num_vectors = self.vector_store.total_vectors
            num_meta = len(self.vector_store.metadata_map)
            if num_vectors != total_valid_chunks or num_meta != total_valid_chunks:
                raise ValueError(
                    f"INDEX_VALIDATION_ERROR: Mismatch during build: "
                    f"chunks={total_valid_chunks}, vectors={num_vectors}, metadata={num_meta}"
                )

            # 9. Atomic persistence to disk (Part 10 & 17)
            self.vector_store.save()

            logger.info(
                f"Knowledge base successfully built and persisted: {num_vectors} vectors, "
                f"dimension={emb_dim}, model='{self.embedding_service.model_name}'"
            )

            return {
                "status": "success",
                "message": f"Successfully indexed {num_vectors} chunks into FAISS vector database.",
                "documents": total_docs,
                "chunks": total_valid_chunks,
                "vectors": num_vectors,
                "dimension": emb_dim,
                "embedding_model": self.embedding_service.model_name,
            }

        except Exception as exc:
            logger.error(f"Error occurred during vector index build: {exc}", exc_info=True)
            raise exc

        finally:
            if close_session:
                session.close()
            _BUILD_LOCK.release()

    def load_index(self) -> bool:
        """
        Load the persistent FAISS index from disk.
        Returns True if loaded, False if not built or corrupted.
        """
        return self.vector_store.load()

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.35,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic vector search with normalized query embedding and cosine similarity ranking.
        Filters results by min_score threshold (Part 24).
        """
        if not query or not query.strip():
            return []

        # Ensure index is active or load from disk
        if not self.vector_store.is_built:
            loaded = self.load_index()
            if not loaded or not self.vector_store.is_built:
                raise RuntimeError("KNOWLEDGE_BASE_NOT_BUILT")

        # Clamp top_k
        k = max(1, min(top_k, 50))

        # Generate query vector with the same embedding model (Part 25)
        query_vec = self.embedding_service.embed_text(query.strip())

        # Perform cosine similarity retrieval in FAISS
        raw_results = self.vector_store.search(query_vec, top_k=k, min_score=min_score)

        # Format output items (Part 20, 21, 28)
        formatted: List[Dict[str, Any]] = []
        for item in raw_results:
            formatted.append({
                "score": item["score"],
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "filename": item.get("filename"),
                "chunk_index": item.get("chunk_index"),
                "page_number": item.get("page_number"),
                "text": item.get("text", ""),
                "section": item.get("section"),
            })

        return formatted

    def get_status(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Return comprehensive knowledge base status (Part 27).
        """
        close_session = False
        session = db
        if session is None:
            session = SessionLocal()
            close_session = True

        total_docs = 0
        total_chunks = 0
        processed_docs = 0

        try:
            total_docs = session.scalar(select(func.count()).select_from(Document)) or 0
            processed_docs = (
                session.scalar(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.processing_status == "processed")
                )
                or 0
            )
            total_chunks = session.scalar(select(func.count()).select_from(DocumentChunk)) or 0
        except Exception as exc:
            logger.warning(f"Failed to query database document/chunk counts: {exc}")
        finally:
            if close_session:
                session.close()

        # Check if index is loaded
        if not self.vector_store.is_built:
            self.load_index()

        idx_ready = self.vector_store.is_built and self.vector_store.total_vectors > 0
        dim = self.vector_store.index.d if self.vector_store.index is not None else EXPECTED_DIMENSION

        idx_path = (settings.VECTORSTORE_DIR / "index.faiss").as_posix()
        meta_path = (settings.VECTORSTORE_DIR / "metadata.json").as_posix()

        status_str = "ready" if idx_ready else "not_built"

        return {
            "status": status_str,
            "documents": total_docs,
            "processed_documents": processed_docs,
            "chunks": total_chunks,
            "vectors": self.vector_store.total_vectors,
            "dimension": dim,
            "embedding_model": self.embedding_service.model_name,
            "index_type": "IndexFlatIP",
            "index_path": idx_path,
            "metadata_path": meta_path,
            "vector_database": "FAISS",
            "rag_status": "retrieval_ready" if idx_ready else "not_ready",
            "last_built": self.vector_store.index_info.get("updated_at"),
        }


# Global singleton instance
vectorstore_service = VectorStoreService()


# Top-level module convenience functions matching Part 13
def build_index(db: Optional[Session] = None, force: bool = False) -> Dict[str, Any]:
    return vectorstore_service.build_index(db=db, force=force)


def load_index() -> bool:
    return vectorstore_service.load_index()


def search(query: str, top_k: int = 5, min_score: float = 0.35, db: Optional[Session] = None) -> List[Dict[str, Any]]:
    return vectorstore_service.search(query=query, top_k=top_k, min_score=min_score, db=db)


def get_status(db: Optional[Session] = None) -> Dict[str, Any]:
    return vectorstore_service.get_status(db=db)
