import os
from typing import List, Set, Optional
from pathlib import Path
from dotenv import load_dotenv

# Base backend directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if available
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class Settings:
    # Application Info
    APP_NAME: str = os.getenv("APP_NAME", "Enterprise Policy RAG API")
    APP_DESCRIPTION: str = (
        "Backend API for a local enterprise document question-answering "
        "system using Retrieval-Augmented Generation."
    )
    APP_VERSION: str = "1.0.0"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # CORS Origins
    _raw_cors = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    )
    CORS_ORIGINS: List[str] = [
        origin.strip() for origin in _raw_cors.split(",") if origin.strip()
    ]
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Database Configuration (defaults to SQLite if not specified, supports PostgreSQL)
    _raw_db_url = os.getenv("DATABASE_URL")
    if not _raw_db_url:
        DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'enterprise_rag.db').resolve().as_posix()}"
    elif _raw_db_url.startswith("sqlite:///./"):
        _rel_part = _raw_db_url.replace("sqlite:///./", "")
        DATABASE_URL: str = f"sqlite:///{(BASE_DIR / _rel_part).resolve().as_posix()}"
    else:
        DATABASE_URL: str = _raw_db_url

    # Document Upload & Storage Paths
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
    ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt"}
    ALLOWED_MIME_TYPES: Set[str] = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "application/octet-stream",
    }
    DOCUMENTS_DIR: Path = Path(os.getenv("DOCUMENTS_DIR", str(BASE_DIR / "documents")))
    VECTORSTORE_DIR: Path = Path(
        os.getenv("VECTOR_STORE_PATH", os.getenv("VECTORSTORE_DIR", str(BASE_DIR / "vectorstore")))
    )
    VECTOR_STORE_PATH: str = str(VECTORSTORE_DIR)

    # Chunking Configurations (Phase 1/3/5 standard: default 900 chars, 120 overlap)
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "900"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "120"))

    # Embedding Configurations (Phase 1/4/6 standard: all-MiniLM-L6-v2, 384d)
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL",
        os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"),
    )
    EMBEDDING_MODEL_NAME: str = EMBEDDING_MODEL
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

    # Retrieval & Threshold Configurations (Phase 1/5/6 standard: Top-K=5, Min Score=0.35)
    RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "8"))
    TOP_K: int = RETRIEVAL_TOP_K
    RAG_TOP_K: int = RETRIEVAL_TOP_K

    SIMILARITY_THRESHOLD: float = float(
        os.getenv("SIMILARITY_THRESHOLD", os.getenv("RELEVANCE_THRESHOLD", os.getenv("RAG_MIN_SCORE", "0.35")))
    )
    RELEVANCE_THRESHOLD: float = SIMILARITY_THRESHOLD
    RAG_MIN_SCORE: float = SIMILARITY_THRESHOLD

    RAG_MAX_CONTEXT_CHUNKS: int = int(os.getenv("RAG_MAX_CONTEXT_CHUNKS", "5"))
    RAG_MAX_CONTEXT_CHARACTERS: int = int(os.getenv("RAG_MAX_CONTEXT_CHARACTERS", "6000"))
    RAG_INCLUDE_ADJACENT_CHUNKS: bool = os.getenv("RAG_INCLUDE_ADJACENT_CHUNKS", "False").lower() in ("true", "1", "t")
    RAG_DEBUG: bool = os.getenv("RAG_DEBUG", "False").lower() in ("true", "1", "t")

    # Local LLM & Ollama Configurations (Phase 1/6 standard: llama3.2:3b @ http://127.0.0.1:11434)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))
    OLLAMA_TOP_P: float = float(os.getenv("OLLAMA_TOP_P", "0.9"))
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
    OLLAMA_MAX_TOKENS: int = int(os.getenv("OLLAMA_MAX_TOKENS", "1000"))

    # Phase 7 Settings: Reranking, Rate Limiting & Background Reindexing
    ENABLE_RERANKING: bool = os.getenv("ENABLE_RERANKING", "False").lower() in ("true", "1", "t")
    CHAT_RATE_LIMIT: str = os.getenv("CHAT_RATE_LIMIT", "30/minute")
    AUTO_REINDEX: bool = os.getenv("AUTO_REINDEX", "True").lower() in ("true", "1", "t")

    # Phase 8 Settings: Security, RBAC & Authentication
    JWT_SECRET: str = os.getenv("JWT_SECRET", "enterprise_jwt_super_secret_key_2026_change_in_prod")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@enterprise.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "Admin@Enterprise2026!")
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")

    # Phase 10 Settings: Advanced Document Intelligence & OCR
    ENABLE_OCR: bool = os.getenv("ENABLE_OCR", "False").lower() in ("true", "1", "t")
    OCR_ENGINE: str = os.getenv("OCR_ENGINE", "pytesseract")
    TESSERACT_CMD: Optional[str] = os.getenv("TESSERACT_CMD", None)
    OCR_MIN_TEXT_LENGTH: int = int(os.getenv("OCR_MIN_TEXT_LENGTH", "50"))

    # Phase 11 Settings: RBAC, Fine-Grained Permissions & Login Throttling
    LOGIN_MAX_FAILED_ATTEMPTS: int = int(os.getenv("LOGIN_MAX_FAILED_ATTEMPTS", "5"))
    LOGIN_LOCKOUT_MINUTES: int = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "15"))
    DEFAULT_DOCUMENT_VISIBILITY: str = os.getenv("DEFAULT_DOCUMENT_VISIBILITY", "ORGANIZATION")

    # Phase 12 Settings: AI Evaluation & Safety Guardrails
    MAX_ANSWER_TOKENS: int = int(os.getenv("MAX_ANSWER_TOKENS", "600"))
    MAX_ANSWER_CHARACTERS: int = int(os.getenv("MAX_ANSWER_CHARACTERS", "3000"))
    ENABLE_GUARDRAILS: bool = os.getenv("ENABLE_GUARDRAILS", "True").lower() in ("true", "1", "t")
    ENABLE_SENSITIVE_DATA_SCRUB: bool = os.getenv("ENABLE_SENSITIVE_DATA_SCRUB", "True").lower() in ("true", "1", "t")
    GROUNDING_SIMILARITY_THRESHOLD: float = float(os.getenv("GROUNDING_SIMILARITY_THRESHOLD", "0.45"))

    def __init__(self):
        # Ensure essential directories exist
        self.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
