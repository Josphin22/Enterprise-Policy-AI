import logging
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

import datetime
from app.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_metadata import DocumentMetadata
from app.utils.file_utils import (
    sanitize_filename,
    get_file_extension,
    is_allowed_extension,
)
from app.utils.errors import (
    InvalidFileTypeError,
    FileTooLargeError,
    EmptyDocumentError,
    DocumentExtractionFailedError,
    PasswordProtectedError,
    CorruptedDocumentError,
    ImageOnlyDocumentError,
    OCRProcessingError,
)
from app.services.extraction_service import extraction_service
from app.services.chunking_service import chunking_service
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentRecordItem,
    DocumentUploadResponse,
    DocumentTextResponse,
    DocumentDeleteResponse,
    DocumentChunksResponse,
    ChunkResponse,
    PagePreviewItem,
    ChunkPreviewItem,
    DocumentPreviewResponse,
)

logger = logging.getLogger("enterprise_rag.documents")


class DocumentService:
    @staticmethod
    async def save_uploaded_file(
        file: UploadFile,
        db: Session,
        owner_id: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> Any:
        """
        Validate file, save safely with UUID to disk, extract and clean text,
        and persist complete document metadata in database with visibility scope.
        """
        # 1. Validate filename exists and check for path traversal
        if not file.filename or not file.filename.strip():
            logger.warning("Upload rejected: missing filename")
            raise InvalidFileTypeError("Filename cannot be empty.")

        raw_filename = file.filename.strip()
        if ".." in raw_filename or "/" in raw_filename or "\\" in raw_filename or "\x00" in raw_filename:
            logger.warning(f"Upload rejected: path traversal sequence in filename '{raw_filename}'")
            raise InvalidFileTypeError("Invalid filename: directory traversal characters are not permitted.")

        clean_original_name = sanitize_filename(file.filename)
        file_ext = get_file_extension(clean_original_name).lower().lstrip(".")

        # 2. Validate allowed extensions (.pdf, .docx, .txt)
        if not is_allowed_extension(clean_original_name):
            logger.warning(f"Upload rejected: unsupported file extension '.{file_ext}'")
            raise InvalidFileTypeError(
                f"Only PDF, DOCX and TXT files are supported. Received '.{file_ext}'."
            )

        # 3. Read content and validate size (Max 25 MB) and not empty
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        contents = await file.read()
        total_bytes = len(contents)

        if total_bytes == 0:
            logger.warning("Upload rejected: empty file")
            raise EmptyDocumentError("Uploaded file is empty.")

        if total_bytes > max_bytes:
            logger.warning(f"Upload rejected: file size {total_bytes} bytes exceeds {max_bytes} bytes limit")
            raise FileTooLargeError(
                f"Maximum allowed file size is {settings.MAX_UPLOAD_SIZE_MB} MB."
            )

        # 4. Generate unique UUID and safe destination path
        doc_id = str(uuid.uuid4())
        stored_filename = f"{doc_id}_{clean_original_name}"
        destination_path = settings.DOCUMENTS_DIR / stored_filename

        try:
            with open(destination_path, "wb") as buffer:
                buffer.write(contents)
            logger.info(f"File stored safely: {destination_path.name} ({total_bytes} bytes)")
        except Exception as write_err:
            logger.error(f"File write failed: {write_err}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store uploaded file: {str(write_err)}",
            )

        # Determine visibility
        doc_vis = (visibility or settings.DEFAULT_DOCUMENT_VISIBILITY or "ORGANIZATION").upper()
        if doc_vis not in ("ORGANIZATION", "TEAM", "PRIVATE"):
            doc_vis = "ORGANIZATION"

        # 5. Create initial Document record in Database (status='processing')
        doc_record = Document(
            id=doc_id,
            filename=stored_filename,
            original_filename=clean_original_name,
            file_type=file_ext,
            file_size=total_bytes,
            file_path=str(destination_path),
            owner_id=owner_id,
            visibility=doc_vis,
            processing_status="processing",
            chunk_count=0,
            extracted_text=None,
            text_length=0,
            error_message=None,
        )
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)

        # 6. Extract, clean, and chunk document text
        logger.info(f"Starting text extraction for document {doc_id} ({clean_original_name})")
        doc_record.processing_status = "processing"
        db.commit()

        try:
            extraction_result = extraction_service.extract_document(
                file_path=destination_path,
                file_type=file_ext,
            )

            extracted_text = extraction_result["text"]
            text_len = extraction_result["character_count"]
            pages = extraction_result.get("pages", [])

            # 7. Chunk document using ChunkingService
            logger.info(f"Starting chunking for document {doc_id} ({text_len} chars)")
            chunks = chunking_service.chunk_document(
                text=extracted_text,
                document_id=doc_record.id,
                filename=doc_record.original_filename,
                file_type=file_ext,
                pages=pages,
            )

            if not chunks:
                logger.warning(f"Document {doc_id} produced 0 chunks (empty).")
                raise EmptyDocumentError("No extractable chunks found in document.")

            # 8. Persist chunks transactionally (clean old chunks if any)
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc_record.id))

            chunk_records = []
            for c in chunks:
                chunk_records.append(
                    DocumentChunk(
                        id=c["id"],
                        document_id=doc_record.id,
                        chunk_index=c["chunk_index"],
                        text=c["text"],
                        page_number=c.get("page_number"),
                        page_start=c.get("page_start"),
                        page_end=c.get("page_end"),
                        section=c.get("section"),
                        character_count=c["character_count"],
                    )
                )

            db.add_all(chunk_records)

            doc_record.extracted_text = extracted_text
            doc_record.text_length = text_len
            doc_record.chunk_count = len(chunk_records)
            doc_record.processing_status = "processed"
            doc_record.error_message = None

            # Phase 10: Persist document metadata
            page_cnt = len(pages) if file_ext == "pdf" else None
            tbl_cnt = extraction_result.get("table_count", 0)
            ocr_app = extraction_result.get("ocr_applied", False)
            lang = extraction_result.get("language")

            meta_rec = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == doc_record.id).first()
            if not meta_rec:
                meta_rec = DocumentMetadata(
                    document_id=doc_record.id,
                    title=doc_record.original_filename,
                    page_count=page_cnt,
                    table_count=tbl_cnt,
                    ocr_applied=ocr_app,
                    language=lang,
                    processed_at=datetime.datetime.now(datetime.timezone.utc),
                )
                db.add(meta_rec)
            else:
                meta_rec.page_count = page_cnt
                meta_rec.table_count = tbl_cnt
                meta_rec.ocr_applied = ocr_app
                meta_rec.language = lang
                meta_rec.processed_at = datetime.datetime.now(datetime.timezone.utc)

            db.commit()
            db.refresh(doc_record)

            logger.info(
                f"Document {doc_id} extracted, chunked, and processed successfully: "
                f"{text_len} chars, {len(chunk_records)} chunks, {tbl_cnt} tables, OCR={ocr_app}."
            )

            record_item = DocumentRecordItem(
                id=doc_record.id,
                document_id=doc_record.id,
                filename=doc_record.original_filename,
                original_filename=doc_record.original_filename,
                file_type=doc_record.file_type,
                file_size=doc_record.file_size,
                size=doc_record.file_size,
                status=doc_record.processing_status,
                text_length=doc_record.text_length,
                chunk_count=doc_record.chunk_count,
                page_count=page_cnt,
                table_count=tbl_cnt,
                ocr_applied=ocr_app,
                language=lang,
                visibility=doc_record.visibility,
                owner_id=doc_record.owner_id,
                created_at=doc_record.created_at.isoformat() if doc_record.created_at else None,
                uploaded_at=doc_record.upload_date.isoformat() if doc_record.upload_date else None,
                error_message=None,
            )

            return DocumentUploadResponse(
                success=True,
                document=record_item,
                id=doc_record.id,
                document_id=doc_record.id,
                filename=doc_record.original_filename,
                file_type=doc_record.file_type,
                file_size=doc_record.file_size,
                size=doc_record.file_size,
                status=doc_record.processing_status,
                text_length=doc_record.text_length,
                chunk_count=doc_record.chunk_count,
                page_count=page_cnt,
                table_count=tbl_cnt,
                ocr_applied=ocr_app,
                language=lang,
            )

        except (EmptyDocumentError, PasswordProtectedError, CorruptedDocumentError, ImageOnlyDocumentError, OCRProcessingError) as doc_err:
            doc_record.processing_status = "failed"
            doc_record.error_message = doc_err.message
            db.commit()
            db.refresh(doc_record)
            logger.warning(f"Document {doc_id} processing failed ({doc_err.error_code}): {doc_err.message}")

            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "document": {
                        "id": doc_record.id,
                        "filename": doc_record.original_filename,
                        "status": "failed",
                    },
                    "error": {
                        "code": doc_err.error_code,
                        "message": doc_err.message,
                    },
                },
            )

        except Exception as ext_err:
            err_msg = str(ext_err)
            doc_record.processing_status = "failed"
            doc_record.error_message = err_msg
            db.commit()
            db.refresh(doc_record)
            logger.error(f"Document {doc_id} extraction failed: {err_msg}", exc_info=True)

            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "success": False,
                    "document": {
                        "id": doc_record.id,
                        "filename": doc_record.original_filename,
                        "status": "failed",
                    },
                    "error": {
                        "code": "DOCUMENT_EXTRACTION_FAILED",
                        "message": "Unable to extract readable text from the document.",
                    },
                },
            )

    @staticmethod
    def list_all_documents(db: Session, user: Optional[Any] = None) -> DocumentListResponse:
        """
        List enterprise policy documents accessible to the user from PostgreSQL / SQLite.
        Enforces RBAC: Users see ORGANIZATION docs, their own docs, and permitted team/private docs.
        """
        from app.services.permission_service import permission_service

        allowed_ids = permission_service.get_authorized_document_ids(db, user, required_permission="VIEW")

        stmt = select(Document).order_by(Document.upload_date.desc())
        if allowed_ids is not None:
            if not allowed_ids:
                return DocumentListResponse(documents=[], total=0)
            stmt = stmt.where(Document.id.in_(allowed_ids))

        docs = db.scalars(stmt).all()

        documents: List[DocumentResponse] = []
        for doc in docs:
            meta = doc.metadata_rel
            documents.append(
                DocumentResponse(
                    success=True,
                    id=doc.id,
                    document_id=doc.id,
                    filename=doc.original_filename,
                    original_filename=doc.original_filename,
                    file_type=doc.file_type,
                    file_size=doc.file_size,
                    size=doc.file_size,
                    status=doc.processing_status,
                    text_length=doc.text_length or 0,
                    chunk_count=doc.chunk_count or 0,
                    page_count=meta.page_count if meta else None,
                    table_count=meta.table_count if meta else 0,
                    ocr_applied=meta.ocr_applied if meta else False,
                    language=meta.language if meta else None,
                    visibility=doc.visibility,
                    owner_id=doc.owner_id,
                    created_at=doc.created_at.isoformat() if doc.created_at else None,
                    uploaded_at=doc.upload_date.isoformat() if doc.upload_date else None,
                    error_message=doc.error_message,
                )
            )

        return DocumentListResponse(
            documents=documents,
            total=len(documents),
        )

    @staticmethod
    def get_document_by_id(document_id: str, db: Session, user: Optional[Any] = None) -> DocumentResponse:
        """
        Retrieve document metadata from database by ID with permission enforcement.
        """
        doc = db.get(Document, document_id)
        if not doc:
            logger.warning(f"Document lookup failed: ID '{document_id}' not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' was not found.",
            )

        from app.services.permission_service import permission_service
        if not permission_service.check_document_access(db, document_id, user, required_permission="VIEW"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this document.",
            )

        meta = doc.metadata_rel
        return DocumentResponse(
            success=True,
            id=doc.id,
            document_id=doc.id,
            filename=doc.original_filename,
            original_filename=doc.original_filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            size=doc.file_size,
            status=doc.processing_status,
            text_length=doc.text_length or 0,
            chunk_count=doc.chunk_count or 0,
            page_count=meta.page_count if meta else None,
            table_count=meta.table_count if meta else 0,
            ocr_applied=meta.ocr_applied if meta else False,
            language=meta.language if meta else None,
            visibility=doc.visibility,
            owner_id=doc.owner_id,
            created_at=doc.created_at.isoformat() if doc.created_at else None,
            uploaded_at=doc.upload_date.isoformat() if doc.upload_date else None,
            error_message=doc.error_message,
        )

    @staticmethod
    def get_document_text(document_id: str, db: Session, user: Optional[Any] = None) -> DocumentTextResponse:
        """
        Retrieve full extracted text for testing Phase 2 extraction.
        Enforces document access permissions.
        """
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' was not found.",
            )

        from app.services.permission_service import permission_service
        if not permission_service.check_document_access(db, document_id, user, required_permission="VIEW"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this document text.",
            )

        if doc.processing_status == "failed":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "DOCUMENT_EXTRACTION_FAILED",
                    "message": f"Document extraction failed: {doc.error_message or 'No extractable text.'}",
                },
            )

        # If extracted_text not populated yet (e.g. legacy document), extract on-demand
        text = doc.extracted_text
        if not text and Path(doc.file_path).exists():
            try:
                res = extraction_service.extract_document(Path(doc.file_path), file_type=doc.file_type)
                text = res["text"]
                doc.extracted_text = text
                doc.text_length = len(text)
                db.commit()
            except Exception as e:
                logger.warning(f"On-demand extraction error for {doc.id}: {e}")

        return DocumentTextResponse(
            document_id=doc.id,
            filename=doc.original_filename,
            text=text or "",
            text_length=doc.text_length or len(text or ""),
        )

    @staticmethod
    def delete_document_by_id(document_id: str, db: Session, user: Optional[Any] = None) -> DocumentDeleteResponse:
        """
        Delete document record from database and delete physical file from disk.
        Enforces authorization: non-admin users cannot delete others' documents.
        """
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' was not found.",
            )

        # RBAC ownership check: if authenticated non-admin, must own the document
        if user and getattr(user, "role", "USER") != "ADMIN":
            if doc.owner_id and doc.owner_id != getattr(user, "id", None):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to delete this document.",
                )

        stored_path = Path(doc.file_path)
        if stored_path.exists() and stored_path.is_file():
            try:
                stored_path.unlink()
                logger.info(f"Unlinked physical file: {stored_path}")
            except Exception as e:
                logger.error(f"Failed to unlink file {stored_path}: {e}")

        try:
            db.delete(doc)
            db.commit()
            logger.info(f"Deleted Document record {document_id} from database.")
        except Exception as db_err:
            db.rollback()
            logger.error(f"Database error deleting document {document_id}: {db_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete document from database.",
            )

        return DocumentDeleteResponse(
            success=True,
            document_id=document_id,
            message="Document deleted successfully.",
        )

    @staticmethod
    def get_document_chunks(document_id: str, db: Session, user: Optional[Any] = None) -> DocumentChunksResponse:
        """
        Retrieve chunks for a document from the database.
        Enforces document access permissions.
        """
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' was not found.",
            )

        from app.services.permission_service import permission_service
        if not permission_service.check_document_access(db, document_id, user, required_permission="VIEW"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view chunks of this document.",
            )

        stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index.asc())
        chunks = db.scalars(stmt).all()
        chunk_items = [
            ChunkResponse(
                id=c.id,
                chunk_id=c.id,
                document_id=c.document_id,
                chunk_index=c.chunk_index,
                text=c.text,
                page_number=c.page_number,
                page_start=c.page_start,
                page_end=c.page_end,
                page=c.page_number,
                section=c.section,
                character_count=c.character_count,
            )
            for c in chunks
        ]
        return DocumentChunksResponse(
            success=True,
            document_id=document_id,
            filename=doc.original_filename,
            chunk_count=len(chunk_items),
            chunks=chunk_items,
        )

    @staticmethod
    def reprocess_document(document_id: str, db: Session) -> Dict[str, Any]:
        """
        Reprocess an existing document: clean old chunks, extract, chunk, and update chunk_count.
        Guarantees transactional safety with rollback and no duplicate chunks.
        """
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' was not found.",
            )

        file_path = Path(doc.file_path)
        if not file_path.exists() or not file_path.is_file():
            doc.processing_status = "failed"
            doc.error_message = f"Physical file missing on disk at {file_path}"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Physical file for document '{doc.original_filename}' is missing on disk.",
            )

        doc.processing_status = "processing"
        db.commit()

        try:
            file_ext = (doc.file_type or "").lower().lstrip(".")
            extraction_result = extraction_service.extract_document(
                file_path=file_path,
                file_type=file_ext,
            )

            extracted_text = extraction_result["text"]
            text_len = extraction_result["character_count"]
            pages = extraction_result.get("pages", [])

            chunks = chunking_service.chunk_document(
                text=extracted_text,
                document_id=doc.id,
                filename=doc.original_filename,
                file_type=file_ext,
                pages=pages,
            )

            if not chunks:
                raise EmptyDocumentError("No extractable chunks found in document.")

            # Transactional chunk replacement: delete old chunks first
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))

            chunk_records = [
                DocumentChunk(
                    id=c["id"],
                    document_id=doc.id,
                    chunk_index=c["chunk_index"],
                    text=c["text"],
                    page_number=c.get("page_number"),
                    page_start=c.get("page_start"),
                    page_end=c.get("page_end"),
                    section=c.get("section"),
                    character_count=c["character_count"],
                )
                for c in chunks
            ]
            db.add_all(chunk_records)

            doc.extracted_text = extracted_text
            doc.text_length = text_len
            doc.chunk_count = len(chunk_records)
            doc.processing_status = "processed"
            doc.error_message = None

            db.commit()
            db.refresh(doc)

            logger.info(
                f"Document {doc.id} reprocessed successfully: {doc.chunk_count} chunks created."
            )

            return {
                "success": True,
                "document_id": doc.id,
                "status": "processed",
                "chunk_count": doc.chunk_count,
                "message": f"Successfully processed document into {doc.chunk_count} chunks.",
            }

        except Exception as err:
            db.rollback()
            err_msg = str(err)
            doc.processing_status = "failed"
            doc.error_message = err_msg
            db.commit()
            logger.error(f"Reprocessing document {document_id} failed: {err_msg}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document processing failed: {err_msg}",
            )


    @staticmethod
    def get_document_preview(document_id: str, db: Session, user: Optional[Any] = None) -> DocumentPreviewResponse:
        """
        Preview extracted document content with page, section, and chunk details.
        Does NOT expose internal server filesystem paths.
        Enforces user document access control.
        """
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{document_id}' not found.",
            )

        from app.services.permission_service import permission_service
        if not permission_service.check_document_access(db, document_id, user, required_permission="VIEW"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to preview this document.",
            )

        meta = doc.metadata_rel
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )

        # Collect unique sections
        sections: List[str] = []
        seen_sec = set()
        for c in chunks:
            if c.section and c.section.lower() not in seen_sec:
                sections.append(c.section)
                seen_sec.add(c.section.lower())

        # Group preview by pages
        page_dict: Dict[Optional[int], List[DocumentChunk]] = {}
        for c in chunks:
            p_num = c.page_number
            if p_num not in page_dict:
                page_dict[p_num] = []
            page_dict[p_num].append(c)

        pages_preview = []
        for p_num, p_chunks in page_dict.items():
            combined_page_text = "\n\n".join(c.text for c in p_chunks)
            primary_sec = p_chunks[0].section if p_chunks else None
            pages_preview.append(
                PagePreviewItem(
                    page_number=p_num,
                    section=primary_sec,
                    text=combined_page_text,
                    chunk_count=len(p_chunks),
                )
            )

        chunks_preview = [
            ChunkPreviewItem(
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                section=c.section,
                text=c.text,
                character_count=c.character_count,
            )
            for c in chunks
        ]

        return DocumentPreviewResponse(
            success=True,
            document_id=doc.id,
            filename=doc.original_filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.processing_status,
            page_count=meta.page_count if meta else (len(pages_preview) if doc.file_type == "pdf" else None),
            table_count=meta.table_count if meta else 0,
            ocr_applied=meta.ocr_applied if meta else False,
            language=meta.language if meta else None,
            total_chunks=len(chunks),
            sections=sections,
            pages=pages_preview,
            chunks=chunks_preview,
        )


document_service = DocumentService()

