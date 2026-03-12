from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import Column, Text, DateTime, UUID, ForeignKey
from cognee.infrastructure.databases.relational import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, nullable=False, index=True)
    dataset_id = Column(UUID, nullable=True)   # None = 全部数据集
    search_type = Column(Text, nullable=False, default="GRAPH_COMPLETION")
    title = Column(Text, nullable=False, default="新对话")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID, primary_key=True, default=uuid4)
    session_id = Column(UUID, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Text, nullable=False)   # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
