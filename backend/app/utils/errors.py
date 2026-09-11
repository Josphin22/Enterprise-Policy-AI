"""
Standardized enterprise error codes and exception classes for Enterprise Policy AI.
"""
from typing import Optional, Any, Dict
from fastapi import HTTPException, status


class EnterpriseRAGException(HTTPException):
    """Base exception for Enterprise Policy RAG."""

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code,
                "message": message,
                "details": self.details,
            },
        )


class InvalidFileTypeError(EnterpriseRAGException):
    def __init__(self, message: str = "Only .pdf, .docx, and .txt files are supported.", details: Optional[Dict[str, Any]] = None):
        super().__init__("INVALID_FILE_TYPE", message, status.HTTP_400_BAD_REQUEST, details)


class FileTooLargeError(EnterpriseRAGException):
    def __init__(self, message: str = "Uploaded file exceeds the maximum allowed size limit.", details: Optional[Dict[str, Any]] = None):
        super().__init__("FILE_TOO_LARGE", message, 413, details)


class DocumentExtractionFailedError(EnterpriseRAGException):
    def __init__(self, message: str = "Failed to extract clean text from document.", details: Optional[Dict[str, Any]] = None):
        super().__init__("DOCUMENT_EXTRACTION_FAILED", message, 422, details)


class EmptyDocumentError(EnterpriseRAGException):
    def __init__(self, message: str = "Document contains no extractable text.", details: Optional[Dict[str, Any]] = None):
        super().__init__("EMPTY_DOCUMENT", message, 422, details)


class EmbeddingModelError(EnterpriseRAGException):
    def __init__(self, message: str = "Embedding model failed to generate or validate vectors.", details: Optional[Dict[str, Any]] = None):
        super().__init__("EMBEDDING_MODEL_ERROR", message, status.HTTP_500_INTERNAL_SERVER_ERROR, details)


class FAISSError(EnterpriseRAGException):
    def __init__(self, message: str = "FAISS vector database operation failed.", details: Optional[Dict[str, Any]] = None):
        super().__init__("FAISS_ERROR", message, status.HTTP_500_INTERNAL_SERVER_ERROR, details)


class OllamaUnavailableError(EnterpriseRAGException):
    def __init__(self, message: str = "Local Ollama daemon is unreachable or offline.", details: Optional[Dict[str, Any]] = None):
        super().__init__("OLLAMA_UNAVAILABLE", message, status.HTTP_503_SERVICE_UNAVAILABLE, details)


class OllamaModelNotFoundError(EnterpriseRAGException):
    def __init__(self, message: str = "Configured local Ollama model is not pulled or installed.", details: Optional[Dict[str, Any]] = None):
        super().__init__("OLLAMA_MODEL_NOT_FOUND", message, status.HTTP_404_NOT_FOUND, details)


class DatabaseError(EnterpriseRAGException):
    def __init__(self, message: str = "Relational database persistence operation failed.", details: Optional[Dict[str, Any]] = None):
        super().__init__("DATABASE_ERROR", message, status.HTTP_500_INTERNAL_SERVER_ERROR, details)


class NoRelevantContextError(EnterpriseRAGException):
    def __init__(self, message: str = "No enterprise policy documentation found exceeding relevance threshold.", details: Optional[Dict[str, Any]] = None):
        super().__init__("NO_RELEVANT_CONTEXT", message, status.HTTP_200_OK, details)


class PasswordProtectedError(EnterpriseRAGException):
    def __init__(self, message: str = "Password-protected or encrypted documents are not supported. Please remove password encryption before uploading.", details: Optional[Dict[str, Any]] = None):
        super().__init__("PASSWORD_PROTECTED", message, 422, details)


class CorruptedDocumentError(EnterpriseRAGException):
    def __init__(self, message: str = "The document file is corrupted, incomplete, or unreadable.", details: Optional[Dict[str, Any]] = None):
        super().__init__("CORRUPTED_DOCUMENT", message, 422, details)


class ImageOnlyDocumentError(EnterpriseRAGException):
    def __init__(self, message: str = "Document appears to be a scanned or image-only PDF with no embedded text. Enable OCR to extract content.", details: Optional[Dict[str, Any]] = None):
        super().__init__("IMAGE_ONLY_DOCUMENT", message, 422, details)


class OCRProcessingError(EnterpriseRAGException):
    def __init__(self, message: str = "OCR text extraction failed for scanned document.", details: Optional[Dict[str, Any]] = None):
        super().__init__("OCR_PROCESSING_FAILED", message, 422, details)

