"""API Keys管理路由"""
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime

from cognee.modules.users.models import User, ApiKey
from cognee.modules.users.methods import get_authenticated_user
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee import __version__ as cognee_version
from sqlalchemy import text, select


class CreateApiKeyRequest(BaseModel):
    """创建API Key请求"""
    name: str = Field(..., min_length=1, max_length=100, description="API Key名称")
    expires_in_days: Optional[int] = Field(None, ge=1, le=3650, description="过期天数（1-3650天，None表示永不过期）")
    scopes: Optional[list[str]] = Field(default=[], description="权限范围")


class ToggleApiKeyRequest(BaseModel):
    """启用/禁用API Key请求"""
    is_active: bool


async def require_tenant_admin(user: User = Depends(get_authenticated_user)) -> User:
    """
    要求用户是租户管理员或超级管理员
    """
    if user.is_superuser:
        return user
    
    if not user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with any tenant."
        )
    
    # 检查是否有管理员角色
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
        is_admin = row.count > 0 if row else False
    
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant administrators can perform this action."
        )
    
    return user


def get_api_keys_router() -> APIRouter:
    """创建API Keys管理路由"""
    router = APIRouter()
    
    @router.post("")
    async def create_api_key(
        request: CreateApiKeyRequest,
        user: User = Depends(require_tenant_admin)
    ):
        """
        创建API Key（租户管理员）
        
        租户管理员可以为其租户创建API Keys用于程序化访问API。
        
        ## 请求参数
        - **name** (str): API Key名称（必填，1-100字符）
        - **expires_in_days** (int, optional): 过期天数（1-3650天，不填表示永不过期）
        - **scopes** (list[str], optional): 权限范围（预留扩展）
        
        ## 响应
        返回创建的API Key信息，包括完整的Key明文（仅此次返回，之后无法查看）。
        
        ## 安全提示
        - ⚠️ API Key明文仅在创建时返回一次，请妥善保管
        - ⚠️ 如果Key泄露，请立即撤销
        - ⚠️ 建议为不同用途创建不同的Key，方便管理和撤销
        
        ## 错误码
        - **403 Forbidden**: 用户不是租户管理员
        - **404 Not Found**: 租户不存在
        """
        from cognee.modules.users.permissions.methods import get_tenant
        
        # 获取租户信息
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not associated with any tenant."
            )
        
        tenant = await get_tenant(user.tenant_id)
        
        # 创建API Key
        api_key, full_key = ApiKey.create_api_key(
            tenant_id=user.tenant_id,
            tenant_code=tenant.tenant_code,
            created_by=user.id,
            name=request.name,
            expires_in_days=request.expires_in_days,
            scopes=request.scopes
        )
        
        # 保存到数据库
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            session.add(api_key)
            await session.commit()
            await session.refresh(api_key)
        
        return JSONResponse(
            status_code=201,
            content={
                "message": "API Key created successfully.",
                "api_key": {
                    "id": str(api_key.id),
                    "name": api_key.name,
                    "key": full_key,  # ⚠️ 仅此次返回
                    "key_prefix": api_key.key_prefix,
                    "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                    "is_active": api_key.is_active,
                    "created_at": api_key.created_at.isoformat(),
                },
                "warning": "⚠️ Please save this API Key now. You won't be able to see it again!",
                "cognee_version": cognee_version,
            }
        )
    
    @router.get("")
    async def list_api_keys(
        user: User = Depends(require_tenant_admin)
    ):
        """
        获取租户的API Keys列表（租户管理员）
        
        返回当前租户的所有API Keys列表（不包含完整Key明文）。
        
        ## 响应
        返回API Keys列表，包括：
        - Key ID、名称、前缀（部分隐藏）
        - 创建时间、过期时间
        - 最后使用时间
        - 启用状态
        
        ## 注意
        - 完整的Key明文不会返回（安全考虑）
        - 仅显示Key前缀（如：tenant_ABC123_********）
        
        ## 错误码
        - **403 Forbidden**: 用户不是租户管理员
        """
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not associated with any tenant."
            )
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            result = await session.execute(
                select(ApiKey).where(ApiKey.tenant_id == user.tenant_id).order_by(ApiKey.created_at.desc())
            )
            api_keys = result.scalars().all()
        
        return JSONResponse(
            status_code=200,
            content={
                "api_keys": [
                    {
                        "id": str(key.id),
                        "name": key.name,
                        "key_prefix": key.key_prefix,  # 只显示前缀
                        "is_active": key.is_active,
                        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                        "created_at": key.created_at.isoformat(),
                        "created_by": str(key.created_by),
                    }
                    for key in api_keys
                ],
                "total": len(api_keys),
                "cognee_version": cognee_version,
            }
        )
    
    @router.delete("/{key_id}")
    async def revoke_api_key(
        key_id: UUID,
        user: User = Depends(require_tenant_admin)
    ):
        """
        撤销API Key（租户管理员）
        
        永久删除指定的API Key。撤销后，该Key将无法再用于认证。
        
        ## 路径参数
        - **key_id** (UUID): API Key的ID
        
        ## 响应
        返回撤销成功的消息。
        
        ## 使用场景
        - Key泄露时立即撤销
        - 员工离职时撤销其创建的Key
        - 不再使用的集成
        
        ## 错误码
        - **403 Forbidden**: 用户不是租户管理员
        - **404 Not Found**: API Key不存在或不属于当前租户
        """
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not associated with any tenant."
            )
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            # 检查Key是否存在且属于当前租户
            result = await session.execute(
                select(ApiKey).where(
                    ApiKey.id == key_id,
                    ApiKey.tenant_id == user.tenant_id
                )
            )
            api_key = result.scalars().first()
            
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="API Key not found or does not belong to your tenant."
                )
            
            # 删除Key
            await session.delete(api_key)
            await session.commit()
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "API Key revoked successfully.",
                "key_id": str(key_id),
                "cognee_version": cognee_version,
            }
        )
    
    @router.patch("/{key_id}/active")
    async def toggle_api_key_active(
        key_id: UUID,
        request: ToggleApiKeyRequest,
        user: User = Depends(require_tenant_admin)
    ):
        """
        启用/禁用API Key（租户管理员）
        
        临时禁用API Key而不删除它。禁用的Key无法用于认证，但可以随时重新启用。
        
        ## 路径参数
        - **key_id** (UUID): API Key的ID
        
        ## 请求参数
        - **is_active** (bool): 是否启用
        
        ## 响应
        返回操作成功的消息。
        
        ## 使用场景
        - 临时停用某个集成
        - 调试问题时暂时禁用Key
        - 定期轮换Key时的过渡期
        
        ## 错误码
        - **403 Forbidden**: 用户不是租户管理员
        - **404 Not Found**: API Key不存在或不属于当前租户
        """
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not associated with any tenant."
            )
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            # 检查Key是否存在且属于当前租户
            result = await session.execute(
                select(ApiKey).where(
                    ApiKey.id == key_id,
                    ApiKey.tenant_id == user.tenant_id
                )
            )
            api_key = result.scalars().first()
            
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="API Key not found or does not belong to your tenant."
                )
            
            # 更新状态
            api_key.is_active = request.is_active
            await session.commit()
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"API Key {'enabled' if request.is_active else 'disabled'} successfully.",
                "key_id": str(key_id),
                "is_active": request.is_active,
                "cognee_version": cognee_version,
            }
        )
    
    return router
