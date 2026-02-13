"""Unit tests for search retrieval verification (T501-T509).

Validates that get_search_type_tools dispatches to the correct retriever classes
with the correct parameters for each SearchType. All retriever classes are mocked
to avoid real DB/LLM connections.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from cognee.modules.search.types import SearchType
from cognee.modules.search.exceptions import UnsupportedSearchTypeError

# The module path used for patching all retriever imports
_MOD = "cognee.modules.search.methods.get_search_type_tools"


def _make_mock_retriever(**extra_methods):
    """Create a MagicMock retriever instance with standard get_completion/get_context methods."""
    instance = MagicMock()
    instance.get_completion = MagicMock(name="get_completion")
    instance.get_context = MagicMock(name="get_context")
    for name, val in extra_methods.items():
        setattr(instance, name, val)
    return instance


def _patch_all_retrievers():
    """Return a dict of patches for every retriever class used in get_search_type_tools.

    This prevents any real instantiation of retrievers that might need DB connections.
    """
    retriever_classes = [
        "GraphCompletionRetriever",
        "CompletionRetriever",
        "ChunksRetriever",
        "SummariesRetriever",
        "JaccardChunksRetriever",
        "HybridRetriever",
        "UserQAFeedback",
        "TemporalRetriever",
        "CodeRetriever",
        "CypherSearchRetriever",
        "NaturalLanguageRetriever",
        "CodingRulesRetriever",
        "GraphCompletionCotRetriever",
        "GraphCompletionContextExtensionRetriever",
        "GraphSummaryCompletionRetriever",
    ]
    patches = {}
    for cls_name in retriever_classes:
        p = patch(f"{_MOD}.{cls_name}")
        patches[cls_name] = p
    return patches


class _AllRetrieversMockedBase:
    """Base class that patches all retriever classes for every test method."""

    @pytest.fixture(autouse=True)
    def _patch_all(self):
        """Fixture that patches every retriever class and stores mocks on self."""
        patches = _patch_all_retrievers()
        self.mocks = {}
        started = []
        for name, p in patches.items():
            mock_cls = p.start()
            started.append(p)
            # Create a default return instance with get_completion/get_context
            mock_instance = _make_mock_retriever()
            # UserQAFeedback has add_feedback, CodingRulesRetriever has get_existing_rules
            if name == "UserQAFeedback":
                mock_instance.add_feedback = MagicMock(name="add_feedback")
            if name == "CodingRulesRetriever":
                mock_instance.get_existing_rules = MagicMock(name="get_existing_rules")
            mock_cls.return_value = mock_instance
            self.mocks[name] = mock_cls
        yield
        for p in started:
            p.stop()

    def _get_mock_instance(self, cls_name):
        """Get the mock instance that would be returned by the mocked constructor."""
        return self.mocks[cls_name].return_value


# ---------------------------------------------------------------------------
# T501: GRAPH_COMPLETION search
# ---------------------------------------------------------------------------
class TestT501GraphCompletion(_AllRetrieversMockedBase):
    """T501: Test GRAPH_COMPLETION search type."""

    @pytest.mark.asyncio
    async def test_graph_completion_returns_tools(self):
        """get_search_type_tools should return a non-empty list for GRAPH_COMPLETION."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.GRAPH_COMPLETION, "test query")
        assert isinstance(tools, list)
        assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_graph_completion_retriever_instantiated_with_correct_params(self):
        """GraphCompletionRetriever should receive system_prompt_path, top_k, node_type, etc."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools
        from cognee.modules.engine.models.node_set import NodeSet

        await get_search_type_tools(
            SearchType.GRAPH_COMPLETION,
            "test query",
            system_prompt_path="custom_prompt.txt",
            top_k=5,
            node_name=["Entity"],
            save_interaction=True,
            system_prompt="Custom system prompt",
        )

        mock_cls = self.mocks["GraphCompletionRetriever"]
        # GraphCompletionRetriever is called multiple times: twice for GRAPH_COMPLETION
        # (get_completion + get_context) and once more for HYBRID_SEARCH composition,
        # because the search_tasks dict is built eagerly for all types.
        assert mock_cls.call_count >= 2

        # Find calls that match our custom parameters.
        # GraphCompletionRetriever is called at least twice for GRAPH_COMPLETION
        # (get_completion + get_context), and also once more for HYBRID_SEARCH
        # composition, since all search_tasks entries are built eagerly.
        matching_calls = [
            call for call in mock_cls.call_args_list
            if call[1].get("system_prompt_path") == "custom_prompt.txt"
        ]
        assert len(matching_calls) >= 2, (
            f"Expected at least 2 calls with custom_prompt.txt, got {len(matching_calls)}"
        )
        call_kwargs = matching_calls[0][1]
        assert call_kwargs["system_prompt_path"] == "custom_prompt.txt"
        assert call_kwargs["top_k"] == 5
        assert call_kwargs["node_type"] == NodeSet
        assert call_kwargs["node_name"] == ["Entity"]
        assert call_kwargs["save_interaction"] is True
        assert call_kwargs["system_prompt"] == "Custom system prompt"

    @pytest.mark.asyncio
    async def test_graph_completion_tools_contain_completion_and_context(self):
        """The tools list should contain get_completion and get_context methods."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.GRAPH_COMPLETION, "test query")
        assert len(tools) == 2

        mock_instance = self._get_mock_instance("GraphCompletionRetriever")
        assert tools[0] is mock_instance.get_completion
        assert tools[1] is mock_instance.get_context

    @pytest.mark.asyncio
    async def test_graph_completion_all_tools_callable(self):
        """Every tool returned for GRAPH_COMPLETION should be callable."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.GRAPH_COMPLETION, "test query")
        for tool in tools:
            assert callable(tool)


# ---------------------------------------------------------------------------
# T502: RAG_COMPLETION search
# ---------------------------------------------------------------------------
class TestT502RagCompletion(_AllRetrieversMockedBase):
    """T502: Test RAG_COMPLETION search type."""

    @pytest.mark.asyncio
    async def test_rag_completion_returns_tools(self):
        """get_search_type_tools should return tools for RAG_COMPLETION."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.RAG_COMPLETION, "test query")
        assert isinstance(tools, list)
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_rag_completion_uses_completion_retriever(self):
        """RAG_COMPLETION should use CompletionRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.RAG_COMPLETION, "test query")
        mock_instance = self._get_mock_instance("CompletionRetriever")
        assert tools[0] is mock_instance.get_completion
        assert tools[1] is mock_instance.get_context

    @pytest.mark.asyncio
    async def test_rag_completion_system_prompt_path_passed(self):
        """system_prompt_path should be forwarded to CompletionRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.RAG_COMPLETION,
            "test query",
            system_prompt_path="my_prompt.txt",
        )

        mock_cls = self.mocks["CompletionRetriever"]
        assert mock_cls.call_count == 2
        call_kwargs = mock_cls.call_args_list[0][1]
        assert call_kwargs["system_prompt_path"] == "my_prompt.txt"

    @pytest.mark.asyncio
    async def test_rag_completion_system_prompt_passed(self):
        """system_prompt should be forwarded to CompletionRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.RAG_COMPLETION,
            "test query",
            system_prompt="Direct system prompt",
        )

        mock_cls = self.mocks["CompletionRetriever"]
        call_kwargs = mock_cls.call_args_list[0][1]
        assert call_kwargs["system_prompt"] == "Direct system prompt"

    @pytest.mark.asyncio
    async def test_rag_completion_top_k_passed(self):
        """top_k should be forwarded to CompletionRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.RAG_COMPLETION,
            "test query",
            top_k=15,
        )

        mock_cls = self.mocks["CompletionRetriever"]
        call_kwargs = mock_cls.call_args_list[0][1]
        assert call_kwargs["top_k"] == 15


# ---------------------------------------------------------------------------
# T503: CHUNKS search
# ---------------------------------------------------------------------------
class TestT503Chunks(_AllRetrieversMockedBase):
    """T503: Test CHUNKS search type."""

    @pytest.mark.asyncio
    async def test_chunks_returns_tools(self):
        """get_search_type_tools should return tools for CHUNKS."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.CHUNKS, "test query")
        assert isinstance(tools, list)
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_chunks_uses_chunks_retriever(self):
        """CHUNKS should use ChunksRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.CHUNKS, "test query")
        mock_instance = self._get_mock_instance("ChunksRetriever")
        assert tools[0] is mock_instance.get_completion
        assert tools[1] is mock_instance.get_context

    @pytest.mark.asyncio
    async def test_chunks_top_k_forwarded(self):
        """top_k parameter should be forwarded to ChunksRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(SearchType.CHUNKS, "test query", top_k=20)

        mock_cls = self.mocks["ChunksRetriever"]
        # ChunksRetriever is called twice (once per tool)
        call_kwargs = mock_cls.call_args_list[0][1]
        assert call_kwargs["top_k"] == 20


# ---------------------------------------------------------------------------
# T504: SUMMARIES search
# ---------------------------------------------------------------------------
class TestT504Summaries(_AllRetrieversMockedBase):
    """T504: Test SUMMARIES search type."""

    @pytest.mark.asyncio
    async def test_summaries_returns_tools(self):
        """get_search_type_tools should return tools for SUMMARIES."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.SUMMARIES, "test query")
        assert isinstance(tools, list)
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_summaries_uses_summaries_retriever(self):
        """SUMMARIES should use SummariesRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.SUMMARIES, "test query")
        mock_instance = self._get_mock_instance("SummariesRetriever")
        assert tools[0] is mock_instance.get_completion
        assert tools[1] is mock_instance.get_context

    @pytest.mark.asyncio
    async def test_summaries_top_k_passed(self):
        """top_k should be forwarded to SummariesRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(SearchType.SUMMARIES, "test query", top_k=7)

        mock_cls = self.mocks["SummariesRetriever"]
        call_kwargs = mock_cls.call_args_list[0][1]
        assert call_kwargs["top_k"] == 7


# ---------------------------------------------------------------------------
# T505: CHUNKS_LEXICAL search
# ---------------------------------------------------------------------------
class TestT505ChunksLexical(_AllRetrieversMockedBase):
    """T505: Test CHUNKS_LEXICAL search type."""

    @pytest.mark.asyncio
    async def test_chunks_lexical_returns_tools(self):
        """get_search_type_tools should return tools for CHUNKS_LEXICAL."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.CHUNKS_LEXICAL, "test query")
        assert isinstance(tools, list)
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_chunks_lexical_uses_jaccard_retriever(self):
        """CHUNKS_LEXICAL should use JaccardChunksRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.CHUNKS_LEXICAL, "test query")
        mock_instance = self._get_mock_instance("JaccardChunksRetriever")
        assert tools[0] is mock_instance.get_completion
        assert tools[1] is mock_instance.get_context

    @pytest.mark.asyncio
    async def test_chunks_lexical_top_k_forwarded(self):
        """top_k should be forwarded to JaccardChunksRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(SearchType.CHUNKS_LEXICAL, "test query", top_k=3)

        mock_cls = self.mocks["JaccardChunksRetriever"]
        # The lambda in the source uses JaccardChunksRetriever(top_k=top_k)
        call_kwargs = mock_cls.call_args_list[0][1]
        assert call_kwargs["top_k"] == 3


# ---------------------------------------------------------------------------
# T506: HYBRID_SEARCH end-to-end
# ---------------------------------------------------------------------------
class TestT506HybridSearch(_AllRetrieversMockedBase):
    """T506: Test HYBRID_SEARCH end-to-end composition."""

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_tools(self):
        """get_search_type_tools should return tools for HYBRID_SEARCH."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.HYBRID_SEARCH, "test query")
        assert isinstance(tools, list)
        assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_hybrid_search_only_get_completion(self):
        """HYBRID_SEARCH should only return get_completion (not get_context)."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.HYBRID_SEARCH, "test query")
        # Only 1 tool: HybridRetriever.get_completion
        assert len(tools) == 1

    @pytest.mark.asyncio
    async def test_hybrid_search_uses_hybrid_retriever(self):
        """The tool returned should be HybridRetriever.get_completion."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.HYBRID_SEARCH, "test query")
        mock_hr_instance = self._get_mock_instance("HybridRetriever")
        assert tools[0] is mock_hr_instance.get_completion

    @pytest.mark.asyncio
    async def test_hybrid_retriever_composed_with_correct_sub_retrievers(self):
        """HybridRetriever should be composed of ChunksRetriever, GraphCompletionRetriever,
        and JaccardChunksRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(SearchType.HYBRID_SEARCH, "test query")

        mock_hr_cls = self.mocks["HybridRetriever"]
        assert mock_hr_cls.called, "HybridRetriever should have been instantiated"

        call_kwargs = mock_hr_cls.call_args[1]
        # vector_retriever should come from ChunksRetriever
        mock_chunks_instance = self._get_mock_instance("ChunksRetriever")
        assert call_kwargs["vector_retriever"] is mock_chunks_instance.get_completion

        # graph_retriever should come from GraphCompletionRetriever
        mock_graph_instance = self._get_mock_instance("GraphCompletionRetriever")
        assert call_kwargs["graph_retriever"] is mock_graph_instance.get_completion

        # lexical_retriever should come from JaccardChunksRetriever
        mock_jaccard_instance = self._get_mock_instance("JaccardChunksRetriever")
        assert call_kwargs["lexical_retriever"] is mock_jaccard_instance.get_completion

    @pytest.mark.asyncio
    async def test_hybrid_retriever_receives_top_k(self):
        """HybridRetriever should receive the top_k parameter."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(SearchType.HYBRID_SEARCH, "test query", top_k=25)

        mock_hr_cls = self.mocks["HybridRetriever"]
        call_kwargs = mock_hr_cls.call_args[1]
        assert call_kwargs["top_k"] == 25


# ---------------------------------------------------------------------------
# T507: Search quality metrics and validation
# ---------------------------------------------------------------------------
class TestT507SearchQualityMetrics(_AllRetrieversMockedBase):
    """T507: Test FEELING_LUCKY, CYPHER/NATURAL_LANGUAGE env var, and invalid types."""

    @pytest.mark.asyncio
    async def test_feeling_lucky_triggers_select_search_type(self):
        """FEELING_LUCKY should call select_search_type to dynamically choose a type."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        with patch(f"{_MOD}.select_search_type", new_callable=AsyncMock) as mock_select:
            # Make select_search_type return CHUNKS
            mock_select.return_value = SearchType.CHUNKS

            tools = await get_search_type_tools(SearchType.FEELING_LUCKY, "what is AI?")
            mock_select.assert_called_once_with("what is AI?")
            # Tools should be from CHUNKS since that's what select_search_type returned
            mock_chunks_instance = self._get_mock_instance("ChunksRetriever")
            assert tools[0] is mock_chunks_instance.get_completion

    @pytest.mark.asyncio
    async def test_feeling_lucky_select_returns_rag(self):
        """FEELING_LUCKY should use whatever type select_search_type returns (RAG_COMPLETION)."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        with patch(f"{_MOD}.select_search_type", new_callable=AsyncMock) as mock_select:
            mock_select.return_value = SearchType.RAG_COMPLETION

            tools = await get_search_type_tools(SearchType.FEELING_LUCKY, "explain this")
            mock_instance = self._get_mock_instance("CompletionRetriever")
            assert tools[0] is mock_instance.get_completion

    @pytest.mark.asyncio
    async def test_cypher_disabled_raises_error(self):
        """CYPHER type should raise UnsupportedSearchTypeError when ALLOW_CYPHER_QUERY=false."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        with patch.dict(os.environ, {"ALLOW_CYPHER_QUERY": "false"}):
            with pytest.raises(UnsupportedSearchTypeError, match="disabled"):
                await get_search_type_tools(SearchType.CYPHER, "MATCH (n) RETURN n")

    @pytest.mark.asyncio
    async def test_natural_language_disabled_raises_error(self):
        """NATURAL_LANGUAGE type should raise UnsupportedSearchTypeError when ALLOW_CYPHER_QUERY=false."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        with patch.dict(os.environ, {"ALLOW_CYPHER_QUERY": "false"}):
            with pytest.raises(UnsupportedSearchTypeError, match="disabled"):
                await get_search_type_tools(SearchType.NATURAL_LANGUAGE, "find all people")

    @pytest.mark.asyncio
    async def test_cypher_enabled_returns_tools(self):
        """CYPHER type should return tools when ALLOW_CYPHER_QUERY is true (default)."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        with patch.dict(os.environ, {"ALLOW_CYPHER_QUERY": "true"}):
            tools = await get_search_type_tools(SearchType.CYPHER, "MATCH (n) RETURN n")
            assert isinstance(tools, list)
            assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_natural_language_enabled_returns_tools(self):
        """NATURAL_LANGUAGE type should return tools when ALLOW_CYPHER_QUERY is true."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        with patch.dict(os.environ, {"ALLOW_CYPHER_QUERY": "true"}):
            tools = await get_search_type_tools(SearchType.NATURAL_LANGUAGE, "find people")
            assert isinstance(tools, list)
            assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_invalid_search_type_raises_error(self):
        """An invalid/unsupported search type should raise UnsupportedSearchTypeError."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        # Use a string that is not a valid SearchType - the function checks .get() returning None
        with pytest.raises(UnsupportedSearchTypeError):
            await get_search_type_tools("NONEXISTENT_TYPE", "test query")


# ---------------------------------------------------------------------------
# T508: Search type completeness
# ---------------------------------------------------------------------------
class TestT508SearchTypeCompleteness(_AllRetrieversMockedBase):
    """T508: Test that all SearchType enum values have corresponding dispatch entries."""

    @pytest.mark.asyncio
    async def test_all_search_types_except_feeling_lucky_have_entries(self):
        """Every SearchType (except FEELING_LUCKY which is dynamically dispatched)
        should be handled by get_search_type_tools without raising UnsupportedSearchTypeError."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        # FEELING_LUCKY calls select_search_type which needs LLM, so skip it
        skip_types = {SearchType.FEELING_LUCKY}

        with patch.dict(os.environ, {"ALLOW_CYPHER_QUERY": "true"}):
            for search_type in SearchType:
                if search_type in skip_types:
                    continue
                tools = await get_search_type_tools(search_type, "test query")
                assert isinstance(tools, list), f"{search_type} did not return a list"
                assert len(tools) > 0, f"{search_type} returned empty list"

    @pytest.mark.asyncio
    async def test_feedback_type_returns_user_qa_feedback_tools(self):
        """FEEDBACK type should return UserQAFeedback tools."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.FEEDBACK, "test query")
        mock_instance = self._get_mock_instance("UserQAFeedback")
        assert len(tools) == 1
        assert tools[0] is mock_instance.add_feedback

    @pytest.mark.asyncio
    async def test_temporal_type_returns_temporal_retriever_tools(self):
        """TEMPORAL type should return TemporalRetriever tools."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.TEMPORAL, "test query")
        mock_instance = self._get_mock_instance("TemporalRetriever")
        assert len(tools) == 2
        assert tools[0] is mock_instance.get_completion
        assert tools[1] is mock_instance.get_context

    @pytest.mark.asyncio
    async def test_code_type_returns_code_retriever_tools(self):
        """CODE type should return CodeRetriever tools."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.CODE, "test query")
        mock_instance = self._get_mock_instance("CodeRetriever")
        assert len(tools) == 2
        assert tools[0] is mock_instance.get_completion
        assert tools[1] is mock_instance.get_context

    @pytest.mark.asyncio
    async def test_coding_rules_type_returns_coding_rules_retriever_tools(self):
        """CODING_RULES type should return CodingRulesRetriever tools."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.CODING_RULES, "test query")
        mock_instance = self._get_mock_instance("CodingRulesRetriever")
        assert len(tools) == 1
        assert tools[0] is mock_instance.get_existing_rules

    @pytest.mark.asyncio
    async def test_graph_completion_cot_type_returns_tools(self):
        """GRAPH_COMPLETION_COT type should return GraphCompletionCotRetriever tools."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(SearchType.GRAPH_COMPLETION_COT, "test query")
        mock_instance = self._get_mock_instance("GraphCompletionCotRetriever")
        assert len(tools) == 2
        assert tools[0] is mock_instance.get_completion
        assert tools[1] is mock_instance.get_context

    @pytest.mark.asyncio
    async def test_graph_completion_context_extension_type_returns_tools(self):
        """GRAPH_COMPLETION_CONTEXT_EXTENSION type should return correct tools."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(
            SearchType.GRAPH_COMPLETION_CONTEXT_EXTENSION, "test query"
        )
        mock_instance = self._get_mock_instance("GraphCompletionContextExtensionRetriever")
        assert len(tools) == 2
        assert tools[0] is mock_instance.get_completion
        assert tools[1] is mock_instance.get_context

    @pytest.mark.asyncio
    async def test_graph_summary_completion_type_returns_tools(self):
        """GRAPH_SUMMARY_COMPLETION type should return correct tools."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        tools = await get_search_type_tools(
            SearchType.GRAPH_SUMMARY_COMPLETION, "test query"
        )
        mock_instance = self._get_mock_instance("GraphSummaryCompletionRetriever")
        assert len(tools) == 2
        assert tools[0] is mock_instance.get_completion
        assert tools[1] is mock_instance.get_context


# ---------------------------------------------------------------------------
# T509: Hybrid retrieval parameter forwarding
# ---------------------------------------------------------------------------
class TestT509HybridParameterForwarding(_AllRetrieversMockedBase):
    """T509: Verify parameter forwarding for mixed retrieval scenarios."""

    @pytest.mark.asyncio
    async def test_save_interaction_forwarded_to_graph_completion(self):
        """save_interaction should be forwarded to GraphCompletionRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.GRAPH_COMPLETION, "test query", save_interaction=True
        )

        mock_cls = self.mocks["GraphCompletionRetriever"]
        call_kwargs = mock_cls.call_args_list[0][1]
        assert call_kwargs["save_interaction"] is True

    @pytest.mark.asyncio
    async def test_save_interaction_false_forwarded(self):
        """save_interaction=False should be forwarded correctly."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.GRAPH_COMPLETION, "test query", save_interaction=False
        )

        mock_cls = self.mocks["GraphCompletionRetriever"]
        call_kwargs = mock_cls.call_args_list[0][1]
        assert call_kwargs["save_interaction"] is False

    @pytest.mark.asyncio
    async def test_save_interaction_forwarded_to_hybrid_graph_retriever(self):
        """save_interaction should be forwarded to the GraphCompletionRetriever inside HYBRID_SEARCH."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.HYBRID_SEARCH, "test query", save_interaction=True
        )

        mock_cls = self.mocks["GraphCompletionRetriever"]
        # Find the call that was used for the hybrid retriever's graph_retriever
        # (it will be one of the calls to GraphCompletionRetriever)
        found = False
        for call in mock_cls.call_args_list:
            kwargs = call[1]
            if kwargs.get("save_interaction") is True:
                found = True
                break
        assert found, "save_interaction=True not found in any GraphCompletionRetriever call"

    @pytest.mark.asyncio
    async def test_node_name_forwarded_to_graph_completion(self):
        """node_name parameter should be forwarded to GraphCompletionRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.GRAPH_COMPLETION,
            "test query",
            node_name=["Person", "Organization"],
        )

        mock_cls = self.mocks["GraphCompletionRetriever"]
        call_kwargs = mock_cls.call_args_list[0][1]
        assert call_kwargs["node_name"] == ["Person", "Organization"]

    @pytest.mark.asyncio
    async def test_node_name_forwarded_to_hybrid_graph_retriever(self):
        """node_name should be forwarded to GraphCompletionRetriever inside HYBRID_SEARCH."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.HYBRID_SEARCH, "test query", node_name=["Entity"]
        )

        mock_cls = self.mocks["GraphCompletionRetriever"]
        found = False
        for call in mock_cls.call_args_list:
            kwargs = call[1]
            if kwargs.get("node_name") == ["Entity"]:
                found = True
                break
        assert found, "node_name=['Entity'] not found in any GraphCompletionRetriever call"

    @pytest.mark.asyncio
    async def test_system_prompt_overrides_when_both_provided_rag(self):
        """When both system_prompt and system_prompt_path are provided,
        both should be forwarded to CompletionRetriever (RAG_COMPLETION)."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.RAG_COMPLETION,
            "test query",
            system_prompt_path="fallback.txt",
            system_prompt="Override prompt",
        )

        mock_cls = self.mocks["CompletionRetriever"]
        call_kwargs = mock_cls.call_args_list[0][1]
        # Both should be passed; it's up to the retriever to decide precedence
        assert call_kwargs["system_prompt"] == "Override prompt"
        assert call_kwargs["system_prompt_path"] == "fallback.txt"

    @pytest.mark.asyncio
    async def test_system_prompt_overrides_when_both_provided_graph(self):
        """When both system_prompt and system_prompt_path are provided,
        both should be forwarded to GraphCompletionRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.GRAPH_COMPLETION,
            "test query",
            system_prompt_path="fallback.txt",
            system_prompt="Override prompt",
        )

        mock_cls = self.mocks["GraphCompletionRetriever"]
        call_kwargs = mock_cls.call_args_list[0][1]
        assert call_kwargs["system_prompt"] == "Override prompt"
        assert call_kwargs["system_prompt_path"] == "fallback.txt"

    @pytest.mark.asyncio
    async def test_last_k_forwarded_to_user_qa_feedback(self):
        """last_k should be forwarded to UserQAFeedback for FEEDBACK type."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.FEEDBACK, "test query", last_k=5
        )

        mock_cls = self.mocks["UserQAFeedback"]
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["last_k"] == 5

    @pytest.mark.asyncio
    async def test_node_name_forwarded_to_coding_rules(self):
        """node_name should be forwarded as rules_nodeset_name to CodingRulesRetriever."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools

        await get_search_type_tools(
            SearchType.CODING_RULES,
            "test query",
            node_name=["my_ruleset"],
        )

        mock_cls = self.mocks["CodingRulesRetriever"]
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["rules_nodeset_name"] == ["my_ruleset"]

    @pytest.mark.asyncio
    async def test_default_parameter_values(self):
        """Default parameters should be correctly applied when not explicitly provided."""
        from cognee.modules.search.methods.get_search_type_tools import get_search_type_tools
        from cognee.modules.engine.models.node_set import NodeSet

        await get_search_type_tools(SearchType.GRAPH_COMPLETION, "test query")

        mock_cls = self.mocks["GraphCompletionRetriever"]
        call_kwargs = mock_cls.call_args_list[0][1]
        # Default values from the function signature
        assert call_kwargs["system_prompt_path"] == "answer_simple_question.txt"
        assert call_kwargs["top_k"] == 10
        assert call_kwargs["node_type"] == NodeSet
        assert call_kwargs["node_name"] is None
        assert call_kwargs["save_interaction"] is False
        assert call_kwargs["system_prompt"] is None
