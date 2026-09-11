import logging
from typing import Union, Optional
from fastapi import APIRouter, UploadFile, File, Path, Depends, status, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from app.config import settings
from app.database.session import get_db, SessionLocal
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    DocumentTextResponse,
    DocumentProcessResponse,
    DocumentDeleteResponse,
    DocumentChunksResponse,
    DocumentPreviewResponse,
    DocumentPermissionGrantRequest,
    DocumentPermissionResponse,
    DocumentVisibilityUpdateRequest,
)
from app.services.document_service import document_service
from app.services.document_processing.processor import document_processor
from app.core.auth import get_optional_user, require_manager_or_admin, get_current_user
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.services.permission_service import permission_service

logger = logging.getLogger("enterprise_rag.documents")
router = APIRouter(prefix="/documents", tags=["Documents"])


def _bg_auto_reindex():
    try:
        from app.rag.pipeline import rag_pipeline
        bg_db = SessionLocal()
        try:
            logger.info("Executing background automatic knowledge base re-indexing...")
            rag_pipeline.build_knowledge_base(bg_db)
            logger.info("Background automatic knowledge base re-indexing completed successfully.")
        finally:
            bg_db.close()
    except Exception as exc:
        logger.error(f"Background auto-reindex error: {exc}", exc_info=True)


@router.post(
    "/upload",
    response_model=Union[DocumentUploadResponse, DocumentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload Enterprise Document",
    description="Upload a PDF, DOCX, or TXT enterprise policy document, validate size/format, save to disk with UUID, and extract clean text.",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(..., description="The policy document file (PDF, DOCX, TXT)"),
    visibility: Optional[str] = None,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Receives file, validates format & size (<= 25MB), saves safely to backend/documents/,
    extracts & normalizes text page-by-page, and persists complete record in PostgreSQL/SQLite.
    Triggers non-blocking background index rebuild when AUTO_REINDEX=true.
    """
    owner_id = user.id if user else None
    upload_result = await document_service.save_uploaded_file(
        file, db, owner_id=owner_id, visibility=visibility
    )

    client_ip = request.client.host if request.client else None
    doc_id = None
    if isinstance(upload_result, dict):
        doc_id = upload_result.get("document_id") or upload_result.get("id")
    elif hasattr(upload_result, "document_id"):
        doc_id = getattr(upload_result, "document_id")
    elif hasattr(upload_result, "id"):
        doc_id = getattr(upload_result, "id")

    log_audit_event(
        db=db,
        action="DOCUMENT_UPLOAD",
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        resource_type="document",
        resource_id=str(doc_id) if doc_id else None,
        metadata={"filename": file.filename},
        ip_address=client_ip,
    )

    if settings.AUTO_REINDEX:
        background_tasks.add_task(_bg_auto_reindex)
    return upload_result


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List All Uploaded Documents",
    description="Retrieve all enterprise policy document records from database.",
)
async def list_documents(
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Returns authentic database records of uploaded enterprise policy documents permitted for the user.
    """
    return document_service.list_all_documents(db, user=user)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get Document Details",
    description="Retrieve metadata details for a specific document by its unique UUID.",
)
async def get_document(
    document_id: str = Path(..., description="Unique document UUID"),
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Returns single document record from database or 404/403 if not found or unauthorized.
    """
    return document_service.get_document_by_id(document_id, db, user=user)


@router.get(
    "/{document_id}/text",
    response_model=DocumentTextResponse,
    summary="Get Extracted Document Text",
    description="Retrieve full normalized extracted text for a document for Phase 2 verification.",
)
async def get_document_text(
    document_id: str = Path(..., description="Unique document UUID"),
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Returns complete extracted text content and character count by document ID.
    """
    return document_service.get_document_text(document_id, db, user=user)


@router.get(
    "/{document_id}/preview",
    response_model=DocumentPreviewResponse,
    summary="Get Document Preview",
    description="Preview extracted document content with page numbers, detected sections, and text without exposing internal server paths.",
)
async def get_document_preview(
    document_id: str = Path(..., description="Unique document UUID"),
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Returns structured preview of document pages, sections, and chunks without server filesystem paths.
    """
    return document_service.get_document_preview(document_id, db, user=user)


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete Document",
    description="Delete document record and its chunks from database, and remove physical file from disk.",
)
async def delete_document(
    background_tasks: BackgroundTasks,
    request: Request,
    document_id: str = Path(..., description="Unique document UUID"),
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Deletes the physical file from disk and removes database entity.
    Triggers automatic knowledge base rebuild to purge stale vectors from FAISS.
    """
    del_res = document_service.delete_document_by_id(document_id, db, user=user)

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="DOCUMENT_DELETE",
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        resource_type="document",
        resource_id=document_id,
        ip_address=client_ip,
    )

    if settings.AUTO_REINDEX:
        background_tasks.add_task(_bg_auto_reindex)

    return del_res


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
    summary="Process Document (Extraction & Chunking)",
    description="Partition extracted text into semantic chunks and persist chunks to database.",
)
async def process_document(
    background_tasks: BackgroundTasks,
    document_id: str = Path(..., description="Unique document UUID"),
    db: Session = Depends(get_db),
):
    """
    Executes chunking pipeline: partitions extracted text into chunks and updates database.
    Triggers background knowledge base rebuild if AUTO_REINDEX=true.
    """
    result = document_processor.process_document(document_id, db)
    if settings.AUTO_REINDEX and result.get("success"):
        background_tasks.add_task(_bg_auto_reindex)

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
    description="Retrieve all extracted and partitioned chunks for a specific document.",
)
async def get_document_chunks(
    document_id: str = Path(..., description="Unique document UUID"),
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Returns list of extracted text chunks with page numbers, sections, and character counts.
    """
    return document_service.get_document_chunks(document_id, db, user=user)


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


# =========================================================================
# Document Visibility & Fine-Grained Permissions (Phase 11)
# =========================================================================

@router.patch(
    "/{document_id}/visibility",
    response_model=DocumentResponse,
    summary="Update Document Visibility",
    description="Set document visibility scope (ORGANIZATION, TEAM, or PRIVATE). Requires document owner, manager, or admin.",
)
async def update_document_visibility(
    request: Request,
    req: DocumentVisibilityUpdateRequest,
    document_id: str = Path(..., description="Unique document UUID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.document import Document
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # Must be owner, manager, or admin
    if user.role not in ("ADMIN", "MANAGER") and doc.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify visibility for this document.",
        )

    vis = req.visibility.upper().strip()
    if vis not in ("ORGANIZATION", "TEAM", "PRIVATE"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Visibility must be one of: 'ORGANIZATION', 'TEAM', 'PRIVATE'.",
        )

    old_vis = doc.visibility
    doc.visibility = vis
    db.commit()
    db.refresh(doc)

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="DOCUMENT_VISIBILITY_UPDATE",
        user_id=user.id,
        user_email=user.email,
        resource_type="document",
        resource_id=document_id,
        metadata={"old_visibility": old_vis, "new_visibility": vis},
        ip_address=client_ip,
    )

    return document_service.get_document_by_id(document_id, db, user=user)


@router.post(
    "/{document_id}/permissions",
    response_model=DocumentPermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant Document Permission",
    description="Explicitly grant VIEW, CHAT, EDIT, DELETE, or ADMIN permission on a document. Requires owner, manager, or admin.",
)
async def grant_document_permission(
    request: Request,
    req: DocumentPermissionGrantRequest,
    document_id: str = Path(..., description="Unique document UUID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.document import Document
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if user.role not in ("ADMIN", "MANAGER") and doc.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to grant access to this document.",
        )

    perm = permission_service.grant_permission(
        db=db,
        document_id=document_id,
        permission=req.permission,
        user_id=req.user_id,
        role=req.role,
    )

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="PERMISSION_GRANT",
        user_id=user.id,
        user_email=user.email,
        resource_type="document_permission",
        resource_id=perm.id,
        metadata={
            "document_id": document_id,
            "target_user_id": req.user_id,
            "target_role": req.role,
            "permission": req.permission,
        },
        ip_address=client_ip,
    )

    return perm


@router.delete(
    "/{document_id}/permissions/{permission_id}",
    summary="Revoke Document Permission",
    description="Revoke an explicit document permission by ID. Requires owner, manager, or admin.",
)
async def revoke_document_permission(
    request: Request,
    document_id: str = Path(..., description="Unique document UUID"),
    permission_id: str = Path(..., description="Unique permission UUID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.document import Document
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if user.role not in ("ADMIN", "MANAGER") and doc.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to revoke access to this document.",
        )

    revoked = permission_service.revoke_permission(db, permission_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found.")

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="PERMISSION_REVOKE",
        user_id=user.id,
        user_email=user.email,
        resource_type="document_permission",
        resource_id=permission_id,
        metadata={"document_id": document_id},
        ip_address=client_ip,
    )

    return {"success": True, "message": "Permission revoked successfully."}

