"""
LLM response cache based on content hashing.

Caches LLM responses keyed by SHA256(model + system_prompt + text_input + response_model_name).
Uses file-based storage for persistence across restarts.
Only used for extraction tasks - answer generation is never cached.
"""
import hashlib
import json
import os
import time
from typing import Optional, Type
from pydantic import BaseModel

from cognee.shared.logging_utils import get_logger

logger = get_logger("llm_cache")


def _get_cache_config() -> dict:
    """Load cache config from YAML."""
    try:
        from cognee.infrastructure.config.yaml_config import get_module_config
        return get_module_config("model_selection").get("cache", {})
    except Exception:
        return {}


def _get_cache_dir() -> str:
    """Get the cache directory path."""
    config = _get_cache_config()
    cache_dir = config.get("cache_dir", ".cognee_cache/llm")
    if not os.path.isabs(cache_dir):
        cache_dir = os.path.join(os.getcwd(), cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _compute_cache_key(
    model: str,
    system_prompt: str,
    text_input: str,
    response_model_name: str,
) -> str:
    """Compute SHA256 hash for cache key."""
    content = f"{model}|{system_prompt}|{text_input}|{response_model_name}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def is_cache_enabled() -> bool:
    """Check if LLM caching is enabled."""
    config = _get_cache_config()
    return config.get("enabled", False)


def get_cached_response(
    model: str,
    system_prompt: str,
    text_input: str,
    response_model: Type[BaseModel],
) -> Optional[BaseModel]:
    """
    Look up a cached LLM response.

    Returns the cached response model instance if found and not expired,
    otherwise returns None.
    """
    if not is_cache_enabled():
        return None

    config = _get_cache_config()
    ttl = config.get("ttl_seconds", 604800)

    response_model_name = response_model.__name__ if isinstance(response_model, type) else str(response_model)
    cache_key = _compute_cache_key(model, system_prompt, text_input, response_model_name)
    cache_file = os.path.join(_get_cache_dir(), f"{cache_key}.json")

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)

        # Check TTL
        if time.time() - cached.get("timestamp", 0) > ttl:
            os.remove(cache_file)
            return None

        # Reconstruct response model
        if response_model is str:
            return cached["response"]
        else:
            return response_model.model_validate(cached["response"])

    except Exception as e:
        logger.debug(f"Cache read failed for {cache_key[:12]}: {e}")
        return None


def set_cached_response(
    model: str,
    system_prompt: str,
    text_input: str,
    response_model: Type[BaseModel],
    response,
) -> None:
    """Store an LLM response in the cache."""
    if not is_cache_enabled():
        return

    response_model_name = response_model.__name__ if isinstance(response_model, type) else str(response_model)
    cache_key = _compute_cache_key(model, system_prompt, text_input, response_model_name)
    cache_file = os.path.join(_get_cache_dir(), f"{cache_key}.json")

    try:
        if response_model is str or isinstance(response, str):
            response_data = response
        else:
            response_data = response.model_dump()

        cached = {
            "timestamp": time.time(),
            "model": model,
            "response_model": response_model_name,
            "response": response_data,
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cached, f, ensure_ascii=False)

        logger.debug(f"Cached LLM response: {cache_key[:12]}")

    except Exception as e:
        logger.debug(f"Cache write failed for {cache_key[:12]}: {e}")
