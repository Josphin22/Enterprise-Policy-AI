"""
Centralized configuration export for the Enterprise Policy AI Backend.
Aliases app.config.settings to allow direct imports via `import config` or `from backend.config import settings`.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path if needed
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings, Settings

__all__ = ["settings", "Settings"]
