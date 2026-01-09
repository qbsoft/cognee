import os
import re
import json
import uuid
from typing import Optional
from fastapi import Depends, Request, Response, HTTPException, status
from fastapi_users.exceptions import UserNotExists
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from contextlib import asynccontextmanager
from sqlalchemy import select

from .models import User
from .get_user_db import get_user_db
from .methods.get_user_by_email import get_user_by_email


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = os.getenv(
        "FASTAPI_USERS_RESET_PASSWORD_TOKEN_SECRET", "super_secret"
    )
    verification_token_secret = os.getenv("FASTAPI_USERS_VERIFICATION_TOKEN_SECRET", "super_secret")

    # async def get(self, id: models.ID) -> models.UP:
    #     """
    #     Get a user by id.

    #     :param id: Id. of the user to retrieve.
    #     :raises UserNotExists: The user does not exist.
    #     :return: A user.
    #     """
    #     user = await get_user(id)

    #     if user is None:
    #         raise UserNotExists()

    #     return user

    async def get_by_email(self, user_email: str) -> Optional[User]:
        user = await get_user_by_email(user_email)

        if user is None:
            raise UserNotExists()

        return user

    async def on_after_login(
        self, user: User, request: Optional[Request] = None, response: Optional[Response] = None
    ):
        access_token_cookie = response.headers.get("Set-Cookie")
        match = re.search(
            r"(?i)\bSet-Cookie:\s*([^=]+)=([^;]+)", f"Set-Cookie: {access_token_cookie}"
        )
        if match:
            access_token = match.group(2)
            response.status_code = 200
            response.body = json.dumps(
                {"access_token": access_token, "token_type": "bearer"}
            ).encode(encoding="utf-8")
            response.headers.append("Content-Type", "application/json")

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        """
        用户注册后的钩子函数
        
        处理：
        1. 如果使用了邀请令牌，标记为已使用
        2. 根据租户编码或邀请令牌将用户加入租户
        3. 将用户分配为 "普通用户" 角色
        """
        print(f"User {user.id} has registered.")
        
        # 如果有 tenant_id，说明已经分配好了，不需要处理
        if user.tenant_id:
            return
        
        # 从请求中获取租户编码或邀请令牌（如果有）
        # 注：这些字段已经在 UserCreate 中定义，但不会被保存到数据库
        # 我们需要从 request body 中手动提取并处理
        
        # TODO: 如果需要，这里可以处理租户分配逻辑
        # 但由于 FastAPI Users 的限制，我们会在自定义的注册端点中处理

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


get_user_manager_context = asynccontextmanager(get_user_manager)
