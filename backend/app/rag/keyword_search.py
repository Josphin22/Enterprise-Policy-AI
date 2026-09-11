"""
Enterprise Policy AI - Keyword Search Engine (Phase 9)
Provides exact term, number, date, currency, and full-text keyword retrieval
across PostgreSQL and SQLite with metadata filtering and BM25-style scoring.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, text

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.document_metadata import DocumentMetadata
from app.rag.schemas import CandidateChunk, MetadataFilter

logger = logging.getLogger("enterprise_rag.rag.keyword_search")

# Common English stop words that carry minimal topical value
STOP_WORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves", "tell", "show", "give", "find", "explain", "describe",
    "many", "much", "does", "mean", "state", "mention", "applicable", "detail"
}

# Regex patterns for exact numerical, currency, and temporal entities
RE_CURRENCY = re.compile(r"(?:₹|\$|INR|USD|Rs\.?|EUR)\s*\d+(?:,\d+)*(?:\.\d+)?", re.IGNORECASE)
RE_COMPOUND_NUMBER = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:days?|months?|years?|hours?|weeks?|mins?|minutes?|%|percent)\b",
    re.IGNORECASE,
)
RE_STANDALONE_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
RE_DATE_WORDS = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b(?:\s+\d{1,2}(?:st|nd|rd|th)?)?(?:,?\s+\d{4})?",
    re.IGNORECASE,
)
RE_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


class KeywordSearchEngine:
    """
    Full-text and exact term search engine querying document chunks.
    Combines SQL text search (PostgreSQL FTS or SQLite token matching)
    with exact term/number/date preservation and metadata filtering.
    """

    @staticmethod
    def extract_search_entities(query: str) -> Dict[str, List[str]]:
        """
        Extract exact entities from user query:
        - numbers (e.g. '18 days', '30 days', '5 years', '15', '1.25')
        - currencies (e.g. '₹50,000', '$100')
        - dates (e.g. 'January', 'December 31', '2026')
        - keywords (meaningful tokens stripped of punctuation and stopwords)
        """
        clean_text = query.strip()

        currencies = [m.group(0).strip() for m in RE_CURRENCY.finditer(clean_text)]
        compound_numbers = [m.group(0).strip() for m in RE_COMPOUND_NUMBER.finditer(clean_text)]
        all_numbers = [m.group(0).strip() for m in RE_STANDALONE_NUMBER.finditer(clean_text)]

        # Unique numbers preserving compound forms first
        number_tokens = list(dict.fromkeys(compound_numbers + all_numbers))

        date_matches = [m.group(0).strip() for m in RE_DATE_WORDS.finditer(clean_text)]
        year_matches = [m.group(0).strip() for m in RE_YEAR.finditer(clean_text)]
        date_tokens = list(dict.fromkeys(date_matches + year_matches))

        # Meaningful search tokens
        raw_words = re.findall(r"[A-Za-z0-9_#₹$%-]+", clean_text.lower())
        keywords = [
            w for w in raw_words
            if len(w) > 1 and w not in STOP_WORDS and not w.isdigit()
        ]
        # Keep unique in order
        keywords = list(dict.fromkeys(keywords))

        return {
            "currencies": currencies,
            "numbers": number_tokens,
            "dates": date_tokens,
            "keywords": keywords,
        }

    def search(
        self,
        query: str,
        db: Session,
        top_k: int = 10,
        filters: Optional[Any] = None,
        min_score: float = 0.05,
    ) -> List[CandidateChunk]:
        """
        Execute keyword search against document_chunks in the database.
        Optionally applies metadata filters (document_id, file_type, owner_id, status, department).
        """
        if not query or not query.strip() or not db:
            return []

        entities = self.extract_search_entities(query)
        keywords = entities["keywords"]
        numbers = entities["numbers"]
        currencies = entities["currencies"]
        dates = entities["dates"]

        all_target_terms = list(dict.fromkeys(currencies + dates + numbers + keywords))
        if not all_target_terms:
            fallback_words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", query) if len(w) > 1]
            all_target_terms = fallback_words[:5]

        if not all_target_terms:
            return []

        # Parse metadata filters
        f_doc_id = None
        f_file_type = None
        f_owner_id = None
        f_status = None
        f_dept = None

        f_allowed_doc_ids = None

        if filters:
            if isinstance(filters, dict):
                f_doc_id = filters.get("document_id")
                f_file_type = filters.get("file_type")
                f_owner_id = filters.get("owner_id")
                f_status = filters.get("status") or filters.get("processing_status")
                f_dept = filters.get("department")
                f_allowed_doc_ids = filters.get("allowed_document_ids")
            elif isinstance(filters, MetadataFilter):
                f_doc_id = filters.document_id
                f_file_type = filters.file_type
                f_owner_id = filters.owner_id
                f_status = filters.status
                f_dept = filters.department
                f_allowed_doc_ids = filters.allowed_document_ids

        # Normalize file_type filter if provided (support both '.pdf' and 'pdf')
        if f_file_type:
            raw_ft = f_file_type.lower().strip()
            dot_ft = raw_ft if raw_ft.startswith(".") else f".{raw_ft}"
            nodot_ft = raw_ft.lstrip(".")
            stmt = stmt.where(Document.file_type.in_([dot_ft, nodot_ft]))

        # Base query joining DocumentChunk with Document and DocumentMetadata
        stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                DocumentChunk.chunk_index,
                DocumentChunk.text,
                DocumentChunk.page_number,
                DocumentChunk.section,
                DocumentChunk.character_count,
                Document.filename,
                Document.file_type,
                Document.owner_id,
                Document.processing_status,
                DocumentMetadata.department,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .outerjoin(DocumentMetadata, Document.id == DocumentMetadata.document_id)
        )

        # Apply metadata filters strictly in SQL
        if f_doc_id:
            stmt = stmt.where(DocumentChunk.document_id == str(f_doc_id))
        if f_allowed_doc_ids is not None:
            # If allowed_document_ids is an empty list/set, user has access to 0 documents
            if not f_allowed_doc_ids:
                return []
            stmt = stmt.where(DocumentChunk.document_id.in_([str(d) for d in f_allowed_doc_ids]))
        if f_file_type:
            raw_ft = f_file_type.lower().strip()
            dot_ft = raw_ft if raw_ft.startswith(".") else f".{raw_ft}"
            nodot_ft = raw_ft.lstrip(".")
            stmt = stmt.where(Document.file_type.in_([dot_ft, nodot_ft]))
        if f_owner_id:
            stmt = stmt.where(Document.owner_id == str(f_owner_id))
        if f_status:
            stmt = stmt.where(Document.processing_status == str(f_status))
        if f_dept:
            stmt = stmt.where(DocumentMetadata.department == str(f_dept))

        # Candidate selection
        matched_chunks: List[CandidateChunk] = []

        try:
            # Fetch candidate rows
            rows = db.execute(stmt).all()
            if not rows:
                return []

            for row in rows:
                chunk_id = row[0]
                doc_id = row[1]
                chunk_idx = row[2]
                chunk_text = row[3] or ""
                page_num = row[4]
                section_name = row[5]
                char_count = row[6] or len(chunk_text)
                filename = row[7] or "Document"

                lower_text = chunk_text.lower()
                chunk_score = 0.0
                match_reasons = []

                # Exact currency match bonus (+0.30)
                for cur in currencies:
                    cur_clean = cur.replace(",", "").lower()
                    text_clean = lower_text.replace(",", "")
                    if cur.lower() in lower_text or cur_clean in text_clean:
                        chunk_score += 0.30
                        match_reasons.append(f"exact_currency:{cur}")

                # Exact date match bonus (+0.25)
                for dt in dates:
                    if dt.lower() in lower_text:
                        chunk_score += 0.25
                        match_reasons.append(f"exact_date:{dt}")

                # Exact number / compound number match bonus (+0.25)
                for num in numbers:
                    num_pat = r"\b" + re.escape(num.lower()) + r"\b"
                    if re.search(num_pat, lower_text):
                        chunk_score += 0.25
                        match_reasons.append(f"exact_number:{num}")
                    elif num.lower() in lower_text:
                        chunk_score += 0.12
                        match_reasons.append(f"partial_number:{num}")

                # Keyword term frequency scoring
                matched_kw_count = 0
                for kw in keywords:
                    kw_lower = kw.lower()
                    if kw_lower in lower_text:
                        matched_kw_count += 1
                        occ = min(lower_text.count(kw_lower), 3)
                        chunk_score += 0.10 * occ

                if matched_kw_count > 0:
                    match_reasons.append(f"keywords_matched:{matched_kw_count}/{len(keywords)}")

                # Exact full phrase match bonus
                clean_q = query.lower().strip()
                if len(clean_q.split()) >= 3 and clean_q in lower_text:
                    chunk_score += 0.35
                    match_reasons.append("exact_phrase_match")

                if chunk_score <= 0.0:
                    continue

                # Normalize score to [0.0, 1.0]
                norm_score = min(1.0, round(chunk_score, 4))

                if norm_score >= min_score:
                    matched_chunks.append(
                        CandidateChunk(
                            chunk_id=str(chunk_id),
                            document_id=str(doc_id),
                            filename=str(filename),
                            chunk_index=int(chunk_idx),
                            page=page_num,
                            section=section_name,
                            text=chunk_text,
                            character_count=char_count,
                            score=norm_score,
                            source_type="keyword",
                            keyword_score=norm_score,
                            match_reasons=match_reasons,
                        )
                    )

            # Sort descending by score
            matched_chunks.sort(key=lambda c: c.score, reverse=True)
            return matched_chunks[:top_k]

        except Exception as exc:
            logger.error(f"Keyword search failed: {exc}", exc_info=True)
            return []


# Global singleton instance
keyword_search_engine = KeywordSearchEngine()
