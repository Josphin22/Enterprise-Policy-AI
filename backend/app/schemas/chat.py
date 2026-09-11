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
    id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    title: str = Field(..., examples=["Leave Policy Questions"])
    created_at: str = Field(..., examples=["2026-09-03T11:00:00Z"])
    updated_at: Optional[str] = Field(None, examples=["2026-09-03T11:05:00Z"])
    message_count: int = Field(0, examples=[2])


class ChatMessageResponse(BaseModel):
    id: str = Field(..., examples=["msg_12345"])
    session_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    role: str = Field(..., examples=["user"])
    content: str = Field(..., examples=["How many annual leave days are allowed?"])
    created_at: str = Field(..., examples=["2026-09-03T11:00:00Z"])


class ChatRequest(BaseModel):
    message: Optional[str] = Field(
        None,
        max_length=2000,
        examples=["How many annual leave days are allowed?"],
    )
    question: Optional[str] = Field(
        None,
        max_length=2000,
        examples=["How many annual leave days are allowed?"],
    )
    conversation_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    session_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    top_k: Optional[int] = Field(5, ge=1, le=10, description="Top-K candidate chunks")
    document_id: Optional[str] = Field(None, description="Optional document UUID filter")
    language: Optional[str] = Field("en", description="Language code for response: en, ta, hi")

    @model_validator(mode="before")
    @classmethod
    def validate_inputs(cls, values: Any) -> Any:
        if isinstance(values, dict):
            raw_q = values.get("message") or values.get("question")
            if raw_q is None or not str(raw_q).strip():
                raise ValueError("Message/question cannot be empty or solely whitespace.")
            q_str = str(raw_q).strip()
            if len(q_str) > 2000:
                raise ValueError("Message/question exceeds maximum length of 2000 characters.")
            values["message"] = q_str
            values["question"] = q_str

            conv_id = values.get("conversation_id") or values.get("session_id")
            if conv_id:
                values["conversation_id"] = str(conv_id).strip()
                values["session_id"] = str(conv_id).strip()
            
            # Normalize language
            lang = values.get("language")
            if lang:
                values["language"] = str(lang).strip().lower()
            else:
                values["language"] = "en"
        return values


class ChatResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    status: str = Field("success", examples=["success", "insufficient_context", "llm_unavailable", "model_not_found"])
    conversation_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    session_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    message_id: Optional[str] = Field(None, examples=["msg_12345"])
    assistant_message_id: Optional[str] = Field(None, examples=["msg_67890"])
    question: Optional[str] = Field(None, examples=["How many annual leave days are allowed?"])
    query: Optional[str] = Field(None, examples=["How many annual leave days are allowed?"])
    answer: Optional[str] = Field(None, description="Grounded natural-language answer with inline citations [Source 1], [Source 2]")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Authoritative source citations from retrieval")
    total_sources: int = Field(0, examples=[2])
    retrieval: Optional[Dict[str, Any]] = Field(
        None,
        description="Retrieval execution metadata (retrieved_count, top_k, threshold)",
    )
    context: Optional[str] = Field("", description="Grounded context constructed from relevant chunks")
    retrieval_duration_ms: Optional[float] = Field(0.0)
    llm_duration_ms: Optional[float] = Field(0.0)
    total_duration_ms: Optional[float] = Field(0.0)
    guardrail_status: Optional[str] = Field("PASSED", examples=["PASSED", "GROUNDING_WARNING", "NO_ANSWER_REFUSAL"])
    grounding_warning: Optional[bool] = Field(False, description="Flag indicating whether answer contains unverified claims")
    grounding_classification: Optional[str] = Field("SUPPORTED", examples=["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"])
    confidence: Optional[str] = Field("High", examples=["High", "Medium", "Low", "None"])
    language: Optional[str] = Field("en", examples=["en", "ta", "hi"])
    sensitive_data_redacted: Optional[bool] = Field(False, description="Flag indicating whether sensitive secrets were redacted")
    message: Optional[str] = Field(
        None,
        examples=["Grounded answer generated successfully."],
    )


class ChatHistoryResponse(BaseModel):
    history: List[Dict[str, Any]] = Field(default_factory=list)
    sessions: List[SessionResponse] = Field(default_factory=list)
    total: int = Field(0, examples=[0])


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, examples=["Leave Policy Questions"])

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Conversation title cannot be empty or whitespace.")
        return v.strip()


class ConversationResponse(BaseModel):
    id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    title: str = Field(..., examples=["Leave Policy Questions"])
    created_at: str = Field(..., examples=["2026-09-03T11:00:00Z"])
    updated_at: str = Field(..., examples=["2026-09-03T11:05:00Z"])
    message_count: int = Field(0, examples=[2])


class ConversationDetailResponse(BaseModel):
    id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    title: str = Field(..., examples=["Leave Policy Questions"])
    created_at: str = Field(..., examples=["2026-09-03T11:00:00Z"])
    updated_at: str = Field(..., examples=["2026-09-03T11:05:00Z"])
    messages: List[Dict[str, Any]] = Field(default_factory=list)


class DeleteConversationResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    message: str = Field("Conversation deleted successfully.", examples=["Conversation deleted successfully."])
    conversation_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])


class FeedbackRequest(BaseModel):
    message_id: Optional[str] = Field(None, min_length=1, max_length=36, examples=["550e8400-e29b-41d4-a716-446655440000"])
    rating: Literal["positive", "negative"] = Field(..., examples=["positive"])
    comment: Optional[str] = Field(None, max_length=1000, examples=["Accurate citation."])


class FeedbackResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    feedback_id: Optional[str] = Field(None, examples=["fb_12345"])
    message: str = Field(
        "Feedback recorded successfully in persistent database.",
        examples=["Feedback recorded successfully in persistent database."],
    )
