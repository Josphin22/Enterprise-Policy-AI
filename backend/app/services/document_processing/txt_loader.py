import logging
from pathlib import Path
from typing import List
from app.services.document_processing.base_loader import BaseDocumentLoader, ExtractedBlock

logger = logging.getLogger("enterprise_rag.document_processing.txt")


class TxtLoader(BaseDocumentLoader):
    """
    Reads plain text files with robust multi-encoding fallback (UTF-8, Latin-1, CP1252).
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
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()
            success_encoding = "utf-8 (with replacement)"

        logger.info(f"TxtLoader read {file_path.name} using {success_encoding} ({len(raw_text)} chars)")

        return [
            ExtractedBlock(
                text=raw_text,
                page_number=None,
                section=None,
                metadata={
                    "filename": file_path.name,
                    "file_type": "txt",
                    "encoding": success_encoding,
                },
            )
        ]


txt_loader = TxtLoader()
