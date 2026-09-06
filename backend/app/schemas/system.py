from typing import Optional, List
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["healthy"])
    service: str = Field(..., examples=["Enterprise Policy RAG"])


class ComponentStatus(BaseModel):
    status: str = Field(..., examples=["healthy"])
    details: Optional[str] = Field(None, examples=["FastAPI core runtime online"])
    type: Optional[str] = Field(None, examples=["FAISS"])
    vectors: Optional[int] = Field(None, examples=[125])
    name: Optional[str] = Field(None, examples=["all-MiniLM-L6-v2"])


class SystemStatusResponse(BaseModel):
    backend: ComponentStatus
    database: ComponentStatus
    vector_database: ComponentStatus
    embedding_model: ComponentStatus
    llm: ComponentStatus


class KnowledgeBaseStatusResponse(BaseModel):
    status: str = Field("not_built", examples=["ready", "not_built"])
    documents: int = Field(0, description="Total ingested documents")
    processed_documents: int = Field(0, description="Total processed documents with extracted chunks")
    chunks: int = Field(0, description="Total extracted text chunks")
    vectors: int = Field(0, description="Total indexed vectors in FAISS")
    embedding_model: str = Field("all-MiniLM-L6-v2", examples=["all-MiniLM-L6-v2"])
    embedding_dimension: int = Field(384, examples=[384])
    vector_database: str = Field("FAISS", examples=["FAISS"])
    rag_status: str = Field("not_ready", examples=["retrieval_ready", "not_ready"])
    last_built: Optional[str] = Field(None, examples=["2026-09-03T12:00:00Z"])


class KnowledgeBaseBuildResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    status: str = Field("built", examples=["built", "no_processed_chunks"])
    documents: int = Field(0, examples=[3])
    chunks: int = Field(0, examples=[125])
    vectors: int = Field(0, examples=[125])
    embedding_model: Optional[str] = Field(None, examples=["all-MiniLM-L6-v2"])
    embedding_dimension: Optional[int] = Field(None, examples=[384])
    message: str = Field(..., examples=["Successfully built FAISS index."])


class KnowledgeBaseSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, examples=["How many annual leave days are allowed?"])
    top_k: int = Field(5, ge=1, le=50, examples=[5])


class SearchResultItem(BaseModel):
    chunk_id: Optional[str] = Field(None, examples=["1198c603-51bf-4e08-ba90-57169f417537"])
    document_id: Optional[str] = Field(None, examples=["8f3b1e22-c104-4530-bf64-ec3b80b7e923"])
    filename: Optional[str] = Field(None, examples=["Leave_Policy.pdf"])
    page: Optional[int] = Field(None, examples=[1])
    section: Optional[str] = Field(None, examples=["Annual Vacation Leave"])
    text: str = Field(..., examples=["Employees are entitled to 15 days of annual paid vacation leave..."])
    score: float = Field(..., examples=[0.8754])


class KnowledgeBaseSearchResponse(BaseModel):
    query: str = Field(..., examples=["How many annual leave days are allowed?"])
    results: List[SearchResultItem] = Field(default_factory=list)
    total_matches: int = Field(0, examples=[5])
