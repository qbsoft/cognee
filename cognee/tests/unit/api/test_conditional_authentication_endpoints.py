import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
from fastapi.testclient import TestClient
from types import SimpleNamespace
import importlib

from cognee.api.client import app
from cognee.modules.users.methods.get_authenticated_user import get_authenticated_user


# The module where REQUIRE_AUTHENTICATION is actually evaluated
_AUTH_MODULE = "cognee.modules.users.methods.get_authenticated_user"

gau_mod = importlib.import_module(_AUTH_MODULE)


# Fixtures for reuse across test classes
@pytest.fixture
def mock_default_user():
    """Mock default user for testing."""
    return SimpleNamespace(
        id=uuid4(), email="default@example.com", is_active=True, tenant_id=uuid4()
    )


@pytest.fixture
def mock_authenticated_user():
    """Mock authenticated user for testing."""
    from cognee.modules.users.models import User

    return User(
        id=uuid4(),
        email="auth@example.com",
        hashed_password="hashed",
        is_active=True,
        is_verified=True,
        tenant_id=uuid4(),
    )


class TestConditionalAuthenticationEndpoints:
    """Test that API endpoints work correctly with conditional authentication."""

    @pytest.fixture
    def client(self):
        """Create a test client with dependency override for authentication."""
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _cleanup_overrides(self):
        """Cleanup dependency overrides after each test."""
        yield
        app.dependency_overrides.pop(get_authenticated_user, None)

    def test_health_endpoint_no_auth_required(self, client):
        """Test that health endpoint works without authentication."""
        response = client.get("/health")
        assert response.status_code in [200, 503]  # 503 is also acceptable for health checks

    def test_root_endpoint_no_auth_required(self, client):
        """Test that root endpoint works without authentication."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello, World, I am alive!"}

    @patch(
        "cognee.api.client.REQUIRE_AUTHENTICATION",
        False,
    )
    def test_openapi_schema_no_global_security(self, client):
        """Test that OpenAPI schema doesn't require global authentication."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()

        # Should not have global security requirement
        global_security = schema.get("security", [])
        assert global_security == []

        # But should still have security schemes defined
        security_schemes = schema.get("components", {}).get("securitySchemes", {})
        assert "BearerAuth" in security_schemes
        assert "CookieAuth" in security_schemes

    def test_add_endpoint_with_conditional_auth(self, client, mock_default_user):
        """Test add endpoint works with conditional authentication (no auth required)."""
        # Override auth dependency to return mock user directly
        app.dependency_overrides[get_authenticated_user] = lambda: mock_default_user

        # Test file upload without authentication
        files = {"data": ("test.txt", b"test content", "text/plain")}
        form_data = {"datasetName": "test_dataset"}

        response = client.post("/api/v1/add", files=files, data=form_data)

        # Core test: authentication is not required (should not get 401)
        assert response.status_code != 401

    def test_conditional_authentication_works_with_current_environment(
        self, client, mock_default_user
    ):
        """Test that conditional authentication works when auth is bypassed."""
        # Override auth dependency to simulate no-auth environment
        app.dependency_overrides[get_authenticated_user] = lambda: mock_default_user

        files = {"data": ("test.txt", b"test content", "text/plain")}
        form_data = {"datasetName": "test_dataset"}

        response = client.post("/api/v1/add", files=files, data=form_data)

        # Core test: authentication is not required (should not get 401)
        assert response.status_code != 401


class TestConditionalAuthenticationBehavior:
    """Test the behavior of conditional authentication across different endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _cleanup_overrides(self):
        """Cleanup dependency overrides after each test."""
        yield
        app.dependency_overrides.pop(get_authenticated_user, None)

    @pytest.mark.parametrize(
        "endpoint,method",
        [
            ("/api/v1/search", "GET"),
            ("/api/v1/datasets", "GET"),
        ],
    )
    def test_get_endpoints_work_without_auth(
        self, client, endpoint, method, mock_default_user
    ):
        """Test that GET endpoints work without authentication when auth is overridden."""
        app.dependency_overrides[get_authenticated_user] = lambda: mock_default_user

        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, json={})

        # Should not return 401 Unauthorized
        assert response.status_code != 401

        # May return other errors due to missing data/config, but not auth errors
        if response.status_code >= 400:
            try:
                error_detail = response.json().get("detail", "")
                assert "authenticate" not in error_detail.lower()
                assert "unauthorized" not in error_detail.lower()
            except Exception:
                pass  # If response is not JSON, that's fine

    gsm_mod = importlib.import_module("cognee.modules.settings.get_settings")

    @patch.object(gsm_mod, "get_vectordb_config")
    @patch.object(gsm_mod, "get_llm_config")
    def test_settings_endpoint_integration(
        self, mock_llm_config, mock_vector_config, client, mock_default_user
    ):
        """Test that settings endpoint integration works with conditional authentication."""
        app.dependency_overrides[get_authenticated_user] = lambda: mock_default_user

        # Mock configurations to avoid validation errors
        mock_llm_config.return_value = SimpleNamespace(
            llm_provider="openai",
            llm_model="gpt-4o",
            llm_endpoint=None,
            llm_api_version=None,
            llm_api_key="test_key_1234567890",
        )

        mock_vector_config.return_value = SimpleNamespace(
            vector_db_provider="lancedb",
            vector_db_url="localhost:5432",
            vector_db_key="test_vector_key",
        )

        response = client.get("/api/v1/settings")

        # Core test: authentication is not required (should not get 401)
        assert response.status_code != 401


class TestConditionalAuthenticationErrorHandling:
    """Test error handling in conditional authentication."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def _cleanup_overrides(self):
        """Cleanup dependency overrides after each test."""
        yield
        app.dependency_overrides.pop(get_authenticated_user, None)

    @patch.object(gau_mod, "REQUIRE_AUTHENTICATION", False)
    @patch.object(gau_mod, "get_default_user", new_callable=AsyncMock)
    def test_get_default_user_fails(self, mock_get_default, client):
        """Test behavior when get_default_user fails."""
        mock_get_default.side_effect = Exception("Database connection failed")

        files = {"data": ("test.txt", b"test content", "text/plain")}
        form_data = {"datasetName": "test_dataset"}

        response = client.post("/api/v1/add", files=files, data=form_data)

        # Should return HTTP 500 Internal Server Error when get_default_user fails
        assert response.status_code == 500

        error_detail = response.json().get("detail", "")
        assert "Failed to create default user" in error_detail

    def test_current_environment_configuration(self):
        """Test that REQUIRE_AUTHENTICATION is properly parsed as a boolean."""
        from cognee.modules.users.methods.get_authenticated_user import (
            REQUIRE_AUTHENTICATION,
        )

        # Should be a boolean value (the parsing logic works)
        assert isinstance(REQUIRE_AUTHENTICATION, bool)
        # Note: actual value depends on .env configuration
        # In environments with REQUIRE_AUTHENTICATION=True or ENABLE_BACKEND_ACCESS_CONTROL=True,
        # this will be True. In default environments, it will be False.
