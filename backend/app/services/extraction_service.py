"""
ExtractionService coordinating multi-format document text extraction across PDF, DOCX, and TXT files.
Implements the standardized Phase 2 and Phase 10 interfaces:
extract_document(file_path, file_type) -> {
    "text": str,
    "pages": List[Dict[str, Any]],
    "total_pages": int,
    "character_count": int,
    "sections": List[str],
    "table_count": int,
    "ocr_applied": bool,
    "language": Optional[str],
}
"""
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.services.document_processing.base_loader import ExtractedBlock
from app.services.document_processing.pdf_loader import pdf_loader
from app.services.document_processing.docx_loader import docx_loader
from app.services.document_processing.txt_loader import txt_loader
from app.services.document_processing.text_cleaner import text_cleaner
from app.services.document_processing.section_detector import section_detector
from app.utils.errors import (
    EmptyDocumentError,
    InvalidFileTypeError,
    DocumentExtractionFailedError,
    PasswordProtectedError,
    CorruptedDocumentError,
    ImageOnlyDocumentError,
    OCRProcessingError,
)

logger = logging.getLogger("enterprise_rag.extraction_service")


def _detect_language_heuristic(text: str) -> Optional[str]:
    """
    Heuristic language detection without heavy external libraries.
    Evaluates common English stop words and Latin character ratio.
    """
    if not text or len(text.strip()) < 30:
        return None

    ascii_alpha = sum(1 for c in text if c.isascii() and c.isalpha())
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0 or (ascii_alpha / total_alpha) < 0.7:
        return None

    common_english = {"the", "and", "for", "are", "with", "this", "that", "from", "policy", "employee", "leave", "shall", "work"}
    words = {w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", text[:2000])}
    if len(words.intersection(common_english)) >= 2:
        return "en"
    return None


class ExtractionService:
    """Multi-format enterprise document extraction service with table, section, and OCR intelligence."""

    @staticmethod
    def extract_document(file_path: Path, file_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract clean text, tables, sections, and structural page data from PDF, DOCX, or TXT document.
        Validates content and raises EmptyDocumentError if no readable text is present.
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {path_obj}")

        suffix = (file_type or path_obj.suffix).lower().lstrip(".")

        try:
            if suffix == "pdf":
                blocks: List[ExtractedBlock] = pdf_loader.load(path_obj)
            elif suffix == "docx":
                blocks: List[ExtractedBlock] = docx_loader.load(path_obj)
            elif suffix == "txt":
                blocks: List[ExtractedBlock] = txt_loader.load(path_obj)
            else:
                raise InvalidFileTypeError(f"Unsupported file format '.{suffix}'. Supported: .pdf, .docx, .txt")

        except (EmptyDocumentError, PasswordProtectedError, CorruptedDocumentError, InvalidFileTypeError, ImageOnlyDocumentError, OCRProcessingError):
            raise
        except Exception as exc:
            logger.error(f"Text extraction failed for {path_obj.name}: {exc}", exc_info=True)
            raise DocumentExtractionFailedError(f"Unable to extract readable text from '{path_obj.name}': {str(exc)}") from exc

        # Structure pages and normalize text
        pages: List[Dict[str, Any]] = []
        valid_texts: List[str] = []
        total_tables = 0
        ocr_applied_overall = False
        all_sections: List[str] = []
        seen_sections = set()

        for block in blocks:
            cleaned = text_cleaner.clean(block.text)
            if cleaned:
                valid_texts.append(cleaned)

            meta = block.metadata or {}
            if meta.get("ocr_applied"):
                ocr_applied_overall = True
            total_tables += meta.get("table_count", 1 if meta.get("is_table") else 0)

            if block.section and block.section.lower() not in seen_sections:
                all_sections.append(block.section)
                seen_sections.add(block.section.lower())

            pages.append({
                "page_number": block.page_number,
                "text": cleaned,
                "section": block.section,
                "metadata": meta,
            })

        combined_text = "\n\n".join(valid_texts).strip()

        # Check for empty or whitespace-only documents
        if not combined_text:
            logger.warning(f"Extracted text for {path_obj.name} is empty or whitespace-only.")
            raise EmptyDocumentError(f"No extractable text was found in '{path_obj.name}'.")

        # Discover any additional sections across combined text
        detected_headings = section_detector.extract_all_headings(combined_text)
        for h in detected_headings:
            if h.lower() not in seen_sections:
                all_sections.append(h)
                seen_sections.add(h.lower())

        lang = _detect_language_heuristic(combined_text)

        logger.info(
            f"Extraction completed for {path_obj.name}: {len(pages)} pages/blocks, "
            f"{len(combined_text)} characters, {len(all_sections)} sections, {total_tables} tables."
        )

        return {
            "text": combined_text,
            "pages": pages,
            "total_pages": len(pages),
            "character_count": len(combined_text),
            "sections": all_sections,
            "table_count": total_tables,
            "ocr_applied": ocr_applied_overall,
            "language": lang,
        }

    # Backward compatibility
    @classmethod
    def extract(cls, file_path: Path) -> List[ExtractedBlock]:
        result = cls.extract_document(file_path)
        return [
            ExtractedBlock(
                text=p["text"],
                page_number=p["page_number"],
                section=p.get("section"),
                metadata={"filename": file_path.name},
            )
            for p in result["pages"]
        ]


extraction_service = ExtractionService()
