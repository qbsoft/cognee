import asyncio
from typing import Any, Optional, Type, List
from uuid import NAMESPACE_OID, uuid5

from cognee.infrastructure.engine import DataPoint
from cognee.modules.graph.cognee_graph.CogneeGraphElements import Edge, Node
from cognee.tasks.storage import add_data_points
from cognee.modules.graph.utils import resolve_edges_to_text
from cognee.modules.graph.utils.convert_node_to_data_point import get_all_subclasses
from cognee.modules.retrieval.base_graph_retriever import BaseGraphRetriever
from cognee.modules.retrieval.utils.brute_force_triplet_search import brute_force_triplet_search
from cognee.modules.retrieval.utils.completion import generate_completion, summarize_text
from cognee.modules.retrieval.utils.session_cache import (
    save_conversation_history,
    get_conversation_history,
)
from cognee.shared.logging_utils import get_logger
from cognee.modules.retrieval.utils.extract_uuid_from_node import extract_uuid_from_node
from cognee.modules.retrieval.utils.models import CogneeUserInteraction
from cognee.modules.engine.models.node_set import NodeSet
from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.infrastructure.databases.vector import get_vector_engine
from cognee.infrastructure.databases.vector.exceptions import CollectionNotFoundError
from cognee.context_global_variables import session_user
from cognee.infrastructure.databases.cache.config import CacheConfig

logger = get_logger("GraphCompletionRetriever")

# Marker used to identify KD synthetic edges in the context list
_KD_EDGE_MARKER = "__kd_ref__"

# Marker used to identify DocumentChunk synthetic edges (direct vector search fallback)
_DC_EDGE_MARKER = "__dc_ref__"

# Marker used to identify neighbor-expanded edges for visualization only.
# These edges enrich the graph display but are excluded from LLM answer context.
_VIZ_ONLY_MARKER = "__viz_only__"

# Node types to exclude from GRAPH VISUALIZATION (frontend display).
# These are infrastructure nodes that clutter the graph without visual value.
_VIZ_FILTER_NODE_TYPES = {
    "NodeSet", "nodeset",
    "Timestamp", "timestamp",
    "DocumentChunk", "documentchunk",
    "TextSummary", "textsummary",
    "KnowledgeDistillation", "knowledgedistillation",
}

# Node types to exclude from LLM ANSWER CONTEXT (graph edges section only).
# NOTE: DocumentChunk and TextSummary are intentionally NOT filtered here —
# they contain valuable source text that serves as a safety net when KD
# vectors miss certain facts. They are also searched separately via
# _search_document_chunks() for explicit fallback.
_INTERNAL_NODE_TYPES = {
    "NodeSet", "nodeset",
    "Timestamp", "timestamp",
}


def _get_routing_config() -> dict:
    """Read document routing configuration."""
    try:
        from cognee.infrastructure.config.yaml_config import get_module_config
        search_cfg = get_module_config("search")
        return search_cfg.get("search", {}).get("document_routing", {})
    except Exception:
        return {}


def _should_enable_routing(doc_count: int) -> bool:
    """Check if document routing should be enabled based on document count."""
    config = _get_routing_config()
    min_count = config.get("min_doc_count", 20)
    enabled = config.get("enabled", True)
    return enabled and doc_count > min_count


def _filter_results_by_doc_names(results, doc_names):
    """Filter vector search results to only those matching document names.

    Uses the [来源: docname] prefix already present in KD vectors.
    If doc_names is None, all results pass through (no filtering).
    """
    if doc_names is None:
        return results

    filtered = []
    for result in results:
        text = result.payload.get("text", "") if hasattr(result, 'payload') else ""
        if any(f"[来源: {name}]" in text for name in doc_names):
            filtered.append(result)
    return filtered


class GraphCompletionRetriever(BaseGraphRetriever):
    """
    Retriever for handling graph-based completion searches.

    This class provides methods to retrieve graph nodes and edges, resolve them into a
    human-readable format, and generate completions based on graph context. Public methods
    include:
    - resolve_edges_to_text
    - get_triplets
    - get_context
    - get_completion
    """

    def __init__(
        self,
        user_prompt_path: str = "graph_context_for_question.txt",
        system_prompt_path: str = "answer_simple_question.txt",
        system_prompt: Optional[str] = None,
        top_k: Optional[int] = 5,
        node_type: Optional[Type] = None,
        node_name: Optional[List[str]] = None,
        save_interaction: bool = False,
        similarity_threshold: float = 0.5,
    ):
        """Initialize retriever with prompt paths and search parameters."""
        self.save_interaction = save_interaction
        self.user_prompt_path = user_prompt_path
        self.system_prompt_path = system_prompt_path
        self.system_prompt = system_prompt
        self.top_k = top_k if top_k is not None else 5
        self.node_type = node_type
        self.node_name = node_name
        self.similarity_threshold = similarity_threshold

    async def resolve_edges_to_text(self, retrieved_edges: list) -> str:
        """
        Converts retrieved graph edges into a human-readable string format.

        Parameters:
        -----------

            - retrieved_edges (list): A list of edges retrieved from the graph.

        Returns:
        --------

            - str: A formatted string representation of the nodes and their connections.
        """
        return await resolve_edges_to_text(retrieved_edges)

    async def get_triplets(self, query: str) -> List[Edge]:
        """
        Retrieves relevant graph triplets based on a query string.

        Parameters:
        -----------

            - query (str): The query string used to search for relevant triplets in the graph.

        Returns:
        --------

            - list: A list of found triplets that match the query.
        """
        subclasses = get_all_subclasses(DataPoint)
        vector_index_collections: List[str] = []

        for subclass in subclasses:
            # Skip KnowledgeDistillation - it's searched separately in
            # _search_knowledge_distillation() and has no graph edges anyway
            if subclass.__name__ == "KnowledgeDistillation":
                continue
            if "metadata" in subclass.model_fields:
                metadata_field = subclass.model_fields["metadata"]
                if hasattr(metadata_field, "default") and metadata_field.default is not None:
                    if isinstance(metadata_field.default, dict):
                        index_fields = metadata_field.default.get("index_fields", [])
                        for field_name in index_fields:
                            vector_index_collections.append(f"{subclass.__name__}_{field_name}")

        logger.info(
            "get_triplets: searching %d collections: %s",
            len(vector_index_collections), vector_index_collections,
        )

        found_triplets = await brute_force_triplet_search(
            query,
            top_k=self.top_k,
            similarity_threshold=self.similarity_threshold,
            collections=vector_index_collections or None,
            node_type=self.node_type,
            node_name=self.node_name,
        )

        return found_triplets

    async def get_context(self, query: str) -> List[Edge]:
        """
        Retrieves and resolves graph triplets into context based on a query.

        Also supplements results with KnowledgeDistillation direct vector search.
        KD search MUST happen here (not in get_completion) because get_context runs
        within the dataset database context (ContextVar is set), while get_completion
        may run outside it (after asyncio.gather in use_combined_context mode).

        KD results are wrapped as synthetic Edge objects with a special marker
        so get_completion() can extract and format them separately.

        Parameters:
        -----------

            - query (str): The query string used to retrieve context from the graph triplets.

        Returns:
        --------

            - List[Edge]: Retrieved triplets plus synthetic edges for KnowledgeDistillation.
        """
        graph_engine = await get_graph_engine()
        is_empty = await graph_engine.is_empty()

        if is_empty:
            logger.warning("Search attempt on an empty knowledge graph")
            # Still try KD search even if graph is empty
            kd_edges = await self._search_knowledge_distillation(query)
            return kd_edges if kd_edges else []

        # === Document routing (MUST run before any vector search) ===
        # For large datasets (>20 docs), select only relevant documents
        # to prevent noise pollution from unrelated documents.
        routed_doc_names = None
        try:
            from cognee.infrastructure.databases.vector import get_vector_engine as get_ve
            ve = get_ve()
            has_index_cards = await ve.has_collection("DocumentIndexCard_summary")
            if has_index_cards:
                card_results = await ve.search(
                    "DocumentIndexCard_summary", query, limit=100,
                )
                doc_count = len(card_results) if card_results else 0

                if _should_enable_routing(doc_count):
                    config = _get_routing_config()
                    top_k = config.get("top_k", 3)
                    confidence_threshold = config.get("confidence_threshold", 0.3)
                    # Score gap: only include docs within this distance of best match
                    score_gap = config.get("score_gap", 0.08)

                    if card_results and card_results[0].score < confidence_threshold:
                        best_score = card_results[0].score
                        # Apply score gap filter: only include documents
                        # whose card score is close to the best match.
                        # This prevents loosely-related noise docs from being
                        # included when there's a clearly best-matching document.
                        top_cards = []
                        for card in card_results[:top_k]:
                            if card.score <= best_score + score_gap:
                                top_cards.append(card)
                        # Always include at least the best match
                        if not top_cards and card_results:
                            top_cards = [card_results[0]]

                        routed_doc_names = set()
                        for card in top_cards:
                            name = card.payload.get("doc_name", "")
                            if name:
                                routed_doc_names.add(name)
                        logger.info(
                            f"Document routing: {doc_count} docs, selected {len(routed_doc_names)} "
                            f"(top score: {best_score:.3f}, gap filter: {score_gap}), "
                            f"docs: {routed_doc_names}"
                        )
                    else:
                        # Low confidence — still activate routing mode to skip
                        # graph triplets/DC, but with empty doc_names the soft
                        # boost in KD search will have no effect (all KDs equal).
                        routed_doc_names = set()
                        logger.info(
                            f"Document routing: low confidence "
                            f"(best score: {card_results[0].score:.3f} > {confidence_threshold}), "
                            f"graph/DC skipped but KD unfiltered"
                        )
        except Exception as e:
            logger.debug(f"Document routing skipped: {e}")

        # === Graph triplet search ===
        # When document routing is active, SKIP graph triplet search entirely.
        # Reason: Entity/EntityType vectors come from ALL documents (including noise),
        # and there is no doc_name field on graph entities to filter by.
        # KD vectors (searched below with doc_names filtering) are the primary
        # knowledge source and contain comprehensive aggregated facts.
        if routed_doc_names is not None:
            triplets = []
            logger.info(
                "Graph triplet search SKIPPED (document routing active, %d docs selected). "
                "Using KD-only retrieval for noise isolation.",
                len(routed_doc_names),
            )
        else:
            triplets = await self.get_triplets(query)

            if len(triplets) == 0:
                logger.warning(
                    "Graph triplet search returned 0 results for query: '%s'. "
                    "Possible causes: (1) Entity/EntityType vector collections don't exist "
                    "(re-run cognify to rebuild), (2) similarity_threshold=%.2f is too strict, "
                    "(3) graph nodes exist but have no matching vector indexes.",
                    query, self.similarity_threshold,
                )
                # Fallback: Try DocumentChunk with relaxed threshold
                try:
                    triplets = await brute_force_triplet_search(
                        query,
                        top_k=self.top_k,
                        collections=["DocumentChunk_text"],
                        similarity_threshold=0.95,
                        min_quality_score=0.0,
                        ensure_diversity=False,
                    )
                    if triplets:
                        logger.info("DocumentChunk fallback found %d results", len(triplets))
                except Exception as fallback_err:
                    logger.warning("DocumentChunk fallback failed: %s", fallback_err)
                    triplets = []

        # Supplement with KnowledgeDistillation direct vector search.
        # KD nodes have no graph edges, so brute_force_triplet_search discards them.
        # We search the vector index directly and create synthetic Edge objects
        # with a special marker so get_completion() can format them prominently.
        kd_edges = await self._search_knowledge_distillation(query, doc_names=routed_doc_names)
        if kd_edges:
            triplets = list(triplets) + kd_edges
            logger.info(
                "Added %d KnowledgeDistillation edges to context for query: %s",
                len(kd_edges), query[:50],
            )

        # Supplement with DocumentChunk direct vector search as safety net.
        # IMPORTANT: When document routing is active, skip DC search to avoid
        # noise pollution — DC payload has no doc_name field for filtering.
        if routed_doc_names is None:
            dc_edges = await self._search_document_chunks(query)
            if dc_edges:
                triplets = list(triplets) + dc_edges
                logger.info(
                    "Added %d DocumentChunk edges as fallback context for query: %s",
                    len(dc_edges), query[:50],
                )
        else:
            logger.info(
                "DocumentChunk search skipped (document routing active, %d docs selected)",
                len(routed_doc_names),
            )

        # Expand with 1-hop neighbor edges for richer graph visualization.
        # These are marked _VIZ_ONLY and excluded from LLM answer context.
        viz_edges = await self._expand_neighbors_for_viz(triplets)
        if viz_edges:
            triplets = list(triplets) + viz_edges
            logger.info("Added %d neighbor edges for visualization", len(viz_edges))

        if len(triplets) == 0:
            logger.warning("Empty context was provided to the completion")
            return []

        return triplets

    async def _search_document_chunks(self, query: str, doc_names=None) -> List[Edge]:
        """
        Direct vector search on DocumentChunk_text collection as safety net.

        When KnowledgeDistillation vectors don't cover certain facts (e.g.,
        specific process steps, party identities, phase lists), the raw
        document chunks serve as a reliable fallback because they contain
        the complete source text.

        Results are wrapped as synthetic Edge objects with _DC_EDGE_MARKER
        so get_completion() can format them as a separate "原文参考段落" section.

        MUST be called within the dataset database context (ContextVar set).
        """
        try:
            vector_engine = get_vector_engine()
            results = await vector_engine.search(
                "DocumentChunk_text", query, limit=10,
            )
            if not results:
                return []

            # Re-rank by keyword overlap (same approach as KD search)
            import re
            cjk_runs = re.findall(r'[\u4e00-\u9fff]+', query)
            query_keywords = set()
            for run in cjk_runs:
                bigrams = [run[j:j+2] for j in range(len(run) - 1)]
                query_keywords.update(bigrams)
            query_keywords |= set(re.findall(r'\d+', query))

            candidates = []
            for result in results:
                # Use a generous threshold — DC is a fallback safety net
                if result.score > 0.7:
                    continue
                text = result.payload.get("text", "")
                if not text or len(text.strip()) < 30:
                    continue
                # Keyword boost
                hits = sum(1 for kw in query_keywords if kw in text)
                boosted_score = result.score - (hits * 0.1)
                candidates.append((boosted_score, result.score, text))

            candidates.sort(key=lambda x: x[0])
            # Keep top 2 chunks — enough for fallback without overwhelming context.
            # Using 2 instead of 3 reduces noise that can confuse the LLM when
            # KD already has the answer (e.g., counts/totals not repeated in raw text).
            candidates = candidates[:2]

            edges = []
            for i, (boosted, orig_score, text) in enumerate(candidates):
                first_line = text.split('\n')[0].strip() if text else ""
                display_name = first_line[:40] + "..." if len(first_line) > 40 else first_line
                dc_node = Node(
                    node_id=f"dc_{i}",
                    attributes={
                        "name": display_name or "文档段落",
                        "_dc_marker": _DC_EDGE_MARKER,
                        "text": text,
                        "type": "DocumentChunk",
                        "description": text,
                        "vector_distance": orig_score,
                    },
                )
                edge = Edge(
                    node1=dc_node,
                    node2=dc_node,
                    attributes={
                        "relationship_name": "source_document_chunk",
                        "relationship_type": "source_document_chunk",
                    },
                    directed=False,
                )
                edges.append(edge)

            if edges:
                logger.info(
                    "DocumentChunk search: %d results for query '%s'",
                    len(edges), query[:50],
                )
            return edges
        except CollectionNotFoundError:
            logger.debug("DocumentChunk_text collection not found, skipping")
            return []
        except Exception as e:
            logger.warning("DocumentChunk search failed: %s", e)
            return []

    async def _search_knowledge_distillation(self, query: str, doc_names=None) -> List[Edge]:
        """
        Direct vector search on KnowledgeDistillation_text collection.

        Creates synthetic Edge objects with a marker attribute so they can be
        identified and formatted separately in get_completion().

        Results are re-ranked by keyword overlap with the query so that KDs
        containing exact query terms are presented first.

        When doc_names is provided (from document routing), KD from those
        documents receives a score BOOST (soft preference) rather than hard
        filtering.  This ensures the correct document's KD is preferred while
        still allowing KD from other documents to surface when routing selects
        the wrong document (common for generic queries).

        MUST be called within the dataset database context (ContextVar set).
        """
        try:
            vector_engine = get_vector_engine()
            # When routing is active (doc_names is not None, even if empty set),
            # search broadly (200) to ensure KD from the correct document is
            # in the candidate pool.  Without routing (None), 30 is sufficient.
            search_limit = 200 if doc_names is not None else 30
            results = await vector_engine.search(
                "KnowledgeDistillation_text", query, limit=search_limit,
            )
            if not results:
                return []

            # NOTE: No hard filtering by doc_names.  Instead, we apply a soft
            # score boost below so that KD from routed documents is preferred
            # but KD from other documents can still surface.
            if doc_names is not None:
                logger.info(
                    f"KD soft-boost mode: {len(results)} total results, "
                    f"boosting {len(doc_names)} routed documents: {doc_names}"
                )

            # Extract query keywords using 2-char CJK bigrams + numbers.
            # We use bigrams instead of full CJK runs because Chinese text
            # has no spaces, so a full run would be the entire query string
            # which would never match in KD text.
            import re
            cjk_runs = re.findall(r'[\u4e00-\u9fff]+', query)
            query_keywords = set()
            focus_keywords = set()  # Last bigrams = topic focus of the query
            for run in cjk_runs:
                bigrams = [run[j:j+2] for j in range(len(run) - 1)]
                query_keywords.update(bigrams)
                # Last 2 bigrams of the last CJK run are the query focus
                if run == cjk_runs[-1] and bigrams:
                    focus_keywords.update(bigrams[-2:])
            query_keywords |= set(re.findall(r'\d+', query))

            # Build candidate list with keyword-boosted scores.
            # Use a generous distance threshold (0.8) because the embedding
            # API (DashScope) is non-deterministic — the same query can yield
            # distances that fluctuate by ~0.15 between runs.  We rely on
            # keyword re-ranking below to surface the best matches.
            candidates = []
            for result in results:
                if result.score > 0.8:
                    continue
                text = result.payload.get("text", "")
                if not text:
                    continue
                # Count keyword hits with stronger weight for focus keywords
                regular_hits = sum(1 for kw in (query_keywords - focus_keywords) if kw in text)
                focus_hits = sum(1 for kw in focus_keywords if kw in text)
                # Lower score = better.
                # Focus keywords (last bigrams of query = topic noun) get a
                # very strong boost (-1.0 each) so that KDs matching the
                # exact topic reliably outrank semantically-similar but
                # topically-different results (e.g. "流程" vs "阶段").
                boosted_score = result.score - (regular_hits * 0.1) - (focus_hits * 1.0)

                # Soft document routing boost: KD from routed documents gets
                # a significant score bonus.  This acts as a strong preference
                # without hard-filtering, so KD from the correct document can
                # still surface even if routing picked wrong documents.
                if doc_names:
                    is_routed_doc = any(f"[来源: {name}]" in text for name in doc_names)
                    if is_routed_doc:
                        boosted_score -= 0.3  # strong preference for routed docs

                candidates.append((boosted_score, result.score, text))

            # Sort by boosted score (lower is better) and keep top results.
            # For large datasets (routing active), keep more candidates (8)
            # to ensure diverse coverage across potential document matches.
            candidates.sort(key=lambda x: x[0])
            max_candidates = 8 if doc_names is not None else 5
            candidates = candidates[:max_candidates]

            edges = []
            for i, (boosted, orig_score, text) in enumerate(candidates):
                # Generate a meaningful display name from the KD text
                first_line = text.split('\n')[0].strip() if text else ""
                display_name = first_line[:40] + "..." if len(first_line) > 40 else first_line
                kd_node = Node(
                    node_id=f"kd_{i}",
                    attributes={
                        "name": display_name or "蒸馏知识",
                        "_kd_marker": _KD_EDGE_MARKER,
                        "text": text,
                        "type": "KnowledgeDistillation",
                        "description": text,
                        "vector_distance": orig_score,
                    },
                )
                edge = Edge(
                    node1=kd_node,
                    node2=kd_node,
                    attributes={
                        "relationship_name": "distilled_knowledge",
                        "relationship_type": "distilled_knowledge",
                    },
                    directed=False,
                )
                edges.append(edge)

            if edges:
                logger.info(
                    "KnowledgeDistillation search: %d results for query '%s'",
                    len(edges), query[:50],
                )
            return edges
        except CollectionNotFoundError:
            logger.debug("KnowledgeDistillation_text collection not found, skipping")
            return []
        except Exception as e:
            logger.warning("KnowledgeDistillation search failed: %s", e)
            return []

    async def _expand_neighbors_for_viz(self, triplets: List[Edge]) -> List[Edge]:
        """
        Expand the context with 1-hop neighbor edges from Neo4j for richer
        graph visualization. These edges are marked with _VIZ_ONLY_MARKER
        so they are excluded from LLM answer generation.

        MUST be called within the dataset database context (ContextVar set).
        """
        try:
            graph_engine = await get_graph_engine()

            # Check if graph engine supports batch neighbor query
            if not hasattr(graph_engine, 'get_batch_neighbor_edges'):
                logger.debug("Graph engine does not support get_batch_neighbor_edges, skipping")
                return []

            # Collect unique node IDs from existing triplets (skip KD/synthetic nodes)
            node_ids = set()
            existing_edge_keys = set()
            for edge in triplets:
                n1_id = str(edge.node1.id)
                n2_id = str(edge.node2.id)
                # Skip KD synthetic nodes (they have ids like "kd_0")
                if not n1_id.startswith("kd_"):
                    node_ids.add(n1_id)
                if not n2_id.startswith("kd_"):
                    node_ids.add(n2_id)
                # Track existing edges to avoid duplicates
                existing_edge_keys.add((n1_id, n2_id))
                existing_edge_keys.add((n2_id, n1_id))

            if not node_ids:
                return []

            # Batch query Neo4j for 1-hop neighbors
            neighbor_results = await graph_engine.get_batch_neighbor_edges(list(node_ids))

            if not neighbor_results:
                return []

            # Build Edge objects for new (non-duplicate) neighbor edges
            viz_edges = []
            seen_pairs = set()
            max_viz_edges = 30  # Limit to avoid frontend overload

            for source_id, target_id, rel_type, rel_props, source_props, target_props in neighbor_results:
                # Skip edges that already exist in triplets
                if (source_id, target_id) in existing_edge_keys:
                    continue
                # Skip duplicate pairs in results
                pair_key = (source_id, target_id) if source_id < target_id else (target_id, source_id)
                if pair_key in seen_pairs:
                    continue
                # Skip edges involving internal node types
                src_type = source_props.get("type", "")
                tgt_type = target_props.get("type", "")
                # Check labels from Neo4j as well (labels may be in props)
                src_labels = source_props.get("_labels", [])
                tgt_labels = target_props.get("_labels", [])
                if (src_type in _VIZ_FILTER_NODE_TYPES or tgt_type in _VIZ_FILTER_NODE_TYPES
                        or any(lbl in _VIZ_FILTER_NODE_TYPES for lbl in src_labels)
                        or any(lbl in _VIZ_FILTER_NODE_TYPES for lbl in tgt_labels)):
                    continue
                seen_pairs.add(pair_key)

                # Create Node objects with viz-only marker
                node1 = Node(
                    node_id=source_id,
                    attributes={
                        "name": source_props.get("name", ""),
                        "type": source_props.get("type", "unknown"),
                        "description": source_props.get("description", ""),
                        "_viz_only": _VIZ_ONLY_MARKER,
                    },
                )
                node2 = Node(
                    node_id=target_id,
                    attributes={
                        "name": target_props.get("name", ""),
                        "type": target_props.get("type", "unknown"),
                        "description": target_props.get("description", ""),
                        "_viz_only": _VIZ_ONLY_MARKER,
                    },
                )

                # Clean relationship name
                clean_rel = rel_type.replace("`", "") if rel_type else "related_to"

                edge = Edge(
                    node1=node1,
                    node2=node2,
                    attributes={
                        "relationship_name": clean_rel,
                        "relationship_type": clean_rel,
                    },
                    directed=True,
                )
                viz_edges.append(edge)

                if len(viz_edges) >= max_viz_edges:
                    break

            if viz_edges:
                logger.info(
                    "Neighbor expansion: %d viz-only edges from %d seed nodes",
                    len(viz_edges), len(node_ids),
                )
            return viz_edges

        except Exception as e:
            logger.warning("Neighbor expansion failed (non-fatal): %s", e)
            return []

    async def get_completion(
        self,
        query: str,
        context: Optional[List[Edge]] = None,
        session_id: Optional[str] = None,
    ) -> List[str]:
        """
        Generates a completion using graph connections context based on a query.

        Parameters:
        -----------

            - query (str): The query string for which a completion is generated.
            - context (Optional[Any]): Optional context to use for generating the completion; if
              not provided, context is retrieved based on the query. (default None)
            - session_id (Optional[str]): Optional session identifier for caching. If None,
              defaults to 'default_session'. (default None)

        Returns:
        --------

            - Any: A generated completion based on the query and context provided.
        """
        triplets = context

        if triplets is None:
            triplets = await self.get_context(query)

        # Separate KD edges, DC edges, and viz-only edges from graph edges
        graph_edges = []
        kd_texts = []
        dc_texts = []
        for edge in triplets:
            # Skip viz-only edges — they are for graph display, not LLM context
            if (hasattr(edge, 'node1') and
                    edge.node1.attributes.get("_viz_only") == _VIZ_ONLY_MARKER):
                continue
            # Skip edges involving internal/structural node types (NodeSet, Timestamp)
            if hasattr(edge, 'node1') and hasattr(edge, 'node2'):
                n1_type = edge.node1.attributes.get("type", "")
                n2_type = edge.node2.attributes.get("type", "")
                if n1_type in _INTERNAL_NODE_TYPES or n2_type in _INTERNAL_NODE_TYPES:
                    continue
            # Classify edge by marker
            if (hasattr(edge, 'node1') and
                    edge.node1.attributes.get("_kd_marker") == _KD_EDGE_MARKER):
                kd_texts.append(edge.node1.attributes.get("text", ""))
            elif (hasattr(edge, 'node1') and
                    edge.node1.attributes.get("_dc_marker") == _DC_EDGE_MARKER):
                dc_texts.append(edge.node1.attributes.get("text", ""))
            else:
                graph_edges.append(edge)

        # Convert graph edges to text
        graph_context = await resolve_edges_to_text(graph_edges)

        # Build context with three tiers of information:
        # 1. KD (highest priority: cross-chunk aggregated knowledge)
        # 2. Graph edges (entity relationships from knowledge graph)
        # 3. DocumentChunks (raw source text as safety net fallback)
        context_text = ""

        # Tier 1: KD content BEFORE graph context as high-priority reference.
        if kd_texts:
            kd_section = "【核心参考知识（准确性最高，与下方图谱信息冲突时以此为准）】\n"
            for i, text in enumerate(kd_texts, 1):
                kd_section += f"{i}. {text}\n\n"
            context_text = kd_section + "\n"

        # Tier 2: Graph edges
        context_text += graph_context

        # Tier 3: DocumentChunk raw text as fallback supplement.
        # These are the original document paragraphs most relevant to the query.
        # When KD or graph edges don't contain certain facts, this section
        # ensures the LLM has access to the raw source text.
        if dc_texts:
            dc_section = "\n\n【原文参考段落（仅供补充参考，核心参考知识已涵盖的事实无需在此验证）】\n"
            for i, text in enumerate(dc_texts, 1):
                dc_section += f"--- 段落{i} ---\n{text}\n\n"
            context_text += dc_section

        cache_config = CacheConfig()
        user = session_user.get()
        user_id = getattr(user, "id", None)
        session_save = user_id and cache_config.caching

        if session_save:
            conversation_history = await get_conversation_history(session_id=session_id)

            context_summary, completion = await asyncio.gather(
                summarize_text(context_text),
                generate_completion(
                    query=query,
                    context=context_text,
                    user_prompt_path=self.user_prompt_path,
                    system_prompt_path=self.system_prompt_path,
                    system_prompt=self.system_prompt,
                    conversation_history=conversation_history,
                ),
            )
        else:
            completion = await generate_completion(
                query=query,
                context=context_text,
                user_prompt_path=self.user_prompt_path,
                system_prompt_path=self.system_prompt_path,
                system_prompt=self.system_prompt,
            )

        if self.save_interaction and context and triplets and completion:
            await self.save_qa(
                question=query, answer=completion, context=context_text, triplets=triplets
            )

        if session_save:
            await save_conversation_history(
                query=query,
                context_summary=context_summary,
                answer=completion,
                session_id=session_id,
            )

        return [completion]

    async def save_qa(self, question: str, answer: str, context: str, triplets: List) -> None:
        """
        Saves a question and answer pair for later analysis or storage.
        Parameters:
        -----------
            - question (str): The question text.
            - answer (str): The answer text.
            - context (str): The context text.
            - triplets (List): A list of triples retrieved from the graph.
        """
        nodeset_name = "Interactions"
        interactions_node_set = NodeSet(
            id=uuid5(NAMESPACE_OID, name=nodeset_name), name=nodeset_name
        )
        source_id = uuid5(NAMESPACE_OID, name=(question + answer + context))

        cognee_user_interaction = CogneeUserInteraction(
            id=source_id,
            question=question,
            answer=answer,
            context=context,
            belongs_to_set=interactions_node_set,
        )

        await add_data_points(data_points=[cognee_user_interaction])

        relationships = []
        relationship_name = "used_graph_element_to_answer"
        for triplet in triplets:
            target_id_1 = extract_uuid_from_node(triplet.node1)
            target_id_2 = extract_uuid_from_node(triplet.node2)
            if target_id_1 and target_id_2:
                relationships.append(
                    (
                        source_id,
                        target_id_1,
                        relationship_name,
                        {
                            "relationship_name": relationship_name,
                            "source_node_id": source_id,
                            "target_node_id": target_id_1,
                            "ontology_valid": False,
                            "feedback_weight": 0,
                        },
                    )
                )

                relationships.append(
                    (
                        source_id,
                        target_id_2,
                        relationship_name,
                        {
                            "relationship_name": relationship_name,
                            "source_node_id": source_id,
                            "target_node_id": target_id_2,
                            "ontology_valid": False,
                            "feedback_weight": 0,
                        },
                    )
                )

            if len(relationships) > 0:
                graph_engine = await get_graph_engine()
                await graph_engine.add_edges(relationships)
