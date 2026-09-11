"""
OCR service providing local OCR capability for scanned documents and image-based PDF pages.
Executes selectively only on pages with insufficient extracted text when ENABLE_OCR=True.
"""
import io
import logging
from typing import Optional, Callable
from PIL import Image
import pymupdf
from app.config import settings
from app.utils.errors import OCRProcessingError

logger = logging.getLogger("enterprise_rag.document_processing.ocr")


class OCRService:
    """
    Locally deployable OCR service for scanned PDF pages and embedded images.
    Adheres to strict performance principles:
    - Never runs when ENABLE_OCR=False.
    - Runs selectively only when page text is below minimum threshold and page contains images/visuals.
    - Handles engine absence and runtime errors gracefully without crashing the pipeline.
    """

    def __init__(self):
        self._custom_ocr_handler: Optional[Callable[[Image.Image], str]] = None

    @property
    def is_enabled(self) -> bool:
        return bool(settings.ENABLE_OCR)

    def set_custom_handler(self, handler: Optional[Callable[[Image.Image], str]]) -> None:
        """Allow injecting custom/mock OCR handler for testing or alternate local OCR engines."""
        self._custom_ocr_handler = handler

    def should_ocr_page(self, page: pymupdf.Page, extracted_text: str) -> bool:
        """
        Determine whether a PDF page warrants OCR.
        Evaluates:
        1. Is OCR enabled globally?
        2. Is the extracted text length below the minimum threshold?
        3. Does the page contain image objects or visual drawings indicating scanned content?
        """
        if not self.is_enabled:
            return False

        clean_text = (extracted_text or "").strip()
        if len(clean_text) >= settings.OCR_MIN_TEXT_LENGTH:
            # Page already contains sufficient native text; avoid costly OCR pass
            return False

        # Check if page contains images or graphics
        try:
            images = page.get_images()
            if len(images) > 0:
                return True
        except Exception:
            pass

        try:
            drawings = page.get_drawings()
            if len(drawings) > 0:
                return True
        except Exception:
            pass

        # If page text is virtually empty (< 10 chars) on a multi-pixel page, treat as scanned
        rect = page.rect
        if rect.width > 100 and rect.height > 100 and len(clean_text) < 10:
            return True

        return False

    def ocr_page(self, page: pymupdf.Page, dpi: int = 150) -> str:
        """
        Perform OCR on a single PyMuPDF page by rendering to pixmap and processing with local OCR.
        Returns extracted text, or raises OCRProcessingError / returns empty on failure.
        """
        if not self.is_enabled:
            return ""

        try:
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            pil_image = Image.open(io.BytesIO(img_bytes))
        except Exception as render_err:
            logger.error(f"Failed to render PDF page to image for OCR: {render_err}", exc_info=True)
            raise OCRProcessingError(f"Failed to render page image for OCR: {render_err}") from render_err

        # Check if a custom/mock handler is registered
        if self._custom_ocr_handler is not None:
            try:
                return self._custom_ocr_handler(pil_image)
            except Exception as custom_err:
                logger.warning(f"Custom OCR handler error: {custom_err}")
                raise OCRProcessingError(f"OCR handler failure: {custom_err}") from custom_err

        # 1. Try RapidOCR (high accuracy offline engine based on ONNXRuntime)
        try:
            from rapidocr_onnxruntime import RapidOCR
            if not hasattr(self, "_rapid_ocr_engine"):
                self._rapid_ocr_engine = RapidOCR()
            ocr_res, _ = self._rapid_ocr_engine(img_bytes)
            if ocr_res:
                ocr_text = "\n".join([line[1] for line in ocr_res if len(line) > 1 and line[1]])
                if ocr_text.strip():
                    logger.info(f"RapidOCR successfully extracted {len(ocr_text)} characters from page.")
                    return ocr_text
        except Exception as rapid_err:
            logger.debug(f"RapidOCR pass failed or not available: {rapid_err}")

        # 2. Fallback to pytesseract
        try:
            import pytesseract

            if settings.TESSERACT_CMD:
                pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

            ocr_text = pytesseract.image_to_string(pil_image)
            logger.info(f"pytesseract extracted {len(ocr_text)} characters from page.")
            return ocr_text or ""
        except ImportError:
            logger.warning("pytesseract and RapidOCR both unavailable for scanned page OCR.")
            return ""
        except Exception as ocr_err:
            logger.warning(f"Local OCR engine encountered an error: {ocr_err}")
            return ""

    def ocr_image_bytes(self, image_bytes: bytes) -> str:
        """OCR directly from raw image bytes (e.g. uploaded standalone scan)."""
        if not self.is_enabled:
            return ""

        # 1. Try RapidOCR
        try:
            from rapidocr_onnxruntime import RapidOCR
            if not hasattr(self, "_rapid_ocr_engine"):
                self._rapid_ocr_engine = RapidOCR()
            ocr_res, _ = self._rapid_ocr_engine(image_bytes)
            if ocr_res:
                ocr_text = "\n".join([line[1] for line in ocr_res if len(line) > 1 and line[1]])
                if ocr_text.strip():
                    return ocr_text
        except Exception:
            pass

        # 2. Fallback
        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            if self._custom_ocr_handler is not None:
                return self._custom_ocr_handler(pil_image)

            import pytesseract
            if settings.TESSERACT_CMD:
                pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
            return pytesseract.image_to_string(pil_image) or ""
        except Exception as exc:
            logger.warning(f"OCR image bytes failed: {exc}")
            return ""


ocr_service = OCRService()
