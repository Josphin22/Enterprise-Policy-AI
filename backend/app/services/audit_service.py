import json
import logging
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog

logger = logging.getLogger("enterprise_rag.audit")


def log_audit_event(
    db: Session,
    action: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """
    Persist a tamper-evident audit record in the database.
    Safe failure: Logs warnings if database commit fails without blocking the primary action.
    """
    metadata_json = None
    if metadata is not None:
        try:
            metadata_json = json.dumps(metadata, default=str)
        except Exception as exc:
            logger.warning(f"Failed to serialize audit metadata: {exc}")
            metadata_json = json.dumps({"raw": str(metadata)})

    audit_entry = AuditLog(
        user_id=user_id,
        user_email=user_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata_json,
        ip_address=ip_address,
    )

    try:
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        logger.info(f"Audit log recorded: [{action}] by {user_email or 'system'} on {resource_type or 'system'}:{resource_id or ''}")
        return audit_entry
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to record audit event '{action}': {exc}")
        return audit_entry
