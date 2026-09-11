import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status, Request
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
    RenameConversationRequest,
    ConversationResponse,
    ConversationDetailResponse,
    DeleteConversationResponse,
)
from app.services.chat_service import chat_service
from app.core.auth import get_optional_user
from app.models.user import User
from app.services.audit_service import log_audit_event

logger = logging.getLogger("enterprise_rag.chat")

# Primary chat router (/api/chat)
router = APIRouter(prefix="/chat", tags=["Chat & Inference"])

# Dedicated conversations router (/api/conversations)
conversations_router = APIRouter(prefix="/conversations", tags=["Conversations"])


# =========================================================================
# Chat Sessions & Conversations Endpoints
# =========================================================================

@router.post(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Chat Session",
    description="Create a new persistent conversation session thread in PostgreSQL.",
)
@conversations_router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Conversation",
    description="Create a new persistent conversation thread in PostgreSQL.",
)
async def create_chat_session(
    request: CreateSessionRequest = CreateSessionRequest(),
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Creates a new ChatSession record in the database and returns its unique identifier.
    """
    return chat_service.create_session(title=request.title, user_id=user.id if user else None, db=db)


@router.get(
    "/sessions",
    response_model=List[SessionResponse],
    summary="List Chat Sessions",
    description="Retrieve all persistent chat session threads from PostgreSQL.",
)
@conversations_router.get(
    "",
    response_model=List[SessionResponse],
    summary="List Conversations",
    description="Retrieve all persistent conversations from PostgreSQL ordered by newest updated first.",
)
async def list_chat_sessions(
    search: Optional[str] = Query(None, description="Optional search filter on conversation title"),
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Returns list of all active chat sessions stored in PostgreSQL with optional search filter.
    """
    return chat_service.list_sessions(db=db, search=search, user_id=user.id if user else None)


@conversations_router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get Conversation Details",
    description="Retrieve conversation metadata and all historical messages with source citations.",
)
@router.get(
    "/sessions/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get Session Details",
    include_in_schema=False,
)
async def get_conversation_details(
    conversation_id: str,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Returns conversation metadata and historical messages with sources.
    """
    u_id = user.id if (user and user.role != "ADMIN") else None
    return chat_service.get_session_details(session_id=conversation_id, db=db, user_id=u_id)


@conversations_router.patch(
    "/{conversation_id}",
    response_model=SessionResponse,
    summary="Rename Conversation",
    description="Rename an existing conversation thread title.",
)
@router.patch(
    "/sessions/{conversation_id}",
    response_model=SessionResponse,
    summary="Rename Session",
    include_in_schema=False,
)
async def rename_conversation(
    conversation_id: str,
    request: RenameConversationRequest,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Updates the title of an existing conversation thread.
    """
    u_id = user.id if (user and user.role != "ADMIN") else None
    return chat_service.rename_session(session_id=conversation_id, new_title=request.title, db=db, user_id=u_id)


@conversations_router.delete(
    "/{conversation_id}",
    response_model=DeleteConversationResponse,
    summary="Delete Conversation",
    description="Permanently delete a conversation thread and all its messages.",
)
@router.delete(
    "/sessions/{conversation_id}",
    response_model=DeleteConversationResponse,
    summary="Delete Session",
    include_in_schema=False,
)
async def delete_conversation(
    conversation_id: str,
    req: Request,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Permanently deletes the conversation and cascade-removes associated messages.
    """
    u_id = user.id if (user and user.role != "ADMIN") else None
    chat_service.delete_session(session_id=conversation_id, db=db, user_id=u_id)

    client_ip = req.client.host if req.client else None
    log_audit_event(
        db=db,
        action="CONVERSATION_DELETE",
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        resource_type="conversation",
        resource_id=conversation_id,
        ip_address=client_ip,
    )

    return DeleteConversationResponse(
        success=True,
        message="Conversation deleted successfully.",
        conversation_id=conversation_id,
    )


# =========================================================================
# Chat Q&A & Inference Endpoint
# =========================================================================

@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask Policy Question",
    description="Submit an enterprise policy question with multi-turn context and source grounding.",
)
async def send_chat_message(
    request: ChatRequest,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Validates question, executes contextual retrieval, queries Ollama, and persists messages in PostgreSQL.
    """
    logger.info(f"Chat question received: '{request.question[:60]}...' (doc_id={request.document_id}, lang={request.language})")
    return chat_service.handle_chat_message(
        question=request.question or request.message,
        session_id=request.session_id or request.conversation_id,
        db=db,
        top_k=request.top_k,
        document_id=request.document_id,
        user_id=user.id if user else None,
        language=request.language,
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


# =========================================================================
# Feedback Endpoints
# =========================================================================

@router.post(
    "/messages/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Message Feedback",
    description="Record positive or negative rating and comment for an assistant message.",
)
async def submit_message_feedback(
    message_id: str,
    request: FeedbackRequest,
    db: Session = Depends(get_db),
):
    """
    Records thumbs-up or thumbs-down feedback for an assistant response.
    """
    return chat_service.submit_feedback(
        message_id=message_id,
        rating=request.rating,
        comment=request.comment,
        db=db,
    )


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
