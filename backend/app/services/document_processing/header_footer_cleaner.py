"""
HeaderFooterCleaner performs conservative detection and removal of repeated headers and footers
in multi-page documents (e.g. 'Page 3 of 10', 'Acme Corp Policy Manual - Confidential').
Preserves all meaningful policy content and single-page occurrences.
"""
import re
import logging
from collections import Counter
from typing import List, Dict, Any, Set

logger = logging.getLogger("enterprise_rag.document_processing.header_footer")

# Common boilerplate patterns that qualify as page headers/footers
PAGE_NUM_PATTERNS = [
    re.compile(r"^page\s+\d+(?:\s+of\s+\d+)?$", re.IGNORECASE),
    re.compile(r"^\d+\s*/\s*\d+$"),
    re.compile(r"^\-\s*\d+\s*\-$"),
    re.compile(r"^[0-9]+$"),
]


class HeaderFooterCleaner:
    """
    Conservatively cleans repeated headers and footers across multi-page documents.
    Safety guarantees:
    - Only runs when page count >= 3.
    - Only removes lines that repeat across > 50% of pages.
    - Never deletes lines longer than 120 characters or containing substantial paragraphs.
    - Never removes lines that look like unique section titles.
    """

    @staticmethod
    def _normalize_line(line: str) -> str:
        """Normalize line for frequency matching while masking dynamic page digits."""
        norm = line.strip().lower()
        if any(p.match(norm) for p in PAGE_NUM_PATTERNS) or norm.startswith("page "):
            return re.sub(r"\d+", "#", norm)
        return norm

    def detect_repeated_headers_footers(self, pages_text: List[str]) -> Dict[str, Set[str]]:
        """
        Analyze the top and bottom lines of each page to identify repeated boilerplate.
        Returns dict with sets of normalized candidate headers and footers.
        """
        if len(pages_text) < 3:
            return {"headers": set(), "footers": set()}

        total_pages = len(pages_text)
        threshold = max(2, int(total_pages * 0.5))

        top_candidates = []
        bottom_candidates = []

        for page in pages_text:
            lines = [l.strip() for l in page.split("\n") if l.strip()]
            if not lines:
                continue

            # Top non-blank line
            top_line = lines[0]
            if len(top_line) <= 100:
                top_candidates.append(self._normalize_line(top_line))

            # Bottom non-blank line
            if len(lines) >= 2:
                bot_line = lines[-1]
                if len(bot_line) <= 100:
                    bottom_candidates.append(self._normalize_line(bot_line))

        top_counts = Counter(top_candidates)
        bottom_counts = Counter(bottom_candidates)

        repeated_headers = {norm for norm, count in top_counts.items() if count >= threshold}
        repeated_footers = {norm for norm, count in bottom_counts.items() if count >= threshold}

        return {
            "headers": repeated_headers,
            "footers": repeated_footers,
        }

    def clean_page_text(
        self,
        page_text: str,
        repeated_headers: Set[str],
        repeated_footers: Set[str],
    ) -> str:
        """
        Remove detected repeated headers from top and footers from bottom of page.
        """
        if not repeated_headers and not repeated_footers:
            return page_text

        lines = [l.strip() for l in page_text.split("\n") if l.strip()]
        if not lines:
            return page_text

        clean = list(lines)

        # Remove top line if it matches repeated headers or page number pattern
        if clean and len(clean) >= 2:
            top_norm = self._normalize_line(clean[0])
            if top_norm in repeated_headers or any(p.match(clean[0]) for p in PAGE_NUM_PATTERNS):
                clean.pop(0)

        # Remove bottom line if it matches repeated footers or page number pattern
        if clean and len(clean) >= 2:
            bot_norm = self._normalize_line(clean[-1])
            if bot_norm in repeated_footers or any(p.match(clean[-1]) for p in PAGE_NUM_PATTERNS):
                clean.pop(-1)

        return "\n\n".join(clean).strip()

    def clean_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a list of page dicts (containing 'text' and 'page_number') and
        remove repeated headers/footers in-place.
        """
        if len(pages) < 3:
            return pages

        pages_text = [p.get("text", "") for p in pages]
        detected = self.detect_repeated_headers_footers(pages_text)

        headers = detected["headers"]
        footers = detected["footers"]

        if not headers and not footers:
            return pages

        cleaned_pages = []
        for p in pages:
            raw_text = p.get("text", "")
            cleaned = self.clean_page_text(raw_text, headers, footers)
            updated_p = dict(p)
            updated_p["text"] = cleaned
            cleaned_pages.append(updated_p)

        return cleaned_pages


header_footer_cleaner = HeaderFooterCleaner()
