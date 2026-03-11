"""
OpenAI-compatible embedding engine.

Replaces LiteLLMEmbeddingEngine by calling the /v1/embeddings endpoint
directly via the ``openai`` SDK.  Works with any provider that exposes an
OpenAI-compatible API: DashScope, DeepSeek, Zhipu, Moonshot, SiliconFlow,
OpenAI, Mistral, vLLM, LM Studio, etc.
"""

import asyncio
import logging
import math
import os
from typing import List, Optional

import numpy as np
from openai import AsyncOpenAI, APIError, APIConnectionError, APITimeoutError
from tenacity import (
    retry,
    stop_after_delay,
    wait_exponential_jitter,
    before_sleep_log,
    retry_if_exception_type,
)

from cognee.shared.logging_utils import get_logger
from cognee.infrastructure.databases.vector.embeddings.EmbeddingEngine import EmbeddingEngine
from cognee.infrastructure.databases.exceptions import EmbeddingException
from cognee.infrastructure.llm.tokenizer.TikToken import TikTokenTokenizer
from cognee.infrastructure.llm.tokenizer.HuggingFace import HuggingFaceTokenizer

logger = get_logger("OpenAICompatibleEmbeddingEngine")


class OpenAICompatibleEmbeddingEngine(EmbeddingEngine):
    """
    Embedding engine that calls any OpenAI-compatible ``/v1/embeddings``
    endpoint using the ``openai`` async SDK.

    Public methods
    --------------
    - embed_text : embed a list of strings into vectors
    - get_vector_size : return embedding dimensionality
    - get_batch_size : return batch size for caller-level batching
    """

    def __init__(
        self,
        model: str = "text-embedding-v3",
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        dimensions: int = 1024,
        max_completion_tokens: int = 8191,
        batch_size: int = 36,
    ):
        self.model = model
        self.api_key = api_key or ""
        self.endpoint = endpoint
        self.dimensions = dimensions
        self.max_completion_tokens = max_completion_tokens
        self.batch_size = batch_size

        # Build the async client
        client_kwargs: dict = {"api_key": self.api_key}
        if self.endpoint:
            client_kwargs["base_url"] = self.endpoint
        self._client = AsyncOpenAI(**client_kwargs)

        # Tokenizer (best-effort: TikToken for OpenAI-style, fallback for others)
        self.tokenizer = self._load_tokenizer()

        # Mock mode
        enable_mocking = os.getenv("MOCK_EMBEDDING", "false")
        if isinstance(enable_mocking, bool):
            enable_mocking = str(enable_mocking).lower()
        self.mock = enable_mocking in ("true", "1", "yes")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_delay(128),
        wait=wait_exponential_jitter(2, 128),
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError)),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
        reraise=True,
    )
    async def embed_text(self, text: List[str]) -> List[List[float]]:
        """Embed *text* and return a list of float vectors."""
        if self.mock:
            return [[0.0] * self.dimensions for _ in text]

        try:
            # Some providers (e.g. older DashScope) don't support the
            # ``dimensions`` parameter – pass it only when it makes sense.
            kwargs: dict = {"model": self.model, "input": text}
            if self.dimensions and self._supports_dimensions():
                kwargs["dimensions"] = self.dimensions

            response = await self._client.embeddings.create(**kwargs)
            return [item.embedding for item in response.data]

        except APIError as exc:
            # Context-window exceeded – split & retry
            if "context" in str(exc).lower() or "too many tokens" in str(exc).lower():
                return await self._handle_context_overflow(text, exc)
            logger.error("Embedding API error with model %s: %s", self.model, exc)
            raise EmbeddingException(
                f"Failed to embed using model {self.model}"
            ) from exc

        except Exception as exc:
            logger.error("Error embedding text: %s", exc)
            raise

    def get_vector_size(self) -> int:
        return self.dimensions

    def get_batch_size(self) -> int:
        return self.batch_size

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _supports_dimensions(self) -> bool:
        """Return True if the model/provider likely supports the dimensions param."""
        model_lower = self.model.lower()
        # OpenAI text-embedding-3-* supports it; most Chinese providers don't
        if "text-embedding-3" in model_lower:
            return True
        # DashScope text-embedding-v3 supports dimensions
        if "text-embedding-v3" in model_lower:
            return True
        return False

    async def _handle_context_overflow(
        self, text: List[str], original_error: Exception
    ) -> List[List[float]]:
        """Split oversized input and recursively embed."""
        if isinstance(text, list) and len(text) > 1:
            mid = math.ceil(len(text) / 2)
            left_vecs, right_vecs = await asyncio.gather(
                self.embed_text(text[:mid]),
                self.embed_text(text[mid:]),
            )
            return left_vecs + right_vecs

        if isinstance(text, list) and len(text) == 1:
            s = text[0]
            logger.debug("Pooling embeddings for oversized string (len=%d)", len(s))
            third = len(s) // 3
            left_part, right_part = s[: third * 2], s[third:]
            (left_vec,), (right_vec,) = await asyncio.gather(
                self.embed_text([left_part]),
                self.embed_text([right_part]),
            )
            pooled = (np.array(left_vec) + np.array(right_vec)) / 2
            return [pooled.tolist()]

        raise original_error

    def _load_tokenizer(self):
        """Best-effort tokenizer selection."""
        model_short = self.model.split("/")[-1]
        try:
            return TikTokenTokenizer(
                model=model_short,
                max_completion_tokens=self.max_completion_tokens,
            )
        except Exception:
            pass
        try:
            return HuggingFaceTokenizer(
                model=self.model,
                max_completion_tokens=self.max_completion_tokens,
            )
        except Exception:
            pass
        # Ultimate fallback – TikToken with default encoding
        return TikTokenTokenizer(
            model=None,
            max_completion_tokens=self.max_completion_tokens,
        )
