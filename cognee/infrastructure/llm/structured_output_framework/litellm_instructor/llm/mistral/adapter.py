import instructor
from pydantic import BaseModel
from typing import Type
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, BadRequestError

from cognee.shared.logging_utils import get_logger
from cognee.modules.observability.get_observe import get_observe
from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.llm_interface import (
    LLMInterface,
)
from cognee.infrastructure.llm.config import get_llm_config

import logging
from tenacity import (
    retry,
    stop_after_delay,
    wait_exponential_jitter,
    retry_if_exception_type,
    before_sleep_log,
)

logger = get_logger()
observe = get_observe()


class MistralAdapter(LLMInterface):
    """
    Adapter for Mistral AI API, for structured output generation and prompt display.

    Public methods:
    - acreate_structured_output
    - show_prompt
    """

    name = "Mistral"
    model: str
    api_key: str
    max_completion_tokens: int

    def __init__(self, api_key: str, model: str, max_completion_tokens: int, endpoint: str = None):
        self.model = model
        self.max_completion_tokens = max_completion_tokens

        # Mistral supports OpenAI-compatible API
        client_kwargs = {"api_key": api_key or get_llm_config().llm_api_key}
        if endpoint:
            client_kwargs["base_url"] = endpoint
        else:
            client_kwargs["base_url"] = "https://api.mistral.ai/v1"

        async_client = AsyncOpenAI(**client_kwargs)
        self.aclient = instructor.from_openai(async_client, mode=instructor.Mode.JSON)

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
        """
        Generate a response from the user query.
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": f"""Use the given format to extract information
                from the following input: {text_input}""",
                },
            ]
            try:
                response = await self.aclient.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_completion_tokens,
                    max_retries=5,
                    messages=messages,
                    response_model=response_model,
                    temperature=get_llm_config().llm_temperature,
                )
                if response.choices and response.choices[0].message.content:
                    content = response.choices[0].message.content
                    return response_model.model_validate_json(content)
                else:
                    raise ValueError("Failed to get valid response after retries")
            except BadRequestError as e:
                logger.error(f"Bad request error: {str(e)}")
                raise ValueError(f"Invalid request: {str(e)}")

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Schema validation failed: {str(e)}")
            raise ValueError(f"Response failed schema validation: {str(e)}")
