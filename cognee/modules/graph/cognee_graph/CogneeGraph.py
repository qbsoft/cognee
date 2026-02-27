import time
from cognee.shared.logging_utils import get_logger
from typing import List, Dict, Union, Optional, Type

from cognee.modules.graph.exceptions import (
    EntityNotFoundError,
    EntityAlreadyExistsError,
    InvalidDimensionsError,
)
from cognee.infrastructure.databases.graph.graph_db_interface import GraphDBInterface
from cognee.modules.graph.cognee_graph.CogneeGraphElements import Node, Edge
from cognee.modules.graph.cognee_graph.CogneeAbstractGraph import CogneeAbstractGraph
from cognee.modules.retrieval.utils.result_quality_scorer import (
    rank_results_by_quality,
)
import heapq

logger = get_logger("CogneeGraph")


class CogneeGraph(CogneeAbstractGraph):
    """
    Concrete implementation of the AbstractGraph class for Cognee.

    This class provides the functionality to manage nodes and edges,
    and project a graph from a database using adapters.
    """

    nodes: Dict[str, Node]
    edges: List[Edge]
    directed: bool

    def __init__(self, directed: bool = True):
        self.nodes = {}
        self.edges = []
        self.directed = directed

    def add_node(self, node: Node) -> None:
        if node.id not in self.nodes:
            self.nodes[node.id] = node
        else:
            raise EntityAlreadyExistsError(message=f"Node with id {node.id} already exists.")

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)
        edge.node1.add_skeleton_edge(edge)
        edge.node2.add_skeleton_edge(edge)

    def get_node(self, node_id: str) -> Node:
        return self.nodes.get(node_id, None)

    def get_edges_from_node(self, node_id: str) -> List[Edge]:
        node = self.get_node(node_id)
        if node:
            return node.skeleton_edges
        else:
            raise EntityNotFoundError(message=f"Node with id {node_id} does not exist.")

    def get_edges(self) -> List[Edge]:
        return self.edges

    async def project_graph_from_db(
        self,
        adapter: Union[GraphDBInterface],
        node_properties_to_project: List[str],
        edge_properties_to_project: List[str],
        directed=True,
        node_dimension=1,
        edge_dimension=1,
        memory_fragment_filter=[],
        node_type: Optional[Type] = None,
        node_name: Optional[List[str]] = None,
    ) -> None:
        if node_dimension < 1 or edge_dimension < 1:
            raise InvalidDimensionsError()
        try:
            import time

            start_time = time.time()

            # Determine projection strategy
            if node_type is not None and node_name not in [None, [], ""]:
                nodes_data, edges_data = await adapter.get_nodeset_subgraph(
                    node_type=node_type, node_name=node_name
                )
                if not nodes_data or not edges_data:
                    raise EntityNotFoundError(
                        message="Nodeset does not exist, or empty nodetes projected from the database."
                    )
            elif len(memory_fragment_filter) == 0:
                nodes_data, edges_data = await adapter.get_graph_data()
                if not nodes_data or not edges_data:
                    raise EntityNotFoundError(message="Empty graph projected from the database.")
            else:
                nodes_data, edges_data = await adapter.get_filtered_graph_data(
                    attribute_filters=memory_fragment_filter
                )
                if not nodes_data or not edges_data:
                    raise EntityNotFoundError(
                        message="Empty filtered graph projected from the database."
                    )

            # Process nodes
            for node_id, properties in nodes_data:
                node_attributes = {key: properties.get(key) for key in node_properties_to_project}
                self.add_node(Node(str(node_id), node_attributes, dimension=node_dimension))

            # Process edges
            for source_id, target_id, relationship_type, properties in edges_data:
                source_node = self.get_node(str(source_id))
                target_node = self.get_node(str(target_id))
                if source_node and target_node:
                    edge_attributes = {
                        key: properties.get(key) for key in edge_properties_to_project
                    }
                    edge_attributes["relationship_type"] = relationship_type

                    edge = Edge(
                        source_node,
                        target_node,
                        attributes=edge_attributes,
                        directed=directed,
                        dimension=edge_dimension,
                    )
                    self.add_edge(edge)

                    source_node.add_skeleton_edge(edge)
                    target_node.add_skeleton_edge(edge)
                else:
                    raise EntityNotFoundError(
                        message=f"Edge references nonexistent nodes: {source_id} -> {target_id}"
                    )

            # Final statistics
            projection_time = time.time() - start_time
            logger.info(
                f"Graph projection completed: {len(self.nodes)} nodes, {len(self.edges)} edges in {projection_time:.2f}s"
            )

        except Exception as e:
            logger.error(f"Error during graph projection: {str(e)}")
            raise

    async def map_vector_distances_to_graph_nodes(self, node_distances) -> None:
        mapped_nodes = 0
        unmapped_ids = []
        for category, scored_results in node_distances.items():
            category_mapped = 0
            category_unmapped = 0
            for scored_result in scored_results:
                node_id = str(scored_result.id)
                score = scored_result.score
                node = self.get_node(node_id)
                if node:
                    node.add_attribute("vector_distance", score)
                    mapped_nodes += 1
                    category_mapped += 1
                else:
                    category_unmapped += 1
                    if len(unmapped_ids) < 5:
                        unmapped_ids.append((category, node_id, score))
            if category_unmapped > 0:
                logger.info(f"  {category}: {category_mapped} mapped, {category_unmapped} unmapped (IDs not in graph)")
        if unmapped_ids:
            logger.info(f"  示例未映射ID: {unmapped_ids}")

    async def map_vector_distances_to_graph_edges(
        self, vector_engine, query_vector, edge_distances
    ) -> None:
        try:
            if query_vector is None or len(query_vector) == 0:
                raise ValueError("Failed to generate query embedding.")

            if edge_distances is None:
                start_time = time.time()
                edge_distances = await vector_engine.search(
                    collection_name="EdgeType_relationship_name",
                    query_vector=query_vector,
                    limit=None,
                )
                projection_time = time.time() - start_time
                logger.info(
                    f"Edge collection distances were calculated separately from nodes in {projection_time:.2f}s"
                )

            embedding_map = {result.payload["text"]: result.score for result in edge_distances}

            for edge in self.edges:
                relationship_type = edge.attributes.get("relationship_type")
                distance = embedding_map.get(relationship_type, None)
                if distance is not None:
                    edge.attributes["vector_distance"] = distance

        except Exception as ex:
            logger.error(f"Error mapping vector distances to edges: {str(ex)}")
            raise ex

    async def calculate_top_triplet_importances(
        self, k: int, similarity_threshold: float = 0.5, query: Optional[str] = None,
        dynamic_threshold: bool = True
    ) -> List[Edge]:
        """
        计算并返回最重要的 top-k 个三元组。
        
        Args:
            k: 返回的三元组数量
            similarity_threshold: 相似度阈值（归一化后的距离），用于过滤相关边。
                由于 lower is better，阈值应该是一个值（如 0.3-0.7）。
                默认值为 0.5，表示更严格地过滤相关性较低的节点。
                过滤逻辑：
                - 如果两个节点都低于阈值，保留该边
                - 如果至少一个节点非常相关（< 0.3），且另一个节点中等相关（< 0.7），保留该边
                - 否则过滤掉
            query: 查询文本（可选），如果提供，将使用质量评分进行排序
            dynamic_threshold: 是否使用动态阈值调整（默认True）
        
        Returns:
            最重要的 top-k 个三元组列表
        """
        def score(edge):
            n1 = edge.node1.attributes.get("vector_distance", float("inf"))
            n2 = edge.node2.attributes.get("vector_distance", float("inf"))
            e = edge.attributes.get("vector_distance", float("inf"))
            return n1 + n2 + e
        
        # 动态阈值调整：根据结果数量调整阈值
        adjusted_threshold = similarity_threshold
        if dynamic_threshold:
            # 先进行一次初步过滤，看看有多少结果
            preliminary_relevant = [
                edge for edge in self.edges
                if edge.node1.attributes.get("type", "") != "NodeSet" and
                   edge.node2.attributes.get("type", "") != "NodeSet" and
                   (edge.node1.attributes.get("vector_distance", float("inf")) != float("inf") or
                    edge.node2.attributes.get("vector_distance", float("inf")) != float("inf"))
            ]
            
            # 如果初步结果太少，放宽阈值
            if len(preliminary_relevant) < k * 2:
                adjusted_threshold = min(similarity_threshold + 0.1, 0.7)
                logger.debug(f"动态调整阈值: {similarity_threshold} -> {adjusted_threshold} (结果数: {len(preliminary_relevant)})")
            # 如果初步结果太多，收紧阈值
            elif len(preliminary_relevant) > k * 10:
                adjusted_threshold = max(similarity_threshold - 0.1, 0.3)
                logger.debug(f"动态调整阈值: {similarity_threshold} -> {adjusted_threshold} (结果数: {len(preliminary_relevant)})")
        
        def is_relevant(edge):
            """
            检查边是否与查询相关。
            改进的过滤逻辑：
            1. 过滤掉系统节点（NodeSet 类型）
            2. 两个节点都低于阈值（严格相关）
            3. 或者至少一个节点非常相关（< 0.3），且另一个节点也相关（< 阈值）
            """
            # 过滤掉系统节点（NodeSet 类型）
            n1_type = edge.node1.attributes.get("type", "")
            n2_type = edge.node2.attributes.get("type", "")
            if n1_type == "NodeSet" or n2_type == "NodeSet":
                return False
            
            n1_dist = edge.node1.attributes.get("vector_distance", float("inf"))
            n2_dist = edge.node2.attributes.get("vector_distance", float("inf"))
            
            # 处理 None 值，将其视为 inf
            if n1_dist is None:
                n1_dist = float("inf")
            if n2_dist is None:
                n2_dist = float("inf")
            
            # 如果两个节点都没有有效的 vector_distance，过滤掉
            if n1_dist == float("inf") and n2_dist == float("inf"):
                return False
            
            # 使用调整后的阈值
            threshold = adjusted_threshold
            
            # 情况1：两个节点都低于阈值（严格相关）
            both_relevant = (
                n1_dist != float("inf") and n1_dist < threshold and
                n2_dist != float("inf") and n2_dist < threshold
            )
            
            # 情况2：至少一个节点非常相关（< 0.3），且另一个节点也相关（< 阈值）
            # 这样更严格，避免包含过多低相关节点
            one_highly_relevant = (
                (n1_dist != float("inf") and n1_dist < 0.3 and 
                 n2_dist != float("inf") and n2_dist < threshold) or
                (n2_dist != float("inf") and n2_dist < 0.3 and 
                 n1_dist != float("inf") and n1_dist < threshold)
            )
            
            return both_relevant or one_highly_relevant
        
        # 先过滤掉不相关的边（至少一个节点必须有有效的 vector_distance 且低于阈值）

        # ===== 诊断: 分析所有边的距离分布 =====
        diag_edge_stats = {"no_dist": 0, "nodeset": 0, "both_below": 0, "one_high": 0, "above_threshold": 0}
        diag_dist_values = []
        for edge in self.edges:
            n1_type = edge.node1.attributes.get("type", "")
            n2_type = edge.node2.attributes.get("type", "")
            if n1_type == "NodeSet" or n2_type == "NodeSet":
                diag_edge_stats["nodeset"] += 1
                continue
            n1_dist = edge.node1.attributes.get("vector_distance", float("inf"))
            n2_dist = edge.node2.attributes.get("vector_distance", float("inf"))
            if n1_dist is None: n1_dist = float("inf")
            if n2_dist is None: n2_dist = float("inf")
            if n1_dist == float("inf") and n2_dist == float("inf"):
                diag_edge_stats["no_dist"] += 1
                continue
            # 记录距离值用于分析
            if n1_dist != float("inf"): diag_dist_values.append(n1_dist)
            if n2_dist != float("inf"): diag_dist_values.append(n2_dist)
            # 分类
            if (n1_dist != float("inf") and n1_dist < adjusted_threshold and
                n2_dist != float("inf") and n2_dist < adjusted_threshold):
                diag_edge_stats["both_below"] += 1
            elif ((n1_dist != float("inf") and n1_dist < 0.3 and n2_dist != float("inf") and n2_dist < adjusted_threshold) or
                  (n2_dist != float("inf") and n2_dist < 0.3 and n1_dist != float("inf") and n1_dist < adjusted_threshold)):
                diag_edge_stats["one_high"] += 1
            else:
                diag_edge_stats["above_threshold"] += 1

        print(f"\n[DIAG-GRAPH] ===== 边过滤诊断 =====")
        print(f"[DIAG-GRAPH] 总边数: {len(self.edges)}")
        print(f"[DIAG-GRAPH] 使用阈值: adjusted={adjusted_threshold}, original={similarity_threshold}")
        print(f"[DIAG-GRAPH] NodeSet边 (跳过): {diag_edge_stats['nodeset']}")
        print(f"[DIAG-GRAPH] 无距离边 (两端都无距离): {diag_edge_stats['no_dist']}")
        print(f"[DIAG-GRAPH] 两端都低于阈值 (保留): {diag_edge_stats['both_below']}")
        print(f"[DIAG-GRAPH] 一端高相关 (保留): {diag_edge_stats['one_high']}")
        print(f"[DIAG-GRAPH] 超过阈值 (丢弃): {diag_edge_stats['above_threshold']}")
        if diag_dist_values:
            diag_dist_values.sort()
            print(f"[DIAG-GRAPH] 距离分布: min={min(diag_dist_values):.4f}, max={max(diag_dist_values):.4f}, "
                  f"median={diag_dist_values[len(diag_dist_values)//2]:.4f}, "
                  f"count={len(diag_dist_values)}")
            # 显示距离直方图
            buckets = [0]*10
            for d in diag_dist_values:
                bucket = min(int(d * 10), 9)
                buckets[bucket] += 1
            print(f"[DIAG-GRAPH] 距离直方图:")
            for i, count in enumerate(buckets):
                bar = "#" * min(count, 50)
                print(f"[DIAG-GRAPH]   {i*0.1:.1f}-{(i+1)*0.1:.1f}: {count:3d} {bar}")

        relevant_edges = [edge for edge in self.edges if is_relevant(edge)]

        if not relevant_edges:
            logger.warning(
                f"No relevant edges found with similarity threshold {similarity_threshold}. "
                "This may indicate that the query is not related to any nodes in the graph."
            )
            print(f"[DIAG-GRAPH] ❌ 没有边通过 is_relevant 过滤! 所有结果被丢弃!")
            # 显示最接近阈值的边以辅助调试
            near_threshold_edges = []
            for edge in self.edges:
                n1_type = edge.node1.attributes.get("type", "")
                n2_type = edge.node2.attributes.get("type", "")
                if n1_type == "NodeSet" or n2_type == "NodeSet":
                    continue
                n1_dist = edge.node1.attributes.get("vector_distance", float("inf"))
                n2_dist = edge.node2.attributes.get("vector_distance", float("inf"))
                if n1_dist is None: n1_dist = float("inf")
                if n2_dist is None: n2_dist = float("inf")
                if n1_dist == float("inf") and n2_dist == float("inf"):
                    continue
                min_dist = min(
                    n1_dist if n1_dist != float("inf") else 999,
                    n2_dist if n2_dist != float("inf") else 999
                )
                near_threshold_edges.append((min_dist, edge))
            near_threshold_edges.sort(key=lambda x: x[0])
            print(f"[DIAG-GRAPH] 最接近阈值的 5 条边:")
            for dist, edge in near_threshold_edges[:5]:
                n1_name = edge.node1.attributes.get("name", "?")
                n2_name = edge.node2.attributes.get("name", "?")
                n1_d = edge.node1.attributes.get("vector_distance", "inf")
                n2_d = edge.node2.attributes.get("vector_distance", "inf")
                rel = edge.attributes.get("relationship_name", edge.attributes.get("relationship_type", "?"))
                print(f"[DIAG-GRAPH]   '{n1_name}'(d={n1_d}) --[{rel}]--> '{n2_name}'(d={n2_d})")
            return []

        print(f"[DIAG-GRAPH] ✓ {len(relevant_edges)} 条边通过 is_relevant 过滤")
        logger.info(
            f"Filtered {len(self.edges)} edges to {len(relevant_edges)} relevant edges "
            f"(threshold: {similarity_threshold}), selecting top {k}"
        )
        
        # 如果提供了查询文本，使用质量评分进行排序
        if query and relevant_edges:
            try:
                scored_results = rank_results_by_quality(relevant_edges, query)
                # 返回前k个最高质量的结果
                return [edge for edge, _ in scored_results[:k]]
            except Exception as e:
                logger.warning(f"质量评分失败，使用默认排序: {str(e)}")
                # 如果质量评分失败，回退到默认排序
                return heapq.nsmallest(k, relevant_edges, key=score)
        
        # 然后选择 top-k（使用最小堆，因为 lower score is better）
        return heapq.nsmallest(k, relevant_edges, key=score)
