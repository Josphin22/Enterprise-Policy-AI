import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from app.config import settings, BASE_DIR
from app.database.base import Base

logger = logging.getLogger("enterprise_rag.database")

# Handle SQLite vs PostgreSQL engine configuration
# Fallback SQLite database URL anchored to BASE_DIR
SQLITE_FALLBACK_URL = f"sqlite:///{(BASE_DIR / 'enterprise_rag.db').resolve().as_posix()}"

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
    Also ensures newly added columns exist in the documents table.
    """
    try:
        # Import all models to ensure they are registered with Base.metadata
        import app.models  # noqa: F401

        if check_db_connection():
            Base.metadata.create_all(bind=engine)
            # Automatic schema migration check for documents and document_chunks tables
            try:
                inspector = inspect(engine)
                existing_tables = inspector.get_table_names()
                with engine.connect() as conn:
                    if "users" in existing_tables:
                        user_cols = {col["name"] for col in inspector.get_columns("users")}
                        if "role" not in user_cols:
                            conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'USER'"))
                            conn.commit()
                            logger.info("Added missing column 'role' to users table.")
                        try:
                            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)"))
                            conn.commit()
                        except Exception as idx_err:
                            logger.debug(f"User role index notice: {idx_err}")

                    if "documents" in existing_tables:
                        existing_cols = {col["name"] for col in inspector.get_columns("documents")}
                        new_cols = {
                            "extracted_text": "TEXT",
                            "text_length": "INTEGER",
                            "error_message": "TEXT",
                            "owner_id": "VARCHAR(36)",
                            "visibility": "VARCHAR(20) DEFAULT 'ORGANIZATION'",
                        }
                        for col_name, col_type in new_cols.items():
                            if col_name not in existing_cols:
                                conn.execute(text(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}"))
                                conn.commit()
                                logger.info(f"Added missing column '{col_name}' ({col_type}) to documents table.")

                        try:
                            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_owner_id ON documents(owner_id)"))
                            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_visibility ON documents(visibility)"))
                            conn.commit()
                        except Exception as idx_err:
                            logger.debug(f"Document owner/visibility index notice: {idx_err}")

                    if "document_chunks" in existing_tables:
                        chunk_cols = {col["name"] for col in inspector.get_columns("document_chunks")}
                        new_chunk_cols = {
                            "page_start": "INTEGER",
                            "page_end": "INTEGER",
                        }
                        for col_name, col_type in new_chunk_cols.items():
                            if col_name not in chunk_cols:
                                conn.execute(text(f"ALTER TABLE document_chunks ADD COLUMN {col_name} {col_type}"))
                                conn.commit()
                                logger.info(f"Added missing column '{col_name}' ({col_type}) to document_chunks table.")

                        # Ensure document_id and chunk_index indexes on document_chunks
                        try:
                            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id)"))
                            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_doc_chunk_idx ON document_chunks(document_id, chunk_index)"))
                            if engine.dialect.name == "postgresql":
                                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chunks_fts ON document_chunks USING gin(to_tsvector('english', text))"))
                            conn.commit()
                        except Exception as idx_err:
                            logger.debug(f"Index creation note: {idx_err}")

                    if "document_metadata" in existing_tables:
                        meta_cols = {col["name"] for col in inspector.get_columns("document_metadata")}
                        new_meta_cols = {
                            "department": "VARCHAR(100)",
                            "page_count": "INTEGER",
                            "language": "VARCHAR(20)",
                            "ocr_applied": "BOOLEAN DEFAULT FALSE",
                            "table_count": "INTEGER DEFAULT 0",
                            "processed_at": "TIMESTAMP",
                        }
                        for col_name, col_type in new_meta_cols.items():
                            if col_name not in meta_cols:
                                conn.execute(text(f"ALTER TABLE document_metadata ADD COLUMN {col_name} {col_type}"))
                                conn.commit()
                                logger.info(f"Added missing column '{col_name}' ({col_type}) to document_metadata table.")
                        try:
                            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_metadata_department ON document_metadata(department)"))
                            conn.commit()
                        except Exception as idx_err:
                            logger.debug(f"Metadata department index note: {idx_err}")

                    if "chat_messages" in existing_tables:
                        msg_cols = {col["name"] for col in inspector.get_columns("chat_messages")}
                        new_msg_cols = {
                            "sources_json": "TEXT",
                            "retrieval_metadata_json": "TEXT",
                        }
                        for col_name, col_type in new_msg_cols.items():
                            if col_name not in msg_cols:
                                conn.execute(text(f"ALTER TABLE chat_messages ADD COLUMN {col_name} {col_type}"))
                                conn.commit()
                                logger.info(f"Added missing column '{col_name}' ({col_type}) to chat_messages table.")

                    if "chat_sessions" in existing_tables:
                        try:
                            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at)"))
                            conn.commit()
                        except Exception as idx_err:
                            logger.debug(f"ChatSession index note: {idx_err}")
            except Exception as mig_err:
                logger.warning(f"Schema migration check note: {mig_err}")

            # Seed default administrator if not present
            try:
                from app.models.user import User
                from app.core.security import hash_password
                from sqlalchemy.orm import Session
                with Session(bind=engine) as seed_db:
                    admin_exists = seed_db.query(User).filter(
                        (User.role == "ADMIN") | (User.email == settings.ADMIN_EMAIL)
                    ).first()
                    if not admin_exists:
                        admin_user = User(
                            username=settings.ADMIN_USERNAME,
                            email=settings.ADMIN_EMAIL,
                            hashed_password=hash_password(settings.ADMIN_PASSWORD),
                            role="ADMIN",
                            is_active=True,
                        )
                        seed_db.add(admin_user)
                        seed_db.commit()
                        logger.info(f"Default admin user created: {settings.ADMIN_EMAIL}")
            except Exception as seed_err:
                logger.warning(f"Admin seeding notice: {seed_err}")

            logger.info("Database tables verified/initialized successfully.")
        else:
            logger.warning("Database is currently unreachable. Operating with degraded data layer.")
    except Exception as exc:
        logger.warning(f"Database table initialization notice: {exc}")
