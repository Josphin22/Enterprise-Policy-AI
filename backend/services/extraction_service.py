"""
Re-export extraction_service from app.services.extraction_service
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.extraction_service import extraction_service, ExtractionService

__all__ = ["extraction_service", "ExtractionService"]
