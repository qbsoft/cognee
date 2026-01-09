"""
检索结果质量评分工具

为检索结果计算质量分数，提升检索结果相关性。
"""
from typing import List, Tuple, Optional
from difflib import SequenceMatcher
from cognee.modules.graph.cognee_graph.CogneeGraphElements import Edge, Node
from cognee.shared.logging_utils import get_logger

logger = get_logger("result_quality_scorer")


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    计算两个文本的相似度（0-1之间）
    
    Args:
        text1: 第一个文本
        text2: 第二个文本
        
    Returns:
        相似度分数（0-1之间）
    """
    if not text1 or not text2:
        return 0.0
    
    if text1 == text2:
        return 1.0
    
    # 使用SequenceMatcher计算相似度
    similarity = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    # 检查是否包含关系（一个文本是否包含另一个）
    if text1.lower() in text2.lower() or text2.lower() in text1.lower():
        # 如果一个是另一个的子串，提高相似度
        shorter = min(len(text1), len(text2))
        longer = max(len(text1), len(text2))
        if shorter > 0:
            containment_ratio = shorter / longer
            # 如果较短的文本占较长的80%以上，认为是高度相似的
            if containment_ratio >= 0.8:
                similarity = max(similarity, 0.9)
    
    return similarity


def calculate_result_relevance_score(
    query: str,
    result_node: Node,
    result_edge: Optional[Edge] = None,
) -> float:
    """
    计算检索结果相关性分数（0-1之间）
    
    评分维度：
    - 向量距离（0.4）：已计算，转换为相关性分数
    - 文本匹配度（0.3）：查询与节点名称/描述的匹配度
    - 上下文相关性（0.2）：节点在查询上下文中的重要性
    - 连接度（0.1）：节点与其他相关节点的连接数
    
    Args:
        query: 查询文本
        result_node: 结果节点
        result_edge: 结果边（可选）
        
    Returns:
        相关性分数（0-1之间）
    """
    score = 0.0
    
    # 1. 向量距离（0.4）
    vector_dist = result_node.attributes.get("vector_distance", float("inf"))
    if vector_dist == float("inf") or vector_dist is None:
        vector_score = 0.0
    else:
        # 将距离转换为相关性（距离越小，相关性越高）
        # 假设距离范围是0-1，距离0对应相关性1，距离1对应相关性0
        vector_score = max(0.0, 1.0 - min(vector_dist, 1.0))
    score += vector_score * 0.4
    
    # 2. 文本匹配度（0.3）
    node_name = result_node.attributes.get("name", "")
    node_description = result_node.attributes.get("description", "")
    
    # 计算查询与节点名称的匹配度
    name_similarity = 0.0
    if node_name:
        name_similarity = calculate_text_similarity(query, str(node_name))
    
    # 计算查询与节点描述的匹配度
    desc_similarity = 0.0
    if node_description:
        desc_similarity = calculate_text_similarity(query, str(node_description))
    
    # 取名称和描述匹配度的最大值
    text_score = max(name_similarity, desc_similarity * 0.8)  # 描述匹配度权重稍低
    score += text_score * 0.3
    
    # 3. 上下文相关性（0.2）
    # 如果节点有质量分数，使用它作为上下文相关性的指标
    quality_score = result_node.attributes.get("quality_score", None)
    if quality_score is not None:
        context_score = float(quality_score)
    else:
        # 如果没有质量分数，基于节点属性完整性估算
        has_name = bool(node_name)
        has_description = bool(node_description)
        context_score = 0.5 if (has_name or has_description) else 0.2
    score += context_score * 0.2
    
    # 4. 连接度（0.1）
    # 计算节点的连接数（通过skeleton_edges）
    connection_count = len(result_node.skeleton_edges) if hasattr(result_node, 'skeleton_edges') else 0
    # 归一化连接度（假设最大连接数为50）
    normalized_connections = min(connection_count / 50.0, 1.0) if connection_count > 0 else 0.0
    connection_score = normalized_connections
    score += connection_score * 0.1
    
    return min(score, 1.0)  # 确保分数不超过1.0


def rank_results_by_quality(
    results: List[Edge],
    query: str,
) -> List[Tuple[Edge, float]]:
    """
    按质量分数对结果排序
    
    Args:
        results: 检索结果边列表
        query: 查询文本
        
    Returns:
        排序后的(边, 质量分数)元组列表，按分数降序排列
    """
    scored_results = []
    
    for edge in results:
        # 计算节点1和节点2的平均质量分数
        score1 = calculate_result_relevance_score(query, edge.node1, edge)
        score2 = calculate_result_relevance_score(query, edge.node2, edge)
        
        # 边的质量分数是节点质量分数的平均值，加上边本身的向量距离
        edge_dist = edge.attributes.get("vector_distance", float("inf"))
        if edge_dist != float("inf") and edge_dist is not None:
            edge_score = max(0.0, 1.0 - min(edge_dist, 1.0))
        else:
            edge_score = 0.0
        
        # 综合分数：节点平均分数 * 0.8 + 边分数 * 0.2
        avg_node_score = (score1 + score2) / 2
        final_score = avg_node_score * 0.8 + edge_score * 0.2
        
        scored_results.append((edge, final_score))
    
    # 按分数降序排序
    scored_results.sort(key=lambda x: x[1], reverse=True)
    
    return scored_results


def filter_low_quality_results(
    results: List[Edge],
    query: str,
    min_quality_score: float = 0.6,
) -> List[Edge]:
    """
    过滤低质量检索结果
    
    Args:
        results: 检索结果边列表
        query: 查询文本
        min_quality_score: 最低质量阈值（默认0.6）
        
    Returns:
        过滤后的高质量结果列表
    """
    if not results:
        return []
    
    # 对结果进行质量评分和排序
    scored_results = rank_results_by_quality(results, query)
    
    # 过滤低质量结果
    filtered_results = [
        edge for edge, score in scored_results if score >= min_quality_score
    ]
    
    if len(filtered_results) < len(results):
        logger.info(
            f"质量过滤: 原始结果数 {len(results)}, "
            f"过滤后结果数 {len(filtered_results)} "
            f"(阈值: {min_quality_score})"
        )
    
    return filtered_results

