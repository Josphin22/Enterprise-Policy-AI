import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.config import settings
from app.schemas.system import (
    SystemStatusResponse,
    ComponentStatus,
    KnowledgeBaseStatusResponse,
)
from app.database.connection import check_db_connection
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.embeddings import embedding_service
from app.rag.vector_store import vector_store
from app.llm.service import llm_service

logger = logging.getLogger("enterprise_rag.system")


class SystemService:
    @staticmethod
    def get_system_status() -> SystemStatusResponse:
        """
        Return the operational status of all enterprise RAG subsystems.
        Probes PostgreSQL, FAISS vector store, SentenceTransformers model status, and local Ollama daemon.
        """
        db_is_healthy = check_db_connection()

        # Check if FAISS index is loaded on disk
        if not vector_store.is_built:
            vector_store.load_index()

        v_status = "healthy" if vector_store.is_built else "not_configured"
        v_details = (
            f"FAISS IndexFlatIP online with {vector_store.total_vectors} indexed vectors."
            if vector_store.is_built
            else "FAISS similarity vector index not yet built."
        )

        m_status = "loaded" if embedding_service.is_loaded else "not_loaded"
        m_details = (
            f"{settings.EMBEDDING_MODEL_NAME} model active in memory (dim={embedding_service.get_dimension()})."
            if embedding_service.is_loaded
            else f"{settings.EMBEDDING_MODEL_NAME} embedding model ready to load on-demand."
        )

        # Probe Ollama local LLM status
        llm_stat = llm_service.get_status()
        if llm_stat["status"] == "available":
            llm_component_status = "healthy"
            llm_details = f"Local Ollama model '{settings.OLLAMA_MODEL}' operational."
        elif llm_stat["status"] == "model_not_found":
            llm_component_status = "not_configured"
            llm_details = f"Ollama daemon online, but model '{settings.OLLAMA_MODEL}' is not pulled."
        else:
            llm_component_status = "unavailable"
            llm_details = f"Local Ollama daemon unreachable at {settings.OLLAMA_BASE_URL}."

        return SystemStatusResponse(
            backend=ComponentStatus(
                status="healthy",
                details="FastAPI microservice runtime operational.",
            ),
            database=ComponentStatus(
                status="healthy" if db_is_healthy else "unavailable",
                details="PostgreSQL persistence layer online."
                if db_is_healthy
                else "PostgreSQL database is currently unreachable.",
            ),
            vector_database=ComponentStatus(
                status=v_status,
                details=v_details,
                type="FAISS",
                vectors=vector_store.total_vectors,
            ),
            embedding_model=ComponentStatus(
                status=m_status,
                details=m_details,
                name=settings.EMBEDDING_MODEL_NAME,
            ),
            llm=ComponentStatus(
                status=llm_component_status,
                details=llm_details,
                name=settings.OLLAMA_MODEL,
                type="Ollama",
            ),
        )

    @staticmethod
    def get_knowledge_base_status(db: Session) -> KnowledgeBaseStatusResponse:
        """
        Return the current knowledge base status with actual PostgreSQL document/chunk counts
        and live FAISS vector store metrics.
        """
        total_docs = 0
        processed_docs = 0
        total_chunks = 0

        try:
            total_docs = db.scalar(select(func.count()).select_from(Document)) or 0
            processed_docs = (
                db.scalar(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.processing_status == "processed")
                )
                or 0
            )
            total_chunks = db.scalar(select(func.count()).select_from(DocumentChunk)) or 0
        except Exception as exc:
            logger.warning(f"Error querying knowledge base counts: {exc}")

        # Ensure FAISS index is loaded if available
        if not vector_store.is_built:
            vector_store.load()

        kb_is_ready = vector_store.is_built and vector_store.total_vectors > 0
        dim = vector_store.index.d if vector_store.index is not None else 384

        return KnowledgeBaseStatusResponse(
            status="ready" if kb_is_ready else "not_built",
            documents=total_docs,
            processed_documents=processed_docs,
            chunks=total_chunks,
            vectors=vector_store.total_vectors,
            dimension=dim,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=dim,
            index_type="IndexFlatIP",
            index_path=(settings.VECTORSTORE_DIR / "index.faiss").as_posix(),
            metadata_path=(settings.VECTORSTORE_DIR / "metadata.json").as_posix(),
            vector_database="FAISS",
            rag_status="retrieval_ready" if kb_is_ready else "not_ready",
            last_built=vector_store.index_info.get("updated_at"),
        )


system_service = SystemService()
