"""Unit tests for cognee.modules.metrics module."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from cognee.modules.metrics.operations.get_pipeline_run_metrics import fetch_token_count


class TestFetchTokenCount:
    """Tests for the fetch_token_count function."""

    @pytest.mark.asyncio
    async def test_fetch_token_count_returns_sum(self):
        """Test fetch_token_count returns sum of token counts."""
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar.return_value = 1000

        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_engine = Mock()
        mock_engine.get_async_session = Mock(return_value=AsyncContextManager(mock_session))

        result = await fetch_token_count(mock_engine)
        assert result == 1000

    @pytest.mark.asyncio
    async def test_fetch_token_count_returns_none_when_empty(self):
        """Test fetch_token_count returns None when no data."""
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_engine = Mock()
        mock_engine.get_async_session = Mock(return_value=AsyncContextManager(mock_session))

        result = await fetch_token_count(mock_engine)
        assert result is None


class AsyncContextManager:
    """Helper class for async context manager mocking."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
