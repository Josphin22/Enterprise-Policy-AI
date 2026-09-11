import logging
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.rag.embeddings import embedding_service, EmbeddingService
from app.rag.vector_store import vector_store, FAISSVectorStore

logger = logging.getLogger("enterprise_rag.rag.pipeline")


class RAGPipeline:
    """
    Orchestration layer connecting database processed document chunks,
    SentenceTransformers embeddings, and the persistent local FAISS vector store.
    """

    def __init__(
        self,
        embed_service: Optional[EmbeddingService] = None,
        v_store: Optional[FAISSVectorStore] = None,
    ):
        self.embedding_service = embed_service or embedding_service
        self.vector_store = v_store or vector_store

    def build_knowledge_base(self, db: Session) -> Dict[str, Any]:
        """
        Build or rebuild the FAISS IndexFlatIP from processed database chunks.
        Guarantees zero duplicate vectors and atomic file persistence.
        """
        from services.vectorstore_service import VectorStoreService
        logger.info("Executing Knowledge Base vector index construction via vectorstore_service...")
        svc = VectorStoreService(v_store=self.vector_store, embed_service=self.embedding_service)
        result = svc.build_index(db=db)

        raw_status = result.get("status", "built")
        if raw_status == "success":
            norm_status = "built"
        elif raw_status == "empty":
            norm_status = "no_processed_chunks"
        else:
            norm_status = raw_status

        success = raw_status in ("success", "built")
        return {
            "success": success,
            "status": norm_status,
            "documents": result.get("documents", 0),
            "chunks": result.get("chunks", 0),
            "vectors": result.get("vectors", 0),
            "dimension": result.get("dimension", 384),
            "embedding_model": result.get("embedding_model", self.embedding_service.model_name),
            "embedding_dimension": result.get("dimension", 384),
            "message": result.get("message", "Build completed"),
        }

    def search_knowledge_base(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.35,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Execute cosine similarity retrieval against the FAISS vector database.
        Applies minimum similarity score threshold (default 0.35).
        Raises HTTP 409 KNOWLEDGE_BASE_NOT_BUILT if index has not been built.
        """
        # Validate query string
        if not query or not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query cannot be empty or only whitespace.",
            )

        # Check if vector index is built (Part 29)
        if not self.vector_store.is_built:
            # Check if index exists on disk
            loaded = self.vector_store.load()
            if not loaded or not self.vector_store.is_built:
                logger.warning("Search rejected: Knowledge base has not been built yet.")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="KNOWLEDGE_BASE_NOT_BUILT",
                )

        # Validate top_k
        if top_k <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="top_k must be a positive integer greater than 0.",
            )
        k = min(top_k, 50)

        # Generate normalized query vector with the exact same embedding model (Part 25)
        query_vec = self.embedding_service.embed_text(query.strip())

        # Search FAISS with min_score threshold filtering (Part 24)
        raw_results = self.vector_store.search(query_vec, top_k=k, min_score=min_score)

        # Format output items (Part 20, 21, 28)
        formatted_results: List[Dict[str, Any]] = []
        for item in raw_results:
            formatted_results.append({
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "filename": item.get("filename"),
                "chunk_index": item.get("chunk_index"),
                "page": item.get("page_number") or item.get("page"),
                "page_number": item.get("page_number") or item.get("page"),
                "section": item.get("section"),
                "text": item.get("text", ""),
                "score": round(float(item.get("score", 0.0)), 4),
            })

        return {
            "query": query.strip(),
            "results": formatted_results,
            "total_matches": len(formatted_results),
        }

    def reindex_document(self, document_id: str, db: Session) -> Dict[str, Any]:
        """
        Verify document exists and is processed, then trigger a clean knowledge base rebuild.
        """
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' not found.",
            )

        if doc.processing_status != "processed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document '{doc.original_filename}' has not been processed yet (status='{doc.processing_status}').",
            )

        logger.info(f"Re-indexing knowledge base triggered for document ID: {document_id}")
        return self.build_knowledge_base(db)


# Global singleton instance
rag_pipeline = RAGPipeline()
