import logging
from pathlib import Path
from typing import List
from pypdf import PdfReader
from app.services.document_processing.base_loader import BaseDocumentLoader, ExtractedBlock

logger = logging.getLogger("enterprise_rag.document_processing.pdf")


class PDFLoader(BaseDocumentLoader):
    """
    Extracts text page-by-page from PDF policy documents using pypdf.
    Preserves exact 1-indexed page numbers and records warnings for image-only/blank pages.
    """

    def load(self, file_path: Path, **kwargs) -> List[ExtractedBlock]:
        if not file_path.exists():
            raise FileNotFoundError(f"PDF document not found at: {file_path}")

        extracted_blocks: List[ExtractedBlock] = []

        try:
            reader = PdfReader(str(file_path))
            total_pages = len(reader.pages)
            logger.info(f"PDFLoader parsing {file_path.name} ({total_pages} pages)")

            if total_pages == 0:
                logger.warning(f"PDF {file_path.name} contains 0 pages.")
                return extracted_blocks

            for idx, page in enumerate(reader.pages):
                page_num = idx + 1
                try:
                    page_text = page.extract_text() or ""
                except Exception as extract_err:
                    logger.warning(f"Error extracting text from page {page_num} in {file_path.name}: {extract_err}")
                    page_text = ""

                warning = None
                if not page_text.strip():
                    warning = "text_extraction_warning: No extractable text found on page (may be scanned or image-only)."
                    logger.debug(f"Page {page_num} in {file_path.name} has no extractable text.")

                extracted_blocks.append(
                    ExtractedBlock(
                        text=page_text,
                        page_number=page_num,
                        section=None,
                        metadata={
                            "filename": file_path.name,
                            "file_type": "pdf",
                            "page": page_num,
                            "total_pages": total_pages,
                        },
                        warning=warning,
                    )
                )

        except Exception as exc:
            logger.error(f"Failed to parse PDF file '{file_path}': {exc}", exc_info=True)
            raise ValueError(f"Corrupted or unreadable PDF document: {exc}") from exc

        return extracted_blocks


pdf_loader = PDFLoader()
