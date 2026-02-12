import pytest
from unittest.mock import AsyncMock


class TestLLMEnhancedChunker:
    def test_chunk_strategy_has_llm_enhanced(self):
        from cognee.shared.data_models import ChunkStrategy
        assert hasattr(ChunkStrategy, "LLM_ENHANCED")

    @pytest.mark.asyncio
    async def test_llm_chunker_refines_semantic_chunks(self):
        from cognee.modules.chunking.LLMEnhancedChunker import LLMEnhancedChunker
        initial_chunks = [
            {"text": "Chunk one about topic A.", "cut_type": "paragraph", "chunk_index": 0},
            {"text": "More about topic A.", "cut_type": "paragraph", "chunk_index": 1},
            {"text": "New topic B starts.", "cut_type": "heading", "chunk_index": 2},
        ]
        mock_llm = AsyncMock()
        mock_llm.return_value = {"merge": [[0, 1]], "split": []}
        chunker = LLMEnhancedChunker(llm_client=mock_llm)
        result = await chunker.refine(initial_chunks)
        assert len(result) < len(initial_chunks)

    @pytest.mark.asyncio
    async def test_llm_chunker_handles_llm_failure(self):
        from cognee.modules.chunking.LLMEnhancedChunker import LLMEnhancedChunker
        initial_chunks = [
            {"text": "Chunk A", "cut_type": "paragraph", "chunk_index": 0},
            {"text": "Chunk B", "cut_type": "paragraph", "chunk_index": 1},
        ]
        mock_llm = AsyncMock(side_effect=Exception("LLM unavailable"))
        chunker = LLMEnhancedChunker(llm_client=mock_llm)
        result = await chunker.refine(initial_chunks)
        assert len(result) == 2
        assert result[0]["text"] == "Chunk A"
