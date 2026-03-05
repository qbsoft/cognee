"""
Parallel processing wrapper for cognify pipeline tasks.

Runs distill_knowledge and summarize_text concurrently since both
independently read from data_chunks. distill_knowledge stores its
results internally, while summarize_text's output is passed downstream.
"""
import asyncio
from typing import List, Type, Optional
from pydantic import BaseModel

from cognee.modules.chunking.models.DocumentChunk import DocumentChunk
from cognee.shared.logging_utils import get_logger

logger = get_logger("parallel_processing")


async def parallel_distill_and_summarize(
    data_chunks: List[DocumentChunk],
    summarization_model: Type[BaseModel] = None,
    context_char_limit: int = 24000,
) -> List:
    """
    Run knowledge distillation and text summarization in parallel.

    Both tasks independently read from data_chunks:
    - distill_knowledge: stores KD DataPoints internally, returns data_chunks unchanged
    - summarize_text: generates summaries, returns results for downstream tasks

    Returns summarize_text's output for pipeline continuation.
    """
    from cognee.tasks.summarization.summarize_text import summarize_text
    from cognee.tasks.distillation.distill_knowledge import distill_knowledge

    logger.info(
        f"Starting parallel distillation + summarization for {len(data_chunks)} chunks"
    )

    # Run both tasks concurrently
    distill_task = asyncio.create_task(
        distill_knowledge(data_chunks, context_char_limit=context_char_limit)
    )
    summarize_task = asyncio.create_task(
        summarize_text(data_chunks, summarization_model)
    )

    results = await asyncio.gather(
        distill_task,
        summarize_task,
        return_exceptions=True,
    )

    distill_result, summarize_result = results

    # Log results
    if isinstance(distill_result, Exception):
        logger.error(f"Parallel distillation failed: {distill_result}")
    else:
        logger.info("Parallel distillation completed successfully")

    if isinstance(summarize_result, Exception):
        logger.error(f"Parallel summarization failed: {summarize_result}")
        # If summarization failed, return original chunks
        return data_chunks
    else:
        logger.info("Parallel summarization completed successfully")

    # Return summarize_text's result (for downstream add_data_points)
    return summarize_result
