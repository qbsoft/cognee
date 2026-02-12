"""
Reranking module. Uses BGE-Reranker model to rerank retrieval results.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

_reranker_model = None


def _get_reranker_model(model_name: str = "BAAI/bge-reranker-v2-m3"):
    """
    Load and cache the reranker model (singleton pattern).

    Args:
        model_name: HuggingFace model name for the reranker.

    Returns:
        FlagReranker model instance.

    Raises:
        ImportError: If FlagEmbedding is not installed.
    """
    global _reranker_model
    if _reranker_model is None:
        try:
            from FlagEmbedding import FlagReranker

            _reranker_model = FlagReranker(model_name, use_fp16=True)
            logger.info(f"Reranker model loaded: {model_name}")
        except ImportError:
            raise ImportError(
                "FlagEmbedding is not installed. "
                "Please run: uv pip install FlagEmbedding"
            )
    return _reranker_model


async def rerank(
    query: str,
    results: List[Dict[str, Any]],
    top_k: int = 10,
    model_name: str = "BAAI/bge-reranker-v2-m3",
    text_field: str = "text",
) -> List[Dict[str, Any]]:
    """
    Rerank retrieval results using a cross-encoder reranker model.

    Args:
        query: The search query string.
        results: List of result dicts, each containing at least a text field.
        top_k: Maximum number of results to return after reranking.
        model_name: HuggingFace model name for the reranker.
        text_field: Key in result dicts that contains the text to rerank on.

    Returns:
        Reranked list of results with added "rerank_score" field,
        sorted by score descending, truncated to top_k.
        Falls back to original order if model loading or scoring fails.
    """
    if not results:
        return []

    try:
        model = _get_reranker_model(model_name)

        pairs = [[query, r.get(text_field, "")] for r in results]

        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(None, model.compute_score, pairs)

        if not isinstance(scores, list):
            scores = [scores]

        scored_results = []
        for result, score in zip(results, scores):
            item = result.copy()
            item["rerank_score"] = float(score)
            scored_results.append(item)

        scored_results.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored_results[:top_k]

    except Exception as e:
        logger.warning(f"Reranking failed ({e}), returning original results")
        return results[:top_k]
