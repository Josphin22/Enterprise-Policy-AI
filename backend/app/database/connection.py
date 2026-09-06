import logging
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from app.config import settings
from app.database.base import Base

logger = logging.getLogger("enterprise_rag.database")

# Handle SQLite vs PostgreSQL engine configuration
# Fallback SQLite database URL
SQLITE_FALLBACK_URL = "sqlite:///./enterprise_rag.db"

# Determine active database engine
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine: Engine = create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    logger.info(f"Database engine initialized using local SQLite: {settings.DATABASE_URL}")
else:
    connect_args = {"connect_timeout": 2}
    engine_kwargs = {
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 1800,
        "pool_timeout": 30,
    }
    try:
        candidate_engine = create_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            **engine_kwargs,
        )
        with candidate_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine: Engine = candidate_engine
        logger.info("Database engine initialized successfully using PostgreSQL.")
    except Exception as exc:
        logger.warning(
            f"Configured PostgreSQL at '{settings.DATABASE_URL}' is unreachable ({exc}). "
            f"Automatically falling back to local SQLite ({SQLITE_FALLBACK_URL}) for seamless operation."
        )
        engine: Engine = create_engine(
            SQLITE_FALLBACK_URL,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )


def check_db_connection() -> bool:
    """
    Test whether the active database is reachable and accepting queries.
    Returns True if healthy, False if unreachable or failing.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning(f"Database connection check failed: {exc}")
        return False


def init_db() -> None:
    """
    Initialize database schema by creating all defined tables if database is reachable.
    Safe for development; does not destroy or overwrite existing tables.
    """
    try:
        # Import all models to ensure they are registered with Base.metadata
        import app.models  # noqa: F401

        if check_db_connection():
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables verified/initialized successfully.")
        else:
            logger.warning("Database is currently unreachable. Operating with degraded data layer.")
    except Exception as exc:
        logger.warning(f"Database table initialization notice: {exc}")
