import re
import logging
from typing import List, Tuple, Set
from app.rag.schemas import SourceCitation

logger = logging.getLogger("enterprise_rag.llm.response_parser")


class ResponseParser:
    """
    Validates LLM-generated answers, parses and cross-references citation tags
    against backend-retrieved sources, and removes hallucinated or fabricated citations.
    """

    CITATION_PATTERN = re.compile(r'\[(S\d+)\]', re.IGNORECASE)

    def validate_and_filter_citations(
        self,
        raw_answer: str,
        retrieved_sources: List[SourceCitation],
    ) -> Tuple[str, List[SourceCitation]]:
        """
        Validates raw generated answer, identifies which valid source IDs were actually cited,
        and sanitizes any fabricated citation tags that do not exist in retrieved sources.
        """
        if not raw_answer or not raw_answer.strip():
            return "", []

        cleaned_answer = raw_answer.strip()

        # Map of valid source_id -> SourceCitation
        valid_map = {s.source_id.upper(): s for s in retrieved_sources}
        valid_ids: Set[str] = set(valid_map.keys())

        # Find all cited source tags in generated text
        found_citations = self.CITATION_PATTERN.findall(cleaned_answer)
        found_normalized = [c.upper() for c in found_citations]

        # Check for fabricated source tags (e.g. [S99] when only S1, S2 exist)
        def replace_invalid(match: re.Match) -> str:
            tag = match.group(1).upper()
            if tag in valid_ids:
                return f"[{tag}]"
            logger.warning(f"Sanitized fabricated citation tag [{tag}] not in retrieved sources.")
            return ""  # Remove fabricated citation tag from text

        sanitized_answer = self.CITATION_PATTERN.sub(replace_invalid, cleaned_answer)
        # Clean up any leftover duplicate spaces from removed citations
        sanitized_answer = re.sub(r' +', ' ', sanitized_answer).strip()

        # Determine the ordered list of cited sources that are valid
        cited_sources: List[SourceCitation] = []
        seen_cited: Set[str] = set()

        for tag in found_normalized:
            if tag in valid_map and tag not in seen_cited:
                seen_cited.add(tag)
                cited_sources.append(valid_map[tag])

        # If the LLM didn't explicitly write citation tags but answered based on retrieved context,
        # retain all retrieved valid sources
        final_sources = cited_sources if cited_sources else retrieved_sources

        return sanitized_answer, final_sources


# Global singleton instance
response_parser = ResponseParser()
