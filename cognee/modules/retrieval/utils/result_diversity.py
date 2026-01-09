"""
结果多样性控制工具

确保检索结果多样性，避免结果过于集中。
"""
from typing import List
from cognee.modules.graph.cognee_graph.CogneeGraphElements import Edge
from cognee.shared.logging_utils import get_logger

logger = get_logger("result_diversity")


def ensure_result_diversity(
    results: List[Edge],
    max_similar: int = 2,
    similarity_threshold: float = 0.9,
) -> List[Edge]:
    """
    确保结果多样性
    
    限制相似节点的数量，确保不同类型节点的代表性，避免结果过于集中。
    
    Args:
        results: 检索结果边列表
        max_similar: 每种类型/相似节点的最大数量（默认2）
        similarity_threshold: 节点相似度阈值（默认0.9）
        
    Returns:
        多样性过滤后的结果列表
    """
    if not results:
        return []
    
    diverse_results = []
    seen_types = {}  # 记录每种类型节点的数量
    seen_node_ids = set()  # 记录已包含的节点ID
    
    for edge in results:
        node1_type = edge.node1.attributes.get("type", "unknown")
        node2_type = edge.node2.attributes.get("type", "unknown")
        node1_id = edge.node1.id
        node2_id = edge.node2.id
        
        # 检查节点是否已经包含（避免重复）
        if node1_id in seen_node_ids and node2_id in seen_node_ids:
            # 如果两个节点都已经包含，跳过这条边（避免重复）
            continue
        
        # 检查类型限制
        node1_count = seen_types.get(node1_type, 0)
        node2_count = seen_types.get(node2_type, 0)
        
        # 如果两种类型的节点数量都未超过限制，添加这条边
        if node1_count < max_similar and node2_count < max_similar:
            diverse_results.append(edge)
            seen_types[node1_type] = node1_count + 1
            seen_types[node2_type] = node2_count + 1
            seen_node_ids.add(node1_id)
            seen_node_ids.add(node2_id)
        elif node1_count < max_similar or node2_count < max_similar:
            # 如果至少一个节点类型未超过限制，也添加（但更宽松）
            diverse_results.append(edge)
            if node1_id not in seen_node_ids:
                seen_types[node1_type] = seen_types.get(node1_type, 0) + 1
                seen_node_ids.add(node1_id)
            if node2_id not in seen_node_ids:
                seen_types[node2_type] = seen_types.get(node2_type, 0) + 1
                seen_node_ids.add(node2_id)
    
    if len(diverse_results) < len(results):
        logger.info(
            f"多样性过滤: 原始结果数 {len(results)}, "
            f"过滤后结果数 {len(diverse_results)} "
            f"(类型分布: {dict(seen_types)})"
        )
    
    return diverse_results

