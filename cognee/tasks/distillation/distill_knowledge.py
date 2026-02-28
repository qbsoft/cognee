"""
Auto Knowledge Distillation task for the cognify pipeline.

Automatically generates cross-chunk aggregated knowledge (enumerations,
aggregations, disambiguations, negation statements, Q&A pairs) from document
chunks to improve retrieval precision. This eliminates the need for manually
created supplementary knowledge files.
"""
import asyncio
import json
from collections import defaultdict
from typing import List
from uuid import uuid5, UUID

from pydantic import BaseModel, Field

from cognee.infrastructure.engine.models.KnowledgeDistillation import KnowledgeDistillation
from cognee.infrastructure.llm.LLMGateway import LLMGateway
from cognee.infrastructure.llm.prompts import render_prompt, read_query_prompt
from cognee.modules.chunking.models.DocumentChunk import DocumentChunk
from cognee.root_dir import get_absolute_path
from cognee.shared.logging_utils import get_logger
from cognee.tasks.storage.add_data_points import add_data_points

logger = get_logger("distill_knowledge")

# Prompt base directory
PROMPTS_DIR = get_absolute_path("./tasks/distillation/prompts")

# Max characters per LLM call (conservative estimate: ~4 chars/token, 6000 tokens)
DEFAULT_CONTEXT_CHAR_LIMIT = 24000


class DistillationItem(BaseModel):
    """Single distillation item returned by the LLM."""
    type: str = Field(description="Distillation type: enumeration, aggregation, disambiguation, negation, or qa")
    text: str = Field(description="The distilled knowledge content")


class DistillationResponse(BaseModel):
    """Structured response from the LLM containing all distillation items."""
    items: List[DistillationItem] = Field(
        description="List of knowledge distillation items",
        default_factory=list,
    )


async def distill_knowledge(
    data_chunks: List[DocumentChunk],
    context_char_limit: int = DEFAULT_CONTEXT_CHAR_LIMIT,
) -> List[DocumentChunk]:
    """
    Generate knowledge distillations from document chunks.

    Groups chunks by document, sends each document's combined text to an LLM
    for knowledge distillation, stores the results as KnowledgeDistillation
    DataPoints, and returns the original chunks unchanged.

    This task follows the same pattern as extract_graph_from_data:
    - Internally calls add_data_points() to store generated knowledge
    - Returns original data_chunks unchanged for downstream tasks

    Parameters:
    -----------
        data_chunks: List of DocumentChunk objects from the pipeline.
        context_char_limit: Maximum characters per LLM call.
            Documents exceeding this limit are processed in batches
            with a final merge pass.

    Returns:
    --------
        The original list of DocumentChunk objects (unchanged).
    """
    if not data_chunks:
        return data_chunks

    # Group chunks by document_id
    doc_chunks_map = defaultdict(list)
    for chunk in data_chunks:
        doc_id = _get_document_id(chunk)
        doc_chunks_map[doc_id].append(chunk)

    logger.info(
        f"Knowledge distillation: processing {len(doc_chunks_map)} document(s) "
        f"from {len(data_chunks)} chunk(s)"
    )

    # Process each document
    all_distillation_points = []
    tasks = []

    for doc_id, chunks in doc_chunks_map.items():
        tasks.append(
            _distill_single_document(doc_id, chunks, context_char_limit)
        )

    # Use semaphore to limit concurrent LLM calls
    semaphore = asyncio.Semaphore(3)

    async def _limited_distill(coro):
        async with semaphore:
            return await coro

    results = await asyncio.gather(
        *[_limited_distill(task) for task in tasks],
        return_exceptions=True,
    )

    for doc_id, result in zip(doc_chunks_map.keys(), results):
        if isinstance(result, Exception):
            logger.error(f"Distillation failed for document {doc_id}: {result}")
            continue
        all_distillation_points.extend(result)

    # Store distillation points in vector index
    if all_distillation_points:
        await add_data_points(all_distillation_points)
        logger.info(
            f"Knowledge distillation complete: "
            f"{len(all_distillation_points)} distillation points stored"
        )
    else:
        logger.warning("Knowledge distillation produced no results")

    # Return original chunks unchanged (same pattern as extract_graph_from_data)
    return data_chunks


def _get_document_id(chunk: DocumentChunk) -> UUID:
    """Extract the document ID from a chunk."""
    if hasattr(chunk, 'is_part_of') and chunk.is_part_of is not None:
        return chunk.is_part_of.id
    # Fallback: use chunk's own ID
    return chunk.id


async def _distill_single_document(
    doc_id: UUID,
    chunks: List[DocumentChunk],
    context_char_limit: int,
) -> List[KnowledgeDistillation]:
    """
    Distill knowledge from a single document's chunks.

    If the combined text exceeds context_char_limit, uses hierarchical
    distillation (map-reduce pattern):
    1. First pass: distill batches of chunks
    2. Second pass: merge batch distillations into final result
    """
    # Sort chunks by index for proper ordering
    sorted_chunks = sorted(chunks, key=lambda c: getattr(c, 'chunk_index', 0))
    combined_text = "\n\n".join(chunk.text for chunk in sorted_chunks)

    if len(combined_text) <= context_char_limit:
        # Single-pass distillation
        items = await _call_llm_distill(combined_text)
    else:
        # Hierarchical distillation for large documents
        items = await _hierarchical_distill(sorted_chunks, context_char_limit)

    # Convert to KnowledgeDistillation DataPoints
    distillation_points = []
    for idx, item in enumerate(items):
        # Generate deterministic UUID from doc_id + index
        point_id = uuid5(doc_id, f"KnowledgeDistillation_{idx}")
        point = KnowledgeDistillation(
            id=point_id,
            text=item.text,
            source_document_id=doc_id,
            distillation_type=item.type,
        )
        distillation_points.append(point)

    logger.info(
        f"Document {doc_id}: generated {len(distillation_points)} distillation points "
        f"from {len(chunks)} chunks"
    )
    return distillation_points


async def _hierarchical_distill(
    chunks: List[DocumentChunk],
    context_char_limit: int,
) -> List[DistillationItem]:
    """
    Hierarchical distillation for large documents.

    Splits chunks into batches that fit within context_char_limit,
    distills each batch, then merges all batch results in a final pass.
    """
    # Split into batches
    batches = []
    current_batch = []
    current_length = 0

    for chunk in chunks:
        chunk_len = len(chunk.text)
        if current_length + chunk_len > context_char_limit and current_batch:
            batches.append(current_batch)
            current_batch = [chunk]
            current_length = chunk_len
        else:
            current_batch.append(chunk)
            current_length += chunk_len + 2  # +2 for "\n\n" separator

    if current_batch:
        batches.append(current_batch)

    logger.info(
        f"Hierarchical distillation: {len(chunks)} chunks split into {len(batches)} batches"
    )

    # First pass: distill each batch
    batch_results = []
    for batch in batches:
        batch_text = "\n\n".join(chunk.text for chunk in batch)
        items = await _call_llm_distill(batch_text)
        batch_results.extend(items)

    # If only one batch, no merge needed
    if len(batches) <= 1:
        return batch_results

    # Second pass: merge all batch results
    merge_text = "\n\n".join(
        f"[{item.type.upper()}] {item.text}" for item in batch_results
    )

    if len(merge_text) <= context_char_limit:
        # Merge all at once
        merged_items = await _call_llm_distill(merge_text)
        return merged_items
    else:
        # If merge text is still too large, return batch results as-is
        logger.warning(
            "Merge text exceeds context limit, returning unmerged batch results"
        )
        return batch_results


async def _call_llm_distill(document_text: str) -> List[DistillationItem]:
    """
    Call the LLM to generate knowledge distillations from document text.

    Uses response_model=str to avoid instructor's heavy JSON schema injection
    which can cause Connection errors with some API providers (e.g. DashScope).
    The JSON is parsed manually from the string response.

    Returns a list of DistillationItem objects.
    """
    # Load prompts
    system_prompt = read_query_prompt(
        "distill_knowledge_system.txt",
        base_directory=PROMPTS_DIR,
    )

    context = {"document_text": document_text}
    text_input = render_prompt(
        "distill_knowledge_input.txt",
        context,
        base_directory=PROMPTS_DIR,
    )

    try:
        # Use response_model=str to avoid instructor overhead (large JSON schema
        # injection causes Connection errors with DashScope/Qwen APIs)
        response = await LLMGateway.acreate_structured_output(
            text_input=text_input,
            system_prompt=system_prompt,
            response_model=str,
        )

        if not response or not isinstance(response, str):
            logger.warning("LLM returned empty or non-string response")
            return []

        return _parse_distillation_response(response)

    except Exception as e:
        logger.error(f"LLM distillation call failed: {e}")
        return []


def _parse_distillation_response(response_text: str) -> List[DistillationItem]:
    """
    Parse the LLM's text response into DistillationItem objects.

    Handles multiple JSON formats:
    1. JSON array: [{"type": "...", "text": "..."}, ...]
    2. JSON object with 'items' key: {"items": [...]}
    3. JSON embedded in markdown code blocks: ```json ... ```
    """
    valid_types = {"enumeration", "aggregation", "disambiguation", "negation", "qa"}
    text = response_text.strip()

    # Extract JSON from markdown code blocks if present
    if "```" in text:
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            text = json_match.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array or object in the text
        for start_char, end_char in [('[', ']'), ('{', '}')]:
            start_idx = text.find(start_char)
            end_idx = text.rfind(end_char)
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    parsed = json.loads(text[start_idx:end_idx + 1])
                    break
                except json.JSONDecodeError:
                    continue
        else:
            logger.error(f"Failed to parse JSON from LLM response (first 200 chars): {text[:200]}")
            return []

    # Normalize to list of items
    items_list = []
    if isinstance(parsed, list):
        items_list = parsed
    elif isinstance(parsed, dict):
        if 'items' in parsed:
            items_list = parsed['items']
        else:
            # Single item
            items_list = [parsed]

    # Validate and convert
    valid_items = []
    for raw_item in items_list:
        if not isinstance(raw_item, dict):
            continue
        item_type = raw_item.get('type', '').strip().lower()
        item_text = raw_item.get('text', '').strip()

        if item_type not in valid_types:
            logger.warning(f"Unknown distillation type '{item_type}', skipping")
            continue
        if not item_text:
            continue

        valid_items.append(DistillationItem(type=item_type, text=item_text))

    logger.info(f"Parsed {len(valid_items)} valid distillation items from LLM response")
    return valid_items
