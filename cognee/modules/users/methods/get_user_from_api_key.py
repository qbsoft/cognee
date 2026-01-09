"""API Key认证方法"""
from typing import Optional
from uuid import UUID
from fastapi import Header, HTTPException, status
from sqlalchemy import select, text

from cognee.modules.users.models import User, ApiKey
from cognee.infrastructure.databases.relational import get_relational_engine


async def get_user_from_api_key(api_key: str) -> Optional[User]:
    """
    通过API Key获取用户
    
    此函数验证API Key的有效性，并返回对应的用户对象。
    
    Args:
        api_key: API Key字符串
    
    Returns:
        User对象（如果Key有效）或None
    
    Raises:
        HTTPException: 如果Key无效、过期或被禁用
    """
    if not api_key:
        return None
    
    # 哈希API Key
    key_hash = ApiKey.hash_key(api_key)
    
    db_engine = get_relational_engine()
    async with db_engine.get_async_session() as session:
        # 查找API Key
        result = await session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        )
        api_key = result.scalars().first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key"
            )
        
        # 检查Key是否有效
        if not api_key.is_valid():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key is expired or disabled"
            )
        
        # 更新最后使用时间
        api_key.update_last_used()
        await session.commit()
        
        # 获取用户信息
        user_result = await session.execute(
            select(User).where(User.id == api_key.created_by)
        )
        user = user_result.scalars().first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found for this API Key"
            )
        
        # 检查用户是否激活
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        
        # 检查租户是否过期
        if user.tenant_id:
            from datetime import datetime, timezone
            tenant_result = await session.execute(
                text("""
                    SELECT expires_at FROM tenants WHERE id = :tenant_id
                """),
                {"tenant_id": user.tenant_id}
            )
            tenant_row = tenant_result.fetchone()
            if tenant_row and tenant_row.expires_at:
                if datetime.now(timezone.utc) > tenant_row.expires_at:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Tenant subscription has expired"
                    )
        
        return user


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> User:
    """
    要求必须提供有效的API Key
    
    用于需要API Key认证的端点。
    
    Args:
        x_api_key: HTTP Header中的X-API-Key值（必填）
    
    Returns:
        User对象
    
    Raises:
        HTTPException: 如果未提供Key或Key无效
    """
    user = await get_user_from_api_key(x_api_key)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid API Key required",
            headers={"WWW-Authenticate": "APIKey"},
        )
    
    return user
