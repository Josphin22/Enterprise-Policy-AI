import uuid
import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class AuditLog(Base):
    """
    Append-only audit trail logging user authentication, role mutations,
    document operations, and administrative actions.
    """
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    user_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
        index=True,
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
        index=True,
    )
    metadata_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AuditLog(action='{self.action}', user='{self.user_email}', timestamp='{self.timestamp}')>"
