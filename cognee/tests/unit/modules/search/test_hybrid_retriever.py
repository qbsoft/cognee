import pytest
from unittest.mock import AsyncMock, MagicMock


class TestHybridRetriever:
    def test_search_type_has_hybrid(self):
        from cognee.modules.search.types.SearchType import SearchType
        assert hasattr(SearchType, "HYBRID_SEARCH")

    @pytest.mark.asyncio
    async def test_rrf_fusion_basic(self):
        from cognee.modules.search.retrievers.HybridRetriever import reciprocal_rank_fusion
        vector_results = [
            {"id": "doc1", "score": 0.95},
            {"id": "doc2", "score": 0.90},
            {"id": "doc3", "score": 0.85},
        ]
        graph_results = [
            {"id": "doc2", "score": 0.92},
            {"id": "doc4", "score": 0.88},
            {"id": "doc1", "score": 0.80},
        ]
        lexical_results = [
            {"id": "doc3", "score": 0.88},
            {"id": "doc1", "score": 0.82},
        ]
        fused = reciprocal_rank_fusion(
            [vector_results, graph_results, lexical_results],
            weights=[0.4, 0.3, 0.3],
        )
        assert len(fused) > 0
        result_ids = [r["id"] for r in fused]
        assert "doc1" in result_ids

    @pytest.mark.asyncio
    async def test_rrf_handles_empty_results(self):
        from cognee.modules.search.retrievers.HybridRetriever import reciprocal_rank_fusion
        fused = reciprocal_rank_fusion([[], [], []], weights=[0.4, 0.3, 0.3])
        assert fused == []

    @pytest.mark.asyncio
    async def test_rrf_respects_weights(self):
        from cognee.modules.search.retrievers.HybridRetriever import reciprocal_rank_fusion
        vector_results = [{"id": "doc_A", "score": 0.99}]
        graph_results = [{"id": "doc_B", "score": 0.99}]
        lexical_results = [{"id": "doc_B", "score": 0.99}]
        fused_vector_heavy = reciprocal_rank_fusion(
            [vector_results, graph_results, lexical_results],
            weights=[0.8, 0.1, 0.1],
        )
        fused_graph_heavy = reciprocal_rank_fusion(
            [vector_results, graph_results, lexical_results],
            weights=[0.1, 0.45, 0.45],
        )
        assert fused_vector_heavy[0]["id"] == "doc_A"
        assert fused_graph_heavy[0]["id"] == "doc_B"

    @pytest.mark.asyncio
    async def test_hybrid_retriever_get_completion(self):
        from cognee.modules.search.retrievers.HybridRetriever import HybridRetriever
        mock_vector = AsyncMock(return_value=[{"id": "v1", "score": 0.9, "text": "Vector result 1"}])
        mock_graph = AsyncMock(return_value=[{"id": "g1", "score": 0.85, "text": "Graph result 1"}])
        mock_lexical = AsyncMock(return_value=[{"id": "l1", "score": 0.8, "text": "Lexical result 1"}])
        retriever = HybridRetriever(
            vector_retriever=mock_vector,
            graph_retriever=mock_graph,
            lexical_retriever=mock_lexical,
            weights={"vector": 0.4, "graph": 0.3, "lexical": 0.3},
        )
        result = await retriever.get_completion("test query")
        assert isinstance(result, list)
        assert len(result) > 0
