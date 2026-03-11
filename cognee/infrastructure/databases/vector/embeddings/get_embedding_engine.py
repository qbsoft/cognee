"""
Factory for creating embedding engine instances.

Supports three engines:
- ``fastembed``  – local CPU-based (FastEmbed library)
- ``ollama``     – local GPU-based (Ollama server)
- everything else – OpenAI-compatible API via ``openai`` SDK

The default path reads from ``.env`` / ``EmbeddingConfig``.
``get_embedding_engine_for_user()`` adds user-DB config resolution
(priority: user DB > .env).
"""

from cognee.infrastructure.databases.vector.embeddings.config import get_embedding_config
from cognee.infrastructure.llm.config import get_llm_config
from .EmbeddingEngine import EmbeddingEngine
from functools import lru_cache


def get_embedding_engine() -> EmbeddingEngine:
    """
    Return a singleton embedding engine based on .env / EmbeddingConfig.
    """
    config = get_embedding_config()
    llm_config = get_llm_config()
    return create_embedding_engine(
        config.embedding_provider,
        config.embedding_model,
        config.embedding_dimensions,
        config.embedding_max_completion_tokens,
        config.embedding_endpoint,
        config.embedding_api_key,
        config.embedding_api_version,
        config.embedding_batch_size,
        config.huggingface_tokenizer,
        llm_config.llm_api_key,
        llm_config.llm_provider,
    )


async def get_embedding_engine_for_user(user_id: str) -> EmbeddingEngine:
    """
    Return an embedding engine resolved from the user's DB config.

    Priority: user DB config > .env defaults.
    Falls back to the default ``get_embedding_engine()`` when no user
    config is found.
    """
    try:
        from cognee.infrastructure.llm.providers.service import ModelProviderService

        resolved = await ModelProviderService.resolve_model_config(
            user_id, task_type="embedding"
        )
        if resolved.source == "user" and resolved.api_key:
            # User has configured an embedding provider – build a dedicated engine
            return _create_user_embedding_engine(
                provider_id=resolved.provider_id,
                model_id=resolved.model_id,
                api_key=resolved.api_key,
                base_url=resolved.base_url,
            )
    except Exception:
        pass  # Fall through to default

    return get_embedding_engine()


def _create_user_embedding_engine(
    provider_id: str,
    model_id: str,
    api_key: str,
    base_url: str | None = None,
) -> EmbeddingEngine:
    """
    Build an embedding engine from user-DB-resolved config.

    Does NOT use ``@lru_cache`` – each user may have different creds.
    In practice this is called once per request/session, not in a hot loop.
    """
    config = get_embedding_config()  # for defaults (dimensions, batch_size, etc.)

    if provider_id == "ollama":
        from .OllamaEmbeddingEngine import OllamaEmbeddingEngine

        return OllamaEmbeddingEngine(
            model=model_id,
            dimensions=config.embedding_dimensions,
            max_completion_tokens=config.embedding_max_completion_tokens,
            endpoint=base_url or "http://localhost:11434/api/embeddings",
            huggingface_tokenizer=config.huggingface_tokenizer or "Salesforce/SFR-Embedding-Mistral",
            batch_size=config.embedding_batch_size,
        )

    # All other providers → OpenAI-compatible
    from .OpenAICompatibleEmbeddingEngine import OpenAICompatibleEmbeddingEngine

    return OpenAICompatibleEmbeddingEngine(
        model=model_id,
        api_key=api_key,
        endpoint=base_url,
        dimensions=config.embedding_dimensions,
        max_completion_tokens=config.embedding_max_completion_tokens,
        batch_size=config.embedding_batch_size,
    )


@lru_cache
def create_embedding_engine(
    embedding_provider,
    embedding_model,
    embedding_dimensions,
    embedding_max_completion_tokens,
    embedding_endpoint,
    embedding_api_key,
    embedding_api_version,
    embedding_batch_size,
    huggingface_tokenizer,
    llm_api_key,
    llm_provider,
):
    """
    Create and return a cached embedding engine based on the provider.
    """
    if embedding_provider == "fastembed":
        from .FastembedEmbeddingEngine import FastembedEmbeddingEngine

        return FastembedEmbeddingEngine(
            model=embedding_model,
            dimensions=embedding_dimensions,
            max_completion_tokens=embedding_max_completion_tokens,
            batch_size=embedding_batch_size,
        )

    if embedding_provider == "ollama":
        from .OllamaEmbeddingEngine import OllamaEmbeddingEngine

        return OllamaEmbeddingEngine(
            model=embedding_model,
            dimensions=embedding_dimensions,
            max_completion_tokens=embedding_max_completion_tokens,
            endpoint=embedding_endpoint,
            huggingface_tokenizer=huggingface_tokenizer,
            batch_size=embedding_batch_size,
        )

    # All other providers → OpenAI-compatible (replaces LiteLLM)
    from .OpenAICompatibleEmbeddingEngine import OpenAICompatibleEmbeddingEngine

    effective_api_key = embedding_api_key or (
        embedding_api_key if llm_provider == "custom" else llm_api_key
    )

    return OpenAICompatibleEmbeddingEngine(
        model=embedding_model,
        api_key=effective_api_key,
        endpoint=embedding_endpoint,
        dimensions=embedding_dimensions,
        max_completion_tokens=embedding_max_completion_tokens,
        batch_size=embedding_batch_size,
    )


def clear_embedding_engine_cache():
    """Invalidate the cached embedding engine singleton.

    Call this after a user changes embedding config via the UI so the
    next ``get_embedding_engine()`` call picks up the new settings.
    """
    create_embedding_engine.cache_clear()
