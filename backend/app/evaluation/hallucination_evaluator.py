import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger("enterprise_rag.evaluation.hallucination")


class HallucinationEvaluator:
    """
    Evaluates faithfulness and hallucination in RAG answers:
    - Compares generated answer sentences against retrieved context passages.
    - Classifies answers into SUPPORTED, PARTIALLY_SUPPORTED, or UNSUPPORTED.
    - Calculates dataset-wide Faithfulness % and Hallucination Rate %.
    """

    @staticmethod
    def evaluate_faithfulness(
        answer: str,
        retrieved_context: str,
        status: str,
        is_answerable: bool = True,
    ) -> Dict[str, Any]:
        """
        Evaluate factual support of answer text relative to retrieved context.
        """
        if not is_answerable or status == "insufficient_context":
            # Correct refusals are grounded by definition (zero hallucination)
            return {
                "classification": "SUPPORTED",
                "faithfulness_score": 1.0,
                "supported_sentences": 1,
                "total_sentences": 1,
                "is_hallucination": False,
            }

        answer_clean = (answer or "").strip()
        context_clean = (retrieved_context or "").lower()

        if not answer_clean:
            return {
                "classification": "UNSUPPORTED",
                "faithfulness_score": 0.0,
                "supported_sentences": 0,
                "total_sentences": 1,
                "is_hallucination": True,
            }

        # Split into distinct sentences/clauses
        sentences = [
            s.strip() for s in re.split(r'[.!?\n]', answer_clean) if len(s.strip()) > 10
        ]
        if not sentences:
            sentences = [answer_clean]

        supported_count = 0
        for sent in sentences:
            # Extract key nouns and numbers from sentence
            words = [
                w.lower().strip("[](),:\"'")
                for w in sent.split()
                if len(w) > 3 and not w.lower().startswith("source")
            ]
            if not words:
                continue

            # Check what percentage of key words exist in retrieved context
            found_words = sum(1 for w in words if w in context_clean)
            word_overlap_ratio = found_words / len(words)

            if word_overlap_ratio >= 0.5:
                supported_count += 1

        total_sents = len(sentences)
        faithfulness_ratio = supported_count / total_sents if total_sents > 0 else 0.0

        if faithfulness_ratio >= 0.8:
            classification = "SUPPORTED"
            is_hallucination = False
        elif faithfulness_ratio >= 0.4:
            classification = "PARTIALLY_SUPPORTED"
            is_hallucination = False
        else:
            classification = "UNSUPPORTED"
            is_hallucination = True

        return {
            "classification": classification,
            "faithfulness_score": round(faithfulness_ratio, 4),
            "supported_sentences": supported_count,
            "total_sentences": total_sents,
            "is_hallucination": is_hallucination,
        }

    @staticmethod
    def aggregate_hallucination_metrics(eval_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate individual faithfulness results into dataset-wide hallucination metrics.
        """
        total = len(eval_results)
        if total == 0:
            return {
                "total_evaluated": 0,
                "supported_count": 0,
                "partially_supported_count": 0,
                "unsupported_count": 0,
                "faithfulness_rate": 0.0,
                "hallucination_rate": 0.0,
            }

        supported = sum(1 for r in eval_results if r["classification"] == "SUPPORTED")
        partially = sum(1 for r in eval_results if r["classification"] == "PARTIALLY_SUPPORTED")
        unsupported = sum(1 for r in eval_results if r["classification"] == "UNSUPPORTED")

        faithfulness_rate = ((supported + (partially * 0.5)) / total) * 100
        hallucination_rate = (unsupported / total) * 100

        return {
            "total_evaluated": total,
            "supported_count": supported,
            "partially_supported_count": partially,
            "unsupported_count": unsupported,
            "faithfulness_rate": round(faithfulness_rate, 2),
            "hallucination_rate": round(hallucination_rate, 2),
        }


hallucination_evaluator = HallucinationEvaluator()
