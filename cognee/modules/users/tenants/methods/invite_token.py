from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.modules.users.models import InviteToken, Tenant
from cognee.modules.users.exceptions import TenantNotFoundError


async def create_invite_token(
    tenant_id: UUID,
    created_by: UUID,
    days_valid: int = 7
) -> InviteToken:
    """
    为租户创建一个邀请令牌
    
    Args:
        tenant_id: 租户 ID
        created_by: 创建者用户 ID
        days_valid: 令牌有效天数（默认 7 天）
    
    Returns:
        InviteToken: 创建的邀请令牌对象
    
    Raises:
        TenantNotFoundError: 租户不存在
    """
    db_engine = get_relational_engine()
    
    async with db_engine.get_async_session() as session:
        # 检查租户是否存在
        result = await session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalars().first()
        
        if not tenant:
            raise TenantNotFoundError(message=f"Tenant {tenant_id} not found")
        
        # 创建邀请令牌
        invite_token = InviteToken.create_token_with_expiry(
            tenant_id=tenant_id,
            created_by=created_by,
            days_valid=days_valid
        )
        
        session.add(invite_token)
        await session.commit()
        await session.refresh(invite_token)
        
        return invite_token


async def get_invite_token_by_token(token: str) -> InviteToken | None:
    """
    根据 token 字符串获取邀请令牌
    
    Args:
        token: 令牌字符串
    
    Returns:
        InviteToken | None: 邀请令牌对象，如果不存在则返回 None
    """
    db_engine = get_relational_engine()
    
    async with db_engine.get_async_session() as session:
        result = await session.execute(
            select(InviteToken).where(InviteToken.token == token)
        )
        return result.scalars().first()


async def mark_invite_token_used(token: str, user_id: UUID) -> bool:
    """
    标记邀请令牌为已使用
    
    Args:
        token: 令牌字符串
        user_id: 使用该令牌注册的用户 ID
    
    Returns:
        bool: 是否成功标记
    """
    db_engine = get_relational_engine()
    
    async with db_engine.get_async_session() as session:
        result = await session.execute(
            select(InviteToken).where(InviteToken.token == token)
        )
        invite_token = result.scalars().first()
        
        if not invite_token:
            return False
        
        invite_token.is_used = True
        invite_token.used_by = user_id
        invite_token.used_at = datetime.now(timezone.utc)
        
        await session.merge(invite_token)
        await session.commit()
        
        return True


async def validate_invite_token(token: str) -> tuple[bool, str, UUID | None]:
    """
    验证邀请令牌是否有效
    
    Args:
        token: 令牌字符串
    
    Returns:
        tuple[bool, str, UUID | None]: 
            - 是否有效
            - 错误消息（如果有）
            - 租户 ID（如果有效）
    """
    invite_token = await get_invite_token_by_token(token)
    
    if not invite_token:
        return False, "Invalid invite token", None
    
    if invite_token.is_used:
        return False, "Invite token has already been used", None
    
    if invite_token.expires_at < datetime.now(timezone.utc):
        return False, "Invite token has expired", None
    
    return True, "", invite_token.tenant_id
