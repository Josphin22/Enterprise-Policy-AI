"""
TxtLoader reads plain text policy documents with multi-encoding fallback and section detection.
"""
import logging
from pathlib import Path
from typing import List, Optional
from app.services.document_processing.base_loader import BaseDocumentLoader, ExtractedBlock
from app.services.document_processing.section_detector import section_detector
from app.services.document_processing.table_extractor import table_extractor
from app.utils.errors import CorruptedDocumentError

logger = logging.getLogger("enterprise_rag.document_processing.txt")


class TxtLoader(BaseDocumentLoader):
    """
    Reads plain text files with robust multi-encoding fallback (UTF-8, Latin-1, CP1252),
    detects sections, and parses text-based tables.
    """

    def load(self, file_path: Path, **kwargs) -> List[ExtractedBlock]:
        if not file_path.exists():
            raise FileNotFoundError(f"TXT document not found at: {file_path}")

        raw_text = ""
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
        success_encoding = None

        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    raw_text = f.read()
                success_encoding = enc
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if success_encoding is None:
            # Final fallback with replacement characters
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    raw_text = f.read()
                success_encoding = "utf-8 (with replacement)"
            except Exception as read_err:
                raise CorruptedDocumentError(f"Unable to read text document '{file_path.name}': {read_err}") from read_err

        logger.info(f"TxtLoader read {file_path.name} using {success_encoding} ({len(raw_text)} chars)")

        # Detect any prominent initial section or headers
        detected_sections = section_detector.extract_all_headings(raw_text)
        primary_section = detected_sections[0] if detected_sections else None

        # Check for text tables
        tables = table_extractor.detect_text_tables(raw_text)

        return [
            ExtractedBlock(
                text=raw_text,
                page_number=None,
                section=primary_section,
                metadata={
                    "filename": file_path.name,
                    "file_type": "txt",
                    "encoding": success_encoding,
                    "sections": detected_sections,
                    "table_count": len(tables),
                },
            )
        ]


txt_loader = TxtLoader()
