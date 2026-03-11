"""Per-user default model selection by task type.

task_type values:
  - "chat"       : conversational answers / search results
  - "extraction" : summarization, classification, fast extraction
  - "embedding"  : vector embedding model
"""

from __future__ import annotations

from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, UUID, UniqueConstraint
from cognee.infrastructure.databases.relational import Base


class UserDefaultModel(Base):
    __tablename__ = "user_default_models"

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, nullable=False, index=True)
    task_type = Column(String(30), nullable=False)      # "chat" | "extraction" | "embedding"
    provider_id = Column(String(50), nullable=False)     # "dashscope"
    model_id = Column(String(100), nullable=False)       # "qwen-plus"
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "task_type", name="uq_user_task_type"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "task_type": self.task_type,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
        }
