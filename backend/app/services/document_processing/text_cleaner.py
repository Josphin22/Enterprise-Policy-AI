import re
import unicodedata


class TextCleaner:
    """
    Cleans raw document text safely for RAG indexing.
    Normalizes whitespace and removes control characters while strictly preserving
    all policy figures, numbers (e.g. '15 days'), dates, and section boundaries.
    """

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""

        # 1. Normalize Unicode characters (e.g., standard quotes, hyphens, accents)
        normalized = unicodedata.normalize("NFKC", text)

        # 2. Normalize Windows and legacy line breaks
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Strip unprintable control characters (replace non-whitespace control characters with space)
        cleaned_chars = []
        for ch in normalized:
            if ch in ("\n", "\t"):
                cleaned_chars.append(ch)
            elif unicodedata.category(ch)[0] == "C":
                cleaned_chars.append(" ")
            else:
                cleaned_chars.append(ch)
        normalized = "".join(cleaned_chars)

        # 4. Collapse multiple horizontal spaces and tabs into a single space
        normalized = re.sub(r"[ \t]+", " ", normalized)

        # 5. Collapse excessive line breaks (more than 2 consecutive newlines -> exactly 2 newlines)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)

        # 6. Clean spaces around newlines
        normalized = re.sub(r" *\n *", "\n", normalized)

        return normalized.strip()


text_cleaner = TextCleaner()
