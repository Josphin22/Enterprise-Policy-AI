import re
import uuid
import logging
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("enterprise_rag.services.chunking_service")


class ChunkingService:
    """
    Enterprise-grade document chunking service.
    Implements recursive paragraph-, heading-, and sentence-aware chunking with
    configurable target size and contextual overlap.
    Preserves page boundaries and metadata for citations and downstream RAG retrieval.
    """

    def __init__(self, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs while preserving structure."""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        raw_paras = normalized.split("\n\n")
        paragraphs = []
        for p in raw_paras:
            cleaned = p.strip()
            if cleaned:
                paragraphs.append(cleaned)
        return paragraphs

    def _split_into_sentences(self, paragraph: str) -> List[str]:
        """Split oversized paragraph into sentences without splitting words or numbers."""
        # Match sentence terminators (. ? !) followed by whitespace, avoiding decimals like 3.14 or 1.5
        sentence_pattern = r'(?<=[.?!])\s+(?=[A-Z0-9"\'])'
        raw_sentences = re.split(sentence_pattern, paragraph)
        sentences = [s.strip() for s in raw_sentences if s.strip()]
        return sentences if sentences else [paragraph]

    def _split_large_sentence(self, sentence: str, max_size: int) -> List[str]:
        """Split oversized sentence at word boundaries."""
        words = sentence.split()
        parts = []
        current = []
        curr_len = 0

        for word in words:
            word_len = len(word) + (1 if current else 0)
            if curr_len + word_len <= max_size:
                current.append(word)
                curr_len += word_len
            else:
                if current:
                    parts.append(" ".join(current))
                current = [word]
                curr_len = len(word)

        if current:
            parts.append(" ".join(current))

        return parts if parts else [sentence]

    def _get_overlap_prefix(self, previous_text: str, overlap_len: int) -> str:
        """
        Extract clean overlap prefix from the tail of previous chunk,
        breaking cleanly at a sentence or word boundary.
        """
        if not previous_text or overlap_len <= 0:
            return ""

        tail = previous_text[-overlap_len:].strip()
        # Find first whitespace or sentence boundary in tail to avoid cutting words
        first_space = tail.find(" ")
        if first_space != -1 and first_space < len(tail) - 1:
            clean_tail = tail[first_space + 1:].strip()
        else:
            clean_tail = tail

        return clean_tail

    def _detect_chunk_section(self, text: str, fallback: Optional[str] = None) -> Optional[str]:
        """Identify if chunk text contains or belongs to a specific section."""
        try:
            from app.services.document_processing.section_detector import section_detector
            for line in text.split("\n"):
                h = section_detector.detect_heading(line)
                if h:
                    return h
        except Exception:
            pass
        return fallback

    def chunk_document(
        self,
        text: str,
        document_id: str,
        filename: str = "",
        file_type: str = "txt",
        pages: Optional[List[Dict[str, Any]]] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Partition document text into structured chunks.

        Order of priority:
        1. Preserves document paragraphs and headings.
        2. Groups related paragraphs up to target chunk size.
        3. Splits oversized paragraphs at sentence boundaries.
        4. Applies contextual overlap between adjacent chunks.
        5. Preserves PDF page numbers (page_number, page_start, page_end).
        6. Rejects meaningless empty chunks.
        7. Preserves 1 chunk for documents smaller than chunk_size.
        """
        target_size = chunk_size or self.chunk_size
        overlap = chunk_overlap or self.chunk_overlap
        ext = file_type.lower().lstrip(".")

        clean_full_text = (text or "").strip()
        # Discard empty or whitespace-only documents
        if not clean_full_text or not any(c.isalnum() for c in clean_full_text):
            logger.warning(f"Chunking requested for empty or non-alphanumeric text (doc {document_id})")
            return []

        # Determine if real page information exists (PDF only)
        has_real_pages = (
            ext == "pdf"
            and bool(pages)
            and any(p.get("page_number") is not None for p in pages)
        )

        chunks: List[Dict[str, Any]] = []

        # Case A: Document smaller than chunk_size (or single-page document <= 2500 chars) -> Exactly 1 chunk
        single_page_limit = max(target_size, 2500) if (not has_real_pages or len(pages) <= 1) else target_size
        if len(clean_full_text) <= single_page_limit and not (has_real_pages and len(pages) > 1):
            page_num = pages[0].get("page_number") if has_real_pages and pages else None
            fb_section = pages[0].get("section") if pages else None
            chunk_obj = {
                "id": str(uuid.uuid4()),
                "chunk_id": str(uuid.uuid4()),
                "document_id": document_id,
                "chunk_index": 0,
                "text": clean_full_text,
                "page_number": page_num,
                "page_start": page_num,
                "page_end": page_num,
                "character_count": len(clean_full_text),
                "section": self._detect_chunk_section(clean_full_text, fb_section),
            }
            # Keep both id and chunk_id aligned
            chunk_obj["chunk_id"] = chunk_obj["id"]
            return [chunk_obj]

        # Case B: Multi-page PDF chunking with page preservation
        if has_real_pages and pages:
            chunk_index = 0
            prev_chunk_text = ""

            for page_entry in pages:
                page_text = (page_entry.get("text") or "").strip()
                page_num = page_entry.get("page_number")
                if not page_text or not any(c.isalnum() for c in page_text):
                    continue

                paragraphs = self._split_into_paragraphs(page_text)
                accumulated_text = ""

                for para in paragraphs:
                    candidate = f"{accumulated_text}\n\n{para}".strip() if accumulated_text else para

                    if len(candidate) <= target_size:
                        accumulated_text = candidate
                    else:
                        if accumulated_text:
                            # Prepend overlap from previous chunk if available and not redundant
                            overlap_prefix = self._get_overlap_prefix(prev_chunk_text, overlap)
                            final_text = (
                                f"{overlap_prefix}\n{accumulated_text}".strip()
                                if overlap_prefix and not accumulated_text.startswith(overlap_prefix)
                                else accumulated_text
                            )
                            c_id = str(uuid.uuid4())
                            chunks.append({
                                "id": c_id,
                                "chunk_id": c_id,
                                "document_id": document_id,
                                "chunk_index": chunk_index,
                                "text": final_text,
                                "page_number": page_num,
                                "page_start": page_num,
                                "page_end": page_num,
                                "character_count": len(final_text),
                                "section": self._detect_chunk_section(final_text, page_entry.get("section")),
                            })
                            chunk_index += 1
                            prev_chunk_text = accumulated_text
                            accumulated_text = ""

                        # If individual paragraph is oversized, split it by sentences
                        if len(para) > target_size:
                            sentences = self._split_into_sentences(para)
                            for s in sentences:
                                s_candidate = f"{accumulated_text} {s}".strip() if accumulated_text else s
                                if len(s_candidate) <= target_size:
                                    accumulated_text = s_candidate
                                else:
                                    if accumulated_text:
                                        overlap_prefix = self._get_overlap_prefix(prev_chunk_text, overlap)
                                        final_text = (
                                            f"{overlap_prefix}\n{accumulated_text}".strip()
                                            if overlap_prefix and not accumulated_text.startswith(overlap_prefix)
                                            else accumulated_text
                                        )
                                        c_id = str(uuid.uuid4())
                                        chunks.append({
                                            "id": c_id,
                                            "chunk_id": c_id,
                                            "document_id": document_id,
                                            "chunk_index": chunk_index,
                                            "text": final_text,
                                            "page_number": page_num,
                                            "page_start": page_num,
                                            "page_end": page_num,
                                            "character_count": len(final_text),
                                            "section": self._detect_chunk_section(final_text, page_entry.get("section")),
                                        })
                                        chunk_index += 1
                                        prev_chunk_text = accumulated_text
                                        accumulated_text = ""

                                    if len(s) > target_size:
                                        pieces = self._split_large_sentence(s, target_size)
                                        for piece in pieces:
                                            overlap_prefix = self._get_overlap_prefix(prev_chunk_text, overlap)
                                            final_text = (
                                                f"{overlap_prefix}\n{piece}".strip()
                                                if overlap_prefix and not piece.startswith(overlap_prefix)
                                                else piece
                                            )
                                            c_id = str(uuid.uuid4())
                                            chunks.append({
                                                "id": c_id,
                                                "chunk_id": c_id,
                                                "document_id": document_id,
                                                "chunk_index": chunk_index,
                                                "text": final_text,
                                                "page_number": page_num,
                                                "page_start": page_num,
                                                "page_end": page_num,
                                                "character_count": len(final_text),
                                                "section": self._detect_chunk_section(final_text, page_entry.get("section")),
                                            })
                                            chunk_index += 1
                                            prev_chunk_text = piece
                                    else:
                                        accumulated_text = s
                        else:
                            accumulated_text = para

                if accumulated_text:
                    overlap_prefix = self._get_overlap_prefix(prev_chunk_text, overlap)
                    final_text = (
                        f"{overlap_prefix}\n{accumulated_text}".strip()
                        if overlap_prefix and not accumulated_text.startswith(overlap_prefix)
                        else accumulated_text
                    )
                    c_id = str(uuid.uuid4())
                    chunks.append({
                        "id": c_id,
                        "chunk_id": c_id,
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "text": final_text,
                        "page_number": page_num,
                        "page_start": page_num,
                        "page_end": page_num,
                        "character_count": len(final_text),
                        "section": self._detect_chunk_section(final_text, page_entry.get("section")),
                    })
                    chunk_index += 1
                    prev_chunk_text = accumulated_text

            return chunks

        # Case C: DOCX and TXT (Page numbers are null)
        paragraphs = self._split_into_paragraphs(clean_full_text)
        chunk_index = 0
        prev_chunk_text = ""
        accumulated_text = ""
        active_section = None

        for para in paragraphs:
            # Check if paragraph introduces a new section
            para_sec = self._detect_chunk_section(para)
            if para_sec:
                active_section = para_sec

            candidate = f"{accumulated_text}\n\n{para}".strip() if accumulated_text else para

            if len(candidate) <= target_size:
                accumulated_text = candidate
            else:
                if accumulated_text:
                    overlap_prefix = self._get_overlap_prefix(prev_chunk_text, overlap)
                    final_text = (
                        f"{overlap_prefix}\n{accumulated_text}".strip()
                        if overlap_prefix and not accumulated_text.startswith(overlap_prefix)
                        else accumulated_text
                    )
                    c_id = str(uuid.uuid4())
                    chunks.append({
                        "id": c_id,
                        "chunk_id": c_id,
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "text": final_text,
                        "page_number": None,
                        "page_start": None,
                        "page_end": None,
                        "character_count": len(final_text),
                        "section": self._detect_chunk_section(final_text, active_section),
                    })
                    chunk_index += 1
                    prev_chunk_text = accumulated_text
                    accumulated_text = ""

                # Oversized paragraph
                if len(para) > target_size:
                    sentences = self._split_into_sentences(para)
                    for s in sentences:
                        s_candidate = f"{accumulated_text} {s}".strip() if accumulated_text else s
                        if len(s_candidate) <= target_size:
                            accumulated_text = s_candidate
                        else:
                            if accumulated_text:
                                overlap_prefix = self._get_overlap_prefix(prev_chunk_text, overlap)
                                final_text = (
                                    f"{overlap_prefix}\n{accumulated_text}".strip()
                                    if overlap_prefix and not accumulated_text.startswith(overlap_prefix)
                                    else accumulated_text
                                )
                                c_id = str(uuid.uuid4())
                                chunks.append({
                                    "id": c_id,
                                    "chunk_id": c_id,
                                    "document_id": document_id,
                                    "chunk_index": chunk_index,
                                    "text": final_text,
                                    "page_number": None,
                                    "page_start": None,
                                    "page_end": None,
                                    "character_count": len(final_text),
                                    "section": self._detect_chunk_section(final_text, active_section),
                                })
                                chunk_index += 1
                                prev_chunk_text = accumulated_text
                                accumulated_text = ""

                            if len(s) > target_size:
                                pieces = self._split_large_sentence(s, target_size)
                                for piece in pieces:
                                    overlap_prefix = self._get_overlap_prefix(prev_chunk_text, overlap)
                                    final_text = (
                                        f"{overlap_prefix}\n{piece}".strip()
                                        if overlap_prefix and not piece.startswith(overlap_prefix)
                                        else piece
                                    )
                                    c_id = str(uuid.uuid4())
                                    chunks.append({
                                        "id": c_id,
                                        "chunk_id": c_id,
                                        "document_id": document_id,
                                        "chunk_index": chunk_index,
                                        "text": final_text,
                                        "page_number": None,
                                        "page_start": None,
                                        "page_end": None,
                                        "character_count": len(final_text),
                                        "section": self._detect_chunk_section(final_text, active_section),
                                    })
                                    chunk_index += 1
                                    prev_chunk_text = piece
                            else:
                                accumulated_text = s
                else:
                    accumulated_text = para

        if accumulated_text:
            overlap_prefix = self._get_overlap_prefix(prev_chunk_text, overlap)
            final_text = (
                f"{overlap_prefix}\n{accumulated_text}".strip()
                if overlap_prefix and not accumulated_text.startswith(overlap_prefix)
                else accumulated_text
            )
            c_id = str(uuid.uuid4())
            chunks.append({
                "id": c_id,
                "chunk_id": c_id,
                "document_id": document_id,
                "chunk_index": chunk_index,
                "text": final_text,
                "page_number": None,
                "page_start": None,
                "page_end": None,
                "character_count": len(final_text),
                "section": self._detect_chunk_section(final_text, active_section),
            })

        return chunks


chunking_service = ChunkingService()
