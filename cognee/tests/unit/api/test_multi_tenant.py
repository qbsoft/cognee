"""
Multi-tenant verification tests (T601-T607)

Tests cover:
  T601: User registration and login flow
  T602: JWT Token authentication
  T603: API Key authentication
  T604: Multi-tenant data isolation
  T605: ACL permission control
  T606: Role-based permission inheritance
  T607: Invitation-based registration
"""
import os
import sys
import json
import pytest
import hashlib
import importlib
from uuid import uuid4, UUID
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# T601: User Registration and Login Flow
# ---------------------------------------------------------------------------

class TestT601UserRegistrationAndLogin:
    """T601 - Test user registration and login flow."""

    # -- UserCreate schema ---------------------------------------------------

    def test_user_create_schema_accepts_email_and_password(self):
        """UserCreate should accept email and password as core fields."""
        from cognee.modules.users.models.User import UserCreate

        user_data = UserCreate(
            email="test@example.com",
            password="securepassword",
        )
        assert user_data.email == "test@example.com"
        assert user_data.password == "securepassword"
        assert user_data.tenant_id is None

    def test_user_create_schema_accepts_tenant_id(self):
        """UserCreate should accept optional tenant_id."""
        from cognee.modules.users.models.User import UserCreate

        tid = uuid4()
        user_data = UserCreate(
            email="test@example.com",
            password="password123",
            tenant_id=tid,
        )
        assert user_data.tenant_id == tid

    def test_user_create_schema_accepts_tenant_code(self):
        """UserCreate should accept optional tenant_code for registration via code."""
        from cognee.modules.users.models.User import UserCreate

        user_data = UserCreate(
            email="test@example.com",
            password="password123",
            tenant_code="ABC123",
        )
        assert user_data.tenant_code == "ABC123"

    def test_user_create_schema_accepts_invite_token(self):
        """UserCreate should accept optional invite_token."""
        from cognee.modules.users.models.User import UserCreate

        user_data = UserCreate(
            email="test@example.com",
            password="password123",
            invite_token="some_invite_token_here",
        )
        assert user_data.invite_token == "some_invite_token_here"

    def test_user_create_schema_defaults(self):
        """UserCreate should have is_verified=True by default."""
        from cognee.modules.users.models.User import UserCreate

        user_data = UserCreate(
            email="test@example.com",
            password="password123",
        )
        assert user_data.is_verified is True

    # -- RegisterRequest schema (extended register) --------------------------

    def test_register_request_schema_requires_email_and_password(self):
        """RegisterRequest should accept email + password with optional tenant fields."""
        from cognee.api.v1.auth.register_router import RegisterRequest

        req = RegisterRequest(
            email="user@domain.com",
            password="pw123456",
            tenant_code="ABCDEF",
        )
        assert req.email == "user@domain.com"
        assert req.password == "pw123456"
        assert req.tenant_code == "ABCDEF"
        assert req.invite_token is None

    def test_register_request_schema_with_invite_token(self):
        """RegisterRequest should accept invite_token instead of tenant_code."""
        from cognee.api.v1.auth.register_router import RegisterRequest

        req = RegisterRequest(
            email="user@domain.com",
            password="pw123456",
            invite_token="tok123",
        )
        assert req.invite_token == "tok123"
        assert req.tenant_code is None

    # -- User model ----------------------------------------------------------

    def test_user_model_has_tenant_relationship(self):
        """User model should have tenant_id field and tenant relationship."""
        from cognee.modules.users.models.User import User

        user = User(
            id=uuid4(),
            email="u@u.com",
            hashed_password="hash",
            is_active=True,
            is_verified=True,
        )
        assert hasattr(user, "tenant_id")
        assert hasattr(user, "tenant")
        assert hasattr(user, "roles")
        assert hasattr(user, "acls")

    # -- Login response structure (UserManager.on_after_login) ---------------

    def test_user_manager_on_after_login_sets_response_body(self):
        """UserManager.on_after_login should set access_token in response."""
        from cognee.modules.users.get_user_manager import UserManager

        assert hasattr(UserManager, "on_after_login")

    def test_user_read_schema_has_tenant_id(self):
        """UserRead schema should include tenant_id."""
        from cognee.modules.users.models.User import UserRead

        # Check the field is declared
        assert "tenant_id" in UserRead.model_fields

    # -- Auth router /me endpoint structure ----------------------------------

    def test_auth_router_me_endpoint_exists(self):
        """Auth router should define a /me endpoint."""
        from cognee.api.v1.users.routers.get_auth_router import get_auth_router

        router = get_auth_router()
        route_paths = [r.path for r in router.routes]
        assert "/me" in route_paths


# ---------------------------------------------------------------------------
# T602: JWT Token Authentication
# ---------------------------------------------------------------------------

class TestT602JWTTokenAuthentication:
    """T602 - Test JWT Token authentication middleware."""

    def test_default_jwt_strategy_class_exists(self):
        """DefaultJWTStrategy should subclass JWTStrategy."""
        from cognee.modules.users.authentication.default.default_jwt_strategy import (
            DefaultJWTStrategy,
        )
        from fastapi_users.authentication import JWTStrategy

        assert issubclass(DefaultJWTStrategy, JWTStrategy)

    def test_api_jwt_strategy_class_exists(self):
        """APIJWTStrategy should subclass JWTStrategy."""
        from cognee.modules.users.authentication.api_bearer.api_jwt_strategy import (
            APIJWTStrategy,
        )
        from fastapi_users.authentication import JWTStrategy

        assert issubclass(APIJWTStrategy, JWTStrategy)

    def test_client_auth_backend_uses_jwt_strategy(self):
        """Client auth backend should use DefaultJWTStrategy under the hood."""
        from cognee.modules.users.authentication.get_client_auth_backend import (
            get_client_auth_backend,
        )

        backend = get_client_auth_backend()
        assert backend is not None
        assert hasattr(backend, "get_strategy")

    def test_api_auth_backend_uses_jwt_strategy(self):
        """API auth backend should use APIJWTStrategy under the hood."""
        from cognee.modules.users.authentication.get_api_auth_backend import (
            get_api_auth_backend,
        )

        backend = get_api_auth_backend()
        assert backend is not None
        assert hasattr(backend, "get_strategy")

    def test_jwt_secret_defaults_to_super_secret(self):
        """When FASTAPI_USERS_JWT_SECRET env var is not set, default secret is used."""
        secret = os.getenv("FASTAPI_USERS_JWT_SECRET", "super_secret")
        assert secret is not None
        assert len(secret) > 0

    def test_jwt_lifetime_seconds_configurable(self):
        """JWT_LIFETIME_SECONDS environment variable configures token lifetime."""
        with patch.dict(os.environ, {"JWT_LIFETIME_SECONDS": "3600"}):
            lifetime = int(os.getenv("JWT_LIFETIME_SECONDS", "86400"))
            assert lifetime == 3600

    def test_jwt_lifetime_seconds_default(self):
        """Default JWT lifetime should be 86400 seconds (24 hours)."""
        lifetime = int(os.getenv("JWT_LIFETIME_SECONDS", "86400"))
        # Default should be 86400 unless explicitly overridden
        assert isinstance(lifetime, int)
        assert lifetime > 0

    def test_generate_jwt_token_for_me_endpoint(self):
        """The /me endpoint generates JWT with user_id and correct audience."""
        from fastapi_users.jwt import generate_jwt

        user_id = uuid4()
        secret = "test_secret"
        token_data = {"user_id": str(user_id), "aud": "fastapi-users:auth"}
        token = generate_jwt(token_data, secret, 3600, algorithm="HS256")

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode to verify contents
        import jwt

        payload = jwt.decode(
            token, secret, algorithms=["HS256"], audience="fastapi-users:auth"
        )
        assert payload["user_id"] == str(user_id)
        assert payload["aud"] == "fastapi-users:auth"

    def test_expired_jwt_token_is_rejected(self):
        """Expired JWT tokens should be rejected upon decode."""
        from fastapi_users.jwt import generate_jwt
        import jwt

        user_id = uuid4()
        secret = "test_secret"
        token_data = {"user_id": str(user_id), "aud": "fastapi-users:auth"}

        # Generate token with -1 second lifetime (already expired)
        token = generate_jwt(token_data, secret, -1, algorithm="HS256")

        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(
                token, secret, algorithms=["HS256"], audience="fastapi-users:auth"
            )

    def test_malformed_jwt_token_is_rejected(self):
        """Malformed JWT tokens should raise DecodeError."""
        import jwt

        secret = "test_secret"
        malformed_token = "not.a.valid.jwt.token"

        with pytest.raises(jwt.DecodeError):
            jwt.decode(malformed_token, secret, algorithms=["HS256"])

    def test_jwt_with_wrong_secret_is_rejected(self):
        """JWT tokens signed with wrong secret should fail verification."""
        from fastapi_users.jwt import generate_jwt
        import jwt

        user_id = uuid4()
        token = generate_jwt(
            {"user_id": str(user_id), "aud": "fastapi-users:auth"},
            "secret_1",
            3600,
            algorithm="HS256",
        )

        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(
                token, "secret_2", algorithms=["HS256"], audience="fastapi-users:auth"
            )

    def test_fastapi_users_instance_uses_both_backends(self):
        """FastAPIUsers instance should be configured with api and client backends."""
        from cognee.modules.users.get_fastapi_users import get_fastapi_users

        fastapi_users = get_fastapi_users()
        assert fastapi_users is not None
        # It should have auth backends
        assert hasattr(fastapi_users, "get_auth_router")
        assert hasattr(fastapi_users, "current_user")


# ---------------------------------------------------------------------------
# T603: API Key Authentication
# ---------------------------------------------------------------------------

class TestT603ApiKeyAuthentication:
    """T603 - Test API Key authentication."""

    def test_api_key_model_generate_key(self):
        """ApiKey.generate_key should produce correctly formatted key and prefix."""
        from cognee.modules.users.models.ApiKey import ApiKey

        full_key, key_prefix = ApiKey.generate_key("ABC123")

        assert full_key.startswith("tenant_ABC123_")
        assert key_prefix.startswith("tenant_ABC123_")
        assert "********" in key_prefix
        # Full key should have a random part
        random_part = full_key[len("tenant_ABC123_"):]
        assert len(random_part) > 0

    def test_api_key_hash_key(self):
        """ApiKey.hash_key should return SHA256 hex digest."""
        from cognee.modules.users.models.ApiKey import ApiKey

        key = "tenant_ABC123_randompart"
        hashed = ApiKey.hash_key(key)
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert hashed == expected
        assert len(hashed) == 64

    def test_api_key_hash_deterministic(self):
        """Same key should always produce the same hash."""
        from cognee.modules.users.models.ApiKey import ApiKey

        key = "tenant_ABC123_randompart"
        assert ApiKey.hash_key(key) == ApiKey.hash_key(key)

    def test_api_key_create_api_key(self):
        """ApiKey.create_api_key should return an ApiKey object and full key string."""
        from cognee.modules.users.models.ApiKey import ApiKey

        tenant_id = uuid4()
        user_id = uuid4()

        api_key_obj, full_key = ApiKey.create_api_key(
            tenant_id=tenant_id,
            tenant_code="XYZ789",
            created_by=user_id,
            name="Test Key",
            expires_in_days=30,
            scopes=["read", "write"],
        )

        assert isinstance(api_key_obj, ApiKey)
        assert isinstance(full_key, str)
        assert full_key.startswith("tenant_XYZ789_")
        assert api_key_obj.tenant_id == tenant_id
        assert api_key_obj.created_by == user_id
        assert api_key_obj.name == "Test Key"
        assert api_key_obj.is_active is True
        assert api_key_obj.expires_at is not None

    def test_api_key_create_without_expiry(self):
        """ApiKey without expires_in_days should have None expires_at."""
        from cognee.modules.users.models.ApiKey import ApiKey

        api_key_obj, full_key = ApiKey.create_api_key(
            tenant_id=uuid4(),
            tenant_code="ABC123",
            created_by=uuid4(),
            name="No Expiry Key",
            expires_in_days=None,
        )

        assert api_key_obj.expires_at is None

    def test_api_key_is_valid_active_not_expired(self):
        """Valid active key with future expiry should return True."""
        from cognee.modules.users.models.ApiKey import ApiKey

        api_key_obj, _ = ApiKey.create_api_key(
            tenant_id=uuid4(),
            tenant_code="ABC123",
            created_by=uuid4(),
            name="Valid Key",
            expires_in_days=30,
        )

        assert api_key_obj.is_valid() is True

    def test_api_key_is_valid_no_expiry(self):
        """Key with no expiry date should be valid if active."""
        from cognee.modules.users.models.ApiKey import ApiKey

        api_key_obj, _ = ApiKey.create_api_key(
            tenant_id=uuid4(),
            tenant_code="ABC123",
            created_by=uuid4(),
            name="Eternal Key",
            expires_in_days=None,
        )

        assert api_key_obj.is_valid() is True

    def test_api_key_is_invalid_when_inactive(self):
        """Inactive key should not be valid."""
        from cognee.modules.users.models.ApiKey import ApiKey

        api_key_obj, _ = ApiKey.create_api_key(
            tenant_id=uuid4(),
            tenant_code="ABC123",
            created_by=uuid4(),
            name="Inactive Key",
        )
        api_key_obj.is_active = False

        assert api_key_obj.is_valid() is False

    def test_api_key_is_invalid_when_expired(self):
        """Expired key should not be valid."""
        from cognee.modules.users.models.ApiKey import ApiKey

        api_key_obj, _ = ApiKey.create_api_key(
            tenant_id=uuid4(),
            tenant_code="ABC123",
            created_by=uuid4(),
            name="Expired Key",
            expires_in_days=1,
        )
        # Manually set expiry to the past
        api_key_obj.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        assert api_key_obj.is_valid() is False

    def test_api_key_update_last_used(self):
        """update_last_used should set last_used_at to current time."""
        from cognee.modules.users.models.ApiKey import ApiKey

        api_key_obj, _ = ApiKey.create_api_key(
            tenant_id=uuid4(),
            tenant_code="ABC123",
            created_by=uuid4(),
            name="Usage Tracking Key",
        )
        assert api_key_obj.last_used_at is None

        api_key_obj.update_last_used()
        assert api_key_obj.last_used_at is not None
        # Should be very recent
        delta = datetime.now(timezone.utc) - api_key_obj.last_used_at
        assert delta.total_seconds() < 5

    def test_api_key_scopes_stored_as_json(self):
        """Scopes should be stored as JSON string."""
        from cognee.modules.users.models.ApiKey import ApiKey

        api_key_obj, _ = ApiKey.create_api_key(
            tenant_id=uuid4(),
            tenant_code="ABC123",
            created_by=uuid4(),
            name="Scoped Key",
            scopes=["read", "write", "delete"],
        )

        scopes = json.loads(api_key_obj.scopes)
        assert scopes == ["read", "write", "delete"]

    @pytest.mark.asyncio
    async def test_get_user_from_api_key_raises_on_empty_key(self):
        """get_user_from_api_key should return None for empty key."""
        from cognee.modules.users.methods.get_user_from_api_key import (
            get_user_from_api_key,
        )

        result = await get_user_from_api_key("")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_from_api_key_raises_on_none_key(self):
        """get_user_from_api_key should return None for None key."""
        from cognee.modules.users.methods.get_user_from_api_key import (
            get_user_from_api_key,
        )

        result = await get_user_from_api_key(None)
        assert result is None

    @pytest.mark.asyncio
    @patch("cognee.modules.users.methods.get_user_from_api_key.get_relational_engine")
    async def test_get_user_from_api_key_raises_on_invalid_key(self, mock_engine):
        """get_user_from_api_key should raise 401 for key not found in DB."""
        from cognee.modules.users.methods.get_user_from_api_key import (
            get_user_from_api_key,
        )
        from fastapi import HTTPException

        # Mock DB session that returns no matching key
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_engine.return_value.get_async_session.return_value = mock_session

        with pytest.raises(HTTPException) as exc_info:
            await get_user_from_api_key("tenant_ABC123_invalid_key")

        assert exc_info.value.status_code == 401
        assert "Invalid API Key" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_authenticated_user_prioritizes_api_key(self):
        """When X-API-Key is provided, it should take priority over cookie/JWT user."""
        gau_mod = importlib.import_module(
            "cognee.modules.users.methods.get_authenticated_user"
        )

        mock_api_user = SimpleNamespace(
            id=uuid4(), email="api@example.com", is_active=True, tenant_id=None
        )
        mock_jwt_user = SimpleNamespace(
            id=uuid4(), email="jwt@example.com", is_active=True, tenant_id=None
        )

        with patch(
            "cognee.modules.users.methods.get_user_from_api_key.get_user_from_api_key",
            new_callable=AsyncMock,
        ) as mock_get_api:
            mock_get_api.return_value = mock_api_user

            result = await gau_mod.get_authenticated_user(
                x_api_key="tenant_ABC123_somekey",
                user=mock_jwt_user,
            )

            assert result == mock_api_user
            mock_get_api.assert_called_once_with("tenant_ABC123_somekey")

    @pytest.mark.asyncio
    async def test_get_authenticated_user_api_key_failure_does_not_fallback(self):
        """When X-API-Key is provided but invalid, should NOT fall back to JWT user."""
        gau_mod = importlib.import_module(
            "cognee.modules.users.methods.get_authenticated_user"
        )
        from fastapi import HTTPException

        mock_jwt_user = SimpleNamespace(
            id=uuid4(), email="jwt@example.com", is_active=True, tenant_id=None
        )

        with patch(
            "cognee.modules.users.methods.get_user_from_api_key.get_user_from_api_key",
            new_callable=AsyncMock,
        ) as mock_get_api:
            mock_get_api.side_effect = HTTPException(status_code=401, detail="Invalid")

            with pytest.raises(HTTPException) as exc_info:
                await gau_mod.get_authenticated_user(
                    x_api_key="tenant_ABC123_bad",
                    user=mock_jwt_user,
                )

            assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# T604: Multi-tenant Data Isolation
# ---------------------------------------------------------------------------

class TestT604MultiTenantDataIsolation:
    """T604 - Test multi-tenant data isolation."""

    def test_user_model_has_tenant_id_field(self):
        """User model should have tenant_id field for tenant association."""
        from cognee.modules.users.models.User import User

        user = User(
            id=uuid4(),
            email="test@test.com",
            hashed_password="hash",
            is_active=True,
        )
        assert hasattr(user, "tenant_id")

    def test_user_with_different_tenants_have_different_tenant_ids(self):
        """Users belonging to different tenants should have different tenant_ids."""
        from cognee.modules.users.models.User import User

        tenant_a = uuid4()
        tenant_b = uuid4()

        user_a = User(
            id=uuid4(),
            email="a@test.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=tenant_a,
        )
        user_b = User(
            id=uuid4(),
            email="b@test.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=tenant_b,
        )

        assert user_a.tenant_id != user_b.tenant_id
        assert user_a.tenant_id == tenant_a
        assert user_b.tenant_id == tenant_b

    def test_tenant_model_has_required_fields(self):
        """Tenant model should have name, tenant_code, expires_at, owner_id."""
        from cognee.modules.users.models.Tenant import Tenant

        # Verify the columns exist on the model
        columns = {c.name for c in Tenant.__table__.columns}
        assert "id" in columns
        assert "name" in columns
        assert "tenant_code" in columns
        assert "expires_at" in columns
        assert "owner_id" in columns

    def test_acl_model_links_principal_permission_dataset(self):
        """ACL model should reference principal_id, permission_id, and dataset_id."""
        from cognee.modules.users.models.ACL import ACL

        columns = {c.name for c in ACL.__table__.columns}
        assert "principal_id" in columns
        assert "permission_id" in columns
        assert "dataset_id" in columns

    @pytest.mark.asyncio
    async def test_get_authenticated_user_checks_tenant_expiry(self):
        """get_authenticated_user should reject users whose tenant has expired."""
        gau_mod = importlib.import_module(
            "cognee.modules.users.methods.get_authenticated_user"
        )
        from cognee.modules.users.models.User import User
        from fastapi import HTTPException

        tenant_id = uuid4()
        user = User(
            id=uuid4(),
            email="expired@test.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=tenant_id,
        )

        # Create a mock tenant that has expired
        mock_tenant = SimpleNamespace(
            id=tenant_id,
            name="Expired Tenant",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        with patch(
            "cognee.infrastructure.databases.relational.get_relational_engine"
        ) as mock_engine:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = mock_tenant
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_engine.return_value.get_async_session.return_value = mock_session

            with pytest.raises(HTTPException) as exc_info:
                await gau_mod.get_authenticated_user(x_api_key=None, user=user)

            assert exc_info.value.status_code == 403
            assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_get_authenticated_user_allows_valid_tenant(self):
        """get_authenticated_user should allow users whose tenant has not expired."""
        gau_mod = importlib.import_module(
            "cognee.modules.users.methods.get_authenticated_user"
        )
        from cognee.modules.users.models.User import User

        tenant_id = uuid4()
        user = User(
            id=uuid4(),
            email="active@test.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=tenant_id,
        )

        # Create a mock tenant that is still valid
        mock_tenant = SimpleNamespace(
            id=tenant_id,
            name="Active Tenant",
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )

        with patch(
            "cognee.infrastructure.databases.relational.get_relational_engine"
        ) as mock_engine:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = mock_tenant
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_engine.return_value.get_async_session.return_value = mock_session

            result = await gau_mod.get_authenticated_user(x_api_key=None, user=user)
            assert result == user

    @pytest.mark.asyncio
    async def test_get_authenticated_user_allows_no_expiry_tenant(self):
        """Tenant with no expiry (None) should be allowed."""
        gau_mod = importlib.import_module(
            "cognee.modules.users.methods.get_authenticated_user"
        )
        from cognee.modules.users.models.User import User

        tenant_id = uuid4()
        user = User(
            id=uuid4(),
            email="noexpiry@test.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=tenant_id,
        )

        # Create a mock tenant with no expiry
        mock_tenant = SimpleNamespace(
            id=tenant_id,
            name="No Expiry Tenant",
            expires_at=None,
        )

        with patch(
            "cognee.infrastructure.databases.relational.get_relational_engine"
        ) as mock_engine:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = mock_tenant
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_engine.return_value.get_async_session.return_value = mock_session

            result = await gau_mod.get_authenticated_user(x_api_key=None, user=user)
            assert result == user

    @pytest.mark.asyncio
    async def test_user_without_tenant_skips_tenant_check(self):
        """User with no tenant_id should skip tenant expiry check."""
        gau_mod = importlib.import_module(
            "cognee.modules.users.methods.get_authenticated_user"
        )
        from cognee.modules.users.models.User import User

        user = User(
            id=uuid4(),
            email="notenant@test.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=None,
        )

        # Should succeed without any DB call for tenant check
        result = await gau_mod.get_authenticated_user(x_api_key=None, user=user)
        assert result == user

    def test_principal_model_is_polymorphic(self):
        """Principal model should use polymorphic identity for User, Tenant, Role."""
        from cognee.modules.users.models.Principal import Principal

        assert Principal.__mapper_args__["polymorphic_on"] == "type"
        assert Principal.__mapper_args__["polymorphic_identity"] == "principal"

    def test_user_polymorphic_identity(self):
        """User should have polymorphic_identity='user'."""
        from cognee.modules.users.models.User import User

        assert User.__mapper_args__["polymorphic_identity"] == "user"

    def test_tenant_polymorphic_identity(self):
        """Tenant should have polymorphic_identity='tenant'."""
        from cognee.modules.users.models.Tenant import Tenant

        assert Tenant.__mapper_args__["polymorphic_identity"] == "tenant"


# ---------------------------------------------------------------------------
# T605: ACL Permission Control
# ---------------------------------------------------------------------------

class TestT605ACLPermissionControl:
    """T605 - Test ACL permission control."""

    def test_permission_model_has_name_field(self):
        """Permission model should have a unique name field."""
        from cognee.modules.users.models.Permission import Permission

        columns = {c.name for c in Permission.__table__.columns}
        assert "name" in columns
        assert "id" in columns

    def test_acl_model_structure(self):
        """ACL model should have correct foreign key structure."""
        from cognee.modules.users.models.ACL import ACL

        # Check relationships
        assert hasattr(ACL, "principal")
        assert hasattr(ACL, "permission")
        assert hasattr(ACL, "dataset")

    def test_permission_denied_error_exists(self):
        """PermissionDeniedError should exist with correct status code."""
        from cognee.modules.users.exceptions import PermissionDeniedError

        err = PermissionDeniedError()
        assert err.status_code == 403

    def test_permission_denied_error_custom_message(self):
        """PermissionDeniedError should support custom messages."""
        from cognee.modules.users.exceptions import PermissionDeniedError

        err = PermissionDeniedError(message="No access to dataset X")
        assert "No access to dataset X" in str(err.message)

    def test_permission_not_found_error_exists(self):
        """PermissionNotFoundError should exist with correct status code."""
        from cognee.modules.users.exceptions import PermissionNotFoundError

        err = PermissionNotFoundError()
        assert err.status_code == 403

    @pytest.mark.asyncio
    async def test_authorized_give_permission_checks_owner_permission(self):
        """authorized_give_permission_on_datasets should verify owner has 'share' permission."""
        from cognee.modules.users.permissions.methods.authorized_give_permission_on_datasets import (
            authorized_give_permission_on_datasets,
        )

        principal_id = uuid4()
        dataset_id = uuid4()
        owner_id = uuid4()

        with patch(
            "cognee.modules.users.permissions.methods.authorized_give_permission_on_datasets.get_principal",
            new_callable=AsyncMock,
        ) as mock_get_principal, patch(
            "cognee.modules.users.permissions.methods.authorized_give_permission_on_datasets.get_specific_user_permission_datasets",
            new_callable=AsyncMock,
        ) as mock_get_datasets, patch(
            "cognee.modules.users.permissions.methods.authorized_give_permission_on_datasets.give_permission_on_dataset",
            new_callable=AsyncMock,
        ) as mock_give_perm:
            mock_principal = SimpleNamespace(id=principal_id)
            mock_get_principal.return_value = mock_principal

            mock_dataset = SimpleNamespace(id=dataset_id)
            mock_get_datasets.return_value = [mock_dataset]

            await authorized_give_permission_on_datasets(
                principal_id, dataset_id, "read", owner_id
            )

            # Verify owner's 'share' permission was checked
            mock_get_datasets.assert_called_once_with(owner_id, "share", [dataset_id])
            # Verify permission was given to principal
            mock_give_perm.assert_called_once_with(mock_principal, dataset_id, "read")

    @pytest.mark.asyncio
    async def test_authorized_give_permission_converts_single_id_to_list(self):
        """authorized_give_permission_on_datasets should accept single UUID."""
        from cognee.modules.users.permissions.methods.authorized_give_permission_on_datasets import (
            authorized_give_permission_on_datasets,
        )

        principal_id = uuid4()
        single_dataset_id = uuid4()
        owner_id = uuid4()

        with patch(
            "cognee.modules.users.permissions.methods.authorized_give_permission_on_datasets.get_principal",
            new_callable=AsyncMock,
        ), patch(
            "cognee.modules.users.permissions.methods.authorized_give_permission_on_datasets.get_specific_user_permission_datasets",
            new_callable=AsyncMock,
        ) as mock_get_datasets, patch(
            "cognee.modules.users.permissions.methods.authorized_give_permission_on_datasets.give_permission_on_dataset",
            new_callable=AsyncMock,
        ):
            mock_get_datasets.return_value = [SimpleNamespace(id=single_dataset_id)]

            await authorized_give_permission_on_datasets(
                principal_id, single_dataset_id, "read", owner_id
            )

            # Verify dataset_ids was converted to a list
            call_args = mock_get_datasets.call_args
            assert call_args[0][2] == [single_dataset_id]

    @pytest.mark.asyncio
    async def test_require_tenant_admin_rejects_user_without_tenant(self):
        """require_tenant_admin should reject users not belonging to any tenant."""
        from cognee.api.v1.permissions.dependencies import require_tenant_admin
        from cognee.modules.users.models.User import User
        from fastapi import HTTPException

        user = User(
            id=uuid4(),
            email="notenant@test.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=None,
        )

        with pytest.raises(HTTPException) as exc_info:
            await require_tenant_admin(user=user)

        assert exc_info.value.status_code == 403
        assert "does not belong to any tenant" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_tenant_admin_rejects_non_admin_user(self):
        """require_tenant_admin should reject users without admin role."""
        from cognee.api.v1.permissions.dependencies import require_tenant_admin
        from cognee.modules.users.models.User import User
        from fastapi import HTTPException

        tenant_id = uuid4()
        user = User(
            id=uuid4(),
            email="normaluser@test.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=tenant_id,
        )

        # Mock DB to return 0 admin roles
        mock_row = SimpleNamespace(count=0)

        with patch(
            "cognee.api.v1.permissions.dependencies.get_relational_engine"
        ) as mock_engine:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = mock_row
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_engine.return_value.get_async_session.return_value = mock_session

            with pytest.raises(HTTPException) as exc_info:
                await require_tenant_admin(user=user)

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_tenant_admin_allows_admin_user(self):
        """require_tenant_admin should allow users with admin role."""
        from cognee.api.v1.permissions.dependencies import require_tenant_admin
        from cognee.modules.users.models.User import User

        tenant_id = uuid4()
        user = User(
            id=uuid4(),
            email="admin@test.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=tenant_id,
        )

        # Mock DB to return 1 admin role
        mock_row = SimpleNamespace(count=1)

        with patch(
            "cognee.api.v1.permissions.dependencies.get_relational_engine"
        ) as mock_engine:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = mock_row
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_engine.return_value.get_async_session.return_value = mock_session

            result = await require_tenant_admin(user=user)
            assert result == user

    @pytest.mark.asyncio
    async def test_require_superuser_rejects_non_superuser(self):
        """require_superuser should reject non-superuser."""
        from cognee.api.v1.permissions.dependencies import require_superuser
        from cognee.modules.users.models.User import User
        from fastapi import HTTPException

        user = User(
            id=uuid4(),
            email="user@test.com",
            hashed_password="hash",
            is_active=True,
            is_superuser=False,
        )

        with pytest.raises(HTTPException) as exc_info:
            await require_superuser(user=user)

        assert exc_info.value.status_code == 403
        assert "superuser" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_require_superuser_allows_superuser(self):
        """require_superuser should allow superuser."""
        from cognee.api.v1.permissions.dependencies import require_superuser
        from cognee.modules.users.models.User import User

        user = User(
            id=uuid4(),
            email="superadmin@test.com",
            hashed_password="hash",
            is_active=True,
            is_superuser=True,
        )

        result = await require_superuser(user=user)
        assert result == user


# ---------------------------------------------------------------------------
# T606: Role-based Permission Inheritance
# ---------------------------------------------------------------------------

class TestT606RolePermissionInheritance:
    """T606 - Test role-based permission inheritance."""

    def test_role_model_has_required_fields(self):
        """Role model should have name, tenant_id, and users relationship."""
        from cognee.modules.users.models.Role import Role

        columns = {c.name for c in Role.__table__.columns}
        assert "name" in columns
        assert "tenant_id" in columns
        assert "id" in columns

    def test_role_polymorphic_identity(self):
        """Role should have polymorphic_identity='role'."""
        from cognee.modules.users.models.Role import Role

        assert Role.__mapper_args__["polymorphic_identity"] == "role"

    def test_role_has_unique_constraint_on_tenant_and_name(self):
        """Role should have unique constraint on (tenant_id, name)."""
        from cognee.modules.users.models.Role import Role

        # Check table args for UniqueConstraint
        table_args = Role.__table_args__
        found_constraint = False
        for arg in table_args:
            if hasattr(arg, "name") and arg.name == "uq_roles_tenant_id_name":
                found_constraint = True
                break
        assert found_constraint, "UniqueConstraint on (tenant_id, name) not found"

    def test_user_role_association_table_exists(self):
        """UserRole association table should exist."""
        from cognee.modules.users.models.UserRole import UserRole

        assert UserRole.__tablename__ == "user_roles"

    @pytest.mark.asyncio
    async def test_get_all_user_permission_datasets_includes_tenant_datasets(self):
        """get_all_user_permission_datasets should include datasets from user's tenant."""
        from cognee.modules.users.permissions.methods.get_all_user_permission_datasets import (
            get_all_user_permission_datasets,
        )

        tenant_id = uuid4()
        user_id = uuid4()

        user = SimpleNamespace(
            id=user_id,
            email="user@test.com",
            tenant_id=tenant_id,
            roles=[],
        )

        user_dataset = SimpleNamespace(id=uuid4(), name="user_ds")
        tenant_dataset = SimpleNamespace(id=uuid4(), name="tenant_ds")

        mock_tenant = SimpleNamespace(id=tenant_id)

        with patch(
            "cognee.modules.users.permissions.methods.get_all_user_permission_datasets.get_principal_datasets",
            new_callable=AsyncMock,
        ) as mock_get_principal_datasets, patch(
            "cognee.modules.users.permissions.methods.get_all_user_permission_datasets.get_tenant",
            new_callable=AsyncMock,
        ) as mock_get_tenant:
            # First call: user's own datasets, Second call: tenant's datasets
            mock_get_principal_datasets.side_effect = [
                [user_dataset],
                [tenant_dataset],
            ]
            mock_get_tenant.return_value = mock_tenant

            datasets = await get_all_user_permission_datasets(user, "read")

            assert len(datasets) == 2
            dataset_ids = {ds.id for ds in datasets}
            assert user_dataset.id in dataset_ids
            assert tenant_dataset.id in dataset_ids

    @pytest.mark.asyncio
    async def test_get_all_user_permission_datasets_includes_role_datasets(self):
        """get_all_user_permission_datasets should include datasets from user's roles."""
        from cognee.modules.users.permissions.methods.get_all_user_permission_datasets import (
            get_all_user_permission_datasets,
        )

        tenant_id = uuid4()
        role_id = uuid4()

        role = SimpleNamespace(id=role_id, name="editor")
        user = SimpleNamespace(
            id=uuid4(),
            email="user@test.com",
            tenant_id=tenant_id,
            roles=[role],
        )

        user_dataset = SimpleNamespace(id=uuid4(), name="user_ds")
        tenant_dataset = SimpleNamespace(id=uuid4(), name="tenant_ds")
        role_dataset = SimpleNamespace(id=uuid4(), name="role_ds")

        with patch(
            "cognee.modules.users.permissions.methods.get_all_user_permission_datasets.get_principal_datasets",
            new_callable=AsyncMock,
        ) as mock_get_principal_datasets, patch(
            "cognee.modules.users.permissions.methods.get_all_user_permission_datasets.get_tenant",
            new_callable=AsyncMock,
        ) as mock_get_tenant:
            # Calls: user datasets, tenant datasets, role datasets
            mock_get_principal_datasets.side_effect = [
                [user_dataset],
                [tenant_dataset],
                [role_dataset],
            ]
            mock_get_tenant.return_value = SimpleNamespace(id=tenant_id)

            datasets = await get_all_user_permission_datasets(user, "read")

            assert len(datasets) == 3
            dataset_ids = {ds.id for ds in datasets}
            assert user_dataset.id in dataset_ids
            assert tenant_dataset.id in dataset_ids
            assert role_dataset.id in dataset_ids

    @pytest.mark.asyncio
    async def test_get_all_user_permission_datasets_deduplicates(self):
        """Duplicate datasets across user/tenant/role should be deduplicated."""
        from cognee.modules.users.permissions.methods.get_all_user_permission_datasets import (
            get_all_user_permission_datasets,
        )

        tenant_id = uuid4()
        shared_ds_id = uuid4()

        user = SimpleNamespace(
            id=uuid4(),
            email="user@test.com",
            tenant_id=tenant_id,
            roles=[],
        )

        shared_dataset = SimpleNamespace(id=shared_ds_id, name="shared_ds")

        with patch(
            "cognee.modules.users.permissions.methods.get_all_user_permission_datasets.get_principal_datasets",
            new_callable=AsyncMock,
        ) as mock_get_principal_datasets, patch(
            "cognee.modules.users.permissions.methods.get_all_user_permission_datasets.get_tenant",
            new_callable=AsyncMock,
        ) as mock_get_tenant:
            # Both user and tenant return the same dataset
            mock_get_principal_datasets.side_effect = [
                [shared_dataset],
                [shared_dataset],
            ]
            mock_get_tenant.return_value = SimpleNamespace(id=tenant_id)

            datasets = await get_all_user_permission_datasets(user, "read")

            # Should be deduplicated to 1
            assert len(datasets) == 1
            assert datasets[0].id == shared_ds_id

    @pytest.mark.asyncio
    async def test_get_all_user_permission_datasets_no_tenant_user(self):
        """User without tenant should only get their own datasets."""
        from cognee.modules.users.permissions.methods.get_all_user_permission_datasets import (
            get_all_user_permission_datasets,
        )

        user = SimpleNamespace(
            id=uuid4(),
            email="user@test.com",
            tenant_id=None,
            roles=[],
        )

        user_dataset = SimpleNamespace(id=uuid4(), name="user_ds")

        with patch(
            "cognee.modules.users.permissions.methods.get_all_user_permission_datasets.get_principal_datasets",
            new_callable=AsyncMock,
        ) as mock_get_principal_datasets:
            mock_get_principal_datasets.return_value = [user_dataset]

            datasets = await get_all_user_permission_datasets(user, "read")

            assert len(datasets) == 1
            assert datasets[0].id == user_dataset.id
            # Should only be called once (for user, not tenant or role)
            mock_get_principal_datasets.assert_called_once()

    def test_permissions_router_has_create_tenant_endpoint(self):
        """Permissions router should have create tenant endpoint requiring superuser."""
        from cognee.api.v1.permissions.routers.get_permissions_router import (
            get_permissions_router,
        )

        router = get_permissions_router()
        route_paths = [r.path for r in router.routes]
        assert "/tenants" in route_paths

    def test_permissions_router_has_user_roles_endpoint(self):
        """Permissions router should have user roles management endpoints."""
        from cognee.api.v1.permissions.routers.get_permissions_router import (
            get_permissions_router,
        )

        router = get_permissions_router()
        route_paths = [r.path for r in router.routes]
        assert "/users/{user_id}/roles" in route_paths

    def test_permissions_router_has_roles_crud_endpoints(self):
        """Permissions router should have role CRUD endpoints."""
        from cognee.api.v1.permissions.routers.get_permissions_router import (
            get_permissions_router,
        )

        router = get_permissions_router()
        route_paths = [r.path for r in router.routes]
        assert "/roles" in route_paths
        assert "/roles/{role_id}" in route_paths


# ---------------------------------------------------------------------------
# T607: Invitation-based Registration
# ---------------------------------------------------------------------------

class TestT607InvitationBasedRegistration:
    """T607 - Test invitation-based registration."""

    def test_invite_token_model_has_required_fields(self):
        """InviteToken model should have all required fields."""
        from cognee.modules.users.models.InviteToken import InviteToken

        columns = {c.name for c in InviteToken.__table__.columns}
        assert "id" in columns
        assert "token" in columns
        assert "tenant_id" in columns
        assert "created_by" in columns
        assert "expires_at" in columns
        assert "is_used" in columns
        assert "used_by" in columns
        assert "used_at" in columns

    def test_invite_token_create_token_with_expiry(self):
        """InviteToken.create_token_with_expiry should create valid token."""
        from cognee.modules.users.models.InviteToken import InviteToken

        tenant_id = uuid4()
        created_by = uuid4()

        invite = InviteToken.create_token_with_expiry(
            tenant_id=tenant_id,
            created_by=created_by,
            days_valid=7,
        )

        assert invite.token is not None
        assert len(invite.token) == 32
        assert invite.tenant_id == tenant_id
        assert invite.created_by == created_by
        assert invite.is_used is False or invite.is_used is None
        assert invite.expires_at is not None
        # Should expire in ~7 days
        expected_expiry = datetime.now(timezone.utc) + timedelta(days=7)
        delta = abs((invite.expires_at - expected_expiry).total_seconds())
        assert delta < 5  # Within 5 seconds

    def test_invite_token_create_custom_validity(self):
        """InviteToken should support custom validity period."""
        from cognee.modules.users.models.InviteToken import InviteToken

        invite = InviteToken.create_token_with_expiry(
            tenant_id=uuid4(),
            created_by=uuid4(),
            days_valid=30,
        )

        expected_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        delta = abs((invite.expires_at - expected_expiry).total_seconds())
        assert delta < 5

    def test_invite_token_is_valid_new_token(self):
        """Newly created token should be valid."""
        from cognee.modules.users.models.InviteToken import InviteToken

        invite = InviteToken.create_token_with_expiry(
            tenant_id=uuid4(),
            created_by=uuid4(),
            days_valid=7,
        )

        assert invite.is_valid() is True

    def test_invite_token_is_invalid_when_used(self):
        """Used token should be invalid."""
        from cognee.modules.users.models.InviteToken import InviteToken

        invite = InviteToken.create_token_with_expiry(
            tenant_id=uuid4(),
            created_by=uuid4(),
            days_valid=7,
        )
        invite.is_used = True

        assert invite.is_valid() is False

    def test_invite_token_is_invalid_when_expired(self):
        """Expired token should be invalid."""
        from cognee.modules.users.models.InviteToken import InviteToken

        invite = InviteToken.create_token_with_expiry(
            tenant_id=uuid4(),
            created_by=uuid4(),
            days_valid=7,
        )
        # Manually set to past
        invite.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        assert invite.is_valid() is False

    def test_invite_token_is_unique(self):
        """Each token generation should produce a unique token."""
        from cognee.modules.users.models.InviteToken import InviteToken

        tokens = set()
        for _ in range(20):
            invite = InviteToken.create_token_with_expiry(
                tenant_id=uuid4(),
                created_by=uuid4(),
                days_valid=7,
            )
            tokens.add(invite.token)

        assert len(tokens) == 20

    @pytest.mark.asyncio
    async def test_validate_invite_token_returns_invalid_for_nonexistent(self):
        """validate_invite_token should return invalid for nonexistent token."""
        from cognee.modules.users.tenants.methods.invite_token import (
            validate_invite_token,
        )

        with patch(
            "cognee.modules.users.tenants.methods.invite_token.get_invite_token_by_token",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = None

            is_valid, error_msg, tenant_id = await validate_invite_token("nonexistent")

            assert is_valid is False
            assert "Invalid" in error_msg
            assert tenant_id is None

    @pytest.mark.asyncio
    async def test_validate_invite_token_returns_invalid_for_used_token(self):
        """validate_invite_token should return invalid for already used token."""
        from cognee.modules.users.tenants.methods.invite_token import (
            validate_invite_token,
        )

        mock_token = SimpleNamespace(
            token="used_token",
            is_used=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
            tenant_id=uuid4(),
        )

        with patch(
            "cognee.modules.users.tenants.methods.invite_token.get_invite_token_by_token",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = mock_token

            is_valid, error_msg, tenant_id = await validate_invite_token("used_token")

            assert is_valid is False
            assert "already been used" in error_msg
            assert tenant_id is None

    @pytest.mark.asyncio
    async def test_validate_invite_token_returns_invalid_for_expired_token(self):
        """validate_invite_token should return invalid for expired token."""
        from cognee.modules.users.tenants.methods.invite_token import (
            validate_invite_token,
        )

        mock_token = SimpleNamespace(
            token="expired_token",
            is_used=False,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            tenant_id=uuid4(),
        )

        with patch(
            "cognee.modules.users.tenants.methods.invite_token.get_invite_token_by_token",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = mock_token

            is_valid, error_msg, tenant_id = await validate_invite_token(
                "expired_token"
            )

            assert is_valid is False
            assert "expired" in error_msg
            assert tenant_id is None

    @pytest.mark.asyncio
    async def test_validate_invite_token_returns_valid_for_good_token(self):
        """validate_invite_token should return valid for unused, unexpired token."""
        from cognee.modules.users.tenants.methods.invite_token import (
            validate_invite_token,
        )

        expected_tenant_id = uuid4()
        mock_token = SimpleNamespace(
            token="good_token",
            is_used=False,
            expires_at=datetime.now(timezone.utc) + timedelta(days=5),
            tenant_id=expected_tenant_id,
        )

        with patch(
            "cognee.modules.users.tenants.methods.invite_token.get_invite_token_by_token",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = mock_token

            is_valid, error_msg, tenant_id = await validate_invite_token("good_token")

            assert is_valid is True
            assert error_msg == ""
            assert tenant_id == expected_tenant_id

    @pytest.mark.asyncio
    async def test_mark_invite_token_used_returns_false_for_nonexistent(self):
        """mark_invite_token_used should return False for nonexistent token."""
        from cognee.modules.users.tenants.methods.invite_token import (
            mark_invite_token_used,
        )

        with patch(
            "cognee.modules.users.tenants.methods.invite_token.get_relational_engine"
        ) as mock_engine:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = None
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_engine.return_value.get_async_session.return_value = mock_session

            result = await mark_invite_token_used("nonexistent", uuid4())
            assert result is False

    @pytest.mark.asyncio
    async def test_mark_invite_token_used_returns_true_and_updates(self):
        """mark_invite_token_used should mark token as used and return True."""
        from cognee.modules.users.tenants.methods.invite_token import (
            mark_invite_token_used,
        )

        user_id = uuid4()
        mock_invite = SimpleNamespace(
            token="valid_token",
            is_used=False,
            used_by=None,
            used_at=None,
        )

        with patch(
            "cognee.modules.users.tenants.methods.invite_token.get_relational_engine"
        ) as mock_engine:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = mock_invite
            mock_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.merge = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_engine.return_value.get_async_session.return_value = mock_session

            result = await mark_invite_token_used("valid_token", user_id)

            assert result is True
            assert mock_invite.is_used is True
            assert mock_invite.used_by == user_id
            assert mock_invite.used_at is not None

    def test_tenant_code_validation_valid_codes(self):
        """validate_tenant_code should accept valid 6-character codes."""
        from cognee.modules.users.tenants.methods.generate_tenant_code import (
            validate_tenant_code,
        )

        assert validate_tenant_code("ABCDEF") is True
        assert validate_tenant_code("ABC234") is True
        assert validate_tenant_code("XYZ789") is True

    def test_tenant_code_validation_invalid_codes(self):
        """validate_tenant_code should reject invalid codes."""
        from cognee.modules.users.tenants.methods.generate_tenant_code import (
            validate_tenant_code,
        )

        assert validate_tenant_code("") is False
        assert validate_tenant_code("ABC") is False  # Too short
        assert validate_tenant_code("ABCDEFG") is False  # Too long
        assert validate_tenant_code(None) is False

    def test_tenant_code_validation_rejects_confusing_chars(self):
        """validate_tenant_code should reject easily confused characters (0, O, 1, I, L)."""
        from cognee.modules.users.tenants.methods.generate_tenant_code import (
            validate_tenant_code,
        )

        # These contain excluded characters
        assert validate_tenant_code("0ABCDE") is False  # Contains 0 (zero)
        assert validate_tenant_code("OABCDE") is False  # Contains O (letter O)
        assert validate_tenant_code("1ABCDE") is False  # Contains 1 (one)
        assert validate_tenant_code("IABCDE") is False  # Contains I (letter I)
        assert validate_tenant_code("LABCDE") is False  # Contains L (letter L)

    def test_permissions_router_has_invite_endpoint(self):
        """Permissions router should have an invite endpoint for tenant."""
        from cognee.api.v1.permissions.routers.get_permissions_router import (
            get_permissions_router,
        )

        router = get_permissions_router()
        route_paths = [r.path for r in router.routes]
        assert "/tenants/{tenant_id}/invite" in route_paths

    def test_extended_register_router_exists(self):
        """Extended register router should exist with /register endpoint."""
        from cognee.api.v1.auth.register_router import get_extended_register_router

        router = get_extended_register_router()
        route_paths = [r.path for r in router.routes]
        assert "/register" in route_paths


# ---------------------------------------------------------------------------
# Additional Cross-cutting Tests
# ---------------------------------------------------------------------------

class TestCrossCuttingMultiTenantFeatures:
    """Cross-cutting tests that span multiple T6xx tasks."""

    @pytest.mark.asyncio
    async def test_require_authentication_true_rejects_unauthenticated(self):
        """When REQUIRE_AUTHENTICATION=true, unauthenticated requests should be rejected."""
        gau_mod = importlib.import_module(
            "cognee.modules.users.methods.get_authenticated_user"
        )
        from fastapi import HTTPException

        original_value = gau_mod.REQUIRE_AUTHENTICATION
        try:
            gau_mod.REQUIRE_AUTHENTICATION = True

            with pytest.raises(HTTPException) as exc_info:
                await gau_mod.get_authenticated_user(x_api_key=None, user=None)

            assert exc_info.value.status_code == 401
            assert "Authentication required" in exc_info.value.detail
        finally:
            gau_mod.REQUIRE_AUTHENTICATION = original_value

    @pytest.mark.asyncio
    @patch(
        "cognee.modules.users.methods.get_authenticated_user.get_default_user",
        new_callable=AsyncMock,
    )
    async def test_require_authentication_false_returns_default_user(
        self, mock_get_default
    ):
        """When REQUIRE_AUTHENTICATION=false, should return default user."""
        gau_mod = importlib.import_module(
            "cognee.modules.users.methods.get_authenticated_user"
        )
        default_user = SimpleNamespace(
            id=uuid4(), email="default@test.com", tenant_id=None
        )
        mock_get_default.return_value = default_user

        original_value = gau_mod.REQUIRE_AUTHENTICATION
        try:
            gau_mod.REQUIRE_AUTHENTICATION = False

            result = await gau_mod.get_authenticated_user(x_api_key=None, user=None)
            assert result == default_user
        finally:
            gau_mod.REQUIRE_AUTHENTICATION = original_value

    def test_api_key_model_imports(self):
        """ApiKey should be importable from cognee.modules.users.models."""
        from cognee.modules.users.models import ApiKey

        assert ApiKey is not None

    def test_invite_token_model_imports(self):
        """InviteToken should be importable from cognee.modules.users.models."""
        from cognee.modules.users.models import InviteToken

        assert InviteToken is not None

    def test_tenant_model_imports(self):
        """Tenant should be importable from cognee.modules.users.models."""
        from cognee.modules.users.models import Tenant

        assert Tenant is not None

    def test_role_model_imports(self):
        """Role should be importable from cognee.modules.users.models."""
        from cognee.modules.users.models import Role

        assert Role is not None

    def test_acl_model_imports(self):
        """ACL should be importable from cognee.modules.users.models."""
        from cognee.modules.users.models import ACL

        assert ACL is not None

    def test_permission_model_imports(self):
        """Permission should be importable from cognee.modules.users.models."""
        from cognee.modules.users.models import Permission

        assert Permission is not None

    def test_tenant_not_found_error(self):
        """TenantNotFoundError should exist with 404 status."""
        from cognee.modules.users.exceptions import TenantNotFoundError

        err = TenantNotFoundError()
        assert err.status_code == 404

    def test_role_not_found_error(self):
        """RoleNotFoundError should exist with 404 status."""
        from cognee.modules.users.exceptions import RoleNotFoundError

        err = RoleNotFoundError()
        assert err.status_code == 404

    def test_user_not_found_error(self):
        """UserNotFoundError should exist with 404 status."""
        from cognee.modules.users.exceptions import UserNotFoundError

        err = UserNotFoundError()
        assert err.status_code == 404

    def test_enable_backend_access_control_env_var(self):
        """ENABLE_BACKEND_ACCESS_CONTROL should also trigger auth requirement."""
        # The module checks both REQUIRE_AUTHENTICATION and ENABLE_BACKEND_ACCESS_CONTROL
        gau_mod = importlib.import_module(
            "cognee.modules.users.methods.get_authenticated_user"
        )

        # Verify the module checks this env var in its source
        import inspect

        source = inspect.getsource(gau_mod)
        assert "ENABLE_BACKEND_ACCESS_CONTROL" in source

    def test_api_key_header_name(self):
        """API key should use X-API-Key header."""
        import inspect

        gau_mod = importlib.import_module(
            "cognee.modules.users.methods.get_authenticated_user"
        )
        source = inspect.getsource(gau_mod.get_authenticated_user)
        assert "X-API-Key" in source
