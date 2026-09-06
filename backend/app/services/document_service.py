import logging
from pathlib import Path
from typing import List, Optional
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_metadata import DocumentMetadata
from app.utils.file_utils import (
    sanitize_filename,
    generate_document_id,
    get_file_extension,
    is_allowed_extension,
)
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentProcessResponse,
    DocumentDeleteResponse,
    DocumentChunksResponse,
    ChunkResponse,
)

logger = logging.getLogger("enterprise_rag.documents")


class DocumentService:
    @staticmethod
    async def save_uploaded_file(file: UploadFile, db: Session) -> DocumentResponse:
        """
        Validate, save file to disk, and persist Document record in PostgreSQL.
        """
        if not file.filename:
            logger.warning("Upload rejected: missing filename")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty.",
            )

        clean_original_name = sanitize_filename(file.filename)
        file_ext = get_file_extension(clean_original_name).lstrip(".")

        if not is_allowed_extension(clean_original_name):
            logger.warning(f"Upload rejected: unsupported file extension '{file_ext}'")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{file_ext}'. Allowed formats: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}",
            )

        doc_id = generate_document_id()
        stored_filename = f"{doc_id}_{clean_original_name}"
        destination_path = settings.DOCUMENTS_DIR / stored_filename

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

        try:
            contents = await file.read()
            total_bytes = len(contents)

            if total_bytes > max_bytes:
                logger.warning(
                    f"Upload rejected: file size {total_bytes} exceeds limit {max_bytes}"
                )
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                )

            with open(destination_path, "wb") as buffer:
                buffer.write(contents)

        except HTTPException:
            raise
        except Exception as e:
            if destination_path.exists():
                destination_path.unlink()
            logger.error(f"File write failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store uploaded file: {str(e)}",
            )

        # Create Document record in PostgreSQL
        try:
            doc_record = Document(
                id=doc_id,
                filename=stored_filename,
                original_filename=clean_original_name,
                file_type=file_ext,
                file_size=total_bytes,
                file_path=str(destination_path),
                processing_status="uploaded",
                chunk_count=0,
            )
            db.add(doc_record)
            db.commit()
            db.refresh(doc_record)
            logger.info(f"Document registered in PostgreSQL: id={doc_id}, original_name={clean_original_name}")
        except Exception as db_err:
            db.rollback()
            if destination_path.exists():
                destination_path.unlink()
            logger.error(f"Database insertion failed for document {doc_id}: {db_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save document metadata in database.",
            )

        return DocumentResponse(
            success=True,
            document_id=doc_record.id,
            filename=doc_record.original_filename,
            original_filename=doc_record.original_filename,
            file_type=doc_record.file_type,
            size=doc_record.file_size,
            status=doc_record.processing_status,
            chunk_count=doc_record.chunk_count,
            uploaded_at=doc_record.upload_date.isoformat() if doc_record.upload_date else None,
        )

    @staticmethod
    def list_all_documents(db: Session) -> DocumentListResponse:
        """
        List all enterprise policy documents from PostgreSQL.
        """
        stmt = select(Document).order_by(Document.upload_date.desc())
        docs = db.scalars(stmt).all()

        documents: List[DocumentResponse] = [
            DocumentResponse(
                success=True,
                document_id=doc.id,
                filename=doc.original_filename,
                original_filename=doc.original_filename,
                file_type=doc.file_type,
                size=doc.file_size,
                status=doc.processing_status,
                chunk_count=doc.chunk_count,
                uploaded_at=doc.upload_date.isoformat() if doc.upload_date else None,
            )
            for doc in docs
        ]

        return DocumentListResponse(
            documents=documents,
            total=len(documents),
        )

    @staticmethod
    def get_document_by_id(document_id: str, db: Session) -> DocumentResponse:
        """
        Retrieve document metadata from PostgreSQL by ID.
        """
        doc = db.get(Document, document_id)
        if not doc:
            logger.warning(f"Document lookup failed: ID '{document_id}' not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' was not found.",
            )

        return DocumentResponse(
            success=True,
            document_id=doc.id,
            filename=doc.original_filename,
            original_filename=doc.original_filename,
            file_type=doc.file_type,
            size=doc.file_size,
            status=doc.processing_status,
            chunk_count=doc.chunk_count,
            uploaded_at=doc.upload_date.isoformat() if doc.upload_date else None,
        )

    @staticmethod
    def delete_document_by_id(document_id: str, db: Session) -> DocumentDeleteResponse:
        """
        Delete document record from PostgreSQL and delete physical file from disk.
        """
        doc = db.get(Document, document_id)
        if not doc:
            logger.warning(f"Document delete failed: ID '{document_id}' not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' was not found.",
            )

        stored_path = Path(doc.file_path)

        # Delete physical file
        if stored_path.exists() and stored_path.is_file():
            try:
                stored_path.unlink()
            except Exception as e:
                logger.error(f"Failed to unlink file {stored_path}: {e}")

        # Delete from PostgreSQL
        try:
            db.delete(doc)
            db.commit()
            logger.info(f"Successfully deleted document ID '{document_id}' from database and filesystem.")
        except Exception as db_err:
            db.rollback()
            logger.error(f"Failed to delete document from database: {db_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove document from database.",
            )

        return DocumentDeleteResponse(
            success=True,
            document_id=document_id,
            message="Document deleted successfully.",
        )

    @staticmethod
    def get_document_chunks(document_id: str, db: Session) -> DocumentChunksResponse:
        """
        Retrieve all extracted chunks for a given document from PostgreSQL.
        """
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' was not found.",
            )

        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        chunks = db.scalars(stmt).all()

        chunk_responses = [
            ChunkResponse(
                chunk_id=c.id,
                chunk_index=c.chunk_index,
                text=c.text,
                page=c.page_number,
                section=c.section,
                character_count=c.character_count,
            )
            for c in chunks
        ]

        return DocumentChunksResponse(
            success=True,
            document_id=doc.id,
            chunk_count=len(chunk_responses),
            chunks=chunk_responses,
        )

    @staticmethod
    def get_document_count(db: Session) -> int:
        """Get total count of documents stored in PostgreSQL."""
        try:
            stmt = select(func.count()).select_from(Document)
            return db.scalar(stmt) or 0
        except Exception as exc:
            logger.warning(f"Could not count documents in database: {exc}")
            return 0


document_service = DocumentService()
