import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MetadataFilter(BaseModel):
    document_id: Optional[str] = Field(None, description="Filter candidates by parent document UUID")
    file_type: Optional[str] = Field(None, description="Filter by file extension / type, e.g. pdf, docx, txt")
    owner_id: Optional[str] = Field(None, description="Filter by document owner user UUID")
    status: Optional[str] = Field(None, description="Filter by document status, e.g. processed, uploaded")
    department: Optional[str] = Field(None, description="Filter by departmental metadata")
    allowed_document_ids: Optional[List[str]] = Field(None, description="Enforce RBAC fine-grained document access control")


class CandidateChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique UUID of DocumentChunk")
    document_id: str = Field(..., description="UUID of parent Document")
    filename: str = Field(..., description="Original policy file name")
    chunk_index: int = Field(0, description="Sequential chunk index")
    page: Optional[int] = Field(None, description="1-indexed PDF page number")
    section: Optional[str] = Field(None, description="Extracted section/heading")
    text: str = Field(..., description="Extracted clean chunk text")
    character_count: int = Field(0, description="Length of chunk text")
    score: float = Field(..., description="Relevance score [-1.0 to 1.0 or normalized 0.0 to 1.0]")
    source_type: Optional[str] = Field("semantic", description="Retrieval source: semantic, keyword, or hybrid")
    semantic_score: Optional[float] = Field(None, description="Raw semantic similarity score")
    keyword_score: Optional[float] = Field(None, description="Raw keyword match score")
    match_reasons: List[str] = Field(default_factory=list, description="Reasons for match, e.g. exact_number, date_match")


class SourceCitation(BaseModel):
    source_id: str = Field(..., examples=["Source 1", "S1"], description="Sequential citation tag for LLM referencing")
    document: str = Field(..., examples=["Leave_Policy.pdf"], description="Original filename")
    filename: Optional[str] = Field(None, examples=["Leave_Policy.pdf"], description="Original filename alias")
    document_id: Optional[str] = Field(None, description="UUID of parent Document")
    chunk_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique chunk UUID")
    chunk_index: Optional[int] = Field(0, description="Sequential chunk index")
    page: Optional[int] = Field(None, examples=[1, 2], description="Page number")
    page_number: Optional[int] = Field(None, examples=[1, 2], description="1-indexed Page number alias")
    section: Optional[str] = Field(None, examples=["Annual Vacation Leave"], description="Section name")
    score: float = Field(..., examples=[0.8754], description="Cosine similarity score")
    chunk_text: Optional[str] = Field(None, description="Raw chunk text snippet")
    text: Optional[str] = Field(None, description="Raw chunk text alias")
    preview: Optional[str] = Field(None, description="Clean chunk preview text excerpt")

    def __init__(self, **data: Any):
        if "chunk_id" not in data or not data["chunk_id"]:
            data["chunk_id"] = str(uuid.uuid4())
        if "filename" not in data and "document" in data:
            data["filename"] = data["document"]
        elif "document" not in data and "filename" in data:
            data["document"] = data["filename"]
        if "page_number" not in data and "page" in data:
            data["page_number"] = data["page"]
        elif "page" not in data and "page_number" in data:
            data["page"] = data["page_number"]
        if "chunk_text" not in data and "text" in data:
            data["chunk_text"] = data["text"]
        elif "text" not in data and "chunk_text" in data:
            data["text"] = data["chunk_text"]
        if "preview" not in data or not data["preview"]:
            raw = data.get("chunk_text") or data.get("text") or ""
            data["preview"] = raw[:250].strip() + ("..." if len(raw) > 250 else "") if raw else ""
        super().__init__(**data)


class RAGRetrievalRequest(BaseModel):
    query: str = Field(..., min_length=1, examples=["How many annual leave days are allowed?"])
    top_k: Optional[int] = Field(None, ge=1, le=10, description="Number of candidate chunks (clamped to max 10)")
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Relevance cutoff threshold")
    document_id: Optional[str] = Field(None, description="Filter candidates by parent document UUID")
    filters: Optional[MetadataFilter] = Field(None, description="Metadata filters (document_id, file_type, owner_id, status, department)")
    debug: Optional[bool] = Field(False, description="Whether to include diagnostic trace in response")


class RetrievalDebugInfo(BaseModel):
    candidates: int = Field(..., examples=[5])
    accepted: int = Field(..., examples=[3])
    rejected: int = Field(..., examples=[2])
    threshold: float = Field(..., examples=[0.35])
    embedding_time_ms: float = Field(0.0)
    faiss_time_ms: float = Field(0.0)
    keyword_time_ms: float = Field(0.0)
    merge_time_ms: float = Field(0.0)
    rerank_time_ms: float = Field(0.0)
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


class SearchDiagnosticsResponse(BaseModel):
    query: str
    normalized_query: str
    detected_numbers: List[str] = Field(default_factory=list)
    detected_dates: List[str] = Field(default_factory=list)
    detected_keywords: List[str] = Field(default_factory=list)
    semantic_count: int = 0
    keyword_count: int = 0
    merged_count: int = 0
    final_count: int = 0
    latencies_ms: Dict[str, float] = Field(default_factory=dict)
    semantic_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    keyword_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    merged_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    final_candidates: List[Dict[str, Any]] = Field(default_factory=list)
