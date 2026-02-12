import pytest
from unittest.mock import AsyncMock


class TestGraphValidation:
    @pytest.mark.asyncio
    async def test_validate_adds_confidence_scores(self):
        from cognee.tasks.graph_validation.validate_extracted_graph import validate_extracted_graph
        extracted_data = [
            {"source_entity": "Python", "target_entity": "Programming Language", "relationship": "is_a", "source_text": "Python is a programming language."},
            {"source_entity": "Python", "target_entity": "Snake", "relationship": "is_a", "source_text": "Python is a programming language."},
        ]
        mock_llm = AsyncMock()
        mock_llm.return_value = [
            {"index": 0, "confidence": 0.95, "valid": True, "reason": "Correct"},
            {"index": 1, "confidence": 0.2, "valid": False, "reason": "Snake is wrong context"},
        ]
        result = await validate_extracted_graph(extracted_data, llm_client=mock_llm, confidence_threshold=0.7)
        assert len(result) == 1
        assert result[0]["source_entity"] == "Python"
        assert result[0]["target_entity"] == "Programming Language"
        assert "confidence" in result[0]
        assert result[0]["confidence"] >= 0.7

    @pytest.mark.asyncio
    async def test_validate_keeps_all_when_threshold_zero(self):
        from cognee.tasks.graph_validation.validate_extracted_graph import validate_extracted_graph
        extracted_data = [
            {"source_entity": "A", "target_entity": "B", "relationship": "r1", "source_text": "t1"},
            {"source_entity": "C", "target_entity": "D", "relationship": "r2", "source_text": "t2"},
        ]
        mock_llm = AsyncMock()
        mock_llm.return_value = [
            {"index": 0, "confidence": 0.3, "valid": False, "reason": "low"},
            {"index": 1, "confidence": 0.5, "valid": True, "reason": "medium"},
        ]
        result = await validate_extracted_graph(extracted_data, llm_client=mock_llm, confidence_threshold=0.0)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_validate_handles_llm_failure(self):
        from cognee.tasks.graph_validation.validate_extracted_graph import validate_extracted_graph
        extracted_data = [
            {"source_entity": "A", "target_entity": "B", "relationship": "r1", "source_text": "t1"},
        ]
        mock_llm = AsyncMock(side_effect=Exception("LLM down"))
        result = await validate_extracted_graph(extracted_data, llm_client=mock_llm, confidence_threshold=0.7)
        assert len(result) == 1
        assert result[0]["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_validate_empty_input(self):
        from cognee.tasks.graph_validation.validate_extracted_graph import validate_extracted_graph
        mock_llm = AsyncMock()
        result = await validate_extracted_graph([], llm_client=mock_llm)
        assert result == []
