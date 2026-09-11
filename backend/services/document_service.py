"""
Re-export document_service from app.services.document_service
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.document_service import document_service, DocumentService

__all__ = ["document_service", "DocumentService"]
