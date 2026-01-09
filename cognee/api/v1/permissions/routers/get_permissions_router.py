from uuid import UUID
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cognee.modules.users.models import User
from cognee.modules.users.methods import get_authenticated_user
from cognee.shared.utils import send_telemetry
from cognee import __version__ as cognee_version
from cognee.api.v1.permissions.dependencies import require_tenant_admin, require_superuser


# Pydantic 模型
class UpdateUserRolesRequest(BaseModel):
    role_names: List[str]

class CreateRoleRequest(BaseModel):
    name: str
    description: Optional[str] = None

class UpdateRoleRequest(BaseModel):
    name: str
    description: Optional[str] = None

class UpdateTenantExpiresRequest(BaseModel):
    expires_at: Optional[str] = None  # ISO 8601 格式的日期字符串

class ToggleUserActiveRequest(BaseModel):
    is_active: bool


def get_permissions_router() -> APIRouter:
    permissions_router = APIRouter()

    @permissions_router.post("/datasets/{principal_id}")
    async def give_datasets_permission_to_principal(
        permission_name: str,
        dataset_ids: List[UUID],
        principal_id: UUID,
        user: User = Depends(get_authenticated_user),
    ):
        """
        Grant permission on datasets to a principal (user or role).

        This endpoint allows granting specific permissions on one or more datasets
        to a principal (which can be a user or role). The authenticated user must
        have appropriate permissions to grant access to the specified datasets.

        ## Path Parameters
        - **principal_id** (UUID): The UUID of the principal (user or role) to grant permission to

        ## Request Parameters
        - **permission_name** (str): The name of the permission to grant (e.g., "read", "write", "delete")
        - **dataset_ids** (List[UUID]): List of dataset UUIDs to grant permission on

        ## Response
        Returns a success message indicating permission was assigned.

        ## Error Codes
        - **400 Bad Request**: Invalid request parameters
        - **403 Forbidden**: User doesn't have permission to grant access
        - **500 Internal Server Error**: Error granting permission
        """
        send_telemetry(
            "Permissions API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"POST /v1/permissions/datasets/{str(principal_id)}",
                "dataset_ids": str(dataset_ids),
                "principal_id": str(principal_id),
                "cognee_version": cognee_version,
            },
        )

        from cognee.modules.users.permissions.methods import authorized_give_permission_on_datasets

        await authorized_give_permission_on_datasets(
            principal_id,
            [dataset_id for dataset_id in dataset_ids],
            permission_name,
            user.id,
        )

        return JSONResponse(
            status_code=200, content={"message": "Permission assigned to principal"}
        )

    @permissions_router.post("/roles")
    async def create_role(role_name: str, user: User = Depends(get_authenticated_user)):
        """
        Create a new role.

        This endpoint creates a new role with the specified name. Roles are used
        to group permissions and can be assigned to users to manage access control
        more efficiently. The authenticated user becomes the owner of the created role.

        ## Request Parameters
        - **role_name** (str): The name of the role to create

        ## Response
        Returns a success message indicating the role was created.

        ## Error Codes
        - **400 Bad Request**: Invalid role name or role already exists
        - **500 Internal Server Error**: Error creating the role
        """
        send_telemetry(
            "Permissions API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": "POST /v1/permissions/roles",
                "role_name": role_name,
                "cognee_version": cognee_version,
            },
        )

        from cognee.modules.users.roles.methods import create_role as create_role_method

        role_id = await create_role_method(role_name=role_name, owner_id=user.id)

        return JSONResponse(
            status_code=200, content={"message": "Role created for tenant", "role_id": str(role_id)}
        )

    @permissions_router.post("/users/{user_id}/roles")
    async def add_user_to_role(
        user_id: UUID, role_id: UUID, user: User = Depends(get_authenticated_user)
    ):
        """
        Add a user to a role.

        This endpoint assigns a user to a specific role, granting them all the
        permissions associated with that role. The authenticated user must be
        the owner of the role or have appropriate administrative permissions.

        ## Path Parameters
        - **user_id** (UUID): The UUID of the user to add to the role

        ## Request Parameters
        - **role_id** (UUID): The UUID of the role to assign the user to

        ## Response
        Returns a success message indicating the user was added to the role.

        ## Error Codes
        - **400 Bad Request**: Invalid user or role ID
        - **403 Forbidden**: User doesn't have permission to assign roles
        - **404 Not Found**: User or role doesn't exist
        - **500 Internal Server Error**: Error adding user to role
        """
        send_telemetry(
            "Permissions API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"POST /v1/permissions/users/{str(user_id)}/roles",
                "user_id": str(user_id),
                "role_id": str(role_id),
                "cognee_version": cognee_version,
            },
        )

        from cognee.modules.users.roles.methods import add_user_to_role as add_user_to_role_method

        await add_user_to_role_method(user_id=user_id, role_id=role_id, owner_id=user.id)

        return JSONResponse(status_code=200, content={"message": "User added to role"})

    @permissions_router.post("/users/{user_id}/tenants")
    async def add_user_to_tenant(
        user_id: UUID, tenant_id: UUID, user: User = Depends(get_authenticated_user)
    ):
        """
        Add a user to a tenant.

        This endpoint assigns a user to a specific tenant, allowing them to access
        resources and data associated with that tenant. The authenticated user must
        be the owner of the tenant or have appropriate administrative permissions.

        ## Path Parameters
        - **user_id** (UUID): The UUID of the user to add to the tenant

        ## Request Parameters
        - **tenant_id** (UUID): The UUID of the tenant to assign the user to

        ## Response
        Returns a success message indicating the user was added to the tenant.

        ## Error Codes
        - **400 Bad Request**: Invalid user or tenant ID
        - **403 Forbidden**: User doesn't have permission to assign tenants
        - **404 Not Found**: User or tenant doesn't exist
        - **500 Internal Server Error**: Error adding user to tenant
        """
        send_telemetry(
            "Permissions API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"POST /v1/permissions/users/{str(user_id)}/tenants",
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "cognee_version": cognee_version,
            },
        )

        from cognee.modules.users.tenants.methods import add_user_to_tenant

        await add_user_to_tenant(user_id=user_id, tenant_id=tenant_id, owner_id=user.id)

        return JSONResponse(status_code=200, content={"message": "User added to tenant"})

    @permissions_router.get("/tenants")
    async def get_all_tenants(user: User = Depends(get_authenticated_user)):
        """
        获取所有租户列表
        
        返回系统中所有租户的列表信息。
        
        ## 响应
        返回租户列表，包含每个租户的基本信息。
        
        ## 错误码
        - **401 Unauthorized**: 未登录
        - **500 Internal Server Error**: 获取租户列表失败
        """
        send_telemetry(
            "Permissions API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": "GET /v1/permissions/tenants",
                "cognee_version": cognee_version,
            },
        )
        
        from cognee.modules.users.tenants.methods.get_all_tenants import get_all_tenants as get_all_tenants_method
        
        tenants = await get_all_tenants_method()
        
        # 序列化租户信息
        tenant_list = [
            {
                "id": str(tenant.id),
                "name": tenant.name,
                "tenant_code": tenant.tenant_code,
                "owner_id": str(tenant.owner_id),
                "created_at": tenant.created_at.isoformat(),
                "expires_at": tenant.expires_at.isoformat() if tenant.expires_at else None,
            }
            for tenant in tenants
        ]
        
        return JSONResponse(
            status_code=200,
            content={"tenants": tenant_list}
        )

    @permissions_router.post("/tenants")
    async def create_tenant(tenant_name: str, user: User = Depends(get_authenticated_user)):
        """
        创建新租户（仅 super-admin 可用）

        此端点创建一个新租户。只有系统的 super-admin 用户才能创建租户。
        创建过程会自动：
        1. 生成 6 位唯一租户编码
        2. 设置有效期（15天）
        3. 创建默认角色：管理员、普通用户
        4. 创建租户管理员账号（租户名拼音@tyersoft.com / 12345678）
        5. 将管理员角色分配给管理员账号

        ## 请求参数
        - **tenant_name** (str): 租户名称

        ## 响应
        返回成功消息和租户 ID、租户编码、管理员账号、有效期。

        ## 错误码
        - **403 Forbidden**: 用户不是 super-admin
        - **400 Bad Request**: 租户名无效或已存在
        - **500 Internal Server Error**: 创建租户错误
        """
        # 检查用户是否为 super-admin
        if not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super-admin users can create tenants. "
                       "Please contact system administrator for tenant creation."
            )
        
        send_telemetry(
            "Permissions API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": "POST /v1/permissions/tenants",
                "tenant_name": tenant_name,
                "cognee_version": cognee_version,
            },
        )

        from cognee.modules.users.tenants.methods import create_tenant as create_tenant_method
        from cognee.modules.users.utils.pinyin_converter import generate_tenant_admin_email
        from cognee.modules.users.methods import create_user
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import select, text
        from cognee.modules.users.models import Role

        # 1. 创建租户（有效期 = 创建时间 + 15天）
        tenant_id = await create_tenant_method(
            tenant_name=tenant_name, 
            user_id=user.id,
            auto_initialize=True,  # 自动创建默认角色
        )
        
        # 设置15天有效期
        expires_at = datetime.now(timezone.utc) + timedelta(days=15)
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            await session.execute(
                text("""
                    UPDATE tenants 
                    SET expires_at = :expires_at 
                    WHERE id = :tenant_id
                """),
                {"expires_at": expires_at, "tenant_id": tenant_id}
            )
            await session.commit()
        
        # 2. 获取租户信息
        from cognee.modules.users.permissions.methods import get_tenant
        tenant = await get_tenant(tenant_id)
        
        # 3. 生成管理员邮箱
        admin_email = generate_tenant_admin_email(tenant_name)
        admin_password = "12345678"
        
        # 4. 创建管理员用户
        try:
            admin_user = await create_user(
                email=admin_email,
                password=admin_password,
                tenant_id=str(tenant_id),
                is_superuser=False,
                is_active=True,
                is_verified=True,
            )
            
            # 5. 为管理员分配角色：先分配"普通用户"角色，再分配"管理员"角色
            async with db_engine.get_async_session() as session:
                # 5.1 查找"普通用户"角色
                result = await session.execute(
                    select(Role).where(
                        Role.tenant_id == tenant_id,
                        Role.name == "普通用户"
                    )
                )
                normal_user_role = result.scalars().first()
                
                # 5.2 查找"管理员"角色
                result = await session.execute(
                    select(Role).where(
                        Role.tenant_id == tenant_id,
                        Role.name == "管理员"
                    )
                )
                admin_role = result.scalars().first()
                
                # 5.3 分配两个角色
                if normal_user_role:
                    await session.execute(text("""
                        INSERT INTO user_roles (user_id, role_id)
                        VALUES (:user_id, :role_id)
                        ON CONFLICT DO NOTHING
                    """), {"user_id": str(admin_user.id), "role_id": str(normal_user_role.id)})
                
                if admin_role:
                    await session.execute(text("""
                        INSERT INTO user_roles (user_id, role_id)
                        VALUES (:user_id, :role_id)
                        ON CONFLICT DO NOTHING
                    """), {"user_id": str(admin_user.id), "role_id": str(admin_role.id)})
                
                await session.commit()
        except Exception as e:
            # 如果用户已存在，忽略错误，但记录日志
            print(f"Warning: Failed to create admin user {admin_email}: {str(e)}")
            admin_user = None

        return JSONResponse(
            status_code=200, 
            content={
                "message": "Tenant created successfully with admin account.",
                "tenant_id": str(tenant_id),
                "tenant_code": tenant.tenant_code,
                "expires_at": expires_at.isoformat(),
                "admin_account": {
                    "username": admin_email,
                    "password": admin_password,
                } if admin_user else None,
            }
        )
    
    @permissions_router.patch("/tenants/{tenant_id}/expires")
    async def update_tenant_expires(
        tenant_id: UUID,
        request: UpdateTenantExpiresRequest,
        user: User = Depends(get_authenticated_user)
    ):
        """
        更新租户有效期（仅 super-admin 可用）
        
        设置租户的有效期。超过有效期的租户，其用户将无法登录。
        
        ## 路径参数
        - **tenant_id** (UUID): 租户 ID
        
        ## 请求参数
        - **expires_at** (str, optional): 有效期，ISO 8601 格式 (e.g., "2025-12-31T23:59:59Z")
          - 如果为 null 或不提供，则设置为无限期
        
        ## 响应
        返回更新后的租户信息。
        
        ## 错误码
        - **403 Forbidden**: 用户不是 super-admin
        - **404 Not Found**: 租户不存在
        - **400 Bad Request**: 日期格式错误
        """
        # 检查用户是否为 super-admin
        if not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super-admin users can update tenant expiration."
            )
        
        expires_at = request.expires_at
        
        send_telemetry(
            "Permissions API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"PATCH /v1/permissions/tenants/{str(tenant_id)}/expires",
                "tenant_id": str(tenant_id),
                "expires_at": expires_at,
                "cognee_version": cognee_version,
            },
        )
        
        from cognee.modules.users.permissions.methods import get_tenant
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import text
        
        # 检查租户是否存在
        tenant = await get_tenant(tenant_id)
        
        # 解析日期
        parsed_expires_at = None
        if expires_at:
            try:
                parsed_expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid date format. Use ISO 8601 format (e.g., '2025-12-31T23:59:59Z'): {str(e)}"
                )
        
        # 更新租户有效期
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            await session.execute(
                text("""
                    UPDATE tenants 
                    SET expires_at = :expires_at 
                    WHERE id = :tenant_id
                """),
                {"expires_at": parsed_expires_at, "tenant_id": tenant_id}
            )
            await session.commit()
        
        # 重新获取更新后的租户信息
        updated_tenant = await get_tenant(tenant_id)
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Tenant expiration updated successfully.",
                "tenant_id": str(tenant_id),
                "tenant_name": updated_tenant.name,
                "expires_at": updated_tenant.expires_at.isoformat() if updated_tenant.expires_at else None,
            }
        )

    @permissions_router.post("/tenants/{tenant_id}/invite")
    async def create_tenant_invite(
        tenant_id: UUID,
        days_valid: int = 7,
        user: User = Depends(get_authenticated_user)
    ):
        """
        为租户生成邀请链接（租户管理员或 owner 可用）
        
        生成一个邀请令牌，用户可以通过邀请链接注册并自动加入租户。
        
        ## 路径参数
        - **tenant_id** (UUID): 租户 ID
        
        ## 请求参数
        - **days_valid** (int): 令牌有效天数（默认 7 天）
        
        ## 响应
        返回邀请令牌和完整的邀请链接。
        
        ## 错误码
        - **403 Forbidden**: 用户不是租户 owner 或管理员
        - **404 Not Found**: 租户不存在
        """
        from cognee.modules.users.permissions.methods import get_tenant
        from cognee.modules.users.tenants.methods.invite_token import create_invite_token
        
        # 检查租户是否存在
        tenant = await get_tenant(tenant_id)
        
        # 检查权限：超级管理员、租户owner、或租户管理员（拥有"管理员"角色）
        is_tenant_admin = False
        if user.tenant_id == tenant_id:
            # 检查是否有管理员角色
            from cognee.infrastructure.databases.relational import get_relational_engine
            from sqlalchemy import text
            
            db_engine = get_relational_engine()
            async with db_engine.get_async_session() as session:
                result = await session.execute(text("""
                    SELECT COUNT(*) as count
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = :user_id 
                    AND r.name = '管理员'
                    AND r.tenant_id = :tenant_id
                """), {"user_id": user.id, "tenant_id": tenant_id})
                
                row = result.fetchone()
                is_tenant_admin = row.count > 0 if row else False
        
        if not (user.is_superuser or tenant.owner_id == user.id or is_tenant_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only tenant owner, tenant administrator, or super-admin can create invite links."
            )
        
        send_telemetry(
            "Permissions API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"POST /v1/permissions/tenants/{str(tenant_id)}/invite",
                "tenant_id": str(tenant_id),
                "days_valid": days_valid,
                "cognee_version": cognee_version,
            },
        )
        
        # 创建邀请令牌
        invite_token = await create_invite_token(
            tenant_id=tenant_id,
            created_by=user.id,
            days_valid=days_valid
        )
        
        # 生成邀请链接（前端注册页面加上 token 参数）
        invite_url = f"/auth/signup?invite_token={invite_token.token}"
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Invite token created successfully.",
                "token": invite_token.token,
                "invite_url": invite_url,
                "expires_at": invite_token.expires_at.isoformat(),
                "tenant_code": tenant.tenant_code,
            }
        )
    
    @permissions_router.get("/tenants/{tenant_id}/users")
    async def get_tenant_users(
        tenant_id: UUID,
        user: User = Depends(get_authenticated_user)
    ):
        """
        获取租户的用户列表（超级管理员只读）
        
        超级管理员可以查看任何租户的用户列表。
        
        ## 路径参数
        - **tenant_id** (UUID): 租户 ID
        
        ## 响应
        返回用户列表。
        
        ## 错误码
        - **403 Forbidden**: 用户不是 super-admin
        - **404 Not Found**: 租户不存在
        """
        # 检查是否为 super-admin
        if not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super-admin users can view tenant users."
            )
        
        from cognee.modules.users.permissions.methods import get_tenant
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import text
        
        # 检查租户是否存在
        tenant = await get_tenant(tenant_id)
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            # 查询租户内的所有用户及其角色
            # users表通过principals表获取created_at
            result = await session.execute(text("""
                SELECT 
                    u.id,
                    u.email,
                    u.is_active,
                    u.is_verified,
                    p.created_at,
                    ARRAY_AGG(r.name) FILTER (WHERE r.name IS NOT NULL) as roles
                FROM users u
                JOIN principals p ON u.id = p.id
                LEFT JOIN user_roles ur ON u.id = ur.user_id
                LEFT JOIN roles r ON ur.role_id = r.id
                WHERE u.tenant_id = :tenant_id
                GROUP BY u.id, u.email, u.is_active, u.is_verified, p.created_at
                ORDER BY u.email
            """), {"tenant_id": tenant_id})
            
            users_data = result.fetchall()
            
            users_list = [
                {
                    "id": str(row.id),
                    "email": row.email,
                    "is_active": row.is_active,
                    "is_verified": row.is_verified,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "roles": row.roles if row.roles else [],
                }
                for row in users_data
            ]
        
        return JSONResponse(
            status_code=200,
            content={"users": users_list}
        )
    
    @permissions_router.get("/tenants/{tenant_id}/roles")
    async def get_tenant_roles(
        tenant_id: UUID,
        user: User = Depends(get_authenticated_user)
    ):
        """
        获取租户的角色列表（超级管理员只读）
        
        超级管理员可以查看任何租户的角色列表。
        
        ## 路径参数
        - **tenant_id** (UUID): 租户 ID
        
        ## 响应
        返回角色列表。
        
        ## 错误码
        - **403 Forbidden**: 用户不是 super-admin
        - **404 Not Found**: 租户不存在
        """
        # 检查是否为 super-admin
        if not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super-admin users can view tenant roles."
            )
        
        from cognee.modules.users.permissions.methods import get_tenant
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import select, text
        from cognee.modules.users.models import Role
        
        # 检查租户是否存在
        tenant = await get_tenant(tenant_id)
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            # 查询租户的角色及用户数
            # roles表通过principals表获取created_at
            result = await session.execute(text("""
                SELECT 
                    r.id,
                    r.name,
                    p.created_at,
                    COUNT(ur.user_id) as user_count
                FROM roles r
                JOIN principals p ON r.id = p.id
                LEFT JOIN user_roles ur ON r.id = ur.role_id
                WHERE r.tenant_id = :tenant_id
                GROUP BY r.id, r.name, p.created_at
                ORDER BY r.name
            """), {"tenant_id": tenant_id})
            
            roles_data = result.fetchall()
            
            roles_list = [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "user_count": row.user_count,
                }
                for row in roles_data
            ]
        
        return JSONResponse(
            status_code=200,
            content={"roles": roles_list}
        )

    # ========== 租户管理员专用API ==========
    
    @permissions_router.get("/my-tenant")
    async def get_my_tenant(user: User = Depends(get_authenticated_user)):
        """
        获取当前用户所属租户信息
        
        租户管理员可通过此接口查看自己所属租户的基本信息。
        
        ## 响应
        返回租户基本信息。
        
        ## 错误码
        - **401 Unauthorized**: 未登录
        - **404 Not Found**: 用户不属于任何租户
        """
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not belong to any tenant"
            )
        
        from cognee.modules.users.permissions.methods import get_tenant
        
        tenant = await get_tenant(user.tenant_id)
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "tenant": {
                    "id": str(tenant.id),
                    "name": tenant.name,
                    "tenant_code": tenant.tenant_code,
                    "created_at": tenant.created_at.isoformat(),
                    "expires_at": tenant.expires_at.isoformat() if tenant.expires_at else None,
                }
            }
        )
    
    @permissions_router.get("/my-tenant/users")
    async def get_my_tenant_users(user: User = Depends(get_authenticated_user)):
        """
        获取当前租户的所有用户列表
        
        租户管理员可通过此接口查看本租户内的所有用户。
        
        ## 响应
        返回用户列表，包含每个用户的基本信息和角色。
        
        ## 错误码
        - **401 Unauthorized**: 未登录
        - **404 Not Found**: 用户不属于任何租户
        - **403 Forbidden**: 用户不是租户管理员
        """
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not belong to any tenant"
            )
        
        # TODO: 检查用户是否有管理员角色（可选）
        
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import text
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            # 查询租户内的所有用户及其角色
            # users表通过principals表获取created_at
            result = await session.execute(text("""
                SELECT 
                    u.id,
                    u.email,
                    u.is_active,
                    u.is_verified,
                    p.created_at,
                    ARRAY_AGG(r.name) FILTER (WHERE r.name IS NOT NULL) as roles
                FROM users u
                JOIN principals p ON u.id = p.id
                LEFT JOIN user_roles ur ON u.id = ur.user_id
                LEFT JOIN roles r ON ur.role_id = r.id
                WHERE u.tenant_id = :tenant_id
                GROUP BY u.id, u.email, u.is_active, u.is_verified, p.created_at
                ORDER BY u.email
            """), {"tenant_id": user.tenant_id})
            
            users_data = result.fetchall()
            
            users_list = [
                {
                    "id": str(row.id),
                    "email": row.email,
                    "is_active": row.is_active,
                    "is_verified": row.is_verified,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "roles": list(row.roles) if row.roles else [],
                }
                for row in users_data
            ]
        
        return JSONResponse(
            status_code=200,
            content={"users": users_list}
        )
    
    @permissions_router.get("/my-tenant/roles")
    async def get_my_tenant_roles(user: User = Depends(get_authenticated_user)):
        """
        获取当前租户的所有角色列表
        
        租户管理员可通过此接口查看本租户内的所有角色。
        
        ## 响应
        返回角色列表。
        
        ## 错误码
        - **401 Unauthorized**: 未登录
        - **404 Not Found**: 用户不属于任何租户
        """
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not belong to any tenant"
            )
        
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import text
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            # 查询租户的角色及用户数（包含所有角色）
            # roles表通过principals表获取created_at
            result = await session.execute(text("""
                SELECT 
                    r.id,
                    r.name,
                    p.created_at,
                    COUNT(ur.user_id) as user_count
                FROM roles r
                JOIN principals p ON r.id = p.id
                LEFT JOIN user_roles ur ON r.id = ur.role_id
                WHERE r.tenant_id = :tenant_id
                GROUP BY r.id, r.name, p.created_at
                ORDER BY r.name
            """), {"tenant_id": user.tenant_id})
            
            roles_data = result.fetchall()
            
            roles_list = [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "user_count": row.user_count,
                }
                for row in roles_data
            ]
        
        return JSONResponse(
            status_code=200,
            content={"roles": roles_list}
        )
    
    @permissions_router.post("/my-tenant/roles")
    async def create_my_tenant_role(
        request: CreateRoleRequest,
        user: User = Depends(require_tenant_admin)  # 要求租户管理员权限
    ):
        """
        在当前租户创建新角色
        
        租户管理员可通过此接口创建新的角色。
        
        ## 请求参数
        - **name** (str): 角色名称
        - **description** (str, optional): 角色描述
        
        ## 响应
        返回创建成功的角色信息。
        
        ## 错误码
        - **401 Unauthorized**: 未登录
        - **404 Not Found**: 用户不属于任何租户
        - **400 Bad Request**: 角色名已存在
        """
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not belong to any tenant"
            )
        
        from cognee.modules.users.roles.methods import create_role as create_role_method
        
        try:
            role_id = await create_role_method(
                role_name=request.name,
                owner_id=user.id
            )
            
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Role created successfully",
                    "role_id": str(role_id),
                    "name": request.name,
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    
    @permissions_router.put("/users/{user_id}/roles")
    async def update_user_roles(
        user_id: UUID,
        request: UpdateUserRolesRequest,
        user: User = Depends(require_tenant_admin)  # 要求租户管理员权限
    ):
        """
        更新用户的角色（替换现有角色）
        
        租户管理员可通过此接口为用户分配或更新角色。
        
        ## 路径参数
        - **user_id** (UUID): 用户 ID
        
        ## 请求参数
        - **role_names** (List[str]): 角色名称列表
        
        ## 响应
        返回更新成功消息。
        
        ## 错误码
        - **401 Unauthorized**: 未登录
        - **404 Not Found**: 用户或角色不存在
        """
        if not user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not belong to any tenant"
            )
        
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import select, text
        from cognee.modules.users.models import Role
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            # 1. 删除用户现有的所有角色
            await session.execute(text("""
                DELETE FROM user_roles
                WHERE user_id = :user_id
            """), {"user_id": user_id})
            
            # 2. 为用户添加新角色
            for role_name in request.role_names:
                # 查找角色
                result = await session.execute(
                    select(Role).where(
                        Role.tenant_id == user.tenant_id,
                        Role.name == role_name
                    )
                )
                role = result.scalars().first()
                
                if role:
                    await session.execute(text("""
                        INSERT INTO user_roles (user_id, role_id)
                        VALUES (:user_id, :role_id)
                        ON CONFLICT DO NOTHING
                    """), {"user_id": str(user_id), "role_id": str(role.id)})
            
            await session.commit()
        
        return JSONResponse(
            status_code=200,
            content={"message": "User roles updated successfully"}
        )
    
    @permissions_router.put("/roles/{role_id}")
    async def update_role(
        role_id: UUID,
        request: UpdateRoleRequest,
        user: User = Depends(require_tenant_admin)  # 要求租户管理员权限
    ):
        """
        更新角色信息
        
        ## 路径参数
        - **role_id** (UUID): 角色 ID
        
        ## 请求参数
        - **name** (str): 新角色名称
        - **description** (str, optional): 新角色描述
        """
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import text
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            await session.execute(text("""
                UPDATE roles
                SET name = :name, description = :description
                WHERE id = :role_id AND tenant_id = :tenant_id
            """), {
                "name": request.name,
                "description": request.description,
                "role_id": role_id,
                "tenant_id": user.tenant_id
            })
            await session.commit()
        
        return JSONResponse(
            status_code=200,
            content={"message": "Role updated successfully"}
        )
    
    @permissions_router.delete("/roles/{role_id}")
    async def delete_role(
        role_id: UUID,
        user: User = Depends(require_tenant_admin)  # 要求租户管理员权限
    ):
        """
        删除角色
        
        ## 路径参数
        - **role_id** (UUID): 角色 ID
        """
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import text
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            # 先删除用户-角色关联
            await session.execute(text("""
                DELETE FROM user_roles
                WHERE role_id = :role_id
            """), {"role_id": role_id})
            
            # 再删除角色本身
            await session.execute(text("""
                DELETE FROM roles
                WHERE id = :role_id AND tenant_id = :tenant_id
            """), {"role_id": role_id, "tenant_id": user.tenant_id})
            
            await session.commit()
        
        return JSONResponse(
            status_code=200,
            content={"message": "Role deleted successfully"}
        )
    
    @permissions_router.patch("/users/{user_id}/active")
    async def toggle_user_active(
        user_id: UUID,
        request: ToggleUserActiveRequest,
        user: User = Depends(require_tenant_admin)  # 要求租户管理员权限
    ):
        """
        切换用户启用/禁用状态（租户管理员）
        
        租户管理员可以启用或禁用本租户内的用户。被禁用的用户无法登录系统。
        
        ## 路径参数
        - **user_id** (UUID): 用户 ID
        
        ## 请求参数
        - **is_active** (bool): true=启用，false=禁用
        
        ## 响应
        返回更新后的用户状态。
        
        ## 错误码
        - **403 Forbidden**: 用户不是租户管理员，或尝试修改其他租户的用户
        - **404 Not Found**: 用户不存在
        """
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import text
        
        send_telemetry(
            "Permissions API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"PATCH /v1/permissions/users/{str(user_id)}/active",
                "user_id": str(user_id),
                "is_active": request.is_active,
                "cognee_version": cognee_version,
            },
        )
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            # 检查目标用户是否属于当前租户
            result = await session.execute(text("""
                SELECT id, email, is_active
                FROM users
                WHERE id = :user_id AND tenant_id = :tenant_id
            """), {"user_id": user_id, "tenant_id": user.tenant_id})
            
            target_user = result.fetchone()
            if not target_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found or does not belong to your tenant."
                )
            
            # 更新用户状态
            await session.execute(text("""
                UPDATE users
                SET is_active = :is_active
                WHERE id = :user_id
            """), {"is_active": request.is_active, "user_id": user_id})
            
            await session.commit()
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"User {'enabled' if request.is_active else 'disabled'} successfully.",
                "user_id": str(user_id),
                "is_active": request.is_active,
            }
        )

    return permissions_router
