import asyncio
import time
from typing import List, Optional, Type

from cognee.shared.logging_utils import get_logger, ERROR
from cognee.modules.graph.exceptions.exceptions import EntityNotFoundError
from cognee.infrastructure.databases.vector.exceptions import CollectionNotFoundError
from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.infrastructure.databases.vector import get_vector_engine
from cognee.modules.graph.cognee_graph.CogneeGraph import CogneeGraph
from cognee.modules.graph.cognee_graph.CogneeGraphElements import Edge
from cognee.modules.users.models import User
from cognee.shared.utils import send_telemetry
from cognee.modules.retrieval.utils.result_quality_scorer import (
    filter_low_quality_results,
    rank_results_by_quality,
)
from cognee.modules.retrieval.utils.result_diversity import (
    ensure_result_diversity,
)
from cognee.infrastructure.config.yaml_config import get_module_config

logger = get_logger(level=ERROR)

# 诊断模式开关 - 设为 True 可输出检索管道每个环节的详细信息
_DIAG_MODE = True


def format_triplets(edges):

    def filter_attributes(obj, attributes):
        """Helper function to filter out non-None properties, including nested dicts."""
        result = {}
        for attr in attributes:
            value = getattr(obj, attr, None)
            if value is not None:
                # If the value is a dict, extract relevant keys from it
                if isinstance(value, dict):
                    nested_values = {
                        k: v for k, v in value.items() if k in attributes and v is not None
                    }
                    result[attr] = nested_values
                else:
                    result[attr] = value
        return result

    triplets = []
    for edge in edges:
        node1 = edge.node1
        node2 = edge.node2
        edge_attributes = edge.attributes
        node1_attributes = node1.attributes
        node2_attributes = node2.attributes

        # Filter only non-None properties
        node1_info = {key: value for key, value in node1_attributes.items() if value is not None}
        node2_info = {key: value for key, value in node2_attributes.items() if value is not None}
        edge_info = {key: value for key, value in edge_attributes.items() if value is not None}

        # Create the formatted triplet
        triplet = f"Node1: {node1_info}\nEdge: {edge_info}\nNode2: {node2_info}\n\n\n"
        triplets.append(triplet)

    return "".join(triplets)


async def get_memory_fragment(
    properties_to_project: Optional[List[str]] = None,
    node_type: Optional[Type] = None,
    node_name: Optional[List[str]] = None,
) -> CogneeGraph:
    """Creates and initializes a CogneeGraph memory fragment with optional property projections."""
    if properties_to_project is None:
        # Include source tracing properties for DocumentChunk nodes
        # These enable precise scroll positioning in UI when showing search results
        properties_to_project = [
            "id",
            "description",
            "name",
            "type",
            "text",
            "source_file_path",  # File path for scroll positioning
            "source_data_id",    # Source data UUID
            "start_line",        # Starting line number
            "end_line",          # Ending line number
            "chunk_index",       # Chunk index in document
            "page_number",       # Page number (for PDFs)
            "start_char",        # Character offset start
            "end_char",          # Character offset end
        ]

    memory_fragment = CogneeGraph()

    try:
        graph_engine = await get_graph_engine()

        await memory_fragment.project_graph_from_db(
            graph_engine,
            node_properties_to_project=properties_to_project,
            edge_properties_to_project=["relationship_name"],
            node_type=node_type,
            node_name=node_name,
        )

    except EntityNotFoundError:
        # This is expected behavior - continue with empty fragment
        pass
    except Exception as e:
        logger.error(f"Error during memory fragment creation: {str(e)}")
        # Still return the fragment even if projection failed
        pass

    return memory_fragment


async def brute_force_triplet_search(
    query: str,
    top_k: int = 5,
    collections: Optional[List[str]] = None,
    properties_to_project: Optional[List[str]] = None,
    memory_fragment: Optional[CogneeGraph] = None,
    node_type: Optional[Type] = None,
    node_name: Optional[List[str]] = None,
    similarity_threshold: float = 0.7,
    min_quality_score: float = 0.3,
    ensure_diversity: bool = True,
) -> List[Edge]:
    """
    Performs a brute force search to retrieve the top triplets from the graph.

    Args:
        query (str): The search query.
        top_k (int): The number of top results to retrieve.
        collections (Optional[List[str]]): List of collections to query.
        properties_to_project (Optional[List[str]]): List of properties to project.
        memory_fragment (Optional[CogneeGraph]): Existing memory fragment to reuse.
        node_type: node type to filter
        node_name: node name to filter
        similarity_threshold (float): Similarity threshold for filtering relevant edges.
            Lower values mean stricter filtering. Default is 0.5.
            Filtering logic:
            - Edges where both nodes are below threshold are kept
            - Edges where at least one node is highly relevant (< 0.3) and the other is moderately relevant (< 0.7) are kept
            - Otherwise, edges are filtered out
        min_quality_score (float): Minimum quality score for results (default 0.6).
        ensure_diversity (bool): Whether to ensure result diversity (default True).

    Returns:
        list: The top triplet results.
    """
    if not query or not isinstance(query, str):
        raise ValueError("The query must be a non-empty string.")
    if top_k <= 0:
        raise ValueError("top_k must be a positive integer.")

    if memory_fragment is None:
        memory_fragment = await get_memory_fragment(
            properties_to_project, node_type=node_type, node_name=node_name
        )

    if collections is None:
        collections = [
            "Entity_name",
            "TextSummary_text",
            "EntityType_name",
            "DocumentChunk_text",
        ]

    try:
        vector_engine = get_vector_engine()
    except Exception as e:
        logger.error("Failed to initialize vector engine: %s", e)
        raise RuntimeError("Initialization error") from e

    query_vector = (await vector_engine.embedding_engine.embed_text([query]))[0]

    async def search_in_collection(collection_name: str):
        try:
            return await vector_engine.search(
                collection_name=collection_name, query_vector=query_vector, limit=max(top_k * 10, 50)
            )
        except CollectionNotFoundError:
            return []

    try:
        start_time = time.time()

        results = await asyncio.gather(
            *[search_in_collection(collection_name) for collection_name in collections]
        )

        # ===== 诊断点 1: 向量搜索结果 =====
        if _DIAG_MODE:
            print(f"\n{'='*60}")
            print(f"[DIAG] 检索管道诊断 - 查询: '{query}'")
            print(f"{'='*60}")
            print(f"[DIAG-1] 图谱: {len(memory_fragment.nodes)} 节点, {len(memory_fragment.edges)} 边")
            print(f"[DIAG-1] 向量搜索集合: {collections}")
            for col, res in zip(collections, results):
                if res:
                    scores = [r.score for r in res[:5]]
                    print(f"[DIAG-1]   {col}: {len(res)} 结果, Top-5 距离: {scores}")
                else:
                    print(f"[DIAG-1]   {col}: 0 结果 (空或集合不存在)")

        if all(not item for item in results):
            if _DIAG_MODE:
                print(f"[DIAG-1] FAIL: all collections returned empty! Search terminated.")
            return []

        # Final statistics
        projection_time = time.time() - start_time
        logger.info(
            f"Vector collection retrieval completed: Retrieved distances from {sum(1 for res in results if res)} collections in {projection_time:.2f}s"
        )

        node_distances = {collection: result for collection, result in zip(collections, results)}

        edge_distances = node_distances.get("EdgeType_relationship_name", None)

        await memory_fragment.map_vector_distances_to_graph_nodes(node_distances=node_distances)

        # ===== 诊断点 2: 节点距离映射 =====
        if _DIAG_MODE:
            nodes_with_dist = sum(
                1 for n in memory_fragment.nodes.values()
                if n.attributes.get("vector_distance") is not None
                and n.attributes.get("vector_distance") != float("inf")
            )
            print(f"\n[DIAG-2] 节点距离映射: {nodes_with_dist}/{len(memory_fragment.nodes)} 节点有 vector_distance")
            # 显示有距离的前 10 个节点
            dist_nodes = [
                (n.attributes.get("name", n.id), n.attributes.get("vector_distance"), n.attributes.get("type", ""))
                for n in memory_fragment.nodes.values()
                if n.attributes.get("vector_distance") is not None
                and n.attributes.get("vector_distance") != float("inf")
            ]
            dist_nodes.sort(key=lambda x: x[1])
            for name, dist, ntype in dist_nodes[:10]:
                print(f"[DIAG-2]   name='{name}' type='{ntype}' distance={dist:.4f}")

        await memory_fragment.map_vector_distances_to_graph_edges(
            vector_engine=vector_engine, query_vector=query_vector, edge_distances=edge_distances
        )

        # ===== 诊断点 3: 进入 calculate_top_triplet_importances 之前 =====
        if _DIAG_MODE:
            print(f"\n[DIAG-3] 进入三元组重要性计算, similarity_threshold={similarity_threshold}")

        results = await memory_fragment.calculate_top_triplet_importances(
            k=top_k, similarity_threshold=similarity_threshold, query=query
        )

        # ===== 诊断点 4: calculate_top_triplet_importances 结果 =====
        if _DIAG_MODE:
            print(f"\n[DIAG-4] 三元组重要性计算后: {len(results)} 条结果")
            for i, edge in enumerate(results[:5]):
                n1_name = edge.node1.attributes.get("name", "?")
                n2_name = edge.node2.attributes.get("name", "?")
                n1_dist = edge.node1.attributes.get("vector_distance", "inf")
                n2_dist = edge.node2.attributes.get("vector_distance", "inf")
                rel = edge.attributes.get("relationship_name", edge.attributes.get("relationship_type", "?"))
                print(f"[DIAG-4]   [{i}] '{n1_name}'(d={n1_dist}) --[{rel}]--> '{n2_name}'(d={n2_dist})")

        # 应用质量评分和过滤
        pre_quality_count = len(results) if results else 0
        # ===== 诊断点 5: 显示每条边的质量分数（过滤前）=====
        if _DIAG_MODE and results:
            from cognee.modules.retrieval.utils.result_quality_scorer import rank_results_by_quality
            scored_preview = rank_results_by_quality(results, query)
            print(f"\n[DIAG-5] 质量分数预览 (阈值={min_quality_score}):")
            for edge, sc in scored_preview:
                n1_name = edge.node1.attributes.get("name", "") or edge.node1.attributes.get("text", "")[:30]
                n2_name = edge.node2.attributes.get("name", "")
                rel = edge.attributes.get("relationship_name", "?")
                will_keep = "KEEP" if sc >= min_quality_score else "DROP"
                print(f"[DIAG-5]   [{will_keep}] score={sc:.3f} | '{n1_name}' --[{rel}]--> '{n2_name}'")

        if results and min_quality_score > 0:
            results = filter_low_quality_results(results, query, min_quality_score)

        if _DIAG_MODE:
            print(f"[DIAG-5] 质量过滤: {pre_quality_count} -> {len(results)} (min_quality_score={min_quality_score})")

        # 确保结果多样性
        pre_diversity_count = len(results) if results else 0
        if results and ensure_diversity:
            results = ensure_result_diversity(results)

        # ===== 诊断点 6: 多样性过滤后 =====
        if _DIAG_MODE:
            print(f"[DIAG-6] 多样性过滤: {pre_diversity_count} -> {len(results)}")
        
        # 应用 BGE-Reranker 精排（如果配置启用）
        search_config = get_module_config('search')
        reranking_config = search_config.get('search', {}).get('reranking', {})
        reranking_enabled = reranking_config.get('enabled', False)

        if results and reranking_enabled:
            try:
                from cognee.modules.search.reranking.reranker import rerank
                # 将 Edge 对象转换为 reranker 需要的 dict 格式
                edge_dicts = []
                for edge in results:
                    text_parts = []
                    if hasattr(edge, 'node1') and hasattr(edge.node1, 'attributes'):
                        n1 = edge.node1.attributes
                        text_parts.append(n1.get('name', '') or '')
                        text_parts.append(n1.get('description', '') or '')
                    if hasattr(edge, 'attributes'):
                        text_parts.append(edge.attributes.get('relationship_name', '') or '')
                    if hasattr(edge, 'node2') and hasattr(edge.node2, 'attributes'):
                        n2 = edge.node2.attributes
                        text_parts.append(n2.get('name', '') or '')
                        text_parts.append(n2.get('description', '') or '')
                    edge_dicts.append({
                        'text': ' '.join(filter(None, text_parts)),
                        'edge': edge,
                    })

                reranked = await rerank(
                    query=query,
                    results=edge_dicts,
                    top_k=top_k,
                    text_field='text',
                )
                results = [item['edge'] for item in reranked if 'edge' in item]
                logger.info(f'Reranker applied: {len(results)} results after reranking')
            except ImportError:
                logger.warning('FlagEmbedding not installed, skipping reranking')
            except Exception as e:
                logger.warning(f'Reranking failed ({e}), using original order')

        # 如果结果数量超过top_k，只返回前top_k个
        if len(results) > top_k:
            # 重新排序以确保返回最高质量的结果
            scored_results = rank_results_by_quality(results, query)
            results = [edge for edge, _ in scored_results[:top_k]]

        return results

    except CollectionNotFoundError:
        return []
    except Exception as error:
        logger.error(
            "Error during brute force search for query: %s. Error: %s",
            query,
            error,
        )
        raise error
