from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import (
    get_llm_client,
)
from cognee.infrastructure.llm.LLMGateway import LLMGateway
from cognee.shared.logging_utils import get_logger

logger = get_logger()

# Local model token limits — replaces litellm.model_cost
# Only commonly used models are listed; unknown models return None.
_MODEL_MAX_TOKENS: dict[str, int] = {
    # OpenAI
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4.1": 1047576,
    "gpt-4.1-mini": 1047576,
    "gpt-3.5-turbo": 16385,
    "o1": 200000,
    "o1-mini": 128000,
    "o3": 200000,
    "o3-mini": 200000,
    "o4-mini": 200000,
    # DashScope / Qwen
    "qwen-plus": 131072,
    "qwen-plus-latest": 131072,
    "qwen-turbo": 131072,
    "qwen-turbo-latest": 131072,
    "qwen-max": 32768,
    "qwen-max-latest": 32768,
    "qwen-long": 10000000,
    # DeepSeek
    "deepseek-chat": 65536,
    "deepseek-reasoner": 65536,
    # Anthropic
    "claude-3-opus-20240229": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-haiku-20240307": 200000,
    "claude-sonnet-4-20250514": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    # Gemini
    "gemini-pro": 32768,
    "gemini-1.5-pro": 2097152,
    "gemini-2.0-flash": 1048576,
    # Mistral
    "mistral-large-latest": 128000,
    "mistral-small-latest": 128000,
    # Embeddings
    "text-embedding-3-large": 8191,
    "text-embedding-3-small": 8191,
    "text-embedding-v3": 8192,
    "text-embedding-v2": 2048,
}


def get_max_chunk_tokens():
    """
    Calculate the maximum number of tokens allowed in a chunk.
    """
    # NOTE: Import must be done in function to avoid circular import issue
    from cognee.infrastructure.databases.vector import get_vector_engine

    embedding_engine = get_vector_engine().embedding_engine
    llm_client = get_llm_client(raise_api_key_error=False)

    llm_cutoff_point = llm_client.max_completion_tokens // 2
    max_chunk_tokens = min(embedding_engine.max_completion_tokens, llm_cutoff_point)

    return max_chunk_tokens


def get_model_max_completion_tokens(model_name: str):
    """
    Retrieve the maximum token limit for a specified model name.

    Checks the local model token dictionary first. Falls back to None
    for unknown models.
    """
    # Try exact match
    if model_name in _MODEL_MAX_TOKENS:
        max_tokens = _MODEL_MAX_TOKENS[model_name]
        logger.debug(f"Max input tokens for {model_name}: {max_tokens}")
        return max_tokens

    # Try without provider prefix (e.g. "openai/gpt-4o" → "gpt-4o")
    short_name = model_name.split("/")[-1] if "/" in model_name else None
    if short_name and short_name in _MODEL_MAX_TOKENS:
        max_tokens = _MODEL_MAX_TOKENS[short_name]
        logger.debug(f"Max input tokens for {model_name}: {max_tokens}")
        return max_tokens

    logger.debug(f"Model {model_name} not found in local model token dict.")
    return None


async def test_llm_connection():
    """Test connection to the LLM."""
    try:
        await LLMGateway.acreate_structured_output(
            text_input="test",
            system_prompt='Respond to me with the following string: "test"',
            response_model=str,
        )
    except Exception as e:
        logger.error(e)
        logger.error("Connection to LLM could not be established.")
        raise e


async def test_embedding_connection():
    """Test the connection to the embedding engine."""
    try:
        from cognee.infrastructure.databases.vector import get_vector_engine
        await get_vector_engine().embedding_engine.embed_text("test")
    except Exception as e:
        logger.error(e)
        logger.error("Connection to Embedding handler could not be established.")
        raise e
