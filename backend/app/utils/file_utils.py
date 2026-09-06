import re
import json
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import settings

METADATA_FILE = settings.DOCUMENTS_DIR / "metadata.json"


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and remove unsafe characters.
    """
    # Remove any directory components (e.g., ../ or \\)
    clean_name = Path(filename).name
    # Replace non-alphanumeric/dot/hyphen/underscore characters with underscore
    clean_name = re.sub(r"[^\w\.\-\s]", "_", clean_name)
    # Strip leading/trailing whitespaces and dots
    clean_name = clean_name.strip(" .")
    if not clean_name:
        clean_name = f"document_{uuid.uuid4().hex[:8]}"
    return clean_name


def generate_document_id() -> str:
    """Generate a unique document identifier."""
    return str(uuid.uuid4())


def get_file_extension(filename: str) -> str:
    """Get the lowercased file extension with leading dot (e.g., '.pdf')."""
    return Path(filename).suffix.lower()


def is_allowed_extension(filename: str) -> bool:
    """Check whether the filename has an allowed extension."""
    ext = get_file_extension(filename)
    return ext in settings.ALLOWED_EXTENSIONS


def load_metadata_registry() -> Dict[str, Dict[str, Any]]:
    """
    Load the document metadata registry from the JSON storage file.
    If the file does not exist, return an empty dictionary.
    """
    if not METADATA_FILE.exists():
        return {}
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_metadata_registry(registry: Dict[str, Dict[str, Any]]) -> None:
    """Save the document metadata registry to the JSON storage file."""
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def register_document(
    doc_id: str,
    original_filename: str,
    stored_filename: str,
    file_type: str,
    file_size: int,
    status: str = "uploaded"
) -> Dict[str, Any]:
    """Register a new document record in the metadata registry."""
    registry = load_metadata_registry()
    record = {
        "document_id": doc_id,
        "filename": original_filename,
        "stored_filename": stored_filename,
        "file_type": file_type.lstrip(".").lower(),
        "size": file_size,
        "status": status,
        "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    registry[doc_id] = record
    save_metadata_registry(registry)
    return record


def unregister_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Remove a document record from the metadata registry."""
    registry = load_metadata_registry()
    if doc_id in registry:
        record = registry.pop(doc_id)
        save_metadata_registry(registry)
        return record
    return None
