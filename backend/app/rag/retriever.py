import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.rag.embeddings import embedding_service, EmbeddingService
from app.rag.vector_store import vector_store, FAISSVectorStore
from app.rag.schemas import CandidateChunk

logger = logging.getLogger("enterprise_rag.rag.retriever")


class RAGRetriever:
    """
    Retrieves top-K candidate chunks from the persistent FAISS vector store
    for a given natural language query.
    """

    def __init__(
        self,
        embed_service: Optional[EmbeddingService] = None,
        v_store: Optional[FAISSVectorStore] = None,
    ):
        self.embedding_service = embed_service or embedding_service
        self.vector_store = v_store or vector_store

    def normalize_query(self, query: str) -> str:
        """
        Normalize query string: trim leading/trailing whitespace without altering semantic meaning.
        """
        if not query or not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query cannot be empty or only whitespace.",
            )
        # Collapse multiple spaces into single space, keep original wording and case
        cleaned = " ".join(query.strip().split())
        return cleaned

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        db: Optional[Session] = None,
        document_id: Optional[str] = None,
    ) -> List[CandidateChunk]:
        """
        Embed the normalized query, query FAISS, and return candidate chunks.
        Optionally filter by document_id.
        """
        clean_query = self.normalize_query(query)

        # Ensure FAISS vector index is active
        if not self.vector_store.is_built:
            loaded = self.vector_store.load_index()
            if not loaded or not self.vector_store.is_built:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Knowledge base is not ready. Please process documents and build the knowledge base before asking questions.",
                )

        # Enforce clamped top_k (between 1 and 10)
        req_k = top_k or settings.RAG_TOP_K
        k = max(1, min(req_k, 10))

        logger.info(f"Retrieving top-{k} candidates for query: '{clean_query[:60]}...' (doc_id={document_id})")

        # 1. Generate normalized query embedding
        query_vec = self.embedding_service.embed_text(clean_query)

        # 2. Search FAISS index with optional document filtering
        raw_matches = self.vector_store.search(
            query_vec,
            top_k=k,
            document_id=document_id,
        )

        # 3. Map into structured CandidateChunk objects
        candidates: List[CandidateChunk] = []
        for match in raw_matches:
            candidates.append(
                CandidateChunk(
                    chunk_id=str(match.get("chunk_id") or f"vec-{match.get('vector_id')}"),
                    document_id=str(match.get("document_id") or "unknown-doc"),
                    filename=str(match.get("filename") or "Document"),
                    chunk_index=int(match.get("chunk_index") or 0),
                    page=match.get("page"),
                    section=match.get("section"),
                    text=str(match.get("text") or ""),
                    character_count=int(match.get("character_count") or len(match.get("text") or "")),
                    score=float(match.get("score", 0.0)),
                )
            )

        logger.info(f"Retriever found {len(candidates)} raw candidate chunks in FAISS.")
        return candidates


# Global singleton instance
rag_retriever = RAGRetriever()
