import logging
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.embeddings import embedding_service, EmbeddingService
from app.rag.vector_store import vector_store, FAISSVectorStore

logger = logging.getLogger("enterprise_rag.rag.pipeline")


class RAGPipeline:
    """
    Orchestration layer connecting PostgreSQL processed document chunks,
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
        Extract all chunks from processed documents in PostgreSQL, generate dense embeddings,
        build the FAISS IndexFlatIP, and serialize to disk.
        """
        logger.info("Starting Knowledge Base vector index construction...")

        # 1. Query all processed documents
        processed_docs_stmt = select(Document).where(Document.processing_status == "processed")
        processed_docs = db.scalars(processed_docs_stmt).all()

        if not processed_docs:
            logger.warning("Build aborted: No processed documents found in PostgreSQL.")
            return {
                "success": False,
                "status": "no_processed_chunks",
                "message": "No processed document chunks are available for indexing. Please upload and process documents first.",
                "documents": 0,
                "chunks": 0,
                "vectors": 0,
            }

        # 2. Query all chunks for these processed documents
        doc_ids = [d.id for d in processed_docs]
        chunks_stmt = (
            select(DocumentChunk, Document.original_filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.document_id.in_(doc_ids))
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index.asc())
        )
        chunk_rows = db.execute(chunks_stmt).all()

        if not chunk_rows:
            logger.warning("Build aborted: Processed documents contain 0 chunk records.")
            return {
                "success": False,
                "status": "no_processed_chunks",
                "message": "No chunks found for processed documents.",
                "documents": len(processed_docs),
                "chunks": 0,
                "vectors": 0,
            }

        # 3. Prepare chunk texts and metadata dictionaries
        texts: List[str] = []
        metadata_list: List[Dict[str, Any]] = []

        for chunk_model, orig_filename in chunk_rows:
            texts.append(chunk_model.text)
            metadata_list.append({
                "chunk_id": chunk_model.id,
                "document_id": chunk_model.document_id,
                "filename": orig_filename,
                "chunk_index": chunk_model.chunk_index,
                "page": chunk_model.page_number,
                "section": chunk_model.section,
                "text": chunk_model.text,
                "character_count": chunk_model.character_count,
            })

        total_chunks = len(texts)
        logger.info(f"Embedding {total_chunks} chunks across {len(processed_docs)} documents...")

        # 4. Generate batch embeddings via SentenceTransformers
        embeddings = self.embedding_service.embed_documents(texts)
        dimension = embeddings.shape[1]

        # 5. Create fresh FAISS index and add vectors atomically (prevents duplicate vectors)
        self.vector_store.create_index(dimension)
        self.vector_store.add_vectors(embeddings, metadata_list)

        # 6. Save persistent index and metadata files to disk
        self.vector_store.save_index()

        logger.info(
            f"Knowledge base successfully built: {self.vector_store.total_vectors} vectors, "
            f"dimension={dimension}, model='{self.embedding_service.model_name}'"
        )

        return {
            "success": True,
            "status": "built",
            "documents": len(processed_docs),
            "chunks": total_chunks,
            "vectors": self.vector_store.total_vectors,
            "embedding_model": self.embedding_service.model_name,
            "embedding_dimension": dimension,
            "message": f"Successfully indexed {total_chunks} chunks into FAISS vector database.",
        }

    def search_knowledge_base(
        self,
        query: str,
        top_k: int = 5,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Execute cosine similarity retrieval against the FAISS vector database.
        """
        # Validate query string
        if not query or not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query cannot be empty or only whitespace.",
            )

        # Ensure FAISS index is loaded
        if not self.vector_store.is_built:
            # Attempt to load from disk
            loaded = self.vector_store.load_index()
            if not loaded or not self.vector_store.is_built:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Knowledge base has not been built yet. Please build the knowledge base first.",
                )

        # Validate top_k
        if top_k <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="top_k must be a positive integer greater than 0.",
            )
        k = min(top_k, 50)

        # Generate normalized query vector
        query_vec = self.embedding_service.embed_text(query)

        # Search FAISS
        raw_results = self.vector_store.search(query_vec, top_k=k)

        # Format output items
        formatted_results: List[Dict[str, Any]] = []
        for item in raw_results:
            formatted_results.append({
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "filename": item.get("filename"),
                "page": item.get("page"),
                "section": item.get("section"),
                "text": item.get("text"),
                "score": round(item.get("score", 0.0), 4),
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
