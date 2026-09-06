import uuid
import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class DocumentMetadata(Base):
    """
    Optional extended metadata for policy documents (author, departmental tags, description).
    """
    __tablename__ = "document_metadata"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    author: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    created_date: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_date: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="metadata_rel",
    )

    def __repr__(self) -> str:
        return f"<DocumentMetadata(document_id='{self.document_id}', title='{self.title}')>"
