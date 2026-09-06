import uuid
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import settings
from app.services.document_processing.base_loader import ExtractedBlock

logger = logging.getLogger("enterprise_rag.document_processing.chunker")


@dataclass
class ProcessedChunk:
    """
    Structured representation of a document chunk prepared for PostgreSQL storage and future embedding.
    """
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    page_number: Optional[int]
    section: Optional[str]
    character_count: int
    metadata: Dict[str, Any]


class DocumentChunker:
    """
    Partitions extracted document text into semantic chunks using recursive splitting.
    Preserves page boundaries, sections, and exact policy rules with configurable chunk size and overlap.
    """

    def __init__(self, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
            length_function=len,
            is_separator_regex=False,
        )

    def create_chunks(
        self,
        document_id: str,
        filename: str,
        file_type: str,
        extracted_blocks: List[ExtractedBlock],
    ) -> List[ProcessedChunk]:
        """
        Splits list of extracted blocks into ordered chunks while preserving page and section context.
        """
        chunks: List[ProcessedChunk] = []
        global_chunk_idx = 0

        for block in extracted_blocks:
            clean_text = block.text.strip()
            if not clean_text:
                continue

            # If the block text is smaller than chunk_size, keep as single chunk without fragmentation
            if len(clean_text) <= self.chunk_size:
                raw_splits = [clean_text]
            else:
                raw_splits = self.splitter.split_text(clean_text)

            for split_text in raw_splits:
                trimmed = split_text.strip()
                # Discard trivial empty chunks or noise, but keep short policy statements (e.g. "Max leave: 15 days")
                if not trimmed:
                    continue

                chunk_id = str(uuid.uuid4())
                char_count = len(trimmed)

                chunk_meta = {
                    "document_id": document_id,
                    "filename": filename,
                    "file_type": file_type,
                    "chunk_index": global_chunk_idx,
                    "page": block.page_number,
                    "section": block.section,
                    "character_count": char_count,
                }

                chunks.append(
                    ProcessedChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        chunk_index=global_chunk_idx,
                        text=trimmed,
                        page_number=block.page_number,
                        section=block.section,
                        character_count=char_count,
                        metadata=chunk_meta,
                    )
                )
                global_chunk_idx += 1

        logger.info(
            f"Chunker generated {len(chunks)} chunks for document {document_id} "
            f"(chunk_size={self.chunk_size}, overlap={self.chunk_overlap})"
        )
        return chunks


document_chunker = DocumentChunker()
