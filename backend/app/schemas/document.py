from typing import List, Optional
from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    document_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    filename: str = Field(..., examples=["Leave_Policy.pdf"])
    original_filename: Optional[str] = Field(None, examples=["Leave_Policy.pdf"])
    file_type: Optional[str] = Field(None, examples=["pdf"])
    size: Optional[int] = Field(None, examples=[24567], description="Size in bytes")
    status: str = Field("uploaded", examples=["uploaded"])
    chunk_count: int = Field(0, examples=[0])
    uploaded_at: Optional[str] = Field(None, examples=["2026-09-03T11:00:00Z"])

    model_config = {
        "from_attributes": True
    }


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse] = Field(default_factory=list)
    total: int = Field(0, examples=[0])


class ChunkResponse(BaseModel):
    chunk_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    chunk_index: int = Field(..., examples=[0])
    text: str = Field(..., examples=["Employees are entitled to 15 days of annual leave."])
    page: Optional[int] = Field(None, examples=[1])
    section: Optional[str] = Field(None, examples=["Annual Leave Guidelines"])
    character_count: int = Field(..., examples=[125])

    model_config = {
        "from_attributes": True
    }


class DocumentChunksResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    document_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    chunk_count: int = Field(..., examples=[12])
    chunks: List[ChunkResponse] = Field(default_factory=list)


class DocumentProcessResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    document_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    status: str = Field("processed", examples=["processed"])
    chunk_count: int = Field(0, examples=[12])
    message: str = Field(
        "Successfully processed document into chunks.",
        examples=["Successfully processed document into chunks."]
    )


class DocumentDeleteResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    document_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    message: str = Field("Document deleted successfully.", examples=["Document deleted successfully."])
