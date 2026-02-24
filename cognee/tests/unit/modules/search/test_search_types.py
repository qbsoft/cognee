"""Unit tests for cognee.modules.search.types module."""
import pytest
from enum import Enum

from cognee.modules.search.types import SearchType


class TestSearchType:
    """Tests for the SearchType enum."""

    def test_search_type_is_enum(self):
        """Test that SearchType is an Enum."""
        assert issubclass(SearchType, Enum)

    def test_all_search_types_exist(self):
        """Test that all expected search types are defined."""
        expected_types = [
            "SUMMARIES",
            "CHUNKS",
            "RAG_COMPLETION",
            "GRAPH_COMPLETION",
            "GRAPH_SUMMARY_COMPLETION",
            "CODE",
            "CYPHER",
            "NATURAL_LANGUAGE",
            "GRAPH_COMPLETION_COT",
            "GRAPH_COMPLETION_CONTEXT_EXTENSION",
            "FEELING_LUCKY",
            "FEEDBACK",
            "TEMPORAL",
            "CODING_RULES",
            "CHUNKS_LEXICAL",
        ]

        for type_name in expected_types:
            assert hasattr(SearchType, type_name), f"SearchType missing: {type_name}"

    def test_search_type_values_match_names(self):
        """Test that SearchType values match their names."""
        for search_type in SearchType:
            assert search_type.value == search_type.name

    def test_search_type_from_string(self):
        """Test creating SearchType from string value."""
        assert SearchType("SUMMARIES") == SearchType.SUMMARIES
        assert SearchType("CHUNKS") == SearchType.CHUNKS
        assert SearchType("RAG_COMPLETION") == SearchType.RAG_COMPLETION

    def test_search_type_invalid_string_raises_error(self):
        """Test that invalid string raises ValueError."""
        with pytest.raises(ValueError):
            SearchType("INVALID_TYPE")

    def test_search_type_iteration(self):
        """Test that SearchType can be iterated."""
        types = list(SearchType)
        assert len(types) > 0
        assert SearchType.SUMMARIES in types
        assert SearchType.CHUNKS in types

    def test_search_type_comparison(self):
        """Test SearchType equality comparison."""
        assert SearchType.SUMMARIES == SearchType.SUMMARIES
        assert SearchType.SUMMARIES != SearchType.CHUNKS

    def test_search_type_hash(self):
        """Test that SearchType values are hashable (can be used in sets/dicts)."""
        type_set = {SearchType.SUMMARIES, SearchType.CHUNKS, SearchType.SUMMARIES}
        assert len(type_set) == 2  # Duplicate removed

        type_dict = {SearchType.SUMMARIES: "summary search"}
        assert type_dict[SearchType.SUMMARIES] == "summary search"

    def test_graph_related_types(self):
        """Test graph-related search types."""
        graph_types = [
            SearchType.GRAPH_COMPLETION,
            SearchType.GRAPH_SUMMARY_COMPLETION,
            SearchType.GRAPH_COMPLETION_COT,
            SearchType.GRAPH_COMPLETION_CONTEXT_EXTENSION,
        ]

        for graph_type in graph_types:
            assert "GRAPH" in graph_type.value

    def test_rag_completion_type(self):
        """Test RAG completion search type."""
        assert SearchType.RAG_COMPLETION.value == "RAG_COMPLETION"

    def test_code_search_types(self):
        """Test code-related search types."""
        assert SearchType.CODE.value == "CODE"
        assert SearchType.CODING_RULES.value == "CODING_RULES"

    def test_lexical_search_type(self):
        """Test lexical search type for chunks."""
        assert SearchType.CHUNKS_LEXICAL.value == "CHUNKS_LEXICAL"
