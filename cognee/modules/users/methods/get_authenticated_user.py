import os
from typing import Optional
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Header
from ..models import User
from ..get_fastapi_users import get_fastapi_users
from .get_default_user import get_default_user
from cognee.shared.logging_utils import get_logger


logger = get_logger("get_authenticated_user")

# Check environment variable to determine authentication requirement
REQUIRE_AUTHENTICATION = (
    os.getenv("REQUIRE_AUTHENTICATION", "false").lower() == "true"
    or os.getenv("ENABLE_BACKEND_ACCESS_CONTROL", "false").lower() == "true"
)

fastapi_users = get_fastapi_users()

# Always make auth dependency optional to allow API Key fallback
_auth_dependency = fastapi_users.current_user(active=True, optional=True)


async def get_authenticated_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user: Optional[User] = Depends(_auth_dependency),
) -> User:
    """
    Get authenticated user with support for both Cookie/JWT and API Key authentication:
    
    Authentication priority:
    1. API Key (X-API-Key header) - if provided, ALWAYS try this first
    2. Cookie/JWT - standard session authentication
    3. Default user - if REQUIRE_AUTHENTICATION=false
    
    Environment behavior:
    - If REQUIRE_AUTHENTICATION=true: Enforces authentication (raises 401 if not authenticated)
    - If REQUIRE_AUTHENTICATION=false: Falls back to default user if not authenticated
    - 检查用户所属租户是否在有效期内

    Always returns a User object for consistent typing.
    """
    authenticated_user = None
    
    # Priority 1: API Key authentication (HIGHEST priority)
    # If X-API-Key header is provided, use it regardless of Cookie/JWT state
    if x_api_key:
        try:
            from .get_user_from_api_key import get_user_from_api_key
            # This will raise HTTPException if key is invalid
            authenticated_user = await get_user_from_api_key(x_api_key)
            # If we got here, API Key auth succeeded
        except HTTPException as e:
            # API Key authentication failed - re-raise the exception
            # Don't fall back to Cookie auth when API Key is explicitly provided but invalid
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in API Key authentication: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Internal error during API Key authentication"
            ) from e
    
    # Priority 2: Cookie/JWT authentication
    # Only use if API Key was not provided
    if authenticated_user is None and user is not None:
        authenticated_user = user
    
    # Priority 3: Default user (if authentication is optional)
    if authenticated_user is None:
        if REQUIRE_AUTHENTICATION:
            # Authentication is required but none succeeded
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Provide valid credentials or API Key.",
                headers={"WWW-Authenticate": "Bearer, APIKey"},
            )
        else:
            # Authentication is optional, use default user
            try:
                authenticated_user = await get_default_user()
            except Exception as e:
                # Convert any get_default_user failure into a proper HTTP 500 error
                logger.error(f"Failed to create default user: {str(e)}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to create default user: {str(e)}"
                ) from e
    
    # 检查用户租户是否过期
    if authenticated_user.tenant_id:
        from cognee.infrastructure.databases.relational import get_relational_engine
        from sqlalchemy import select
        from ..models import Tenant
        
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == authenticated_user.tenant_id)
            )
            tenant = result.scalars().first()
            
            if tenant and tenant.expires_at:
                # 检查租户是否过期
                now = datetime.now(timezone.utc)
                if tenant.expires_at < now:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Your tenant '{tenant.name}' has expired. Please contact your administrator."
                    )

    return authenticated_user
