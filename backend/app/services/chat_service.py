import logging
import uuid
import json
import datetime
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.models.chat import ChatSession, ChatMessage
from app.models.feedback import Feedback
from app.models.chat_metric import ChatMetric
from app.schemas.chat import (
    SessionResponse,
    ChatResponse,
    ChatHistoryResponse,
    FeedbackResponse,
    ConversationResponse,
    ConversationDetailResponse,
    DeleteConversationResponse,
)
from app.rag.service import rag_service
try:
    from app.services.query_context_service import query_context_service
except ImportError:
    from services.query_context_service import query_context_service

logger = logging.getLogger("enterprise_rag.chat")


class ChatService:
    @staticmethod
    def create_session(
        title: Optional[str] = None,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
    ) -> SessionResponse:
        """
        Create a new persistent ChatSession in PostgreSQL.
        """
        session_title = title.strip() if title and title.strip() else "Policy Query Session"
        session_obj = ChatSession(
            id=str(uuid.uuid4()),
            title=session_title,
            user_id=user_id,
        )
        try:
            db.add(session_obj)
            db.commit()
            db.refresh(session_obj)
            logger.info(f"Created chat session: id={session_obj.id}, title='{session_obj.title}'")
            return SessionResponse(
                session_id=session_obj.id,
                id=session_obj.id,
                title=session_obj.title,
                created_at=session_obj.created_at.isoformat() if session_obj.created_at else "",
                updated_at=session_obj.updated_at.isoformat() if session_obj.updated_at else (session_obj.created_at.isoformat() if session_obj.created_at else ""),
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
    def list_sessions(
        db: Session,
        search: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[SessionResponse]:
        """
        Retrieve all chat sessions from PostgreSQL ordered by newest updated first.
        Supports optional title search and user scoping.
        """
        stmt = select(ChatSession).order_by(ChatSession.updated_at.desc())

        if user_id:
            stmt = stmt.where(or_(ChatSession.user_id == user_id, ChatSession.user_id.is_(None)))

        if search and search.strip():
            search_pat = f"%{search.strip()}%"
            stmt = stmt.where(ChatSession.title.ilike(search_pat))

        sessions = db.scalars(stmt).all()
        result = []
        for s in sessions:
            result.append(
                SessionResponse(
                    session_id=s.id,
                    id=s.id,
                    title=s.title,
                    created_at=s.created_at.isoformat() if s.created_at else "",
                    updated_at=s.updated_at.isoformat() if s.updated_at else (s.created_at.isoformat() if s.created_at else ""),
                    message_count=len(s.messages) if s.messages else 0,
                )
            )
        return result

    @staticmethod
    def get_session_details(
        session_id: str,
        db: Session,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve detailed conversation thread including messages and saved source citations.
        """
        session_obj = db.get(ChatSession, session_id)
        if not session_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{session_id}' not found.",
            )

        if user_id and session_obj.user_id and session_obj.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{session_id}' not found.",
            )

        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = db.scalars(stmt).all()
        msg_items = []
        for msg in messages:
            sources_parsed = []
            if getattr(msg, "sources_json", None):
                try:
                    sources_parsed = json.loads(msg.sources_json)
                except Exception:
                    pass

            msg_items.append({
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else "",
                "sources": sources_parsed,
            })

        return {
            "id": session_obj.id,
            "title": session_obj.title,
            "created_at": session_obj.created_at.isoformat() if session_obj.created_at else "",
            "updated_at": session_obj.updated_at.isoformat() if session_obj.updated_at else "",
            "messages": msg_items,
        }

    @staticmethod
    def rename_session(
        session_id: str,
        new_title: str,
        db: Session,
        user_id: Optional[str] = None,
    ) -> SessionResponse:
        """
        Rename an existing conversation thread.
        """
        if not new_title or not new_title.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Conversation title cannot be empty or whitespace.",
            )

        session_obj = db.get(ChatSession, session_id)
        if not session_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{session_id}' not found.",
            )

        if user_id and session_obj.user_id and session_obj.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{session_id}' not found.",
            )

        session_obj.title = new_title.strip()
        session_obj.updated_at = datetime.datetime.now(datetime.timezone.utc)

        try:
            db.commit()
            db.refresh(session_obj)
            return SessionResponse(
                session_id=session_obj.id,
                title=session_obj.title,
                created_at=session_obj.created_at.isoformat() if session_obj.created_at else "",
                message_count=len(session_obj.messages) if session_obj.messages else 0,
            )
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to rename conversation {session_id}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to rename conversation.",
            )

    @staticmethod
    def delete_session(
        session_id: str,
        db: Session,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Permanently delete a conversation thread and all its messages.
        """
        session_obj = db.get(ChatSession, session_id)
        if not session_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{session_id}' not found.",
            )

        if user_id and session_obj.user_id and session_obj.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{session_id}' not found.",
            )

        try:
            db.delete(session_obj)
            db.commit()
            logger.info(f"Deleted conversation session: {session_id}")
            return True
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to delete conversation {session_id}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete conversation.",
            )

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
                sources_parsed = []
                if getattr(msg, "sources_json", None):
                    try:
                        sources_parsed = json.loads(msg.sources_json)
                    except Exception:
                        pass

                history_items.append({
                    "id": msg.id,
                    "session_id": msg.session_id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else "",
                    "sources": sources_parsed,
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
        document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        language: Optional[str] = "en",
    ) -> ChatResponse:
        """
        Full Phase 6 & 7 End-to-End Chat Process:
        1. Validates user question (non-empty, max length 2000).
        2. Validates document existence if document_id is supplied.
        3. Validates or auto-creates conversation session in database.
        4. Composes contextual retrieval query using query_context_service.
        5. Persists user query with role='user'.
        6. Verifies knowledge base FAISS readiness.
        7. Executes Phase 5/7 retrieval pipeline (with document filtering and source diversity).
        8. If no relevant chunks: returns safe refusal without calling Ollama.
        9. Calls local Ollama LLM with original user question and specified language.
        10. Validates non-empty response, verifies and parses citations.
        11. Persists assistant answer, sources, and retrieval metadata in database.
        12. Returns structured response with authoritative sources, grounding status, and confidence.
        """
        from app.models.document import Document
        from app.models.user import User
        from app.rag.vector_store import vector_store
        from app.config import settings

        # 1. Validate question
        if not question or not question.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Question/message cannot be empty or solely whitespace.",
            )
        query_text = question.strip()
        if len(query_text) > 2000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Question/message exceeds maximum length of 2000 characters.",
            )

        from app.services.permission_service import permission_service

        # 2. Validate document_id and authorization if provided
        current_db_user = db.get(User, user_id) if user_id else None
        if document_id:
            doc = db.get(Document, document_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document with ID '{document_id}' not found.",
                )
            # Check access permission: user must have CHAT/VIEW permission
            has_access = permission_service.check_document_access(
                db=db,
                document_id=document_id,
                user=current_db_user,
                required_permission="CHAT",
            )
            if not has_access:
                logger.warning(
                    f"Access denied: user '{user_id}' cannot chat with document '{document_id}'"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You do not have permission to query this document.",
                )

        # Resolve user's permitted documents for retrieval security filtering
        allowed_doc_ids_set = permission_service.get_authorized_document_ids(
            db=db,
            user=current_db_user,
            required_permission="CHAT",
        )
        allowed_doc_ids_list = list(allowed_doc_ids_set) if allowed_doc_ids_set is not None else None

        # 3. Validate or auto-create session
        session_obj = None
        if session_id:
            session_obj = db.get(ChatSession, session_id)
            if not session_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chat session '{session_id}' not found.",
                )
            if user_id and session_obj.user_id and session_obj.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chat session '{session_id}' not found.",
                )
            valid_session_id = session_obj.id

            # Auto-update placeholder title if it's the first question
            if session_obj.title in ("Policy Query Session", "Policy Discussion", "New Chat"):
                session_obj.title = query_context_service.generate_conversation_title(query_text)
        else:
            auto_title = query_context_service.generate_conversation_title(query_text)
            session_obj = ChatSession(
                id=str(uuid.uuid4()),
                title=auto_title,
                user_id=user_id,
            )
            db.add(session_obj)
            db.commit()
            db.refresh(session_obj)
            valid_session_id = session_obj.id

        # 4. Contextual retrieval query construction
        retrieval_query = query_text
        if valid_session_id:
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == valid_session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(6)
            )
            recent_db_msgs = db.scalars(stmt).all()
            recent_msgs_formatted = [
                {"role": m.role, "content": m.content} for m in reversed(recent_db_msgs)
            ]
            retrieval_query = query_context_service.build_contextual_retrieval_query(
                query_text, recent_msgs_formatted
            )

        # 5. Persist user message in database
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
            logger.info(f"User query persisted in database: id={user_msg_id}")
        except Exception as exc:
            db.rollback()
            logger.warning(f"Could not persist user message: {exc}")

        # 6. Verify knowledge base index readiness
        if not vector_store.is_built:
            loaded = vector_store.load()
            if not loaded or not vector_store.is_built:
                logger.warning("Search rejected: Knowledge base FAISS index not ready.")
                return ChatResponse(
                    success=False,
                    status="knowledge_base_not_ready",
                    conversation_id=valid_session_id,
                    session_id=valid_session_id,
                    message_id=user_msg_id,
                    assistant_message_id=None,
                    question=query_text,
                    query=query_text,
                    answer="Knowledge base is not ready. Please process documents and build the knowledge base before asking questions.",
                    message="Knowledge base is not ready. Please process documents and build the knowledge base before asking questions.",
                    context="",
                    sources=[],
                    total_sources=0,
                    retrieval={
                        "retrieved_count": 0,
                        "top_k": top_k or settings.RETRIEVAL_TOP_K,
                        "threshold": settings.SIMILARITY_THRESHOLD,
                        "query": retrieval_query,
                    },
                )

        # 7. Execute RAG + Local Ollama Generation (with RBAC document boundary)
        try:
            rag_output = rag_service.generate_rag_answer(
                query=retrieval_query,
                top_k=top_k,
                db=db,
                document_id=document_id,
                original_query=query_text,
                allowed_document_ids=allowed_doc_ids_list,
                language=language,
            )

            status_code = rag_output.get("status", "success")
            answer_text = rag_output.get("answer")
            sources = rag_output.get("sources", [])
            top_score = sources[0].get("score", 0.0) if sources and len(sources) > 0 else 0.0

            retrieval_meta = {
                "retrieved_count": len(sources),
                "top_k": top_k or settings.RETRIEVAL_TOP_K,
                "threshold": settings.SIMILARITY_THRESHOLD,
                "top_score": top_score,
                "query": retrieval_query,
            }

            # 8. Handle Insufficient Context Safe Refusal (without calling Ollama)
            if status_code == "insufficient_context":
                asst_msg_id = str(uuid.uuid4())
                refusal_answer = (
                    answer_text
                    or "I couldn't find that information in the uploaded documents. I could not find sufficient information in the provided enterprise documents to answer this question."
                )
                asst_msg = ChatMessage(
                    id=asst_msg_id,
                    session_id=valid_session_id,
                    role="assistant",
                    content=refusal_answer,
                    sources_json=None,
                    retrieval_metadata_json=json.dumps(retrieval_meta),
                )
                try:
                    db.add(asst_msg)
                    if session_obj:
                        session_obj.updated_at = datetime.datetime.now(datetime.timezone.utc)
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.warning(f"Failed to persist assistant refusal message: {exc}")

                try:
                    metric = ChatMetric(
                        conversation_id=valid_session_id,
                        message_id=asst_msg_id,
                        user_id=user_id,
                        question=query_text,
                        retrieval_count=len(sources),
                        top_score=top_score,
                        response_time_ms=rag_output.get("total_duration_ms", 0.0),
                        retrieval_time_ms=rag_output.get("retrieval_duration_ms", 0.0),
                        ollama_time_ms=rag_output.get("llm_duration_ms", 0.0),
                        answer_found=False,
                    )
                    db.add(metric)
                    db.commit()
                except Exception as met_err:
                    logger.debug(f"Failed to record chat metric refusal: {met_err}")

                return ChatResponse(
                    success=True,
                    status="insufficient_context",
                    conversation_id=valid_session_id,
                    session_id=valid_session_id,
                    message_id=user_msg_id,
                    assistant_message_id=asst_msg_id,
                    question=query_text,
                    query=query_text,
                    message="No sufficiently relevant information was found in the enterprise knowledge base.",
                    answer=refusal_answer,
                    context="",
                    sources=[],
                    total_sources=0,
                    retrieval=retrieval_meta,
                    retrieval_duration_ms=rag_output.get("retrieval_duration_ms", 0.0),
                    llm_duration_ms=rag_output.get("llm_duration_ms", 0.0),
                    total_duration_ms=rag_output.get("total_duration_ms", 0.0),
                    guardrail_status="NO_ANSWER_REFUSAL",
                    grounding_warning=False,
                    grounding_classification="UNSUPPORTED",
                    confidence="None",
                    language=language or "en",
                )

            # 9. Handle Successful Generation
            if rag_output.get("success") and answer_text:
                asst_msg_id = str(uuid.uuid4())
                asst_msg = ChatMessage(
                    id=asst_msg_id,
                    session_id=valid_session_id,
                    role="assistant",
                    content=answer_text,
                    sources_json=json.dumps(sources) if sources else None,
                    retrieval_metadata_json=json.dumps(retrieval_meta),
                )
                try:
                    db.add(asst_msg)
                    if session_obj:
                        session_obj.updated_at = datetime.datetime.now(datetime.timezone.utc)
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.warning(f"Failed to persist assistant answer message: {exc}")

                try:
                    metric = ChatMetric(
                        conversation_id=valid_session_id,
                        message_id=asst_msg_id,
                        user_id=user_id,
                        question=query_text,
                        retrieval_count=len(sources),
                        top_score=top_score,
                        response_time_ms=rag_output.get("total_duration_ms", 0.0),
                        retrieval_time_ms=rag_output.get("retrieval_duration_ms", 0.0),
                        ollama_time_ms=rag_output.get("llm_duration_ms", 0.0),
                        answer_found=True,
                    )
                    db.add(metric)
                    db.commit()
                except Exception as met_err:
                    logger.debug(f"Failed to record chat metric success: {met_err}")

                return ChatResponse(
                    success=True,
                    status="success",
                    conversation_id=valid_session_id,
                    session_id=valid_session_id,
                    message_id=user_msg_id,
                    assistant_message_id=asst_msg_id,
                    question=query_text,
                    query=query_text,
                    message="Grounded answer generated successfully.",
                    answer=answer_text,
                    context=rag_output.get("context", ""),
                    sources=sources,
                    total_sources=len(sources),
                    retrieval=retrieval_meta,
                    retrieval_duration_ms=rag_output.get("retrieval_duration_ms", 0.0),
                    llm_duration_ms=rag_output.get("llm_duration_ms", 0.0),
                    total_duration_ms=rag_output.get("total_duration_ms", 0.0),
                    guardrail_status=rag_output.get("guardrail_status", "PASSED"),
                    grounding_warning=rag_output.get("grounding_warning", False),
                    grounding_classification=rag_output.get("grounding_classification", "SUPPORTED"),
                    confidence=rag_output.get("confidence", "High"),
                    language=language or "en",
                    sensitive_data_redacted=rag_output.get("sensitive_data_redacted", False),
                )

            # 10. Handle LLM Failure (Unavailable / Model not found / Timeout)
            return ChatResponse(
                success=False,
                status=status_code,
                conversation_id=valid_session_id,
                session_id=valid_session_id,
                message_id=user_msg_id,
                assistant_message_id=None,
                question=query_text,
                query=query_text,
                message=rag_output.get("message", "Local LLM answer generation was unsuccessful."),
                answer=None,
                context=rag_output.get("context", ""),
                sources=sources,
                total_sources=len(sources),
                retrieval=retrieval_meta,
                retrieval_duration_ms=rag_output.get("retrieval_duration_ms", 0.0),
                llm_duration_ms=rag_output.get("llm_duration_ms", 0.0),
                total_duration_ms=rag_output.get("total_duration_ms", 0.0),
                guardrail_status="ERROR",
                grounding_warning=True,
                grounding_classification="UNSUPPORTED",
                confidence="None",
            )

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"Chat processing encountered exception: {exc}")
            return ChatResponse(
                success=False,
                status="generation_error",
                conversation_id=valid_session_id,
                session_id=valid_session_id,
                message_id=user_msg_id,
                assistant_message_id=None,
                question=query_text,
                query=query_text,
                message=f"Processing error: {str(exc)}",
                answer=None,
                context="",
                sources=[],
                total_sources=0,
            )

    @staticmethod
    def submit_feedback(
        message_id: str,
        rating: str,
        comment: Optional[str],
        db: Session,
        user_id: Optional[str] = None,
    ) -> FeedbackResponse:
        """
        Store real feedback for a message in PostgreSQL.
        Returns 404 if the target message does not exist.
        Validates rating in ('positive', 'negative').
        """
        if rating not in ("positive", "negative"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Rating must be either 'positive' or 'negative'.",
            )

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
