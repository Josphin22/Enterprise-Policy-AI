"""
Re-export module for ChunkingService in backend/services/
Provides direct access to chunking service components.
"""
from app.services.chunking_service import ChunkingService, chunking_service

__all__ = ["ChunkingService", "chunking_service"]
