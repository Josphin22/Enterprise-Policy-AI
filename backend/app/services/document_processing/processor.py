import logging
from pathlib import Path
from typing import Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.document_processing.pdf_loader import pdf_loader
from app.services.document_processing.docx_loader import docx_loader
from app.services.document_processing.txt_loader import txt_loader
from app.services.document_processing.text_cleaner import text_cleaner
from app.services.document_processing.chunker import document_chunker, ProcessedChunk
from app.services.document_processing.base_loader import ExtractedBlock

logger = logging.getLogger("enterprise_rag.document_processing.processor")


class DocumentProcessor:
    """
    Orchestrates the complete document ingestion pipeline:
    File validation -> Loader -> Text extraction -> Cleaning -> Chunking -> PostgreSQL persistence.
    """

    @staticmethod
    def process_document(document_id: str, db: Session) -> Dict[str, Any]:
        logger.info(f"Starting document processing pipeline for ID: {document_id}")

        # 1. Retrieve document record
        document = db.get(Document, document_id)
        if not document:
            logger.warning(f"Processing failed: document ID '{document_id}' not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' was not found.",
            )

        # 2. Validate physical file exists
        file_path = Path(document.file_path)
        if not file_path.exists() or not file_path.is_file():
            logger.error(f"Processing failed: physical file missing at '{file_path}'")
            document.processing_status = "failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Physical file for document '{document.original_filename}' is missing on disk.",
            )

        # 3. Mark status as 'processing'
        document.processing_status = "processing"
        db.commit()

        try:
            # 4. Select appropriate loader
            file_type = (document.file_type or "").lower().lstrip(".")
            logger.info(f"Document {document_id} detected format: '{file_type}'")

            if file_type == "pdf":
                raw_blocks = pdf_loader.load(file_path)
            elif file_type == "docx":
                raw_blocks = docx_loader.load(file_path)
            elif file_type == "txt":
                raw_blocks = txt_loader.load(file_path)
            else:
                raise ValueError(f"Unsupported document type: '{file_type}'")

            # 5. Clean text in each extracted block
            cleaned_blocks: List[ExtractedBlock] = []
            total_chars = 0
            for block in raw_blocks:
                cleaned_text = text_cleaner.clean(block.text)
                if cleaned_text:
                    total_chars += len(cleaned_text)
                    cleaned_blocks.append(
                        ExtractedBlock(
                            text=cleaned_text,
                            page_number=block.page_number,
                            section=block.section,
                            metadata=block.metadata,
                            warning=block.warning,
                        )
                    )

            logger.info(f"Text extraction completed: {len(cleaned_blocks)} blocks, {total_chars} characters.")

            # 6. Chunking
            chunks: List[ProcessedChunk] = document_chunker.create_chunks(
                document_id=document.id,
                filename=document.original_filename,
                file_type=file_type,
                extracted_blocks=cleaned_blocks,
            )

            # 7. Transactional Chunk Persistence (Remove old chunks if reprocessing)
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

            # 8. Batch insert new chunks
            chunk_records: List[DocumentChunk] = []
            for chunk in chunks:
                chunk_records.append(
                    DocumentChunk(
                        id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        page_number=chunk.page_number,
                        section=chunk.section,
                        character_count=chunk.character_count,
                    )
                )

            if chunk_records:
                db.add_all(chunk_records)

            # 9. Update document status and chunk_count
            document.chunk_count = len(chunk_records)
            document.processing_status = "processed"

            db.commit()
            db.refresh(document)

            logger.info(
                f"Successfully processed document {document_id}: "
                f"status='{document.processing_status}', chunks={document.chunk_count}"
            )

            return {
                "success": True,
                "document_id": document.id,
                "status": document.processing_status,
                "chunk_count": document.chunk_count,
                "message": f"Successfully processed document into {document.chunk_count} chunks.",
            }

        except Exception as proc_err:
            db.rollback()
            logger.error(f"Processing error for document {document_id}: {proc_err}", exc_info=True)

            # Mark status as failed safely
            try:
                failed_doc = db.get(Document, document_id)
                if failed_doc:
                    failed_doc.processing_status = "failed"
                    db.commit()
            except Exception as update_err:
                logger.error(f"Failed to update document status to failed: {update_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document processing failed: {str(proc_err)}",
            )


document_processor = DocumentProcessor()
