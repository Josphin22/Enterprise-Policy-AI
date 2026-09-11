import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

logger = logging.getLogger("enterprise_rag.document_processing.processor")


class DocumentProcessor:
    """
    Orchestrates the document processing pipeline.
    Delegates to DocumentService.reprocess_document for unified, transactional chunking.
    """

    @staticmethod
    def process_document(document_id: str, db: Session) -> Dict[str, Any]:
        from app.services.document_service import document_service
        return document_service.reprocess_document(document_id, db)


document_processor = DocumentProcessor()
