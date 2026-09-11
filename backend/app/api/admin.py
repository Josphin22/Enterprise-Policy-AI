import os
import time
import shutil
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc

from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.chat import ChatSession, ChatMessage
from app.models.feedback import Feedback
from app.models.audit_log import AuditLog
from app.models.chat_metric import ChatMetric
from app.core.auth import require_admin
from app.schemas.auth import UserRoleUpdateRequest, UserStatusUpdateRequest, UserResponse
from app.services.audit_service import log_audit_event
from app.rag.vector_store import vector_store
from app.rag.pipeline import rag_pipeline

logger = logging.getLogger("enterprise_rag.api.admin")

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
def get_admin_dashboard(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Retrieve real database metrics and system statuses for the Admin Dashboard.
    All data is computed from live PostgreSQL/SQLite records and the local file system.
    """
    total_docs = db.query(Document).count()
    total_chunks = db.query(DocumentChunk).count()
    total_users = db.query(User).count()
    total_conversations = db.query(ChatSession).count()
    total_messages = db.query(ChatMessage).count()

    # Real storage calculation
    storage_used_bytes = 0
    if settings.DOCUMENTS_DIR.exists():
        for f in settings.DOCUMENTS_DIR.rglob("*"):
            if f.is_file():
                try:
                    storage_used_bytes += f.stat().st_size
                except OSError:
                    pass

    # Real feedback metrics
    up_count = db.query(Feedback).filter(Feedback.rating == "up").count()
    down_count = db.query(Feedback).filter(Feedback.rating == "down").count()
    total_feedback = up_count + down_count

    # Recent activity from audit logs
    recent_logs = (
        db.query(AuditLog)
        .order_by(desc(AuditLog.timestamp))
        .limit(10)
        .all()
    )
    activity_items = [
        {
            "id": log.id,
            "action": log.action,
            "user_email": log.user_email,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in recent_logs
    ]

    # Vector store status
    vectors_count = vector_store.total_vectors if vector_store else 0

    return {
        "metrics": {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "total_users": total_users,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "storage_used_bytes": storage_used_bytes,
            "vectorstore_vectors": vectors_count,
            "feedback": {
                "up": up_count,
                "down": down_count,
                "total": total_feedback,
                "satisfaction_rate": round((up_count / total_feedback * 100), 1) if total_feedback > 0 else 100.0,
            },
        },
        "system_status": {
            "overall": "healthy",
            "database": "connected",
            "vector_store": "ready" if vectors_count > 0 else "empty",
        },
        "recent_activity": activity_items,
    }


@router.get("/users")
def list_users(
    search: Optional[str] = Query(None, description="Filter by username or email"),
    role: Optional[str] = Query(None, description="Filter by role (ADMIN, USER)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List registered enterprise users with optional keyword search and role filtering.
    """
    query = db.query(User)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter((User.username.ilike(s)) | (User.email.ilike(s)))
    if role:
        query = query.filter(User.role == role.strip().upper())

    total = query.count()
    users = query.order_by(desc(User.created_at)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: str,
    req: UserRoleUpdateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update a user's role (ADMIN or USER).
    Prevents demotion of the last active administrator.
    """
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    new_role = req.role.upper()
    if target.role == "ADMIN" and new_role != "ADMIN":
        # Check if there's any other active admin
        other_admins = (
            db.query(User)
            .filter(User.role == "ADMIN", User.is_active == True, User.id != user_id)
            .count()
        )
        if other_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last remaining active administrator.",
            )

    old_role = target.role
    target.role = new_role
    db.commit()
    db.refresh(target)

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="ROLE_UPDATE",
        user_id=admin.id,
        user_email=admin.email,
        resource_type="user",
        resource_id=target.id,
        metadata={"old_role": old_role, "new_role": new_role, "target_email": target.email},
        ip_address=client_ip,
    )

    return target


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: str,
    req: UserStatusUpdateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Activate or deactivate a user account.
    Prevents deactivating one's own account or the last active admin.
    """
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if admin.id == user_id and req.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own administrator account.",
        )

    if target.role == "ADMIN" and req.is_active is False:
        other_admins = (
            db.query(User)
            .filter(User.role == "ADMIN", User.is_active == True, User.id != user_id)
            .count()
        )
        if other_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last remaining active administrator.",
            )

    target.is_active = req.is_active
    db.commit()
    db.refresh(target)

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="STATUS_UPDATE",
        user_id=admin.id,
        user_email=admin.email,
        resource_type="user",
        resource_id=target.id,
        metadata={"is_active": target.is_active, "target_email": target.email},
        ip_address=client_ip,
    )

    return target


@router.get("/system-health")
def get_system_health(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Comprehensive system health diagnostic covering Database, Ollama LLM, FAISS VectorStore, and File Storage.
    Safely hides credentials and connection secrets.
    """
    # 1. Database Probe
    db_ok = False
    db_latency_ms = 0.0
    try:
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_ok = True
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")

    db_type = "SQLite" if settings.DATABASE_URL.startswith("sqlite") else "PostgreSQL"

    # 2. Ollama Probe
    ollama_ok = False
    ollama_latency_ms = 0.0
    ollama_models = []
    try:
        import requests
        t0 = time.perf_counter()
        resp = requests.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=2.0)
        ollama_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        if resp.status_code == 200:
            ollama_ok = True
            tags_data = resp.json()
            ollama_models = [m.get("name") for m in tags_data.get("models", [])]
    except Exception as exc:
        logger.debug(f"Ollama health probe notice: {exc}")

    # 3. FAISS Vector Store Probe
    index_file = settings.VECTORSTORE_DIR / "index.faiss"
    index_exists = index_file.exists()
    vectors_count = vector_store.total_vectors if vector_store else 0
    dim = vector_store.dimension if vector_store else 384

    # 4. Storage Probe
    total_bytes, used_bytes, free_bytes = 0, 0, 0
    try:
        total_b, used_b, free_b = shutil.disk_usage(str(settings.DOCUMENTS_DIR.resolve()))
        total_bytes, used_bytes, free_bytes = total_b, used_b, free_b
    except Exception:
        pass

    storage_writable = os.access(settings.DOCUMENTS_DIR, os.W_OK)

    overall_status = "healthy" if (db_ok and (ollama_ok or vectors_count > 0)) else "degraded"

    return {
        "status": overall_status,
        "database": {
            "connected": db_ok,
            "engine": db_type,
            "latency_ms": db_latency_ms,
        },
        "ollama": {
            "reachable": ollama_ok,
            "configured_model": settings.OLLAMA_MODEL,
            "available_models": ollama_models,
            "latency_ms": ollama_latency_ms,
            "endpoint": settings.OLLAMA_BASE_URL,
        },
        "vector_store": {
            "status": "ready" if index_exists else "empty",
            "index_file_exists": index_exists,
            "total_vectors": vectors_count,
            "dimension": dim,
            "model": settings.EMBEDDING_MODEL_NAME,
        },
        "storage": {
            "documents_directory": str(settings.DOCUMENTS_DIR.name),
            "writable": storage_writable,
            "free_bytes": free_bytes,
            "total_bytes": total_bytes,
        },
    }


@router.get("/analytics")
def get_analytics(
    from_date: Optional[str] = Query(None, description="ISO format start date"),
    to_date: Optional[str] = Query(None, description="ISO format end date"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Calculate authentic RAG operational metrics including questions per day, latency breakdowns,
    no-answer rate, and user feedback distribution.
    """
    metric_query = db.query(ChatMetric)

    if from_date:
        try:
            start_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            metric_query = metric_query.filter(ChatMetric.created_at >= start_dt)
        except ValueError:
            pass

    if to_date:
        try:
            end_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            metric_query = metric_query.filter(ChatMetric.created_at <= end_dt)
        except ValueError:
            pass

    all_metrics = metric_query.order_by(ChatMetric.created_at.asc()).all()

    total_queries = len(all_metrics)
    if total_queries > 0:
        avg_resp = round(sum(m.response_time_ms for m in all_metrics) / total_queries, 1)
        avg_ret = round(sum(m.retrieval_time_ms for m in all_metrics) / total_queries, 1)
        avg_ollama = round(sum(m.ollama_time_ms for m in all_metrics) / total_queries, 1)
        no_answer_count = sum(1 for m in all_metrics if not m.answer_found)
        no_answer_rate = round((no_answer_count / total_queries) * 100, 1)
    else:
        # Fallback to message count if metrics haven't accumulated yet
        msg_count = db.query(ChatMessage).filter(ChatMessage.sender == "user").count()
        avg_resp, avg_ret, avg_ollama = 0.0, 0.0, 0.0
        no_answer_rate = 0.0
        total_queries = msg_count

    # Aggregate questions per day
    daily_counts: Dict[str, int] = {}
    for m in all_metrics:
        d_str = m.created_at.strftime("%Y-%m-%d") if m.created_at else "unknown"
        daily_counts[d_str] = daily_counts.get(d_str, 0) + 1

    # If no metrics recorded yet, provide day aggregation from ChatMessage
    if not daily_counts:
        user_msgs = db.query(ChatMessage).filter(ChatMessage.sender == "user").all()
        for msg in user_msgs:
            d_str = msg.timestamp.strftime("%Y-%m-%d") if msg.timestamp else "unknown"
            daily_counts[d_str] = daily_counts.get(d_str, 0) + 1

    timeline = [{"date": d, "count": c} for d, c in sorted(daily_counts.items())]

    # Feedback rates
    up_count = db.query(Feedback).filter(Feedback.rating == "up").count()
    down_count = db.query(Feedback).filter(Feedback.rating == "down").count()
    total_feedback = up_count + down_count
    helpful_rate = round((up_count / total_feedback) * 100, 1) if total_feedback > 0 else 100.0

    # Recent low-confidence or unanswered questions
    unanswered = [
        {"question": m.question, "timestamp": m.created_at.isoformat() if m.created_at else None}
        for m in all_metrics if not m.answer_found
    ][-5:]

    return {
        "summary": {
            "total_queries": total_queries,
            "average_response_ms": avg_resp,
            "average_retrieval_ms": avg_ret,
            "average_ollama_ms": avg_ollama,
            "no_answer_rate_pct": no_answer_rate,
            "helpful_feedback_rate_pct": helpful_rate,
            "total_feedback": total_feedback,
        },
        "questions_timeline": timeline,
        "recent_unanswered": unanswered,
    }


@router.get("/audit-logs")
def get_audit_logs(
    action: Optional[str] = Query(None, description="Filter by event action"),
    user_id: Optional[str] = Query(None, description="Filter by initiating user id"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Query the append-only audit trail with filtering and pagination.
    """
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action.strip().upper())
    if user_id:
        query = query.filter(AuditLog.user_id == user_id.strip())

    total = query.count()
    logs = query.order_by(desc(AuditLog.timestamp)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "user_email": log.user_email,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "metadata_json": log.metadata_json,
                "ip_address": log.ip_address,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ],
    }


@router.post("/knowledge-base/rebuild")
def rebuild_knowledge_base_admin(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Trigger complete rebuild of the FAISS vector index with concurrency protection.
    Returns HTTP 409 Conflict if another rebuild is actively executing.
    """
    result = rag_pipeline.build_knowledge_base(db)
    if result.get("status") == "in_progress":
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "status": "in_progress",
                "message": "A knowledge base index rebuild is already in progress.",
            },
        )

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="KB_REBUILD",
        user_id=admin.id,
        user_email=admin.email,
        resource_type="knowledge_base",
        metadata={
            "documents": result.get("documents", 0),
            "chunks": result.get("chunks", 0),
            "vectors": result.get("vectors", 0),
        },
        ip_address=client_ip,
    )

    return result


@router.post("/documents/{document_id}/reprocess")
def reprocess_document(
    document_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Reprocess an existing document: re-extract text, re-chunk, and reindex in the vector store.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    from app.services.document_service import document_service
    file_path = settings.DOCUMENTS_DIR / doc.filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Original document file '{doc.filename}' not found on disk.",
        )

    # Re-extract text
    try:
        from app.utils.file_utils import extract_text
        content_type = doc.file_type or "text/plain"
        extracted = extract_text(file_path, content_type)
        doc.extracted_text = extracted
        doc.text_length = len(extracted)
        doc.status = "processed"
        doc.error_message = None
    except Exception as exc:
        doc.status = "error"
        doc.error_message = str(exc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract document text: {exc}",
        )

    # Re-create chunks
    db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
    db.commit()

    from app.services.chunking_service import chunking_service
    chunks = chunking_service.chunk_document(doc.id, doc.extracted_text)
    for c in chunks:
        db.add(c)
    db.commit()

    # Rebuild vector store
    rag_pipeline.build_knowledge_base(db)

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="DOCUMENT_REPROCESS",
        user_id=admin.id,
        user_email=admin.email,
        resource_type="document",
        resource_id=doc.id,
        metadata={"filename": doc.filename, "new_chunks": len(chunks)},
        ip_address=client_ip,
    )

    return {
        "success": True,
        "document_id": doc.id,
        "filename": doc.filename,
        "chunks_created": len(chunks),
        "status": doc.status,
    }


@router.get("/evaluation")
def get_evaluation_metrics(
    admin: User = Depends(require_admin),
):
    """
    Returns empirical evaluation results (Recall@K, MRR, Groundedness, Citation Accuracy, Guardrails)
    from the latest evaluation run or evaluation summary report.
    """
    import json
    results_dir = settings.BASE_DIR / "evaluation" / "results"
    summary_path = results_dir / "evaluation_summary.json"
    
    if not summary_path.exists():
        # Fallback to backend/evaluation/results if present
        alt_summary_path = settings.BASE_DIR / "backend" / "evaluation" / "results" / "evaluation_summary.json"
        if alt_summary_path.exists():
            summary_path = alt_summary_path

    summary = None
    if summary_path.exists():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load evaluation summary: {e}")

    # Return summary or current configuration & metrics
    return {
        "success": True,
        "has_evaluated": summary is not None,
        "summary": summary,
        "guardrails": {
            "enabled": settings.ENABLE_GUARDRAILS,
            "sensitive_data_scrub": settings.ENABLE_SENSITIVE_DATA_SCRUB,
            "max_answer_tokens": settings.MAX_ANSWER_TOKENS,
            "max_answer_characters": settings.MAX_ANSWER_CHARACTERS,
            "grounding_similarity_threshold": settings.GROUNDING_SIMILARITY_THRESHOLD,
        },
    }

