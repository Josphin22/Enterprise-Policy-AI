import logging
from typing import List, Tuple, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import settings
from app.models.document_chunk import DocumentChunk
from app.rag.schemas import CandidateChunk, SourceCitation

logger = logging.getLogger("enterprise_rag.rag.context_builder")


class ContextBuilder:
    """
    Constructs bounded, grounded prompt context blocks and structured source citations
    from relevant document chunks for local LLM consumption.
    """

    def __init__(
        self,
        max_chunks: Optional[int] = None,
        max_characters: Optional[int] = None,
        include_adjacent: Optional[bool] = None,
    ):
        self.max_chunks = max_chunks or settings.RAG_MAX_CONTEXT_CHUNKS
        self.max_characters = max_characters or settings.RAG_MAX_CONTEXT_CHARACTERS
        self.include_adjacent = (
            include_adjacent
            if include_adjacent is not None
            else settings.RAG_INCLUDE_ADJACENT_CHUNKS
        )

    def deduplicate_chunks(self, chunks: List[CandidateChunk]) -> List[CandidateChunk]:
        """
        Deduplicate chunks containing substantially identical text while preserving
        distinct sections from the same document.
        """
        seen_texts: Set[str] = set()
        unique_chunks: List[CandidateChunk] = []

        for chunk in chunks:
            # Normalize text for deduplication fingerprint
            norm_text = " ".join(chunk.text.strip().lower().split())
            if norm_text not in seen_texts:
                seen_texts.add(norm_text)
                unique_chunks.append(chunk)
            else:
                logger.debug(f"Dropped duplicate chunk: {chunk.chunk_id}")

        return unique_chunks

    def expand_adjacent_chunks(
        self,
        chunks: List[CandidateChunk],
        db: Session,
    ) -> List[CandidateChunk]:
        """
        Optionally retrieve neighboring chunks (chunk_index - 1, chunk_index + 1)
        from PostgreSQL for context continuity when RAG_INCLUDE_ADJACENT_CHUNKS=True.
        """
        if not self.include_adjacent or not db:
            return chunks

        expanded: List[CandidateChunk] = []
        seen_chunk_ids: Set[str] = {c.chunk_id for c in chunks}

        for chunk in chunks:
            expanded.append(chunk)

            # Query adjacent previous and next chunks
            prev_idx = max(0, chunk.chunk_index - 1)
            next_idx = chunk.chunk_index + 1

            adj_stmt = (
                select(DocumentChunk)
                .where(
                    DocumentChunk.document_id == chunk.document_id,
                    DocumentChunk.chunk_index.in_([prev_idx, next_idx]),
                )
                .order_by(DocumentChunk.chunk_index.asc())
            )
            adj_rows = db.scalars(adj_stmt).all()

            for adj in adj_rows:
                if adj.id not in seen_chunk_ids:
                    seen_chunk_ids.add(adj.id)
                    expanded.append(
                        CandidateChunk(
                            chunk_id=adj.id,
                            document_id=adj.document_id,
                            filename=chunk.filename,
                            chunk_index=adj.chunk_index,
                            page=adj.page_number,
                            section=adj.section,
                            text=adj.text,
                            character_count=adj.character_count,
                            score=chunk.score * 0.95,  # Slightly lower score for adjacent context
                        )
                    )

        return expanded

    def build_context(
        self,
        chunks: List[CandidateChunk],
        max_chunks: Optional[int] = None,
        max_characters: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> Tuple[str, List[SourceCitation]]:
        """
        Deduplicate, bound, rank, and format candidate chunks into grounded context string
        and return sequential source citations [S1], [S2], etc.
        """
        limit_chunks = max_chunks or self.max_chunks
        limit_chars = max_characters or self.max_characters

        # 1. Deduplicate identical chunk texts
        unique_chunks = self.deduplicate_chunks(chunks)

        # 2. Optionally expand adjacent chunks
        if self.include_adjacent and db:
            unique_chunks = self.expand_adjacent_chunks(unique_chunks, db)

        # 3. Apply chunk count limit
        selected_chunks = unique_chunks[:limit_chunks]

        # 4. Construct formatted context and citation mapping respecting character limit
        context_blocks: List[str] = []
        sources: List[SourceCitation] = []
        current_char_count = 0

        for idx, chunk in enumerate(selected_chunks):
            source_id = f"S{idx + 1}"

            # Format source header
            header_lines = [f"[Source {source_id}]"]
            header_lines.append(f"Document: {chunk.filename}")
            if chunk.page is not None:
                header_lines.append(f"Page: {chunk.page}")
            if chunk.section:
                header_lines.append(f"Section: {chunk.section}")

            block = "\n".join(header_lines) + f"\n\n{chunk.text.strip()}\n"

            # Check character limit
            if current_char_count + len(block) > limit_chars and context_blocks:
                logger.warning(
                    f"Context truncated at {len(context_blocks)} chunks due to character limit ({limit_chars} max)."
                )
                break

            context_blocks.append(block)
            current_char_count += len(block)

            sources.append(
                SourceCitation(
                    source_id=source_id,
                    document=chunk.filename,
                    page=chunk.page,
                    section=chunk.section,
                    chunk_id=chunk.chunk_id,
                    score=round(chunk.score, 4),
                )
            )

        final_context = "\n---\n\n".join(context_blocks)
        logger.info(
            f"Context constructed: {len(sources)} sources, {len(final_context)} characters."
        )

        return final_context, sources


# Global singleton instance
context_builder = ContextBuilder()
