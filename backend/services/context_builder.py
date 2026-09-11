from typing import List
from app.rag.context_builder import context_builder, ContextBuilder
from app.rag.schemas import SourceCitation


def build_context_from_citations(sources: List[SourceCitation]) -> str:
    """Format a list of SourceCitation objects into a readable context block."""
    blocks = []
    for s in sources:
        src_text = getattr(s, "chunk_text", None) or getattr(s, "text", "") or ""
        doc_name = getattr(s, "filename", None) or getattr(s, "document", "Document")
        page_info = f", Page {s.page}" if getattr(s, "page", None) else ""
        blocks.append(f"[{s.source_id}] ({doc_name}{page_info}):\n{src_text}")
    return "\n\n".join(blocks)


__all__ = ["context_builder", "ContextBuilder", "build_context_from_citations"]
