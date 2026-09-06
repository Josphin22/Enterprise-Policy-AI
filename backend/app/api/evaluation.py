import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.evaluation.runner import EvaluationRunner, RESULTS_DIR
from app.evaluation.dataset import evaluation_dataset

logger = logging.getLogger("enterprise_rag.api.evaluation")

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


class EvaluationRunRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=10)
    min_score: float = Field(default=0.35, ge=0.0, le=1.0)


@router.get("/summary", response_model=Dict[str, Any])
async def get_evaluation_summary():
    """
    Return the latest cached evaluation summary metrics, or run evaluation if not yet generated.
    """
    summary_path = RESULTS_DIR / "evaluation_summary.json"
    if summary_path.exists():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"Error reading cached evaluation summary: {exc}")

    # If no cached summary exists, execute evaluation runner
    runner = EvaluationRunner()
    result = runner.run_evaluation()
    return result["summary"]


@router.get("/results", response_model=List[Dict[str, Any]])
async def get_evaluation_results():
    """
    Return individual test question evaluation results and diagnostics.
    """
    results_path = RESULTS_DIR / "evaluation_results.json"
    if results_path.exists():
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning(f"Error reading cached evaluation results: {exc}")

    runner = EvaluationRunner()
    result = runner.run_evaluation()
    return result["records"]


@router.post("/run", response_model=Dict[str, Any])
async def trigger_evaluation_run(request: EvaluationRunRequest = EvaluationRunRequest()):
    """
    Trigger an on-demand scientific RAG evaluation run with customizable Top-K and threshold.
    """
    try:
        runner = EvaluationRunner(top_k=request.top_k, min_score=request.min_score)
        result = runner.run_evaluation()
        return {
            "success": True,
            "message": f"Evaluation completed for {len(result['records'])} questions.",
            "summary": result["summary"],
            "failed_cases_count": len(result["failed_cases"]),
        }
    except Exception as exc:
        logger.error(f"Evaluation run failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(exc)}")
