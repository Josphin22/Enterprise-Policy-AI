"""
PromptBuilder module in backend/app/llm/
Re-exports grounded prompt builder service and constants.
"""
from services.prompt_builder import (
    prompt_builder,
    PromptBuilder,
    SYSTEM_PROMPT,
)

__all__ = ["prompt_builder", "PromptBuilder", "SYSTEM_PROMPT"]
