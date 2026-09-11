import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class DocumentRecordItem(BaseModel):
    id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    document_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    filename: str = Field(..., examples=["Leave_Policy.pdf"])
    original_filename: Optional[str] = Field(None, examples=["Leave_Policy.pdf"])
    file_type: Optional[str] = Field(None, examples=["pdf"])
    file_size: Optional[int] = Field(None, examples=[14235], description="Size in bytes")
    size: Optional[int] = Field(None, examples=[14235])
    status: str = Field("uploaded", examples=["uploaded", "processing", "processed", "failed", "ocr_processing", "needs_reindex"])
    text_length: int = Field(0, examples=[2847])
    chunk_count: int = Field(0, examples=[0])
    page_count: Optional[int] = Field(None, examples=[3])
    table_count: Optional[int] = Field(0, examples=[1])
    ocr_applied: Optional[bool] = Field(False, examples=[False])
    language: Optional[str] = Field(None, examples=["en"])
    visibility: Optional[str] = Field("ORGANIZATION", examples=["ORGANIZATION", "TEAM", "PRIVATE"])
    owner_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    created_at: Optional[str] = Field(None, examples=["2026-09-03T11:00:00Z"])
    uploaded_at: Optional[str] = Field(None, examples=["2026-09-03T11:00:00Z"])
    error_message: Optional[str] = Field(None)

    model_config = {"from_attributes": True}


class DocumentPermissionGrantRequest(BaseModel):
    permission: str = Field("VIEW", description="Permission level: VIEW, CHAT, EDIT, DELETE, or ADMIN")
    user_id: Optional[str] = Field(None, description="Target user UUID")
    role: Optional[str] = Field(None, description="Target role name (USER, MANAGER, ADMIN)")


class DocumentPermissionResponse(BaseModel):
    id: str
    document_id: str
    user_id: Optional[str] = None
    role: Optional[str] = None
    permission: str
    created_at: Optional[Union[datetime.datetime, str]] = None

    model_config = {"from_attributes": True}


class DocumentVisibilityUpdateRequest(BaseModel):
    visibility: str = Field(..., description="Visibility scope: ORGANIZATION, TEAM, or PRIVATE")



class DocumentUploadResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    document: DocumentRecordItem
    # Top-level aliases to support existing frontend and test expectations
    id: Optional[str] = None
    document_id: Optional[str] = None
    filename: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    size: Optional[int] = None
    status: Optional[str] = None
    text_length: Optional[int] = None
    chunk_count: Optional[int] = None
    page_count: Optional[int] = None
    table_count: Optional[int] = None
    ocr_applied: Optional[bool] = None
    language: Optional[str] = None


class DocumentResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    document_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    filename: str = Field(..., examples=["Leave_Policy.pdf"])
    original_filename: Optional[str] = Field(None, examples=["Leave_Policy.pdf"])
    file_type: Optional[str] = Field(None, examples=["pdf"])
    file_size: Optional[int] = Field(None, examples=[14235])
    size: Optional[int] = Field(None, examples=[14235], description="Size in bytes")
    status: str = Field("uploaded", examples=["uploaded", "processed", "failed", "ocr_processing", "needs_reindex"])
    text_length: int = Field(0, examples=[2847])
    chunk_count: int = Field(0, examples=[0])
    page_count: Optional[int] = Field(None, examples=[3])
    table_count: Optional[int] = Field(0, examples=[1])
    ocr_applied: Optional[bool] = Field(False, examples=[False])
    language: Optional[str] = Field(None, examples=["en"])
    visibility: Optional[str] = Field("ORGANIZATION", examples=["ORGANIZATION", "TEAM", "PRIVATE"])
    owner_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    created_at: Optional[str] = Field(None, examples=["2026-09-03T11:00:00Z"])
    uploaded_at: Optional[str] = Field(None, examples=["2026-09-03T11:00:00Z"])
    error_message: Optional[str] = Field(None)

    model_config = {"from_attributes": True}


class PagePreviewItem(BaseModel):
    page_number: Optional[int] = Field(None, examples=[1])
    section: Optional[str] = Field(None, examples=["1. Leave Policy"])
    text: str = Field(..., examples=["Annual vacation entitlement..."])
    chunk_count: int = Field(0, examples=[2])


class ChunkPreviewItem(BaseModel):
    chunk_index: int = Field(..., examples=[0])
    page_number: Optional[int] = Field(None, examples=[1])
    section: Optional[str] = Field(None, examples=["1. Leave Policy"])
    text: str = Field(..., examples=["Full-time employees receive 18 days of annual leave."])
    character_count: int = Field(..., examples=[120])


class DocumentPreviewResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    document_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    filename: str = Field(..., examples=["Leave_Policy.pdf"])
    file_type: str = Field(..., examples=["pdf"])
    file_size: int = Field(..., examples=[14235])
    status: str = Field("processed", examples=["processed"])
    page_count: Optional[int] = Field(None, examples=[3])
    table_count: int = Field(0, examples=[1])
    ocr_applied: bool = Field(False, examples=[False])
    language: Optional[str] = Field(None, examples=["en"])
    total_chunks: int = Field(0, examples=[5])
    sections: List[str] = Field(default_factory=list, examples=[["1. Introduction", "2. Leave Entitlement"]])
    pages: List[PagePreviewItem] = Field(default_factory=list)
    chunks: List[ChunkPreviewItem] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse] = Field(default_factory=list)
    total: int = Field(0, examples=[1])


class DocumentTextResponse(BaseModel):
    document_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    filename: str = Field(..., examples=["Leave_Policy.pdf"])
    text: str = Field(..., examples=["Employees are entitled to 18 days of annual leave..."])
    text_length: int = Field(..., examples=[2847])


class ChunkResponse(BaseModel):
    id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    chunk_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    document_id: Optional[str] = Field(None, examples=["550e8400-e29b-41d4-a716-446655440000"])
    chunk_index: int = Field(..., examples=[0])
    text: str = Field(..., examples=["Employees are entitled to 18 days of annual leave."])
    page_number: Optional[int] = Field(None, examples=[1])
    page_start: Optional[int] = Field(None, examples=[1])
    page_end: Optional[int] = Field(None, examples=[1])
    page: Optional[int] = Field(None, examples=[1])
    section: Optional[str] = Field(None, examples=["Annual Leave Guidelines"])
    character_count: int = Field(..., examples=[125])

    model_config = {"from_attributes": True}


class DocumentChunksResponse(BaseModel):
    success: bool = Field(True, examples=[True])
    document_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    filename: Optional[str] = Field(None, examples=["Leave_Policy.txt"])
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
