"""Adapter for Generic API LLM provider API (OpenAI-compatible endpoints)"""

import instructor
from typing import Type
from pydantic import BaseModel
from openai import AsyncOpenAI, ContentFilterFinishReasonError, APIConnectionError, APITimeoutError
from instructor.core import InstructorRetryException

from cognee.infrastructure.llm.exceptions import ContentPolicyFilterError
from cognee.infrastructure.llm.config import get_llm_config
from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.llm_interface import (
    LLMInterface,
)
import logging
from cognee.shared.logging_utils import get_logger
from tenacity import (
    retry,
    stop_after_delay,
    wait_exponential_jitter,
    retry_if_exception_type,
    before_sleep_log,
)

logger = get_logger()


class GenericAPIAdapter(LLMInterface):
    """
    Adapter for Generic API LLM provider API (OpenAI-compatible endpoints).

    Supports DashScope, DeepSeek, Zhipu, Moonshot, SiliconFlow, vLLM, LM Studio,
    and any other provider with an OpenAI-compatible /v1/chat/completions endpoint.
    """

    name: str
    model: str
    api_key: str

    def __init__(
        self,
        endpoint,
        api_key: str,
        model: str,
        name: str,
        max_completion_tokens: int,
        fallback_model: str = None,
        fallback_api_key: str = None,
        fallback_endpoint: str = None,
    ):
        self.name = name
        self.model = model
        self.api_key = api_key
        self.endpoint = endpoint
        self.max_completion_tokens = max_completion_tokens

        self.fallback_model = fallback_model
        self.fallback_api_key = fallback_api_key
        self.fallback_endpoint = fallback_endpoint

        # Build OpenAI-compatible async client
        client_kwargs = {"api_key": api_key or ""}
        if endpoint:
            client_kwargs["base_url"] = endpoint
        async_client = AsyncOpenAI(**client_kwargs)
        self.aclient = instructor.from_openai(async_client, mode=instructor.Mode.JSON)

        # Build fallback client if configured
        self._fallback_aclient = None
        if fallback_model and fallback_api_key and fallback_endpoint:
            fb_client = AsyncOpenAI(api_key=fallback_api_key, base_url=fallback_endpoint)
            self._fallback_aclient = instructor.from_openai(fb_client, mode=instructor.Mode.JSON)

    @retry(
        stop=stop_after_delay(128),
        wait=wait_exponential_jitter(2, 128),
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.DEBUG),
        reraise=True,
    )
    async def acreate_structured_output(
        self, text_input: str, system_prompt: str, response_model: Type[BaseModel]
    ) -> BaseModel:
        """Generate a structured response from a user query."""

        try:
            return await self.aclient.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": f"""{text_input}""",
                    },
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                ],
                max_retries=5,
                response_model=response_model,
                temperature=get_llm_config().llm_temperature,
            )
        except (
            ContentFilterFinishReasonError,
            InstructorRetryException,
        ) as error:
            if (
                isinstance(error, InstructorRetryException)
                and "content management policy" not in str(error).lower()
            ):
                raise error

            if not self._fallback_aclient:
                raise ContentPolicyFilterError(
                    f"The provided input contains content that is not aligned with our content policy: {text_input}"
                ) from error

            try:
                return await self._fallback_aclient.chat.completions.create(
                    model=self.fallback_model,
                    messages=[
                        {
                            "role": "user",
                            "content": f"""{text_input}""",
                        },
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                    ],
                    max_retries=5,
                    response_model=response_model,
                    temperature=get_llm_config().llm_temperature,
                )
            except (
                ContentFilterFinishReasonError,
                InstructorRetryException,
            ) as error:
                if (
                    isinstance(error, InstructorRetryException)
                    and "content management policy" not in str(error).lower()
                ):
                    raise error
                else:
                    raise ContentPolicyFilterError(
                        f"The provided input contains content that is not aligned with our content policy: {text_input}"
                    ) from error
