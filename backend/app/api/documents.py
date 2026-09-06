from fastapi import APIRouter, UploadFile, File, Path, Depends, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentProcessResponse,
    DocumentDeleteResponse,
    DocumentChunksResponse,
)
from app.services.document_service import document_service
from app.services.document_processing.processor import document_processor

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Enterprise Document",
    description="Upload a PDF, DOCX, or TXT enterprise policy document and persist its record in PostgreSQL.",
)
async def upload_document(
    file: UploadFile = File(..., description="The policy document file (PDF, DOCX, TXT)"),
    db: Session = Depends(get_db),
):
    """
    Validates file format/size, saves to disk, and stores a persistent record in PostgreSQL.
    """
    return await document_service.save_uploaded_file(file, db)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List All Uploaded Documents",
    description="Retrieve all enterprise policy document records from PostgreSQL.",
)
async def list_documents(db: Session = Depends(get_db)):
    """
    Returns persistent database records of uploaded policy documents.
    """
    return document_service.list_all_documents(db)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get Document Details",
    description="Retrieve metadata details for a specific document from PostgreSQL by its unique ID.",
)
async def get_document(
    document_id: str = Path(..., description="Unique document UUID"),
    db: Session = Depends(get_db),
):
    """
    Returns single document record from database or 404 if not found.
    """
    return document_service.get_document_by_id(document_id, db)


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete Document",
    description="Delete document record and its chunks from PostgreSQL, and remove physical file from disk.",
)
async def delete_document(
    document_id: str = Path(..., description="Unique document UUID"),
    db: Session = Depends(get_db),
):
    """
    Deletes the physical file and removes PostgreSQL database entity and cascaded chunks.
    """
    return document_service.delete_document_by_id(document_id, db)


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
    summary="Process Document (Extraction & Chunking)",
    description="Extract text, clean content, partition into semantic chunks, and persist chunks to PostgreSQL.",
)
async def process_document(
    document_id: str = Path(..., description="Unique document UUID"),
    db: Session = Depends(get_db),
):
    """
    Executes Phase 5 document processing: extracts text, cleans formatting, generates chunks, and updates database.
    """
    result = document_processor.process_document(document_id, db)
    return DocumentProcessResponse(
        success=result["success"],
        document_id=result["document_id"],
        status=result["status"],
        chunk_count=result["chunk_count"],
        message=result["message"],
    )


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunksResponse,
    summary="Get Document Chunks",
    description="Retrieve all extracted and partitioned chunks for a specific document from PostgreSQL.",
)
async def get_document_chunks(
    document_id: str = Path(..., description="Unique document UUID"),
    db: Session = Depends(get_db),
):
    """
    Returns list of extracted text chunks with page numbers, sections, and character counts.
    """
    return document_service.get_document_chunks(document_id, db)


@router.post(
    "/{document_id}/reindex",
    summary="Re-index Document Vectors",
    description="Rebuilds the FAISS vector index to include or update the processed chunks of this document.",
)
async def reindex_document(
    document_id: str = Path(..., description="Unique document UUID"),
    db: Session = Depends(get_db),
):
    """
    Verifies document processing status and rebuilds the FAISS vector index.
    """
    from app.rag.pipeline import rag_pipeline
    return rag_pipeline.reindex_document(document_id, db)

