from uuid import UUID
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.future import select
from sqlalchemy import delete as sql_delete

from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.modules.users.models import User
from cognee.modules.users.methods import get_authenticated_user
from cognee.modules.chat.models import ChatSession, ChatMessage


# ── DTOs ──────────────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    dataset_id: Optional[UUID] = None
    search_type: str = "GRAPH_COMPLETION"
    title: str = "新对话"

class AddMessageRequest(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class SessionDTO(BaseModel):
    id: UUID
    dataset_id: Optional[UUID]
    search_type: str
    title: str
    created_at: datetime

class MessageDTO(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    created_at: datetime


# ── Router factory ─────────────────────────────────────────────────────────────

def get_chat_router() -> APIRouter:
    router = APIRouter()

    # GET /v1/chat/sessions — list user's sessions (newest 20)
    @router.get("/sessions", response_model=List[SessionDTO])
    async def list_sessions(user: User = Depends(get_authenticated_user)):
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            result = await session.execute(
                select(ChatSession)
                .where(ChatSession.user_id == user.id)
                .order_by(ChatSession.created_at.desc())
                .limit(20)
            )
            sessions = result.scalars().all()
        return [
            SessionDTO(
                id=s.id,
                dataset_id=s.dataset_id,
                search_type=s.search_type,
                title=s.title,
                created_at=s.created_at,
            )
            for s in sessions
        ]

    # POST /v1/chat/sessions — create new session
    @router.post("/sessions", response_model=SessionDTO, status_code=status.HTTP_201_CREATED)
    async def create_session(
        body: CreateSessionRequest,
        user: User = Depends(get_authenticated_user),
    ):
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            new_session = ChatSession(
                user_id=user.id,
                dataset_id=body.dataset_id,
                search_type=body.search_type,
                title=body.title,
            )
            session.add(new_session)
            await session.commit()
            await session.refresh(new_session)
        return SessionDTO(
            id=new_session.id,
            dataset_id=new_session.dataset_id,
            search_type=new_session.search_type,
            title=new_session.title,
            created_at=new_session.created_at,
        )

    # DELETE /v1/chat/sessions/{session_id}
    @router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_session(
        session_id: UUID,
        user: User = Depends(get_authenticated_user),
    ):
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            result = await session.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user.id,
                )
            )
            s = result.scalars().first()
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
            await session.execute(
                sql_delete(ChatMessage).where(ChatMessage.session_id == session_id)
            )
            await session.delete(s)
            await session.commit()

    # GET /v1/chat/sessions/{session_id}/messages
    @router.get("/sessions/{session_id}/messages", response_model=List[MessageDTO])
    async def list_messages(
        session_id: UUID,
        user: User = Depends(get_authenticated_user),
    ):
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            result = await session.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user.id,
                )
            )
            if not result.scalars().first():
                raise HTTPException(status_code=404, detail="Session not found")

            msgs = await session.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
            )
            messages = msgs.scalars().all()
        return [
            MessageDTO(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ]

    # POST /v1/chat/sessions/{session_id}/messages
    @router.post(
        "/sessions/{session_id}/messages",
        response_model=MessageDTO,
        status_code=status.HTTP_201_CREATED,
    )
    async def add_message(
        session_id: UUID,
        body: AddMessageRequest,
        user: User = Depends(get_authenticated_user),
    ):
        if body.role not in ("user", "assistant"):
            raise HTTPException(status_code=400, detail="role must be 'user' or 'assistant'")

        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            result = await session.execute(
                select(ChatSession).where(
                    ChatSession.id == session_id,
                    ChatSession.user_id == user.id,
                )
            )
            chat_session = result.scalars().first()
            if not chat_session:
                raise HTTPException(status_code=404, detail="Session not found")

            msg = ChatMessage(
                session_id=session_id,
                role=body.role,
                content=body.content,
            )
            session.add(msg)

            # Update title from first user message
            if body.role == "user" and chat_session.title == "新对话":
                chat_session.title = body.content[:20]

            await session.commit()
            await session.refresh(msg)
        return MessageDTO(
            id=msg.id,
            session_id=msg.session_id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
        )

    return router
