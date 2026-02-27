"""
Hybrid retriever module.
Fuses vector retrieval + graph retrieval + lexical retrieval using
Reciprocal Rank Fusion (RRF) algorithm.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

RRF_K = 60


def reciprocal_rank_fusion(
    result_lists: List[List[Dict[str, Any]]],
    weights: Optional[List[float]] = None,
    k: int = RRF_K,
) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) algorithm.

    Merges multiple ranked result lists into a single list using weighted RRF scores.

    Args:
        result_lists: List of result lists, each containing dicts with at least an "id" key.
        weights: Optional list of weights for each result list. If None, equal weights are used.
        k: RRF constant (default 60). Higher values reduce the impact of rank differences.

    Returns:
        Merged and sorted list of results with added "rrf_score" field.
    """
    if not result_lists:
        return []

    n_lists = len(result_lists)

    if weights is None:
        weights = [1.0 / n_lists] * n_lists
    else:
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            weights = [1.0 / n_lists] * n_lists

    doc_scores: Dict[str, float] = {}
    doc_data: Dict[str, Dict[str, Any]] = {}

    for list_idx, results in enumerate(result_lists):
        weight = weights[list_idx]
        for rank, result in enumerate(results):
            doc_id = result.get("id", str(rank))
            rrf_score = weight * (1.0 / (k + rank + 1))

            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0.0
                doc_data[doc_id] = result.copy()

            doc_scores[doc_id] += rrf_score

    sorted_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)

    result = []
    for doc_id in sorted_ids:
        item = doc_data[doc_id].copy()
        item["rrf_score"] = doc_scores[doc_id]
        result.append(item)

    return result


class HybridRetriever:
    """
    Hybrid retriever that combines vector, graph, and lexical retrieval
    using Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        vector_retriever=None,
        graph_retriever=None,
        lexical_retriever=None,
        weights: Optional[Dict[str, float]] = None,
        top_k: int = 20,
    ):
        """
        Args:
            vector_retriever: Async callable for vector search.
            graph_retriever: Async callable for graph search.
            lexical_retriever: Async callable for lexical search.
            weights: Dict with keys "vector", "graph", "lexical" and float values.
            top_k: Maximum number of results to return.
        """
        self._vector = vector_retriever
        self._graph = graph_retriever
        self._lexical = lexical_retriever
        self._weights = weights or {"vector": 0.4, "graph": 0.3, "lexical": 0.3}
        self._top_k = top_k

    async def get_completion(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Execute hybrid retrieval: run all configured retrievers in parallel,
        then fuse results using RRF.

        Args:
            query: The search query string.
            **kwargs: Additional keyword arguments passed to each retriever.

        Returns:
            Fused and ranked list of results.
        """
        tasks = []
        retrievers = []

        if self._vector:
            tasks.append(self._safe_retrieve(self._vector, query, **kwargs))
            retrievers.append("vector")
        if self._graph:
            tasks.append(self._safe_retrieve(self._graph, query, **kwargs))
            retrievers.append("graph")
        if self._lexical:
            tasks.append(self._safe_retrieve(self._lexical, query, **kwargs))
            retrievers.append("lexical")

        if not tasks:
            return []

        results = await asyncio.gather(*tasks)

        weights = [self._weights.get(r, 0.33) for r in retrievers]
        fused = reciprocal_rank_fusion(list(results), weights=weights)

        return fused[: self._top_k]

    async def get_context(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Execute hybrid retrieval and return fused context (for graph visualization).

        Args:
            query: The search query string.
            **kwargs: Additional keyword arguments passed to each retriever.

        Returns:
            Fused and ranked list of context results.
        """
        return await self.get_completion(query, **kwargs)

    async def _safe_retrieve(self, retriever, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Safely call a retriever, returning empty list on failure."""
        try:
            return await retriever(query, **kwargs)
        except Exception as e:
            logger.warning(f"Retriever call failed: {e}")
            return []
