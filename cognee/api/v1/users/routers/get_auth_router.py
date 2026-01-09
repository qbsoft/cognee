from fastapi import Depends
from sqlalchemy import text
import os

from cognee.modules.users.get_fastapi_users import get_fastapi_users
from cognee.modules.users.models import User
from cognee.modules.users.methods import get_authenticated_user
from cognee.modules.users.authentication.get_client_auth_backend import get_client_auth_backend
from cognee.infrastructure.databases.relational import get_relational_engine
from fastapi_users.jwt import generate_jwt


def get_auth_router():
    auth_backend = get_client_auth_backend()
    auth_router = get_fastapi_users().get_auth_router(auth_backend)

    @auth_router.get("/me")
    async def get_me(user: User = Depends(get_authenticated_user)):
        # 查询用户角色
        roles = []
        if user.tenant_id:
            db_engine = get_relational_engine()
            async with db_engine.get_async_session() as session:
                result = await session.execute(text("""
                    SELECT r.name
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = :user_id
                    ORDER BY r.name
                """), {"user_id": user.id})
                roles = [row.name for row in result.fetchall()]
        
        # 生成access_token供WebSocket使用
        secret = os.getenv("FASTAPI_USERS_JWT_SECRET", "super_secret")
        token_data = {"user_id": str(user.id), "aud": "fastapi-users:auth"}
        access_token = generate_jwt(token_data, secret, 3600, algorithm="HS256")
        
        return {
            "id": str(user.id),
            "email": user.email,
            "name": user.email.split('@')[0],  # 使用邮箱前缀作为名称
            "picture": "",  # 暂时为空
            "is_superuser": user.is_superuser,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "roles": roles,
            "access_token": access_token,  # 添加token供前端存储
        }

    return auth_router
