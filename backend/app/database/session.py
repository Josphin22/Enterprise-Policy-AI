import logging
from typing import Generator
from sqlalchemy.orm import sessionmaker, Session
from app.database.connection import engine

logger = logging.getLogger("enterprise_rag.database")

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding an isolated SQLAlchemy database session.
    Automatically handles transaction boundaries and ensures sessions are closed.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        db.rollback()
        logger.error(f"Database session rolled back due to error: {exc}")
        raise
    finally:
        db.close()
