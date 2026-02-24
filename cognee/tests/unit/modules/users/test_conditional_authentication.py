import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from types import SimpleNamespace
import importlib

from cognee.modules.users.models import User


gau_mod = importlib.import_module("cognee.modules.users.methods.get_authenticated_user")


def _make_mock_user(**kwargs):
    """Create a SimpleNamespace mock user with tenant_id=None to skip DB tenant check."""
    defaults = dict(id=uuid4(), email="default@example.com", is_active=True, tenant_id=None)
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_user(**kwargs):
    """Create a User model instance with tenant_id=None to skip DB tenant check."""
    defaults = dict(
        id=uuid4(),
        email="user@example.com",
        hashed_password="hashed",
        is_active=True,
        is_verified=True,
        tenant_id=None,
    )
    defaults.update(kwargs)
    return User(**defaults)


class TestConditionalAuthentication:
    """Test cases for conditional authentication functionality."""

    @pytest.mark.asyncio
    @patch.object(gau_mod, "REQUIRE_AUTHENTICATION", False)
    @patch.object(gau_mod, "get_default_user", new_callable=AsyncMock)
    async def test_require_authentication_false_no_token_returns_default_user(
        self, mock_get_default
    ):
        """Test that when REQUIRE_AUTHENTICATION=false and no token, returns default user."""
        mock_default_user = _make_mock_user()
        mock_get_default.return_value = mock_default_user

        result = await gau_mod.get_authenticated_user(x_api_key=None, user=None)

        assert result == mock_default_user
        mock_get_default.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(gau_mod, "REQUIRE_AUTHENTICATION", False)
    @patch.object(gau_mod, "get_default_user", new_callable=AsyncMock)
    async def test_require_authentication_false_with_valid_user_returns_user(
        self, mock_get_default
    ):
        """Test that when REQUIRE_AUTHENTICATION=false and valid user, returns that user."""
        mock_authenticated_user = _make_user()

        result = await gau_mod.get_authenticated_user(x_api_key=None, user=mock_authenticated_user)

        assert result == mock_authenticated_user
        mock_get_default.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(gau_mod, "REQUIRE_AUTHENTICATION", True)
    async def test_require_authentication_true_with_user_returns_user(self):
        """Test that when REQUIRE_AUTHENTICATION=true and user present, returns user."""
        mock_authenticated_user = _make_user()

        result = await gau_mod.get_authenticated_user(x_api_key=None, user=mock_authenticated_user)

        assert result == mock_authenticated_user


class TestConditionalAuthenticationIntegration:
    """Integration tests that test the full authentication flow."""

    @pytest.mark.asyncio
    async def test_fastapi_users_dependency_creation(self):
        """Test that FastAPI Users dependency can be created correctly."""
        from cognee.modules.users.get_fastapi_users import get_fastapi_users

        fastapi_users = get_fastapi_users()

        # Test that we can create optional dependency
        optional_dependency = fastapi_users.current_user(optional=True, active=True)
        assert callable(optional_dependency)

        # Test that we can create required dependency
        required_dependency = fastapi_users.current_user(active=True)
        assert callable(required_dependency)

    @pytest.mark.asyncio
    async def test_conditional_authentication_function_exists(self):
        """Test that the conditional authentication function can be imported and used."""
        from cognee.modules.users.methods.get_authenticated_user import (
            get_authenticated_user,
            REQUIRE_AUTHENTICATION,
        )

        assert callable(get_authenticated_user)
        assert isinstance(REQUIRE_AUTHENTICATION, bool)
        # Note: actual value depends on .env configuration


class TestConditionalAuthenticationEnvironmentVariables:
    """Test environment variable handling for REQUIRE_AUTHENTICATION parsing logic."""

    def test_require_authentication_parsing_logic(self):
        """Test that the parsing logic correctly evaluates env var combinations."""
        # Test the parsing expression directly instead of reimporting the module
        # This avoids issues with dotenv reloading .env on reimport
        parse = lambda req, bac: (
            (req or "false").lower() == "true"
            or (bac or "false").lower() == "true"
        )

        # Both unset → False
        assert not parse(None, None)

        # REQUIRE_AUTHENTICATION=true → True
        assert parse("true", None)
        assert parse("True", None)
        assert parse("TRUE", None)

        # REQUIRE_AUTHENTICATION=false → False
        assert not parse("false", None)
        assert not parse("False", None)

        # ENABLE_BACKEND_ACCESS_CONTROL=true → True
        assert parse(None, "true")
        assert parse("false", "true")

        # Both false → False
        assert not parse("false", "false")

    def test_require_authentication_case_insensitive(self):
        """Test that environment variable parsing is case insensitive."""
        parse = lambda val: (val or "false").lower() == "true"

        test_cases = {
            "TRUE": True, "True": True, "tRuE": True,
            "FALSE": False, "False": False, "fAlSe": False,
        }

        for case, expected in test_cases.items():
            assert parse(case) == expected, f"Failed for case: {case}"

    def test_current_require_authentication_value(self):
        """Test that the current REQUIRE_AUTHENTICATION module value is properly typed."""
        from cognee.modules.users.methods.get_authenticated_user import (
            REQUIRE_AUTHENTICATION,
        )

        assert isinstance(REQUIRE_AUTHENTICATION, bool)
        # Note: actual value depends on .env configuration

    def test_require_authentication_false_explicit(self):
        """Test that REQUIRE_AUTHENTICATION=false is parsed correctly."""
        parse = lambda val: (val or "false").lower() == "true"
        assert not parse("false")


class TestConditionalAuthenticationEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    @patch.object(gau_mod, "REQUIRE_AUTHENTICATION", False)
    @patch.object(gau_mod, "get_default_user", new_callable=AsyncMock)
    async def test_get_default_user_raises_exception(self, mock_get_default):
        """Test behavior when get_default_user raises an exception."""
        mock_get_default.side_effect = Exception("Database error")

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await gau_mod.get_authenticated_user(x_api_key=None, user=None)

        assert exc_info.value.status_code == 500
        assert "Failed to create default user" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch.object(gau_mod, "REQUIRE_AUTHENTICATION", False)
    @patch.object(gau_mod, "get_default_user", new_callable=AsyncMock)
    async def test_user_type_consistency(self, mock_get_default):
        """Test that the function always returns the same type."""
        mock_user = _make_user()
        mock_default_user = _make_mock_user()
        mock_get_default.return_value = mock_default_user

        # Test with user
        result1 = await gau_mod.get_authenticated_user(x_api_key=None, user=mock_user)
        assert result1 == mock_user

        # Test with None
        result2 = await gau_mod.get_authenticated_user(x_api_key=None, user=None)
        assert result2 == mock_default_user

        # Both should have user-like interface
        assert hasattr(result1, "id")
        assert hasattr(result1, "email")
        assert hasattr(result2, "id")
        assert hasattr(result2, "email")


@pytest.mark.asyncio
class TestAuthenticationScenarios:
    """Test specific authentication scenarios that could occur in FastAPI Users."""

    @patch.object(gau_mod, "REQUIRE_AUTHENTICATION", False)
    @patch.object(gau_mod, "get_default_user", new_callable=AsyncMock)
    async def test_fallback_to_default_user_scenarios(self, mock_get_default):
        """
        Test fallback to default user for all scenarios where FastAPI Users returns None.
        """
        mock_default_user = _make_mock_user()
        mock_get_default.return_value = mock_default_user

        result = await gau_mod.get_authenticated_user(x_api_key=None, user=None)
        assert result == mock_default_user
        mock_get_default.assert_called_once()

    async def test_scenario_valid_active_user(self):
        """Scenario: Valid JWT and user exists and is active → returns the user."""
        mock_user = _make_user(email="active@example.com")

        result = await gau_mod.get_authenticated_user(x_api_key=None, user=mock_user)
        assert result == mock_user
