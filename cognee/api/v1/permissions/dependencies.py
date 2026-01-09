"""
权限检查依赖项
"""
from fastapi import Depends, HTTPException, status
from cognee.modules.users.models import User
from cognee.modules.users.methods import get_authenticated_user
from cognee.infrastructure.databases.relational import get_relational_engine
from sqlalchemy import text


async def require_tenant_admin(user: User = Depends(get_authenticated_user)) -> User:
    """
    要求用户必须是租户管理员（拥有"管理员"角色）
    
    Args:
        user: 当前认证用户
        
    Returns:
        User: 认证通过的用户
        
    Raises:
        HTTPException: 如果用户不是租户管理员
    """
    if not user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any tenant"
        )
    
    # 检查用户是否有"管理员"角色
    db_engine = get_relational_engine()
    async with db_engine.get_async_session() as session:
        result = await session.execute(text("""
            SELECT COUNT(*) as count
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = :user_id 
            AND r.name = '管理员'
            AND r.tenant_id = :tenant_id
        """), {"user_id": user.id, "tenant_id": user.tenant_id})
        
        row = result.fetchone()
        has_admin_role = row.count > 0 if row else False
    
    if not has_admin_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation requires tenant administrator role (管理员)"
        )
    
    return user


async def require_superuser(user: User = Depends(get_authenticated_user)) -> User:
    """
    要求用户必须是超级管理员
    
    Args:
        user: 当前认证用户
        
    Returns:
        User: 认证通过的用户
        
    Raises:
        HTTPException: 如果用户不是超级管理员
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation requires superuser privileges"
        )
    
    return user
