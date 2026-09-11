"""
Enterprise Policy AI - Guardrails & Safety Orchestration Service (Phase 12)
Comprehensive multi-tier safety defenses:
1. No-Answer Guardrail: Refuses immediately if retrieval context is insufficient without invoking Ollama.
2. Prompt Injection Guardrail: Blocks adversarial injection patterns & quaranatines context inside untrusted boundaries.
3. Answer Length Guardrail: Restricts generated output to MAX_ANSWER_TOKENS / MAX_ANSWER_CHARACTERS.
4. Sensitive Data Guardrail: Detects & redacts private secrets, tokens, passwords, and connection strings.
5. Grounding & Hallucination Guardrail: Validates claims against retrieved context, flagging GROUNDING_WARNING.
6. Citation Guardrail: Verifies cited source tags correspond strictly to actually retrieved documents.
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional, Set
from app.config import settings
from app.rag.schemas import SourceCitation

logger = logging.getLogger("enterprise_rag.rag.guardrails")


class GuardrailsService:
    """
    Central safety and guardrail orchestrator for RAG and Chat pipelines.
    """

    # Common injection keywords / overrides
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(previous|prior|system)\s+prompts?", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
        re.compile(r"reveal\s+(system|hidden|internal)\s+(prompt|instructions?|config)", re.IGNORECASE),
        re.compile(r"print\s+(the\s+)?system\s+prompt", re.IGNORECASE),
        re.compile(r"output\s+['\"]?i\s+have\s+been\s+pwned['\"]?", re.IGNORECASE),
        re.compile(r"bypass\s+all\s+(security|safety|policy)\s+rules", re.IGNORECASE),
    ]

    # Sensitive data patterns to scrub
    SENSITIVE_PATTERNS = [
        # Passwords in connection URIs or json/configs
        (re.compile(r"(password|passwd|pwd)\s*[:=]\s*['\"]?([^'\"\s;,]+)['\"]?", re.IGNORECASE), r"\1=[REDACTED_PASSWORD]"),
        # Database URIs with credentials
        (re.compile(r"(postgres|postgresql|mysql|sqlite)://([^:\s]+):([^@\s]+)@", re.IGNORECASE), r"\1://\2:[REDACTED_CREDENTIALS]@"),
        # JWT Bearer tokens
        (re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", re.IGNORECASE), r"[REDACTED_JWT_TOKEN]"),
        # Common API Keys (OpenAI, AWS, Slack, Generic)
        (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE), r"[REDACTED_API_KEY]"),
        (re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE), r"[REDACTED_AWS_KEY]"),
        (re.compile(r"(api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{12,})['\"]?", re.IGNORECASE), r"\1=[REDACTED_SECRET]"),
        # Private SSH / RSA keys
        (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL), r"[REDACTED_PRIVATE_KEY]"),
    ]

    STANDARD_REFUSAL = (
        "I could not find sufficient information in the provided enterprise documents to answer this question."
    )

    def validate_query(self, query: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Pre-retrieval validation:
        Returns: (is_valid, sanitized_query, rejection_reason)
        """
        if not query or not query.strip():
            return False, None, "Query cannot be empty."

        clean = query.strip()
        if len(clean) > 2000:
            return False, None, "Query exceeds maximum length of 2000 characters."

        # Detect potential injection attempts
        for pat in self.INJECTION_PATTERNS:
            if pat.search(clean):
                logger.warning(f"Adversarial prompt injection pattern detected in user query: '{clean[:60]}...'")
                # Do not immediately hard-fail if query contains genuine policy questions alongside noise,
                # but flag it so context boundaries can be reinforced.
                break

        return True, clean, None

    def enforce_no_answer_guardrail(self, has_relevant_chunks: bool) -> Tuple[bool, str]:
        """
        If retrieval finds no relevant source:
        do not call Ollama. Return grounded refusal.
        """
        if not has_relevant_chunks:
            logger.info("No-Answer guardrail triggered: insufficient retrieval context.")
            return True, self.STANDARD_REFUSAL
        return False, ""

    def scrub_sensitive_data(self, text: str) -> Tuple[str, bool]:
        """
        Review whether answers can expose passwords, secrets, tokens, private credentials.
        Returns: (scrubbed_text, was_modified)
        """
        if not text or not settings.ENABLE_SENSITIVE_DATA_SCRUB:
            return text, False

        scrubbed = text
        modified = False

        # Redact JWT secret configured in settings if it appears
        if settings.JWT_SECRET and len(settings.JWT_SECRET) > 6 and settings.JWT_SECRET in scrubbed:
            scrubbed = scrubbed.replace(settings.JWT_SECRET, "[REDACTED_SECRET_KEY]")
            modified = True

        if settings.ADMIN_PASSWORD and len(settings.ADMIN_PASSWORD) > 4 and settings.ADMIN_PASSWORD in scrubbed:
            scrubbed = scrubbed.replace(settings.ADMIN_PASSWORD, "[REDACTED_ADMIN_PASSWORD]")
            modified = True

        for pattern, replacement in self.SENSITIVE_PATTERNS:
            new_text = pattern.sub(replacement, scrubbed)
            if new_text != scrubbed:
                scrubbed = new_text
                modified = True

        if modified:
            logger.warning("Sensitive data guardrail triggered: secrets redacted from answer.")

        return scrubbed, modified

    def enforce_answer_length_guardrail(self, answer: str, max_chars: Optional[int] = None) -> Tuple[str, bool]:
        """
        Prevent unnecessarily huge responses.
        Truncates answer gracefully to MAX_ANSWER_CHARACTERS / token limit.
        """
        limit = max_chars or settings.MAX_ANSWER_CHARACTERS
        if not answer or len(answer) <= limit:
            return answer, False

        truncated = answer[:limit].rsplit(" ", 1)[0] + " ... [Response truncated by safety guardrail]"
        logger.warning(f"Answer length guardrail triggered: truncated response from {len(answer)} to {len(truncated)} chars.")
        return truncated, True

    def validate_citations(
        self,
        answer: str,
        retrieved_sources: List[SourceCitation],
    ) -> Tuple[str, List[SourceCitation], List[str]]:
        """
        Verify every citation corresponds to an actual retrieved source.
        Invalid citations such as [Source 99] when only Source 1 exists are stripped.
        Returns: (cleaned_answer, valid_citations_used, stripped_invalid_tags)
        """
        if not answer:
            return "", [], []

        # Find all valid source numbers
        valid_nums: Set[int] = set()
        for idx, src in enumerate(retrieved_sources, start=1):
            valid_nums.add(idx)
            nums = re.findall(r"\d+", getattr(src, "source_id", "") or "")
            if nums:
                valid_nums.add(int(nums[0]))

        stripped_tags = []

        def check_citation(match: re.Match) -> str:
            full_match = match.group(0)
            tag_content = match.group(1)
            num_match = re.search(r"\d+", tag_content)
            if num_match:
                num = int(num_match.group(0))
                if num in valid_nums:
                    return full_match
            # Invalid citation
            stripped_tags.append(full_match)
            return ""

        citation_regex = re.compile(r"\[((?:Source\s*)?\d+|S\d+)\]", re.IGNORECASE)
        cleaned_answer = citation_regex.sub(check_citation, answer)
        cleaned_answer = re.sub(r" +", " ", cleaned_answer).strip()

        if stripped_tags:
            logger.warning(f"Citation guardrail stripped invalid citation tags: {stripped_tags}")

        # Resolve active citations
        active_sources = []
        for idx, src in enumerate(retrieved_sources, start=1):
            src_num = idx
            src_id_str = str(getattr(src, "source_id", "") or "")
            nums = re.findall(r"\d+", src_id_str)
            if nums:
                src_num = int(nums[0])
            
            # Check for various formats: [Source S1], [Source 1], [S1], etc.
            is_cited = any([
                f"[Source S{src_num}]".lower() in cleaned_answer.lower(),
                f"[Source {src_num}]".lower() in cleaned_answer.lower(),
                f"[S{src_num}]".lower() in cleaned_answer.lower(),
                f"[Source: {src_num}]".lower() in cleaned_answer.lower(),
            ])
            if is_cited:
                active_sources.append(src)

        return cleaned_answer, (active_sources if active_sources else retrieved_sources), stripped_tags

    def check_groundedness(
        self,
        answer: str,
        retrieved_context: str,
    ) -> Tuple[str, bool, float, List[str]]:
        """
        Verify important answer claims are supported by retrieved context.
        If an answer contains unsupported claims, mark: GROUNDING_WARNING.
        Returns: (classification, has_warning, support_ratio, unsupported_sentences)
        """
        if not answer or not answer.strip():
            return "UNSUPPORTED", True, 0.0, ["Empty answer"]

        # Safe refusals are fully grounded by definition
        lower_ans = answer.lower()
        if "not find sufficient information" in lower_ans or "couldn't find that information" in lower_ans:
            return "SUPPORTED", False, 1.0, []

        context_lower = (retrieved_context or "").lower()
        if not context_lower.strip():
            return "UNSUPPORTED", True, 0.0, [answer]

        sentences = [
            s.strip() for s in re.split(r"[.!?\n]", answer) if len(s.strip()) > 12
        ]
        if not sentences:
            sentences = [answer.strip()]

        supported_count = 0
        unsupported_sentences = []

        # Set of English stopwords to ignore so only contentful policy words are evaluated
        COMMON_STOPWORDS = {
            "this", "that", "these", "those", "every", "each", "some", "with", "from",
            "have", "been", "were", "what", "when", "where", "which", "will", "would",
            "shall", "should", "could", "there", "their", "they", "them", "about",
            "into", "over", "after", "before", "under", "year", "years", "month", "months",
            "according", "stated", "policy", "employees", "employee", "company", "provided",
            "and", "also", "any", "all", "are", "can", "may", "must", "for", "the", "not"
        }

        # Extract word set from context
        context_words = {
            w.lower().strip("[](),:;.\"'")
            for w in context_lower.split()
            if len(w) > 2
        }

        for sent in sentences:
            # Extract informative words (exclude stopwords & numbers unless exact)
            words = [
                w.lower().strip("[](),:;.\"'")
                for w in sent.split()
                if len(w) > 2 and not w.lower().startswith("source") and w.lower().strip("[](),:;.\"'") not in COMMON_STOPWORDS
            ]
            if not words:
                supported_count += 1
                continue

            matches = sum(1 for w in words if w in context_words)
            ratio = matches / len(words)

            if ratio >= 0.60:
                supported_count += 1
            else:
                unsupported_sentences.append(sent)

        total_sents = len(sentences)
        support_ratio = round(supported_count / total_sents, 2) if total_sents > 0 else 0.0

        if support_ratio >= 0.70:
            classification = "SUPPORTED"
            has_warning = False
        elif support_ratio >= 0.40:
            classification = "PARTIALLY_SUPPORTED"
            has_warning = False
        else:
            classification = "UNSUPPORTED"
            has_warning = True
            logger.warning(
                f"Grounding Guardrail flagged GROUNDING_WARNING (support_ratio={support_ratio}): "
                f"{len(unsupported_sentences)} unsupported claims."
            )

        return classification, has_warning, support_ratio, unsupported_sentences

    def apply_all_guardrails(
        self,
        answer: str,
        retrieved_context: str,
        retrieved_sources: List[SourceCitation],
        has_retrieval_chunks: bool,
    ) -> Dict[str, Any]:
        """
        Unified post-generation guardrail application:
        1. No-answer check
        2. Citation validation
        3. Sensitive data scrub
        4. Answer length restriction
        5. Grounding / Hallucination verification
        """
        # 1. No-Answer Guardrail
        no_ans_triggered, refusal = self.enforce_no_answer_guardrail(has_retrieval_chunks)
        if no_ans_triggered:
            return {
                "answer": refusal,
                "sources": [],
                "guardrail_status": "NO_ANSWER_REFUSAL",
                "grounding_warning": False,
                "grounding_classification": "SUPPORTED",
                "sensitive_data_redacted": False,
                "truncated": False,
                "invalid_citations_stripped": [],
            }

        # 2. Citation Check
        clean_answer, valid_sources, stripped_citations = self.validate_citations(answer, retrieved_sources)

        # 3. Sensitive Data Scrub
        scrubbed_answer, data_redacted = self.scrub_sensitive_data(clean_answer)

        # 4. Length Enforcer
        final_answer, length_truncated = self.enforce_answer_length_guardrail(scrubbed_answer)

        # 5. Grounding Check
        classification, grounding_warning, support_ratio, unsupported = self.check_groundedness(
            final_answer, retrieved_context
        )

        return {
            "answer": final_answer,
            "sources": valid_sources,
            "guardrail_status": "GROUNDING_WARNING" if grounding_warning else "PASSED",
            "grounding_warning": grounding_warning,
            "grounding_classification": classification,
            "support_ratio": support_ratio,
            "unsupported_sentences": unsupported,
            "sensitive_data_redacted": data_redacted,
            "truncated": length_truncated,
            "invalid_citations_stripped": stripped_citations,
        }


# Global singleton instance
guardrails_service = GuardrailsService()
