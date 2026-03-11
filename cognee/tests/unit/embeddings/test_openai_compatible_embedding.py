"""Tests for OpenAICompatibleEmbeddingEngine and get_embedding_engine routing."""

import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# OpenAICompatibleEmbeddingEngine tests
# ---------------------------------------------------------------------------

class TestOpenAICompatibleEmbeddingEngine:
    """Unit tests for the new OpenAI-compatible embedding engine."""

    def _make_engine(self, **kwargs):
        defaults = dict(
            model="text-embedding-v3",
            api_key="test-key",
            endpoint="https://example.com/v1",
            dimensions=1024,
            max_completion_tokens=8191,
            batch_size=10,
        )
        defaults.update(kwargs)
        from cognee.infrastructure.databases.vector.embeddings.OpenAICompatibleEmbeddingEngine import (
            OpenAICompatibleEmbeddingEngine,
        )
        return OpenAICompatibleEmbeddingEngine(**defaults)

    def test_init_creates_client(self):
        engine = self._make_engine()
        assert engine._client is not None
        assert engine.model == "text-embedding-v3"
        assert engine.dimensions == 1024
        assert engine.api_key == "test-key"

    def test_get_vector_size(self):
        engine = self._make_engine(dimensions=768)
        assert engine.get_vector_size() == 768

    def test_get_batch_size(self):
        engine = self._make_engine(batch_size=32)
        assert engine.get_batch_size() == 32

    def test_supports_dimensions_openai_v3(self):
        engine = self._make_engine(model="text-embedding-3-large")
        assert engine._supports_dimensions() is True

    def test_supports_dimensions_dashscope_v3(self):
        engine = self._make_engine(model="text-embedding-v3")
        assert engine._supports_dimensions() is True

    def test_supports_dimensions_unknown_model(self):
        engine = self._make_engine(model="some-custom-model")
        assert engine._supports_dimensions() is False

    @pytest.mark.asyncio
    async def test_embed_text_mock_mode(self):
        with patch.dict(os.environ, {"MOCK_EMBEDDING": "true"}):
            engine = self._make_engine(dimensions=128)
            result = await engine.embed_text(["hello", "world"])
            assert len(result) == 2
            assert len(result[0]) == 128
            assert all(v == 0.0 for v in result[0])

    @pytest.mark.asyncio
    async def test_embed_text_calls_openai_sdk(self):
        engine = self._make_engine()

        # Mock the openai client's response
        mock_embedding_1 = MagicMock()
        mock_embedding_1.embedding = [0.1] * 1024
        mock_embedding_2 = MagicMock()
        mock_embedding_2.embedding = [0.2] * 1024
        mock_response = MagicMock()
        mock_response.data = [mock_embedding_1, mock_embedding_2]

        engine._client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await engine.embed_text(["hello", "world"])
        assert len(result) == 2
        assert result[0] == [0.1] * 1024
        assert result[1] == [0.2] * 1024

        # Verify create was called with correct params
        call_kwargs = engine._client.embeddings.create.call_args.kwargs
        assert call_kwargs["model"] == "text-embedding-v3"
        assert call_kwargs["input"] == ["hello", "world"]

    @pytest.mark.asyncio
    async def test_embed_text_dimensions_passed_for_supported_model(self):
        engine = self._make_engine(model="text-embedding-v3", dimensions=512)

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.0] * 512)]
        engine._client.embeddings.create = AsyncMock(return_value=mock_response)

        await engine.embed_text(["test"])
        call_kwargs = engine._client.embeddings.create.call_args.kwargs
        assert call_kwargs.get("dimensions") == 512

    @pytest.mark.asyncio
    async def test_embed_text_no_dimensions_for_unsupported_model(self):
        engine = self._make_engine(model="bge-m3", dimensions=1024)

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.0] * 1024)]
        engine._client.embeddings.create = AsyncMock(return_value=mock_response)

        await engine.embed_text(["test"])
        call_kwargs = engine._client.embeddings.create.call_args.kwargs
        assert "dimensions" not in call_kwargs

    def test_tokenizer_loaded(self):
        engine = self._make_engine()
        assert engine.tokenizer is not None


# ---------------------------------------------------------------------------
# get_embedding_engine routing tests
# ---------------------------------------------------------------------------

class TestGetEmbeddingEngineRouting:
    """Tests for the embedding engine factory routing."""

    def test_fastembed_route(self):
        from cognee.infrastructure.databases.vector.embeddings.get_embedding_engine import (
            create_embedding_engine,
        )
        create_embedding_engine.cache_clear()
        engine = create_embedding_engine(
            "fastembed", "BAAI/bge-small-en", 384, 512,
            None, None, None, 36, None, None, None,
        )
        from cognee.infrastructure.databases.vector.embeddings.FastembedEmbeddingEngine import (
            FastembedEmbeddingEngine,
        )
        assert isinstance(engine, FastembedEmbeddingEngine)
        create_embedding_engine.cache_clear()

    def test_ollama_route(self):
        pytest.importorskip("transformers", reason="transformers not installed")
        from cognee.infrastructure.databases.vector.embeddings.get_embedding_engine import (
            create_embedding_engine,
        )
        create_embedding_engine.cache_clear()
        engine = create_embedding_engine(
            "ollama", "nomic-embed-text", 768, 512,
            "http://localhost:11434/api/embeddings", None, None, 10,
            "Salesforce/SFR-Embedding-Mistral", None, None,
        )
        from cognee.infrastructure.databases.vector.embeddings.OllamaEmbeddingEngine import (
            OllamaEmbeddingEngine,
        )
        assert isinstance(engine, OllamaEmbeddingEngine)
        create_embedding_engine.cache_clear()

    def test_custom_route_uses_openai_compatible(self):
        from cognee.infrastructure.databases.vector.embeddings.get_embedding_engine import (
            create_embedding_engine,
        )
        create_embedding_engine.cache_clear()
        engine = create_embedding_engine(
            "custom", "openai/text-embedding-v3", 1024, 8191,
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "sk-test", None, 10, None, None, None,
        )
        from cognee.infrastructure.databases.vector.embeddings.OpenAICompatibleEmbeddingEngine import (
            OpenAICompatibleEmbeddingEngine,
        )
        assert isinstance(engine, OpenAICompatibleEmbeddingEngine)
        create_embedding_engine.cache_clear()

    def test_openai_route_uses_openai_compatible(self):
        from cognee.infrastructure.databases.vector.embeddings.get_embedding_engine import (
            create_embedding_engine,
        )
        create_embedding_engine.cache_clear()
        engine = create_embedding_engine(
            "openai", "openai/text-embedding-3-large", 3072, 8191,
            None, "sk-openai", None, 36, None, None, None,
        )
        from cognee.infrastructure.databases.vector.embeddings.OpenAICompatibleEmbeddingEngine import (
            OpenAICompatibleEmbeddingEngine,
        )
        assert isinstance(engine, OpenAICompatibleEmbeddingEngine)
        create_embedding_engine.cache_clear()

    def test_cache_clear_function_exists(self):
        from cognee.infrastructure.databases.vector.embeddings.get_embedding_engine import (
            clear_embedding_engine_cache,
        )
        # Should not raise
        clear_embedding_engine_cache()


# ---------------------------------------------------------------------------
# _create_user_embedding_engine tests
# ---------------------------------------------------------------------------

class TestUserEmbeddingEngine:
    """Tests for user-DB-resolved embedding engine creation."""

    def test_create_user_engine_openai_compatible(self):
        from cognee.infrastructure.databases.vector.embeddings.get_embedding_engine import (
            _create_user_embedding_engine,
        )
        engine = _create_user_embedding_engine(
            provider_id="dashscope",
            model_id="text-embedding-v3",
            api_key="sk-test",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        from cognee.infrastructure.databases.vector.embeddings.OpenAICompatibleEmbeddingEngine import (
            OpenAICompatibleEmbeddingEngine,
        )
        assert isinstance(engine, OpenAICompatibleEmbeddingEngine)
        assert engine.api_key == "sk-test"

    def test_create_user_engine_ollama(self):
        pytest.importorskip("transformers", reason="transformers not installed")
        from cognee.infrastructure.databases.vector.embeddings.get_embedding_engine import (
            _create_user_embedding_engine,
        )
        engine = _create_user_embedding_engine(
            provider_id="ollama",
            model_id="nomic-embed-text",
            api_key="",
            base_url="http://localhost:11434/api/embeddings",
        )
        from cognee.infrastructure.databases.vector.embeddings.OllamaEmbeddingEngine import (
            OllamaEmbeddingEngine,
        )
        assert isinstance(engine, OllamaEmbeddingEngine)
