import uuid
import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Feedback(Base):
    """
    Feedback model capturing employee ratings and comments on generated policy answers.
    """
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating: Mapped[str] = mapped_column(
        String(20),  # "positive", "negative"
        nullable=False,
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Relationships
    message: Mapped["ChatMessage"] = relationship(
        "ChatMessage",
        back_populates="feedbacks",
    )

    def __repr__(self) -> str:
        return f"<Feedback(id='{self.id}', message_id='{self.message_id}', rating='{self.rating}')>"
