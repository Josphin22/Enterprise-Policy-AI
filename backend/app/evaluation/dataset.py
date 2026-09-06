import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("enterprise_rag.evaluation.dataset")

DATASET_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "data" / "evaluation_dataset.json"


class EvaluationQuestion(BaseModel):
    id: str
    question: str
    expected_answer: str
    expected_sources: List[str] = Field(default_factory=list)
    expected_keywords: List[str] = Field(default_factory=list)
    expected_numbers: List[float] = Field(default_factory=list)
    expected_dates: List[str] = Field(default_factory=list)
    answerable: bool = True
    category: str = "direct"


class EvaluationDataset:
    def __init__(self, dataset_path: Optional[Path] = None):
        self.dataset_path = dataset_path or DATASET_PATH
        self.questions: List[EvaluationQuestion] = []
        self.load()

    def load(self) -> List[EvaluationQuestion]:
        """Load and validate the evaluation dataset."""
        if not self.dataset_path.exists():
            logger.error(f"Evaluation dataset not found at {self.dataset_path}")
            raise FileNotFoundError(f"Evaluation dataset not found at {self.dataset_path}")

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        self.questions = [EvaluationQuestion(**item) for item in raw_data]
        logger.info(f"Loaded {len(self.questions)} evaluation questions from {self.dataset_path.name}")
        return self.questions

    def get_by_category(self, category: str) -> List[EvaluationQuestion]:
        """Filter questions by category."""
        return [q for q in self.questions if q.category == category]

    def get_answerable(self) -> List[EvaluationQuestion]:
        """Filter answerable questions."""
        return [q for q in self.questions if q.answerable]

    def get_unanswerable(self) -> List[EvaluationQuestion]:
        """Filter unanswerable / refusal test questions."""
        return [q for q in self.questions if not q.answerable]

    @property
    def total(self) -> int:
        return len(self.questions)


evaluation_dataset = EvaluationDataset()
