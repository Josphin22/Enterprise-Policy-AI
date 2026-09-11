"""
SectionDetector identifies section headers, policy headings, and chapter titles in document text.
Supports:
- Numbered headings (e.g. '1. Leave Policy', '2.1 Remote Work Guidelines', 'Section 4 - Benefits')
- Capitalized title lines (e.g. 'EMPLOYEE CODE OF CONDUCT')
- Markdown headings (e.g. '## Annual Leave')
"""
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("enterprise_rag.document_processing.section")

# Compiled regular expressions for robust heading detection
HEADING_PATTERNS = [
    # Markdown headings (# Heading, ## Heading)
    re.compile(r"^(#{1,4})\s+(.+)$"),
    # Numbered headings (1. Leave Policy, 1.2 Remote Work, 1.2.3 Eligibility)
    re.compile(r"^(\d+(?:\.\d+)*)\.?\s+([A-Z][\w\s,/\-()]{2,80})$"),
    # Explicit section or article prefixes (Section 1: Leave Policy, Article II - Probation)
    re.compile(r"^(?:Section|Article|Part|Chapter)\s+([0-9IVXLCDM]+(?:\.[0-9]+)*)[:\-]?\s+([A-Z][\w\s,/\-()]{2,80})$", re.IGNORECASE),
    # Capitalized letter prefixes (A. Standard Hours, B. Overtime Rules)
    re.compile(r"^([A-Z])\.\s+([A-Z][\w\s,/\-()]{2,80})$"),
]


class SectionDetector:
    """Detects headings and segments text by logical policy sections."""

    @staticmethod
    def detect_heading(line: str) -> Optional[str]:
        """
        Check if a single line represents a section heading.
        Returns the normalized heading title or None.
        """
        stripped = line.strip()
        if not stripped or len(stripped) < 3 or len(stripped) > 100:
            return None

        # Check against regex patterns
        for pat in HEADING_PATTERNS:
            match = pat.match(stripped)
            if match:
                return stripped

        # Check for all-caps standalone lines (min 4 chars, max 60 chars, mostly letters)
        if stripped.isupper() and len(stripped) >= 4 and len(stripped) <= 60:
            words = stripped.split()
            if len(words) >= 1 and any(c.isalpha() for c in stripped):
                # Avoid single words like 'PAGE' or 'DRAFT'
                if len(words) >= 2 or len(stripped) >= 6:
                    return stripped.title()

        return None

    def segment_text_by_sections(self, text: str, initial_section: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Split a block of text into chunks delineated by detected section headers.
        Returns list of {"section": Optional[str], "text": str}.
        """
        if not text:
            return []

        lines = text.split("\n")
        segments: List[Dict[str, Any]] = []
        current_section = initial_section
        current_lines: List[str] = []

        for line in lines:
            heading = self.detect_heading(line)
            if heading:
                # Flush previous segment
                if current_lines:
                    seg_text = "\n".join(current_lines).strip()
                    if seg_text:
                        segments.append({
                            "section": current_section,
                            "text": seg_text,
                        })
                    current_lines = []
                current_section = heading
                # Include heading in text as well
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            seg_text = "\n".join(current_lines).strip()
            if seg_text:
                segments.append({
                    "section": current_section,
                    "text": seg_text,
                })

        return segments if segments else [{"section": initial_section, "text": text.strip()}]

    def extract_all_headings(self, text: str) -> List[str]:
        """Extract a deduplicated list of all section headings found in the text."""
        headings = []
        seen = set()
        for line in text.split("\n"):
            h = self.detect_heading(line)
            if h and h.lower() not in seen:
                headings.append(h)
                seen.add(h.lower())
        return headings


section_detector = SectionDetector()
