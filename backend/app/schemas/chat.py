from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, model_validator, field_validator


class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field("Policy Query Session", max_length=255, examples=["Leave Policy Questions"])

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> str:
        if not v or not v.strip():
            return "Policy Query Session"
        return v.strip()


class SessionResponse(BaseModel):
    session_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    title: str = Field(..., examples=["Leave Policy Questions"])
    created_at: str = Field(..., examples=["2026-09-03T11:00:00Z"])
    message_count: int = Field(0, examples=[2])


class ChatMessageResponse(BaseModel):
    id: str = Field(..., examples=["msg_12345"])
    session_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    role: str = Field(..., examples=["user"])
    content: str = Field(..., examples=["How many annual leave days are allowed?"])
    created_at: str = Field(..., examples=["2026-09-03T11:00:00Z"])


class ChatRequest(BaseModel):
    question: Optional[str] = Field(
        None,
        max_length=2000,
        examples=["How many annual leave days are allowed?"],
    )
    message: Optional[str] = Field(
        None,
        max_length=2000,
        examples=["How many annual leave days are allowed?"],
    )
    session_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    top_k: Optional[int] = Field(5, ge=1, le=10, description="Top-K candidate chunks")

    @model_validator(mode="before")
    @classmethod
    def validate_inputs(cls, values: Any) -> Any:
        if isinstance(values, dict):
            q = values.get("question") or values.get("message")
            if not q or not str(q).strip():
                raise ValueError("Question/message cannot be empty or solely whitespace.")
            values["question"] = str(q).strip()
            values["message"] = str(q).strip()
        return values


class ChatResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    status: str = Field("success", examples=["success", "insufficient_context", "llm_unavailable", "model_not_found"])
    query: Optional[str] = Field(None, examples=["How many annual leave days are allowed?"])
    message: Optional[str] = Field(
        None,
        examples=["Grounded answer generated successfully."],
    )
    answer: Optional[str] = Field(None, description="Grounded natural-language answer with inline citations [S1], [S2]")
    context: Optional[str] = Field("", description="Grounded context constructed from relevant chunks")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source citations [S1], [S2]")
    total_sources: int = Field(0, examples=[2])
    session_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    message_id: Optional[str] = Field(None, examples=["msg_12345"])
    assistant_message_id: Optional[str] = Field(None, examples=["msg_67890"])
    retrieval_duration_ms: Optional[float] = Field(0.0)
    llm_duration_ms: Optional[float] = Field(0.0)
    total_duration_ms: Optional[float] = Field(0.0)


class ChatHistoryResponse(BaseModel):
    history: List[Dict[str, Any]] = Field(default_factory=list)
    sessions: List[SessionResponse] = Field(default_factory=list)
    total: int = Field(0, examples=[0])


class FeedbackRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=36, examples=["550e8400-e29b-41d4-a716-446655440000"])
    rating: Literal["positive", "negative"] = Field(..., examples=["positive"])
    comment: Optional[str] = Field(None, max_length=1000, examples=["Accurate citation."])


class FeedbackResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    feedback_id: Optional[str] = Field(None, examples=["fb_12345"])
    message: str = Field(
        "Feedback recorded successfully in persistent database.",
        examples=["Feedback recorded successfully in persistent database."],
    )
