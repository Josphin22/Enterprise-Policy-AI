import re
import logging
from typing import List, Tuple, Set, Dict, Any, Optional

logger = logging.getLogger("enterprise_rag.llm.response_parser")


class ResponseParser:
    """
    Validates LLM-generated answers, parses and cross-references citation tags
    against backend-retrieved sources, and removes hallucinated or fabricated citations.
    Supports both [Source 1] and [S1] formats.
    """

    CITATION_PATTERN = re.compile(r'\[((?:Source\s*)?(\d+)|S(\d+))\]', re.IGNORECASE)

    @staticmethod
    def _extract_number(tag: str) -> Optional[int]:
        nums = re.findall(r'\d+', tag)
        if nums:
            return int(nums[0])
        return None

    def validate_and_filter_citations(
        self,
        raw_answer: str,
        retrieved_sources: List[Any],
    ) -> Tuple[str, List[Any]]:
        """
        Validates raw generated answer, identifies which valid source IDs were actually cited,
        and sanitizes any fabricated citation tags that do not exist in retrieved sources.
        """
        if not raw_answer or not raw_answer.strip():
            return "", []

        cleaned_answer = raw_answer.strip()

        # Build index mapping: index (1-based int) -> SourceCitation
        # Also build string tag mappings for fast lookup
        idx_to_source: Dict[int, Any] = {}
        for idx, s in enumerate(retrieved_sources, start=1):
            num = self._extract_number(s.source_id) or idx
            idx_to_source[num] = s

        valid_nums: Set[int] = set(idx_to_source.keys())

        # Track valid sources cited in order of appearance
        cited_numbers: List[int] = []

        def replace_citation(match: re.Match) -> str:
            full_tag = match.group(1).strip()
            num = self._extract_number(full_tag)

            if num is not None and num in valid_nums:
                cited_numbers.append(num)
                # If original was S1, keep [S1]; if original was Source 1, keep [Source 1]
                if full_tag.upper().startswith("S") and not full_tag.upper().startswith("SOURCE"):
                    return f"[S{num}]"
                return f"[Source {num}]"

            logger.warning(
                f"Sanitized fabricated citation tag [{full_tag}] (index {num}) not in retrieved sources ({sorted(valid_nums)})."
            )
            return ""

        sanitized_answer = self.CITATION_PATTERN.sub(replace_citation, cleaned_answer)
        # Clean up any leftover duplicate spaces or awkward punctuation spacing
        sanitized_answer = re.sub(r' +', ' ', sanitized_answer).strip()
        sanitized_answer = re.sub(r' +([.,;])', r'\1', sanitized_answer)

        # Build ordered list of unique cited sources
        cited_sources: List[Any] = []
        seen_nums: Set[int] = set()

        for num in cited_numbers:
            if num in idx_to_source and num not in seen_nums:
                seen_nums.add(num)
                cited_sources.append(idx_to_source[num])

        # If LLM didn't write explicit citations but context was used, retain all retrieved sources
        final_sources = cited_sources if cited_sources else retrieved_sources

        return sanitized_answer, final_sources


# Global singleton instance
response_parser = ResponseParser()
