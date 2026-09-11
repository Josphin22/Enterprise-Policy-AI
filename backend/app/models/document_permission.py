import uuid
import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class DocumentPermission(Base):
    """
    Fine-grained document permission model (Phase 11).
    Grants explicit VIEW, CHAT, EDIT, DELETE, or ADMIN access
    to specific users or role groups.
    """
    __tablename__ = "document_permissions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )
    permission: Mapped[str] = mapped_column(
        String(20),
        default="VIEW",
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Relationship to parent document
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="permissions",
    )

    __table_args__ = (
        Index("idx_doc_perm_doc_user", "document_id", "user_id"),
        Index("idx_doc_perm_doc_role", "document_id", "role"),
    )

    def __repr__(self) -> str:
        return f"<DocumentPermission(id='{self.id}', doc='{self.document_id}', user='{self.user_id}', perm='{self.permission}')>"
