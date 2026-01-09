"""API Key模型 - 用于租户级别的API认证"""
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from cognee.infrastructure.databases.relational import Base
import secrets
import hashlib


class ApiKey(Base):
    """
    API Key模型
    
    每个租户可以创建多个API Keys用于程序化访问API。
    API Key提供了比Cookie/JWT更适合自动化和集成场景的认证方式。
    """
    __tablename__ = "api_keys"
    
    id = Column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # API Key（哈希存储，仅创建时返回明文）
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    
    # Key前缀（明文，用于UI展示，格式：tenant_XXXX）
    key_prefix = Column(String(30), nullable=False)
    
    # 所属租户
    tenant_id = Column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # 创建者
    created_by = Column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Key名称/描述
    name = Column(String(100), nullable=False)
    
    # 最后使用时间
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # 过期时间
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # 是否启用
    is_active = Column(Boolean, nullable=False, default=True)
    
    # 权限范围（JSON格式，预留扩展）
    scopes = Column(Text, nullable=True, default="[]")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))
    
    @classmethod
    def generate_key(cls, tenant_code: str) -> tuple[str, str]:
        """
        生成API Key
        
        Args:
            tenant_code: 租户编码（6位）
        
        Returns:
            tuple[str, str]: (完整的API Key明文, Key前缀)
            
        格式: tenant_{TENANT_CODE}_{32位随机字符串}
        示例: tenant_ABC123_x7h9k2m4n6p8q1r3s5t7u9v2w4x6y8z1
        """
        # 生成32位随机字符串
        random_part = secrets.token_urlsafe(24)[:32]
        
        # 组合完整Key
        full_key = f"tenant_{tenant_code}_{random_part}"
        
        # 生成前缀（用于UI展示）
        key_prefix = f"tenant_{tenant_code}_{'*' * 8}"
        
        return full_key, key_prefix
    
    @staticmethod
    def hash_key(key: str) -> str:
        """
        对API Key进行哈希处理
        
        Args:
            key: API Key明文
        
        Returns:
            str: SHA256哈希值
        """
        return hashlib.sha256(key.encode()).hexdigest()
    
    @classmethod
    def create_api_key(
        cls,
        tenant_id: UUID,
        tenant_code: str,
        created_by: UUID,
        name: str,
        expires_in_days: int = None,
        scopes: list[str] = None
    ) -> tuple["ApiKey", str]:
        """
        创建新的API Key
        
        Args:
            tenant_id: 租户ID
            tenant_code: 租户编码
            created_by: 创建者用户ID
            name: Key名称
            expires_in_days: 过期天数（None表示永不过期）
            scopes: 权限范围列表
        
        Returns:
            tuple[ApiKey, str]: (ApiKey对象, 完整的Key明文)
        """
        import json
        
        # 生成Key
        full_key, key_prefix = cls.generate_key(tenant_code)
        
        # 计算过期时间
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        
        # 创建对象
        api_key = cls(
            key_hash=cls.hash_key(full_key),
            key_prefix=key_prefix,
            tenant_id=tenant_id,
            created_by=created_by,
            name=name,
            expires_at=expires_at,
            is_active=True,
            scopes=json.dumps(scopes or [])
        )
        
        return api_key, full_key
    
    def is_valid(self) -> bool:
        """
        检查API Key是否有效
        
        Returns:
            bool: True表示有效，False表示无效
        """
        if not self.is_active:
            return False
        
        if self.expires_at:
            now = datetime.now(timezone.utc)
            if now > self.expires_at:
                return False
        
        return True
    
    def update_last_used(self):
        """更新最后使用时间"""
        self.last_used_at = datetime.now(timezone.utc)
