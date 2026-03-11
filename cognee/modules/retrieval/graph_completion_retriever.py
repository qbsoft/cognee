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


def _extract_doc_name_from_card(card) -> str:
    """Extract document name from an IndexCard's text field.

    The text field format is: '文档: <name>\n类型: ...\n...'
    Falls back to doc_name payload field if text parsing fails.
    """
    name = card.payload.get("doc_name", "")
    if name:
        return name
    text = card.payload.get("text", "")
    if text:
        first_line = text.split("\n")[0]
        # Parse "文档: <name>" format
        if ":" in first_line:
            name = first_line.split(":", 1)[1].strip()
            return name
    return ""


async def _llm_select_documents(query: str, card_results: list) -> set:
    """Use the STRONG LLM to select the most relevant document(s).

    Sends full IndexCard text (not just names) to the answer model so it
    can see document types, topics, parties, and key content.  Includes a
    document-type hierarchy so the model can correctly map ambiguous
    queries like "本项目的目标" to the primary project document (SOW).

    Returns a set of document names, or empty set if selection fails.
    """
    if not card_results:
        return set()

    try:
        import re
        from openai import AsyncOpenAI
        from cognee.infrastructure.llm import get_llm_config

        # Build document list with FULL IndexCard text (not just name+type)
        doc_entries = []
        for i, card in enumerate(card_results):
            name = _extract_doc_name_from_card(card)
            text = card.payload.get("text", "")
            if name and text:
                # Include full card text (truncated to ~300 chars)
                card_summary = text.strip()[:300]
                doc_entries.append(f"[{i+1}] {card_summary}")
            elif name:
                doc_entries.append(f"[{i+1}] {name}")

        if not doc_entries:
            return set()

        docs_text = "\n".join(doc_entries)

        prompt = (
            f"用户查询: {query}\n\n"
            f"以下是数据库中所有{len(doc_entries)}个文档的摘要:\n\n"
            f"{docs_text}\n\n"
            "请判断用户最可能在询问哪个文档的内容。\n\n"
            "判断规则:\n"
            "1. 如果查询提到了具体文档名称或独特关键词，直接匹配\n"
            '2. 如果查询使用"本项目"/"本系统"/"该项目"等泛指，通常指'
            "项目的核心定义文档。文档类型优先级:\n"
            "   - SOW/工作说明书/技术规范书 -> 项目核心定义(最高优先)\n"
            "   - 合同/协议书 -> 项目法律条款\n"
            "   - 用户手册/操作指南 -> 系统操作步骤\n"
            '   - 项目计划书 -> 子项目或关联项目(通常不是用户所指的"本项目")\n'
            '3. 如果查询关于系统操作步骤(如"如何填写""操作流程")，'
            "优先匹配用户手册/操作指南类文档\n"
            "4. 如果查询关于合同条款、付款条件、验收标准等商务内容，"
            "优先匹配SOW/合同类文档\n\n"
            "只输出最相关文档的编号(如: 1)。如果有2个同样相关，"
            "输出两个(如: 1,3)。只输出数字，不要解释。"
        )

        # Use the STRONG model (answer_model) for better routing accuracy.
        # This costs ~5x more than turbo per call but dramatically improves
        # document selection accuracy for ambiguous queries.
        llm_config = get_llm_config()
        model = llm_config.llm_model  # Default to the strong model
        try:
            from cognee.infrastructure.config.yaml_config import get_module_config
            model_cfg = get_module_config("model_selection")
            # Use answer_model (strong) if available, otherwise default
            ans_model = model_cfg.get("answer_model", "")
            if ans_model:
                model = ans_model
        except Exception:
            pass

        client_kwargs = {"api_key": llm_config.llm_api_key or ""}
        if llm_config.llm_endpoint:
            client_kwargs["base_url"] = llm_config.llm_endpoint
        client = AsyncOpenAI(**client_kwargs)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个智能文档路由器。根据用户查询和文档摘要，"
                        "选出最可能包含答案的文档。只输出编号。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=20,
            temperature=0,
        )

        answer = response.choices[0].message.content.strip()
        logger.debug("LLM doc selection answer: %s", answer)

        # Parse response — extract numbers
        numbers = re.findall(r'\d+', answer)
        selected = set()
        for num_str in numbers:
            idx = int(num_str) - 1  # Convert to 0-based
            if 0 <= idx < len(card_results):
                name = _extract_doc_name_from_card(card_results[idx])
                if name:
                    selected.add(name)

        return selected

    except Exception as e:
        logger.warning("LLM document selection failed: %s", e)
        return set()


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
        document_scope: Optional[str] = None,
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
        self.document_scope = document_scope

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
            scope_names = {self.document_scope} if self.document_scope else None
            kd_edges = await self._search_knowledge_distillation(
                query, doc_names=scope_names,
            )
            return kd_edges if kd_edges else []

        # === Document scope: user-specified document filter ===
        # When document_scope is set, skip auto-routing but KEEP graph
        # triplets and DC chunks (they provide detailed process steps
        # that KD doesn't cover, e.g., Q14 供应商功能, Q15 采购流程).
        # KD is searched with a large limit (3000) to find the scoped
        # document's entries even when noise docs dominate vector space.
        # The scope instruction in get_completion() tells the LLM to
        # prefer scoped KD content and ignore noise from other docs.
        if self.document_scope:
            logger.info(
                "Document scope active: scoped-KD + graph/DC for '%s'",
                self.document_scope,
            )
            # Fall through to graph/DC search below, but override KD
            # filtering to use scope instead of routing.

        # === Document routing for large datasets ===
        # For large datasets (>20 docs), use the STRONG LLM to select
        # relevant documents from IndexCard summaries with full text
        # and document type hierarchy, then hard-filter KD search.
        # Falls back to LLM KD-level reranking if routing returns empty.
        large_dataset = False
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
                    large_dataset = True
                    # Use STRONG model for document selection
                    routed_doc_names = await _llm_select_documents(
                        query, card_results,
                    )
                    if routed_doc_names:
                        logger.info(
                            "LLM document routing (strong): %d docs, "
                            "selected %d: %s",
                            doc_count, len(routed_doc_names),
                            routed_doc_names,
                        )
                    else:
                        logger.info(
                            "LLM document routing: no selection, "
                            "falling back to KD-level reranking"
                        )
        except Exception as e:
            logger.debug(f"Document routing failed: {e}")

        # === Graph triplet search ===
        # When large dataset detected, SKIP graph triplet search entirely.
        # Reason: Entity/EntityType vectors come from ALL documents (including noise),
        # and there is no doc_name field on graph entities to filter by.
        # KD vectors (searched below with doc consistency) are the primary
        # knowledge source and contain comprehensive aggregated facts.
        if large_dataset:
            triplets = []
            logger.info(
                "Graph triplet search SKIPPED (large dataset, KD-voting mode)."
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
        # When document_scope is set, search with large limit (3000) to find
        # the scoped document's KD entries even when noise docs dominate.
        if self.document_scope:
            kd_doc_filter = {self.document_scope}
            kd_edges = await self._search_knowledge_distillation(
                query,
                doc_names=kd_doc_filter,
                large_dataset=True,
                scope_max_candidates=10,
            )
        else:
            kd_edges = await self._search_knowledge_distillation(
                query, doc_names=routed_doc_names, large_dataset=large_dataset,
            )
        if kd_edges:
            triplets = list(triplets) + kd_edges
            logger.info(
                "Added %d KnowledgeDistillation edges to context for query: %s",
                len(kd_edges), query[:50],
            )

        # Supplement with DocumentChunk direct vector search as safety net.
        # IMPORTANT: When large dataset detected, skip DC search to avoid
        # noise pollution — DC payload has no doc_name field for filtering.
        if not large_dataset:
            dc_edges = await self._search_document_chunks(query)
            if dc_edges:
                triplets = list(triplets) + dc_edges
                logger.info(
                    "Added %d DocumentChunk edges as fallback context for query: %s",
                    len(dc_edges), query[:50],
                )
        else:
            logger.info(
                "DocumentChunk search skipped (large dataset, KD-voting mode)"
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

    async def _search_knowledge_distillation(self, query: str, doc_names=None, large_dataset=False, scope_max_candidates=None) -> List[Edge]:
        """
        Direct vector search on KnowledgeDistillation_text collection.

        Creates synthetic Edge objects with a marker attribute so they can be
        identified and formatted separately in get_completion().

        Architecture for multi-document (large) datasets:
          1. Strong LLM selects document(s) → doc_names
          2. Hard-filter KDs to selected documents
          3. BGE cross-encoder or keyword ranking on filtered pool
          4. If doc routing returned empty: LLM KD-level reranking fallback

        MUST be called within the dataset database context (ContextVar set).
        """
        try:
            vector_engine = get_vector_engine()
            # When document_scope is active (scope_max_candidates set), use a
            # much larger search limit because the scoped document's KD vectors
            # may rank far behind noise docs in raw vector similarity.
            # E.g., "服务范围" is semantically closer to 50 noise docs' "服务范围"
            # Q&A pairs than to the SOW's specific implementation details.
            is_scoped = scope_max_candidates is not None
            search_limit = 3000 if is_scoped else 30
            distance_threshold = 2.0 if is_scoped else 0.8
            results = await vector_engine.search(
                "KnowledgeDistillation_text", query, limit=search_limit,
            )
            if not results:
                return []

            import re
            routing_cfg = _get_routing_config() if large_dataset else {}

            filtered = []
            for r in results:
                if r.score > distance_threshold:
                    continue
                text = r.payload.get("text", "")
                if text:
                    filtered.append((r.score, text))

            if not filtered:
                return []

            # === Document filter: when routing selected docs ===
            # Supports both exact match ([来源: name]) and substring match
            # (e.g. document_scope="正和热电" matches [来源: 正和热电采购系统SOW])
            if doc_names:
                before_count = len(filtered)
                def _kd_matches_doc(text, names):
                    for name in names:
                        if f"[来源: {name}]" in text:
                            return True
                        # Substring match: check if scope keyword appears
                        # in the source tag
                        src_match = re.search(r'\[来源:\s*([^\]]+)\]', text)
                        if src_match and name in src_match.group(1):
                            return True
                    return False
                filtered = [
                    (s, t) for s, t in filtered
                    if _kd_matches_doc(t, doc_names)
                ]
                logger.info(
                    "KD doc filter: %d → %d (docs: %s)",
                    before_count, len(filtered), doc_names,
                )
                if not filtered and not is_scoped:
                    # Hard filter yielded nothing — fall back to unfiltered
                    # (but NOT when scoped — scope should return empty, not noise)
                    logger.warning(
                        "KD doc filter yielded 0 results, falling back to "
                        "unfiltered pool"
                    )
                    filtered = [
                        (r.score, r.payload.get("text", ""))
                        for r in results
                        if r.score <= 0.8 and r.payload.get("text", "")
                    ]

            # === Ranking: keyword-based scoring ===
            candidates = self._rank_kd_by_keywords(
                query, filtered, doc_names, routing_cfg,
            )

            # Sort candidates (lower score = better for all paths)
            candidates.sort(key=lambda x: x[0])
            max_candidates = scope_max_candidates if scope_max_candidates else 5
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

    async def _rerank_kd_with_cross_encoder(
        self, query: str, filtered: list, routing_cfg: dict,
    ) -> tuple:
        """
        Apply BGE cross-encoder reranker to KD candidates.

        The cross-encoder jointly encodes (query, passage) and produces a
        relevance score that is FAR more discriminative than bi-encoder
        cosine similarity.  This is the key to distinguishing "SOW的验收
        标准" from "噪声文档的验收标准" in multi-document scenarios.

        Returns (candidates, reranker_used) where candidates is a list of
        (score, vector_distance, text) tuples with score = -rerank_score
        (lower is better, consistent with rest of pipeline).
        """
        import re
        try:
            from cognee.modules.search.reranking.reranker import rerank

            # Keep [来源: xxx] prefix — it provides document-identity
            # signal to the cross-encoder.  When the query mentions a
            # document type (e.g. "SOW"), matching the prefix boosts
            # the correct KDs significantly.
            rerank_input = []
            for vec_score, text in filtered:
                rerank_input.append({
                    "text": text,
                    "original_text": text,
                    "vector_score": vec_score,
                })

            if not rerank_input:
                return [], False

            # Rerank with generous top_k to feed into consistency filter
            reranked = await rerank(query, rerank_input, top_k=20)

            # Convert to (score, vector_distance, text) format.
            # Negate rerank_score so lower = better (pipeline convention).
            candidates = []
            for item in reranked:
                score = -item["rerank_score"]
                candidates.append((score, item["vector_score"], item["original_text"]))

            if reranked:
                logger.info(
                    "BGE reranker: %d candidates → top-%d, "
                    "best=%.3f, worst=%.3f",
                    len(rerank_input), len(candidates),
                    reranked[0]["rerank_score"],
                    reranked[-1]["rerank_score"],
                )

            return candidates, True

        except ImportError:
            logger.info("BGE reranker not available (FlagEmbedding not installed), "
                       "falling back to keyword ranking")
            return [], False
        except Exception as e:
            logger.warning("BGE reranker failed: %s, falling back to keyword ranking", e)
            return [], False

    async def _llm_rerank_kds(
        self, query: str, candidates: list, top_k: int = 10,
    ) -> list:
        """
        Use LLM to rerank KD candidates by content relevance.

        Unlike document-level routing (which reads IndexCard summaries),
        this reads ACTUAL KD content — making it far more accurate at
        distinguishing content-similar passages from different documents.

        Input: [(score, text), ...] — candidates from bi-encoder
        Output: [(score, text), ...] — selected items in LLM order,
                or empty list on failure (caller falls back to keyword ranking)
        """
        if not candidates:
            return []

        try:
            from openai import AsyncOpenAI
            import re
            from cognee.infrastructure.llm import get_llm_config

            # Build numbered list of KD excerpts (keep [来源: xxx] prefix
            # so LLM can see document grouping)
            entries = []
            for i, (score, text) in enumerate(candidates):
                excerpt = text[:250].replace("\n", " ")
                entries.append(f"[{i+1}] {excerpt}")

            entries_text = "\n".join(entries)

            prompt = (
                f"用户查询: {query}\n\n"
                f"以下是{len(entries)}个候选知识片段（来自不同文档）:\n\n"
                f"{entries_text}\n\n"
                f"请选出与查询最相关的{top_k}个片段编号。\n"
                "选择标准:\n"
                "1. 与查询内容直接匹配（精确相关优于主题相关）\n"
                "2. 包含具体事实、数据、名称或流程步骤\n"
                "3. 优先选择来自同一文档的片段（保证回答一致性）\n"
                "4. 当多个文档有类似内容时，选择内容最详细具体的\n\n"
                f"只输出{top_k}个编号，逗号分隔。不要解释。"
            )

            # Use extraction model (turbo) for speed
            llm_config = get_llm_config()
            try:
                from cognee.infrastructure.config.yaml_config import get_module_config
                model_cfg = get_module_config("model_selection")
                model = model_cfg.get("extraction_model", llm_config.llm_model)
            except Exception:
                model = llm_config.llm_model

            client_kwargs = {"api_key": llm_config.llm_api_key or ""}
            if llm_config.llm_endpoint:
                client_kwargs["base_url"] = llm_config.llm_endpoint
            client = AsyncOpenAI(**client_kwargs)

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是检索系统的重排序器。"
                            "根据用户查询，从候选知识片段中选择最相关的。"
                            "只输出编号，逗号分隔。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=60,
                temperature=0,
            )

            answer = response.choices[0].message.content.strip()
            logger.debug("LLM KD reranking answer: %s", answer)

            # Parse response — extract numbers
            numbers = re.findall(r'\d+', answer)
            selected = []
            seen = set()
            for num_str in numbers:
                idx = int(num_str) - 1  # Convert to 0-based
                if 0 <= idx < len(candidates) and idx not in seen:
                    seen.add(idx)
                    selected.append(candidates[idx])

            if selected:
                logger.info(
                    "LLM KD reranking: %d → %d selected",
                    len(candidates), len(selected),
                )

            return selected

        except Exception as e:
            logger.warning("LLM KD reranking failed: %s", e)
            return []

    def _rank_kd_by_keywords(
        self, query: str, filtered: list, doc_names, routing_cfg: dict,
    ) -> list:
        """
        Fallback keyword-based ranking when BGE reranker is unavailable.

        Uses CJK bigram matching and optional document routing boost.
        """
        import re
        kd_boost = routing_cfg.get("kd_routing_boost", 0.5)

        # Extract query keywords using 2-char CJK bigrams + numbers.
        cjk_runs = re.findall(r'[\u4e00-\u9fff]+', query)
        query_keywords = set()
        focus_keywords = set()
        for run in cjk_runs:
            bigrams = [run[j:j+2] for j in range(len(run) - 1)]
            query_keywords.update(bigrams)
            if run == cjk_runs[-1] and bigrams:
                focus_keywords.update(bigrams[-2:])
        query_keywords |= set(re.findall(r'\d+', query))

        candidates = []
        for vec_score, text in filtered:
            regular_hits = sum(1 for kw in (query_keywords - focus_keywords) if kw in text)
            focus_hits = sum(1 for kw in focus_keywords if kw in text)
            boosted_score = vec_score - (regular_hits * 0.1) - (focus_hits * 1.0)

            if doc_names:
                is_routed_doc = any(f"[来源: {name}]" in text for name in doc_names)
                if is_routed_doc:
                    boosted_score -= kd_boost

            candidates.append((boosted_score, vec_score, text))

        return candidates

    def _apply_document_consistency(
        self, candidates: list, max_candidates: int, routing_cfg: dict,
    ) -> list:
        """
        Re-rank candidates by document consistency: prefer KDs whose source
        document appears multiple times in the result pool.

        Also applies post-coherence filter: if final candidates span >2
        documents, keep only the top-2 most represented.
        """
        import re
        pool_size = min(50, len(candidates))
        pool = candidates[:pool_size]

        doc_counts = {}
        for score, orig, text in pool:
            match = re.search(r'\[来源: (.+?)\]', text)
            dname = match.group(1) if match else ""
            if dname:
                doc_counts[dname] = doc_counts.get(dname, 0) + 1

        if not doc_counts:
            return candidates[:max_candidates]

        consistency_bonus = routing_cfg.get("consistency_bonus", 0.25)
        reranked = []
        for score, orig, text in pool:
            match = re.search(r'\[来源: (.+?)\]', text)
            dname = match.group(1) if match else ""
            siblings = doc_counts.get(dname, 1) - 1
            adjusted = score - siblings * consistency_bonus
            reranked.append((adjusted, orig, text))
        reranked.sort(key=lambda x: x[0])
        result = reranked[:max_candidates]

        # Post-coherence filter: keep only top-2 most represented documents
        final_docs = {}
        for _, _, text in result:
            match = re.search(r'\[来源: (.+?)\]', text)
            d = match.group(1) if match else "?"
            final_docs[d] = final_docs.get(d, 0) + 1

        if len(final_docs) > 2:
            sorted_final = sorted(
                final_docs.items(), key=lambda x: x[1], reverse=True,
            )
            keep_docs = {d for d, _ in sorted_final[:2]}
            result = [
                (s, o, t) for s, o, t in result
                if any(f"[来源: {d}]" in t for d in keep_docs)
            ]
            logger.info(
                "Post-coherence filter: kept %d from %s, dropped: %s",
                len(result), keep_docs, set(final_docs) - keep_docs,
            )

        logger.info(
            "Document consistency: pool=%d, bonus=%.2f, docs: %s",
            pool_size, consistency_bonus, final_docs,
        )
        return result

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

        # When document_scope is set, add a scope instruction FIRST so
        # the LLM prioritizes scoped KD and treats graph/DC as supplementary.
        if self.document_scope:
            context_text += (
                f"【重要：本次查询限定在文档「{self.document_scope}」中。"
                "请优先基于核心参考知识中标注来源为该文档的条目回答。"
                "核心参考知识如果只提供了高层概要（如'是17个流程之一'），"
                "则应从下方原文参考段落中提取该流程的具体步骤、功能细节来补充。"
                "但不要采用核心参考知识中来自其他文档（如环保工程_合同、教育培训_合同等）"
                "的信息来回答本项目的问题。】\n\n"
            )

        # Tier 1: KD content BEFORE graph context as high-priority reference.
        if kd_texts:
            kd_section = "【核心参考知识（准确性最高，与下方图谱信息冲突时以此为准）】\n"
            for i, text in enumerate(kd_texts, 1):
                kd_section += f"{i}. {text}\n\n"
            context_text += kd_section + "\n"

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
