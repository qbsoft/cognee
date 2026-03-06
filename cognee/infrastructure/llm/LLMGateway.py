from typing import Type, Optional, Coroutine
from pydantic import BaseModel
from cognee.infrastructure.llm import get_llm_config


def _get_model_for_task(task_type: str):
    """Get the model override for a given task type from YAML config.

    Returns None if no override is configured (use default model).
    """
    if task_type == "default":
        return None

    try:
        from cognee.infrastructure.config.yaml_config import get_module_config
        model_cfg = get_module_config("model_selection").get("models", {})
    except Exception:
        return None

    if task_type == "extraction":
        model = model_cfg.get("extraction_model", "")
        return model if model else None
    elif task_type == "graph_extraction":
        # Graph extraction is quality-critical, uses dedicated model or default
        model = model_cfg.get("graph_extraction_model", "")
        return model if model else None
    elif task_type == "answer":
        model = model_cfg.get("answer_model", "")
        return model if model else None

    return None


class LLMGateway:
    """
    Class handles selection of structured output frameworks and LLM functions.
    Class used as a namespace for LLM related functions, should not be instantiated, all methods are static.
    """

    @staticmethod
    async def acreate_structured_output(
        text_input: str, system_prompt: str, response_model: Type[BaseModel],
        task_type: str = "default"
    ):
        from cognee.infrastructure.llm.llm_cache import (
            get_cached_response, set_cached_response, is_cache_enabled
        )

        llm_config = get_llm_config()
        model_override = _get_model_for_task(task_type)
        effective_model = model_override or llm_config.llm_model

        # Check cache (for extraction and graph_extraction tasks)
        if task_type in ("extraction", "graph_extraction") and is_cache_enabled():
            cached = get_cached_response(
                effective_model, system_prompt, text_input, response_model
            )
            if cached is not None:
                return cached

        # Call LLM
        if llm_config.structured_output_framework.upper() == "BAML":
            from cognee.infrastructure.llm.structured_output_framework.baml.baml_src.extraction import (
                acreate_structured_output,
            )

            result = await acreate_structured_output(
                text_input=text_input,
                system_prompt=system_prompt,
                response_model=response_model,
            )
        else:
            from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import (
                get_llm_client,
            )

            llm_client = get_llm_client(model_override=model_override)
            result = await llm_client.acreate_structured_output(
                text_input=text_input, system_prompt=system_prompt, response_model=response_model
            )

        # Store in cache (for extraction and graph_extraction tasks)
        if task_type in ("extraction", "graph_extraction") and is_cache_enabled():
            set_cached_response(
                effective_model, system_prompt, text_input, response_model, result
            )

        return result

    @staticmethod
    def create_structured_output(
        text_input: str, system_prompt: str, response_model: Type[BaseModel]
    ) -> BaseModel:
        from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import (
            get_llm_client,
        )

        llm_client = get_llm_client()
        return llm_client.create_structured_output(
            text_input=text_input, system_prompt=system_prompt, response_model=response_model
        )

    @staticmethod
    def create_transcript(input) -> Coroutine:
        from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import (
            get_llm_client,
        )

        llm_client = get_llm_client()
        return llm_client.create_transcript(input=input)

    @staticmethod
    def transcribe_image(input) -> Coroutine:
        from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import (
            get_llm_client,
        )

        llm_client = get_llm_client()
        return llm_client.transcribe_image(input=input)
