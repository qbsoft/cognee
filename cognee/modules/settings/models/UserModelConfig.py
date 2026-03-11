"""Per-user model provider configuration.

Each row stores one user's credentials for one provider (e.g. DashScope).
API keys are stored with simple reversible encoding — upgrade to AES-256
when a dedicated secrets-management layer is added.
"""

from __future__ import annotations

import base64
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Boolean, DateTime, UUID, UniqueConstraint, JSON
from cognee.infrastructure.databases.relational import Base


def _encode(value: str) -> str:
    """Simple base64 encoding — NOT cryptographic, just prevents casual reading."""
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _decode(value: str) -> str:
    return base64.b64decode(value.encode("ascii")).decode("utf-8")


class UserModelConfig(Base):
    __tablename__ = "user_model_configs"

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, nullable=False, index=True)
    provider_id = Column(String(50), nullable=False)        # "dashscope"
    api_key_encoded = Column(Text, nullable=True)           # base64-encoded
    base_url = Column(String(500), nullable=True)           # custom endpoint override
    custom_params = Column(JSON, default=dict)              # extra provider-specific params
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "provider_id", name="uq_user_provider"),
    )

    # -- helpers ----------------------------------------------------------

    def set_api_key(self, raw_key: str) -> None:
        self.api_key_encoded = _encode(raw_key) if raw_key else None

    def get_api_key(self) -> str:
        if not self.api_key_encoded:
            return ""
        return _decode(self.api_key_encoded)

    def api_key_preview(self) -> str:
        """Return masked key like  sk-****f1  for UI display."""
        raw = self.get_api_key()
        if not raw or len(raw) < 8:
            return raw
        return raw[:3] + "****" + raw[-2:]

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "provider_id": self.provider_id,
            "api_key_preview": self.api_key_preview(),
            "base_url": self.base_url or "",
            "custom_params": self.custom_params or {},
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
