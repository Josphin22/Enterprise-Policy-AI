import uuid
import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class ChatMetric(Base):
    """
    Structured query telemetry recorded on each chat interaction
    for fast database aggregations and performance monitoring.
    """
    __tablename__ = "chat_metrics"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    conversation_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    message_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )
    question: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    retrieval_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    top_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    response_time_ms: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    retrieval_time_ms: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    ollama_time_ms: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    answer_found: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<ChatMetric(id='{self.id}', answer_found={self.answer_found}, latency={self.response_time_ms}ms)>"
