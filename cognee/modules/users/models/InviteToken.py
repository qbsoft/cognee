from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, DateTime, UUID, ForeignKey, Boolean
from cognee.infrastructure.databases.relational import Base


class InviteToken(Base):
    """
    邀请令牌模型 - 用于租户邀请用户注册
    
    租户管理员可以生成邀请链接，用户通过链接注册后自动加入对应租户
    """
    __tablename__ = "invite_tokens"

    id = Column(UUID, primary_key=True, index=True, default=uuid4)
    
    # 邀请令牌（32位随机字符串）
    token = Column(String(32), unique=True, nullable=False, index=True)
    
    # 关联的租户 ID
    tenant_id = Column(UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    
    # 创建者（租户管理员）
    created_by = Column(UUID, ForeignKey("users.id"), nullable=False)
    
    # 令牌过期时间（默认 7 天）
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # 是否已使用
    is_used = Column(Boolean, default=False, nullable=False)
    
    # 使用该令牌注册的用户 ID
    used_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    
    # 使用时间
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    @classmethod
    def create_token_with_expiry(cls, tenant_id: UUID, created_by: UUID, days_valid: int = 7):
        """
        创建一个带有过期时间的邀请令牌
        
        Args:
            tenant_id: 租户 ID
            created_by: 创建者用户 ID
            days_valid: 有效天数（默认 7 天）
        
        Returns:
            InviteToken 实例
        """
        import secrets
        
        token = secrets.token_urlsafe(24)[:32]  # 生成 32 位 URL 安全的随机字符串
        expires_at = datetime.now(timezone.utc) + timedelta(days=days_valid)
        
        return cls(
            token=token,
            tenant_id=tenant_id,
            created_by=created_by,
            expires_at=expires_at,
        )
    
    def is_valid(self) -> bool:
        """检查令牌是否有效（未过期且未使用）"""
        now = datetime.now(timezone.utc)
        return not self.is_used and self.expires_at > now
