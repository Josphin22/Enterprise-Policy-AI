"""
PDFLoader extracts text, tables, sections, and page metadata page-by-page from PDF documents using PyMuPDF (fitz).
Integrates:
- Password protection detection (PasswordProtectedError)
- File corruption detection (CorruptedDocumentError)
- Structured markdown table extraction (TableExtractor)
- Heading & section detection (SectionDetector)
- Conservative repeated header/footer cleaning (HeaderFooterCleaner)
- Selective OCR for scanned/image-only pages (OCRService)
"""
import logging
from pathlib import Path
from typing import List, Optional
import pymupdf  # PyMuPDF
from app.services.document_processing.base_loader import BaseDocumentLoader, ExtractedBlock
from app.services.document_processing.text_cleaner import text_cleaner
from app.services.document_processing.table_extractor import table_extractor
from app.services.document_processing.section_detector import section_detector
from app.services.document_processing.header_footer_cleaner import header_footer_cleaner
from app.services.document_processing.ocr_service import ocr_service
from app.utils.errors import PasswordProtectedError, CorruptedDocumentError, EmptyDocumentError

logger = logging.getLogger("enterprise_rag.document_processing.pdf")


class PDFLoader(BaseDocumentLoader):
    """
    Extracts text page-by-page from PDF policy documents using PyMuPDF (fitz).
    Preserves exact 1-indexed page numbers, structural paragraph breaks, and table data.
    """

    def load(self, file_path: Path, **kwargs) -> List[ExtractedBlock]:
        if not file_path.exists():
            raise FileNotFoundError(f"PDF document not found at: {file_path}")

        extracted_blocks: List[ExtractedBlock] = []

        try:
            try:
                doc = pymupdf.open(str(file_path))
            except Exception as open_err:
                logger.error(f"PyMuPDF open error for '{file_path.name}': {open_err}")
                raise CorruptedDocumentError(
                    f"Corrupted or unreadable PDF document '{file_path.name}': {open_err}"
                ) from open_err

            # Check for encryption or password protection
            if doc.is_encrypted or getattr(doc, "needs_pass", False):
                doc.close()
                logger.warning(f"PDF {file_path.name} is password protected.")
                raise PasswordProtectedError(
                    f"PDF document '{file_path.name}' is password-protected or encrypted."
                )

            total_pages = len(doc)
            logger.info(f"PDFLoader parsing {file_path.name} ({total_pages} pages) using PyMuPDF")

            if total_pages == 0:
                logger.warning(f"PDF {file_path.name} contains 0 pages.")
                doc.close()
                return extracted_blocks

            current_section: Optional[str] = None
            page_blocks_raw: List[dict] = []

            for idx, page in enumerate(doc):
                page_num = idx + 1
                try:
                    # 1. Extract native text
                    raw_page_text = page.get_text() or ""
                except Exception as extract_err:
                    logger.warning(f"Error extracting text from page {page_num} in {file_path.name}: {extract_err}")
                    raw_page_text = ""

                cleaned_text = text_cleaner.clean(raw_page_text)
                ocr_applied_on_page = False

                # 2. Check if page warrants selective OCR (low text + visual elements)
                if ocr_service.should_ocr_page(page, cleaned_text):
                    logger.info(f"Page {page_num} in {file_path.name} has low text; executing selective OCR.")
                    try:
                        ocr_result = ocr_service.ocr_page(page)
                        if ocr_result and len(ocr_result.strip()) > len(cleaned_text):
                            cleaned_text = text_cleaner.clean(ocr_result)
                            ocr_applied_on_page = True
                    except Exception as ocr_err:
                        logger.warning(f"Selective OCR failed on page {page_num}: {ocr_err}")

                # 3. Extract tables from this page
                page_tables = table_extractor.extract_tables_from_pdf_page(page, page_num=page_num)
                if page_tables:
                    table_mds = [t["markdown"] for t in page_tables if t.get("markdown")]
                    if table_mds:
                        joined_tables = "\n\n".join(table_mds)
                        if cleaned_text:
                            cleaned_text = f"{cleaned_text}\n\n{joined_tables}"
                        else:
                            cleaned_text = joined_tables

                # 4. Detect section headings on this page
                for line in cleaned_text.split("\n"):
                    h = section_detector.detect_heading(line)
                    if h:
                        current_section = h

                page_blocks_raw.append({
                    "page_number": page_num,
                    "text": cleaned_text,
                    "section": current_section,
                    "tables": page_tables,
                    "ocr_applied": ocr_applied_on_page,
                })

            doc.close()

            # 5. Apply conservative header/footer cleaning across pages if multi-page
            if total_pages >= 3:
                cleaned_page_data = header_footer_cleaner.clean_pages(page_blocks_raw)
            else:
                cleaned_page_data = page_blocks_raw

            # 6. Build final ExtractedBlock list
            for pb in cleaned_page_data:
                p_text = pb["text"]
                p_num = pb["page_number"]
                warning = None
                if not p_text:
                    warning = "text_extraction_warning: No extractable text found on page."

                extracted_blocks.append(
                    ExtractedBlock(
                        text=p_text,
                        page_number=p_num,
                        section=pb.get("section"),
                        metadata={
                            "filename": file_path.name,
                            "file_type": "pdf",
                            "page": p_num,
                            "total_pages": total_pages,
                            "ocr_applied": pb.get("ocr_applied", False),
                            "table_count": len(pb.get("tables", [])),
                        },
                        warning=warning,
                    )
                )

        except (PasswordProtectedError, CorruptedDocumentError, EmptyDocumentError):
            raise
        except Exception as exc:
            logger.error(f"Failed to parse PDF file '{file_path}': {exc}", exc_info=True)
            raise CorruptedDocumentError(f"Corrupted or unreadable PDF document: {exc}") from exc

        return extracted_blocks


pdf_loader = PDFLoader()
