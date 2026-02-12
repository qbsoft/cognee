"""Unit tests for HYBRID_SEARCH registration in search type dispatch.

Tests that HYBRID_SEARCH is properly registered in get_search_type_tools()
and returns the correct HybridRetriever-based tools.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from cognee.modules.search.types import SearchType
from cognee.modules.search.exceptions import UnsupportedSearchTypeError


class TestHybridSearchDispatch:
    """Tests for HYBRID_SEARCH registration in get_search_type_tools."""

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_tools(self):
        """Calling get_search_type_tools(SearchType.HYBRID_SEARCH, ...) should NOT raise
        UnsupportedSearchTypeError and should return a non-empty list."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.HYBRID_SEARCH, "test query")
        assert isinstance(tools, list)
        assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_hybrid_search_tools_are_callable(self):
        """The returned tools for HYBRID_SEARCH should all be callable."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.HYBRID_SEARCH, "test query")
        for tool in tools:
            assert callable(tool), f"Tool {tool} is not callable"

    @pytest.mark.asyncio
    async def test_existing_search_types_still_work(self):
        """Verify GRAPH_COMPLETION, CHUNKS, RAG_COMPLETION, SUMMARIES still work
        (no regression after adding HYBRID_SEARCH)."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        existing_types = [
            SearchType.GRAPH_COMPLETION,
            SearchType.CHUNKS,
            SearchType.RAG_COMPLETION,
            SearchType.SUMMARIES,
        ]

        for search_type in existing_types:
            tools = await get_search_type_tools(search_type, "test query")
            assert isinstance(tools, list), f"{search_type} did not return a list"
            assert len(tools) > 0, f"{search_type} returned empty list"
            for tool in tools:
                assert callable(tool), f"Tool from {search_type} is not callable"

    @pytest.mark.asyncio
    async def test_hybrid_search_uses_hybrid_retriever(self):
        """Verify that HybridRetriever is used for HYBRID_SEARCH
        (the get_completion method should be from HybridRetriever)."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools
        from cognee.modules.search.retrievers.HybridRetriever import HybridRetriever

        tools = await get_search_type_tools(SearchType.HYBRID_SEARCH, "test query")

        # The first tool should be HybridRetriever.get_completion
        # Check that the method is bound to a HybridRetriever instance
        get_completion = tools[0]
        assert hasattr(get_completion, "__self__"), (
            "get_completion should be a bound method of HybridRetriever"
        )
        assert isinstance(get_completion.__self__, HybridRetriever), (
            f"get_completion is bound to {type(get_completion.__self__)}, "
            f"expected HybridRetriever"
        )
