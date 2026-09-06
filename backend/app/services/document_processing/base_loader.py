from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class ExtractedBlock:
    """
    Standardized internal representation of extracted document content.
    """
    text: str
    page_number: Optional[int] = None  # 1-indexed for PDF, None for DOCX/TXT
    section: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    warning: Optional[str] = None


class BaseDocumentLoader(ABC):
    """
    Abstract base loader defining standard interface for multi-format enterprise document parsing.
    """

    @abstractmethod
    def load(self, file_path: Path, **kwargs) -> List[ExtractedBlock]:
        """
        Extract text content and page/structural metadata from file.
        Returns a list of ExtractedBlock instances.
        """
        pass
