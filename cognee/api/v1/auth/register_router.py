from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from cognee.modules.users.models.User import UserCreate
from cognee.modules.users.methods import create_user
from cognee.modules.users.tenants.methods.invite_token import (
    validate_invite_token,
    mark_invite_token_used
)
from cognee.modules.users.tenants.methods.generate_tenant_code import check_tenant_code_exists
from sqlalchemy import select, text
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.modules.users.models import Tenant, Role, User


class RegisterRequest(BaseModel):
    """用户注册请求"""
    email: EmailStr
    password: str
    tenant_code: Optional[str] = None  # 6位租户编码
    invite_token: Optional[str] = None  # 邀请令牌


def get_extended_register_router() -> APIRouter:
    """
    创建一个扩展的用户注册路由
    
    支持：
    1. 通过租户编码注册
    2. 通过邀请令牌注册
    3. 自动将用户加入租户并分配"普通用户"角色
    
    注意：不再支持独立注册，用户必须提供租户编码或邀请令牌之一
    """
    router = APIRouter()

    @router.post("/register")
    async def register_user(data: RegisterRequest):
        """
        用户注册端点（支持租户编码和邀请令牌）
        
        用户必须通过以下方式之一注册：
        1. 提供 tenant_code - 使用6位租户编码注册
        2. 提供 invite_token - 使用邀请链接注册
        
        注意：不再支持独立注册，必须提供租户编码或邀请令牌之一。
        
        ## 请求体
        - **email**: 用户邮箱
        - **password**: 密码
        - **tenant_code** (可选): 6位租户编码
        - **invite_token** (可选): 邀请令牌
        
        ## 响应
        返回创建的用户信息和租户信息
        """
        tenant_id: Optional[UUID] = None
        tenant_code_str: Optional[str] = None
        
        # 验证：必须提供租户编码或邀请令牌之一
        if not data.tenant_code and not data.invite_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration requires either tenant_code or invite_token. Independent registration is no longer supported."
            )
        
        # 验证：租户编码和邀请令牌不能同时提供
        if data.tenant_code and data.invite_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot provide both tenant_code and invite_token"
            )
        
        # 处理邀请令牌
        if data.invite_token:
            is_valid, error_msg, invite_tenant_id = await validate_invite_token(data.invite_token)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid invite token: {error_msg}"
                )
            tenant_id = invite_tenant_id
        
        # 处理租户编码
        elif data.tenant_code:
            # 验证租户编码格式
            from cognee.modules.users.tenants.methods.generate_tenant_code import validate_tenant_code
            
            if not validate_tenant_code(data.tenant_code):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid tenant code format. Must be 6 uppercase letters/digits"
                )
            
            # 查找租户
            db_engine = get_relational_engine()
            async with db_engine.get_async_session() as session:
                result = await session.execute(
                    select(Tenant).where(Tenant.tenant_code == data.tenant_code.upper())
                )
                tenant = result.scalars().first()
                
                if not tenant:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Tenant not found with this code"
                    )
                
                tenant_id = tenant.id
                tenant_code_str = tenant.tenant_code
        
        # 创建用户
        try:
            user = await create_user(
                email=data.email,
                password=data.password,
                tenant_id=str(tenant_id) if tenant_id else None,
                is_superuser=False,
                is_active=True,
                is_verified=True,  # 自动验证
                auto_login=False
            )
        except Exception as e:
            import traceback
            print(f"Registration error for {data.email}: {type(e).__name__}: {str(e)}")
            print(traceback.format_exc())
            error_detail = str(e) if str(e) else repr(e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create user: {error_detail}"
            )
        
        # 如果使用了邀请令牌，标记为已使用
        if data.invite_token:
            await mark_invite_token_used(data.invite_token, user.id)
        
        # 如果加入了租户，自动分配"普通用户"角色
        if tenant_id:
            db_engine = get_relational_engine()
            async with db_engine.get_async_session() as session:
                # 查找"普通用户"角色
                result = await session.execute(
                    select(Role).where(
                        Role.tenant_id == tenant_id,
                        Role.name == "普通用户"
                    )
                )
                user_role = result.scalars().first()
                
                if user_role:
                    # 直接插入用户-角色关联（避免 lazy loading）
                    await session.execute(text("""
                        INSERT INTO user_roles (user_id, role_id)
                        VALUES (:user_id, :role_id)
                        ON CONFLICT DO NOTHING
                    """), {"user_id": str(user.id), "role_id": str(user_role.id)})
                    await session.commit()
        
        return JSONResponse(
            status_code=201,
            content={
                "message": "User registered successfully",
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "tenant_id": str(user.tenant_id) if user.tenant_id else None,
                    "tenant_code": tenant_code_str,
                }
            }
        )

    return router
