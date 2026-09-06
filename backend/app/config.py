import os
from typing import List, Set
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

    # Document upload configurations
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))
    ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt"}
    ALLOWED_MIME_TYPES: Set[str] = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "application/octet-stream",  # Fallback for generic binary/text streams
    }

    # Storage paths
    DOCUMENTS_DIR: Path = BASE_DIR / "documents"
    VECTORSTORE_DIR: Path = BASE_DIR / "vectorstore"

    # Chunking configurations (Phase 5)
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

    # Future integration settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/enterprise_rag"
    )
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    # Embedding and Vector Store configurations (Phase 6)
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL", os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    )
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

    # RAG Retrieval & Context Construction configurations (Phase 7)
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
    RAG_MIN_SCORE: float = float(os.getenv("RAG_MIN_SCORE", "0.35"))
    RAG_MAX_CONTEXT_CHUNKS: int = int(os.getenv("RAG_MAX_CONTEXT_CHUNKS", "5"))
    RAG_MAX_CONTEXT_CHARACTERS: int = int(os.getenv("RAG_MAX_CONTEXT_CHARACTERS", "6000"))
    RAG_INCLUDE_ADJACENT_CHUNKS: bool = os.getenv("RAG_INCLUDE_ADJACENT_CHUNKS", "False").lower() in ("true", "1", "t")
    RAG_DEBUG: bool = os.getenv("RAG_DEBUG", "False").lower() in ("true", "1", "t")

    # Local LLM & Ollama configurations (Phase 8)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))
    OLLAMA_TOP_P: float = float(os.getenv("OLLAMA_TOP_P", "0.9"))
    OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

    def __init__(self):
        # Ensure essential directories exist
        self.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
