import uuid
import datetime
from typing import Optional
from sqlalchemy import String, BigInteger, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Document(Base):
    """
    Document model representing enterprise policy files stored in the repository.
    Tracks file attributes and ingestion lifecycle status in PostgreSQL.
    """
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    upload_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",
        nullable=False,
        index=True,
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # 1-to-1 relationship with DocumentMetadata
    metadata_rel: Mapped[Optional["DocumentMetadata"]] = relationship(
        "DocumentMetadata",
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="joined",
    )

    # 1-to-many relationship with DocumentChunk
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index.asc()",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Document(id='{self.id}', filename='{self.filename}', status='{self.processing_status}', chunks={self.chunk_count})>"
