from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CandidateChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique UUID of DocumentChunk")
    document_id: str = Field(..., description="UUID of parent Document")
    filename: str = Field(..., description="Original policy file name")
    chunk_index: int = Field(0, description="Sequential chunk index")
    page: Optional[int] = Field(None, description="1-indexed PDF page number")
    section: Optional[str] = Field(None, description="Extracted section/heading")
    text: str = Field(..., description="Extracted clean chunk text")
    character_count: int = Field(0, description="Length of chunk text")
    score: float = Field(..., description="Cosine similarity score [-1.0 to 1.0]")


class SourceCitation(BaseModel):
    source_id: str = Field(..., examples=["S1", "S2"], description="Sequential citation tag for LLM referencing")
    document: str = Field(..., examples=["Leave_Policy.pdf"], description="Original filename")
    page: Optional[int] = Field(None, examples=[1, 2], description="Page number")
    section: Optional[str] = Field(None, examples=["Annual Vacation Leave"], description="Section name")
    chunk_id: str = Field(..., description="Unique chunk UUID")
    score: float = Field(..., examples=[0.8754], description="Cosine similarity score")


class RAGRetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, examples=["How many annual leave days are allowed?"])
    top_k: Optional[int] = Field(None, ge=1, le=10, description="Number of candidate chunks (clamped to max 10)")
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relevance cutoff threshold")


class RetrievalDebugInfo(BaseModel):
    candidates: int = Field(..., examples=[5])
    accepted: int = Field(..., examples=[3])
    rejected: int = Field(..., examples=[2])
    threshold: float = Field(..., examples=[0.35])
    embedding_time_ms: float = Field(0.0)
    faiss_time_ms: float = Field(0.0)
    context_build_time_ms: float = Field(0.0)
    total_time_ms: float = Field(0.0)


class RAGRetrievalResponse(BaseModel):
    status: str = Field(..., examples=["success", "insufficient_context"])
    query: str = Field(..., examples=["How many annual leave days are allowed?"])
    context: str = Field(..., description="Structured, formatted context block formatted for LLM ingestion")
    sources: List[SourceCitation] = Field(default_factory=list, description="List of source citations")
    total_sources: int = Field(0, description="Count of accepted relevant sources")
    message: Optional[str] = Field(None, description="Diagnostic or fallback message")
    debug_info: Optional[Dict[str, Any]] = Field(None, description="Debug statistics when RAG_DEBUG=true")
