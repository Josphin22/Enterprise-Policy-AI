import logging
import uuid
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.chat import ChatSession, ChatMessage
from app.models.feedback import Feedback
from app.schemas.chat import (
    SessionResponse,
    ChatResponse,
    ChatHistoryResponse,
    FeedbackResponse,
)
from app.rag.service import rag_service

logger = logging.getLogger("enterprise_rag.chat")


class ChatService:
    @staticmethod
    def create_session(title: Optional[str], db: Session) -> SessionResponse:
        """
        Create a new persistent ChatSession in PostgreSQL.
        """
        session_title = title.strip() if title and title.strip() else "Policy Query Session"
        session_obj = ChatSession(
            id=str(uuid.uuid4()),
            title=session_title,
        )
        try:
            db.add(session_obj)
            db.commit()
            db.refresh(session_obj)
            logger.info(f"Created chat session: id={session_obj.id}, title='{session_obj.title}'")
            return SessionResponse(
                session_id=session_obj.id,
                title=session_obj.title,
                created_at=session_obj.created_at.isoformat() if session_obj.created_at else "",
                message_count=0,
            )
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to create chat session: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create chat session.",
            )

    @staticmethod
    def list_sessions(db: Session) -> List[SessionResponse]:
        """
        Retrieve all chat sessions from PostgreSQL ordered by newest first.
        """
        stmt = select(ChatSession).order_by(ChatSession.created_at.desc())
        sessions = db.scalars(stmt).all()
        result = []
        for s in sessions:
            result.append(
                SessionResponse(
                    session_id=s.id,
                    title=s.title,
                    created_at=s.created_at.isoformat() if s.created_at else "",
                    message_count=len(s.messages) if s.messages else 0,
                )
            )
        return result

    @staticmethod
    def get_chat_history(session_id: Optional[str], db: Session) -> ChatHistoryResponse:
        """
        Read real messages from PostgreSQL. If session_id is provided, returns that session's messages;
        otherwise returns all conversations/sessions.
        """
        history_items: List[Dict[str, Any]] = []

        if session_id:
            session_obj = db.get(ChatSession, session_id)
            if not session_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chat session '{session_id}' was not found.",
                )
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
            )
            messages = db.scalars(stmt).all()
            for msg in messages:
                history_items.append({
                    "id": msg.id,
                    "session_id": msg.session_id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else "",
                })
        else:
            stmt = select(ChatMessage).order_by(ChatMessage.created_at.asc())
            messages = db.scalars(stmt).all()
            for msg in messages:
                history_items.append({
                    "id": msg.id,
                    "session_id": msg.session_id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else "",
                })

        sessions = ChatService.list_sessions(db)

        return ChatHistoryResponse(
            history=history_items,
            sessions=sessions,
            total=len(history_items),
        )

    @staticmethod
    def handle_chat_message(
        question: str,
        session_id: Optional[str],
        db: Session,
        top_k: Optional[int] = None,
    ) -> ChatResponse:
        """
        Full Phase 8 End-to-End Chat Process:
        1. Validates session existence in PostgreSQL (returns 404 if invalid).
        2. Stores user query with role='user'.
        3. Executes complete RAG + Ollama answer generation.
        4. Stores assistant answer with role='assistant' upon successful generation.
        5. Returns structured ChatResponse with grounded answer and authoritative citations.
        """
        query_text = question.strip()

        # 1. Validate session
        valid_session_id = None
        if session_id:
            session_obj = db.get(ChatSession, session_id)
            if not session_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chat session '{session_id}' not found.",
                )
            valid_session_id = session_obj.id

        # 2. Persist user message in PostgreSQL
        user_msg_id = str(uuid.uuid4())
        user_msg = ChatMessage(
            id=user_msg_id,
            session_id=valid_session_id,
            role="user",
            content=query_text,
        )
        try:
            db.add(user_msg)
            db.commit()
            db.refresh(user_msg)
            logger.info(f"User query persisted in PostgreSQL: id={user_msg_id}")
        except Exception as exc:
            db.rollback()
            logger.warning(f"Could not persist user message: {exc}")

        # 3. Execute RAG + Local Ollama Generation
        try:
            rag_output = rag_service.generate_rag_answer(
                query=query_text,
                top_k=top_k,
                db=db,
            )

            status_code = rag_output.get("status", "success")
            answer_text = rag_output.get("answer")
            sources = rag_output.get("sources", [])

            # 4. Handle Insufficient Context Safe Refusal
            if status_code == "insufficient_context":
                asst_msg_id = str(uuid.uuid4())
                asst_msg = ChatMessage(
                    id=asst_msg_id,
                    session_id=valid_session_id,
                    role="assistant",
                    content=answer_text or "I could not find sufficient information in the provided enterprise documents to answer this question.",
                )
                try:
                    db.add(asst_msg)
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.warning(f"Failed to persist assistant refusal message: {exc}")

                return ChatResponse(
                    success=True,
                    status="insufficient_context",
                    query=query_text,
                    message="No sufficiently relevant information was found in the enterprise knowledge base.",
                    answer=asst_msg.content,
                    context="",
                    sources=[],
                    total_sources=0,
                    session_id=valid_session_id,
                    message_id=user_msg_id,
                    assistant_message_id=asst_msg_id,
                    retrieval_duration_ms=rag_output.get("retrieval_duration_ms", 0.0),
                    llm_duration_ms=rag_output.get("llm_duration_ms", 0.0),
                    total_duration_ms=rag_output.get("total_duration_ms", 0.0),
                )

            # 5. Handle Successful Generation
            if rag_output.get("success") and answer_text:
                asst_msg_id = str(uuid.uuid4())
                asst_msg = ChatMessage(
                    id=asst_msg_id,
                    session_id=valid_session_id,
                    role="assistant",
                    content=answer_text,
                )
                try:
                    db.add(asst_msg)
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.warning(f"Failed to persist assistant answer message: {exc}")

                return ChatResponse(
                    success=True,
                    status="success",
                    query=query_text,
                    message="Grounded answer generated successfully.",
                    answer=answer_text,
                    context=rag_output.get("context", ""),
                    sources=sources,
                    total_sources=len(sources),
                    session_id=valid_session_id,
                    message_id=user_msg_id,
                    assistant_message_id=asst_msg_id,
                    retrieval_duration_ms=rag_output.get("retrieval_duration_ms", 0.0),
                    llm_duration_ms=rag_output.get("llm_duration_ms", 0.0),
                    total_duration_ms=rag_output.get("total_duration_ms", 0.0),
                )

            # 6. Handle LLM Failure (Unavailable / Model not found / Timeout)
            return ChatResponse(
                success=False,
                status=status_code,
                query=query_text,
                message=rag_output.get("message", "Local LLM answer generation was unsuccessful."),
                answer=None,
                context=rag_output.get("context", ""),
                sources=sources,
                total_sources=len(sources),
                session_id=valid_session_id,
                message_id=user_msg_id,
                assistant_message_id=None,
                retrieval_duration_ms=rag_output.get("retrieval_duration_ms", 0.0),
                llm_duration_ms=rag_output.get("llm_duration_ms", 0.0),
                total_duration_ms=rag_output.get("total_duration_ms", 0.0),
            )

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Chat processing encounter exception: {exc}")
            return ChatResponse(
                success=False,
                status="generation_error",
                query=query_text,
                message=f"Processing error: {str(exc)}",
                answer=None,
                context="",
                sources=[],
                total_sources=0,
                session_id=valid_session_id,
                message_id=user_msg_id,
            )

    @staticmethod
    def submit_feedback(
        message_id: str,
        rating: str,
        comment: Optional[str],
        db: Session,
    ) -> FeedbackResponse:
        """
        Store real feedback for a message in PostgreSQL.
        Returns 404 if the target message does not exist.
        """
        target_msg = db.get(ChatMessage, message_id)
        if not target_msg:
            logger.warning(f"Feedback rejected: message_id '{message_id}' not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chat message with ID '{message_id}' was not found.",
            )

        fb_id = str(uuid.uuid4())
        feedback_obj = Feedback(
            id=fb_id,
            message_id=target_msg.id,
            rating=rating,
            comment=comment,
        )
        try:
            db.add(feedback_obj)
            db.commit()
            logger.info(f"Feedback recorded in database: fb_id={fb_id}, msg_id={message_id}, rating={rating}")
            return FeedbackResponse(
                success=True,
                feedback_id=fb_id,
                message="Feedback recorded successfully in persistent database.",
            )
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to save feedback: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record feedback.",
            )


chat_service = ChatService()
