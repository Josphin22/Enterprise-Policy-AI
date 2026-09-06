import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.chat import (
    CreateSessionRequest,
    SessionResponse,
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    FeedbackRequest,
    FeedbackResponse,
)
from app.services.chat_service import chat_service

logger = logging.getLogger("enterprise_rag.chat")
router = APIRouter(prefix="/chat", tags=["Chat & Inference"])


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Chat Session",
    description="Create a new persistent conversation session thread in PostgreSQL.",
)
async def create_chat_session(
    request: CreateSessionRequest = CreateSessionRequest(),
    db: Session = Depends(get_db),
):
    """
    Creates a new ChatSession record in the database and returns its unique identifier.
    """
    return chat_service.create_session(title=request.title, db=db)


@router.get(
    "/sessions",
    response_model=List[SessionResponse],
    summary="List Chat Sessions",
    description="Retrieve all persistent chat session threads from PostgreSQL.",
)
async def list_chat_sessions(db: Session = Depends(get_db)):
    """
    Returns list of all active chat sessions stored in PostgreSQL.
    """
    return chat_service.list_sessions(db=db)


@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask Policy Question",
    description="Submit an enterprise policy question. Stores the user query in PostgreSQL. AI RAG inference will connect in Phase 5.",
)
async def send_chat_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Validates question, stores user message in PostgreSQL, and accurately reports LLM state.
    """
    logger.info(f"Chat question received: '{request.question[:60]}...'")
    return chat_service.handle_chat_message(
        question=request.question,
        session_id=request.session_id,
        db=db,
    )


@router.get(
    "/history",
    response_model=ChatHistoryResponse,
    summary="Get Chat History",
    description="Retrieve real conversation history and past messages from PostgreSQL.",
)
async def get_chat_history(
    session_id: Optional[str] = Query(None, description="Optional session UUID filter"),
    db: Session = Depends(get_db),
):
    """
    Returns real chat messages and session metadata from PostgreSQL.
    """
    return chat_service.get_chat_history(session_id=session_id, db=db)


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Answer Feedback",
    description="Record positive or negative rating and comment for a policy answer in PostgreSQL.",
)
async def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db),
):
    """
    Validates feedback rating and message existence, persisting to PostgreSQL.
    """
    logger.info(
        f"Feedback received for message '{request.message_id}': rating={request.rating}"
    )
    return chat_service.submit_feedback(
        message_id=request.message_id,
        rating=request.rating,
        comment=request.comment,
        db=db,
    )
