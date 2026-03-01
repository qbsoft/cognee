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
            if "metadata" in subclass.model_fields:
                metadata_field = subclass.model_fields["metadata"]
                if hasattr(metadata_field, "default") and metadata_field.default is not None:
                    if isinstance(metadata_field.default, dict):
                        index_fields = metadata_field.default.get("index_fields", [])
                        for field_name in index_fields:
                            vector_index_collections.append(f"{subclass.__name__}_{field_name}")

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
            return []

        triplets = await self.get_triplets(query)

        if len(triplets) == 0:
            logger.warning(
                "Graph triplet search returned 0 results, trying DocumentChunk fallback for query: %s",
                query,
            )
            try:
                triplets = await brute_force_triplet_search(
                    query,
                    top_k=self.top_k,
                    collections=["DocumentChunk_text"],
                    similarity_threshold=0.95,
                    min_quality_score=0.0,
                    ensure_diversity=False,
                )
            except Exception as fallback_err:
                logger.warning("DocumentChunk fallback failed: %s", fallback_err)
                triplets = []

        # Supplement with KnowledgeDistillation direct vector search.
        # KD nodes have no graph edges, so brute_force_triplet_search discards them.
        # We search the vector index directly and create synthetic Edge objects
        # with a special marker so get_completion() can format them prominently.
        kd_edges = await self._search_knowledge_distillation(query)
        if kd_edges:
            triplets = list(triplets) + kd_edges
            logger.info(
                "Added %d KnowledgeDistillation edges to context for query: %s",
                len(kd_edges), query[:50],
            )

        if len(triplets) == 0:
            logger.warning("Empty context was provided to the completion")
            return []

        return triplets

    async def _search_knowledge_distillation(self, query: str) -> List[Edge]:
        """
        Direct vector search on KnowledgeDistillation_text collection.

        Creates synthetic Edge objects with a marker attribute so they can be
        identified and formatted separately in get_completion().

        MUST be called within the dataset database context (ContextVar set).
        """
        try:
            vector_engine = get_vector_engine()
            results = await vector_engine.search(
                "KnowledgeDistillation_text", query, limit=5,
            )
            if not results:
                return []

            edges = []
            for i, result in enumerate(results):
                if result.score > 0.5:
                    continue
                text = result.payload.get("text", "")
                if not text:
                    continue

                kd_node = Node(
                    node_id=f"kd_{i}",
                    attributes={
                        "name": _KD_EDGE_MARKER,
                        "text": text,
                        "type": "KnowledgeDistillation",
                        "description": text,
                        "vector_distance": result.score,
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

        # Separate KD edges from graph edges for distinct formatting
        graph_edges = []
        kd_texts = []
        for edge in triplets:
            if (hasattr(edge, 'node1') and
                    edge.node1.attributes.get("name") == _KD_EDGE_MARKER):
                kd_texts.append(edge.node1.attributes.get("text", ""))
            else:
                graph_edges.append(edge)

        # Convert graph edges to text
        graph_context = await resolve_edges_to_text(graph_edges)

        # Append KD content after graph context as supplementary reference
        if kd_texts:
            kd_section = "\n\n【补充参考知识】\n"
            for i, text in enumerate(kd_texts, 1):
                kd_section += f"{i}. {text}\n\n"
            context_text = graph_context + kd_section
        else:
            context_text = graph_context

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
