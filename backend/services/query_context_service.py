"""
Enterprise Policy AI - Smart Contextual Query Service (Phase 7)
Constructs intelligent, contextualized retrieval queries for follow-up questions
while preserving the original user question for final LLM response generation.
"""

import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("enterprise_rag.services.query_context")

# Referential tokens that strongly indicate a conversational follow-up
FOLLOWUP_PRONOUNS = {
    "it", "its", "they", "them", "their", "this", "that", "these", "those",
    "he", "she", "his", "her",
}

FOLLOWUP_PREFIXES = (
    "what about",
    "how about",
    "and ",
    "also ",
    "what if",
    "can i",
    "could i",
    "how many",
    "how much",
    "when ",
    "who ",
    "where ",
    "does it",
    "is it",
    "is there",
    "are there",
    "why ",
    "who approves",
    "who decides",
)


class QueryContextService:
    """
    Analyzes multi-turn conversation context to detect follow-up queries and
    builds targeted contextual queries strictly for semantic retrieval.
    """

    def is_followup_question(
        self,
        query: str,
        recent_messages: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Determines whether the incoming user question is a conversational follow-up
        that requires prior conversation context for accurate retrieval.
        """
        if not recent_messages or len(recent_messages) == 0:
            return False

        q_lower = query.strip().lower()
        words = re.findall(r'\b[a-z]+\b', q_lower)

        # 1. Short queries (<= 6 words) almost always depend on context
        if len(words) <= 6:
            return True

        # 2. Check for explicit follow-up question prefixes
        if any(q_lower.startswith(prefix) for prefix in FOLLOWUP_PREFIXES):
            return True

        # 3. Check for referential pronouns
        if any(w in FOLLOWUP_PRONOUNS for w in words):
            return True

        return False

    def extract_core_intent(self, text: str) -> str:
        """
        Extracts key noun phrases or core policy intent from a previous message.
        """
        clean = text.strip()
        # Remove common greeting or conversational padding
        clean = re.sub(r'^(hi|hello|hey|please|could you tell me|can you tell me)\s*', '', clean, flags=re.IGNORECASE)
        # Truncate if excessively long
        if len(clean) > 120:
            clean = clean[:120].rsplit(' ', 1)[0]
        return clean.strip()

    def build_contextual_retrieval_query(
        self,
        current_question: str,
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        max_turns: int = 4,
    ) -> str:
        """
        Constructs a concise, focused retrieval query by fusing recent conversational
        topic context with the current follow-up question.
        Returns the original query unaltered if it is not a follow-up.
        """
        clean_current = current_question.strip()

        if not recent_messages or not self.is_followup_question(clean_current, recent_messages):
            return clean_current

        # Gather up to max_turns recent messages (newest first)
        history_window = recent_messages[-max_turns:]
        prior_intents: List[str] = []

        for msg in reversed(history_window):
            role = msg.get("role", "")
            content = msg.get("content", "").strip()

            if not content:
                continue

            # Give priority to prior user questions to capture the subject
            if role == "user":
                intent = self.extract_core_intent(content)
                if intent and intent not in prior_intents:
                    prior_intents.append(intent)
                    break  # Most recent prior user question is the primary topic
            elif role == "assistant" and not prior_intents:
                # Also extract key noun phrase from assistant answer if needed
                intent = self.extract_core_intent(content)
                if intent and len(intent) > 10:
                    prior_intents.append(intent)

        if prior_intents:
            primary_topic = prior_intents[0]
            # Avoid repeating if the topic is already mentioned in current question
            if primary_topic.lower() not in clean_current.lower():
                contextual_query = f"{primary_topic}. {clean_current}"
                logger.info(
                    f"Follow-up detected. Composed retrieval query: '{contextual_query}' (Original: '{clean_current}')"
                )
                return contextual_query

        return clean_current

    def generate_conversation_title(self, initial_question: str, max_chars: int = 50) -> str:
        """
        Deterministically derives a clean, readable conversation title from the first question
        without requiring an expensive LLM invocation.
        """
        if not initial_question or not initial_question.strip():
            return "Policy Discussion"

        # Remove question punctuation and filler phrasing
        clean = initial_question.strip()
        clean = re.sub(r'^(what is|what are|how to|how many|can i|explain|tell me about)\s+', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'[?!.,;]+$', '', clean).strip()

        if not clean:
            clean = initial_question.strip()[:max_chars]

        # Capitalize first letter
        clean = clean[0].upper() + clean[1:] if len(clean) > 1 else clean.upper()

        if len(clean) > max_chars:
            clean = clean[:max_chars].rsplit(' ', 1)[0]

        return clean or "Policy Discussion"


# Global singleton instance
query_context_service = QueryContextService()
