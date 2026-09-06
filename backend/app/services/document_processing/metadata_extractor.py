import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from app.models.document import Document


class MetadataExtractor:
    """
    Extracts and normalizes document and chunk metadata for persistent logging and tracking.
    """

    @staticmethod
    def extract_document_metadata(document: Document, total_chars: int, page_count: Optional[int] = None) -> Dict[str, Any]:
        return {
            "document_id": document.id,
            "filename": document.filename,
            "original_filename": document.original_filename,
            "file_type": document.file_type,
            "file_size": document.file_size,
            "character_count": total_chars,
            "page_count": page_count,
            "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    @staticmethod
    def extract_chunk_metadata(
        document_id: str,
        filename: str,
        file_type: str,
        chunk_index: int,
        page_number: Optional[int],
        section: Optional[str],
        char_count: int,
    ) -> Dict[str, Any]:
        return {
            "document_id": document_id,
            "filename": filename,
            "file_type": file_type,
            "chunk_index": chunk_index,
            "page": page_number,
            "section": section,
            "character_count": char_count,
        }


metadata_extractor = MetadataExtractor()
