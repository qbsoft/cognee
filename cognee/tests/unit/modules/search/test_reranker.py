import pytest
from unittest.mock import MagicMock, patch


class TestReranker:
    @pytest.mark.asyncio
    async def test_rerank_reorders_results(self):
        from cognee.modules.search.reranking.reranker import rerank

        results = [
            {"id": "1", "text": "Python is a programming language"},
            {"id": "2", "text": "Java is a programming language"},
            {"id": "3", "text": "The weather is nice today"},
        ]
        query = "What is Python?"

        mock_model = MagicMock()
        mock_model.compute_score.return_value = [0.95, 0.80, 0.10]

        with patch(
            "cognee.modules.search.reranking.reranker._get_reranker_model",
            return_value=mock_model,
        ):
            reranked = await rerank(query, results, top_k=2)

        assert len(reranked) == 2
        assert reranked[0]["id"] == "1"
        assert reranked[1]["id"] == "2"

    @pytest.mark.asyncio
    async def test_rerank_handles_empty_results(self):
        from cognee.modules.search.reranking.reranker import rerank

        reranked = await rerank("query", [], top_k=5)
        assert reranked == []

    @pytest.mark.asyncio
    async def test_rerank_fallback_on_model_failure(self):
        from cognee.modules.search.reranking.reranker import rerank

        results = [
            {"id": "1", "text": "Result A"},
            {"id": "2", "text": "Result B"},
        ]

        with patch(
            "cognee.modules.search.reranking.reranker._get_reranker_model",
            side_effect=Exception("Model not found"),
        ):
            reranked = await rerank("query", results, top_k=5)

        assert len(reranked) == 2
        assert reranked[0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_rerank_adds_rerank_score(self):
        from cognee.modules.search.reranking.reranker import rerank

        results = [{"id": "1", "text": "Some text"}]

        mock_model = MagicMock()
        mock_model.compute_score.return_value = [0.88]

        with patch(
            "cognee.modules.search.reranking.reranker._get_reranker_model",
            return_value=mock_model,
        ):
            reranked = await rerank("query", results, top_k=5)

        assert "rerank_score" in reranked[0]
        assert reranked[0]["rerank_score"] == 0.88
