"""
检索质量指标工具

计算检索质量指标，监控检索效果。
"""
from typing import List, Dict, Optional
from cognee.modules.graph.cognee_graph.CogneeGraphElements import Edge
from cognee.modules.retrieval.utils.result_quality_scorer import (
    calculate_result_relevance_score,
    rank_results_by_quality,
)
from cognee.shared.logging_utils import get_logger

logger = get_logger("quality_metrics")


def calculate_search_quality_metrics(
    query: str,
    results: List[Edge],
    answer: Optional[str] = None,
) -> Dict[str, float]:
    """
    计算检索质量指标
    
    指标包括：
    - 平均相关性分数
    - 结果多样性分数
    - 覆盖率（查询中的实体是否都被检索到）
    - 精确度（检索到的实体是否都与查询相关）
    
    Args:
        query: 查询文本
        results: 检索结果列表
        answer: 答案文本（可选，用于计算覆盖率）
        
    Returns:
        质量指标字典
    """
    if not results:
        return {
            "avg_relevance": 0.0,
            "diversity_score": 0.0,
            "coverage": 0.0,
            "precision": 0.0,
        }
    
    # 1. 平均相关性分数
    relevance_scores = []
    for edge in results:
        score1 = calculate_result_relevance_score(query, edge.node1, edge)
        score2 = calculate_result_relevance_score(query, edge.node2, edge)
        avg_score = (score1 + score2) / 2
        relevance_scores.append(avg_score)
    
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    
    # 2. 结果多样性分数
    diversity_score = calculate_diversity_score(results)
    
    # 3. 覆盖率（如果提供了答案）
    coverage = 0.0
    if answer:
        coverage = calculate_coverage(query, results, answer)
    
    # 4. 精确度
    precision = calculate_precision(query, results)
    
    return {
        "avg_relevance": round(avg_relevance, 3),
        "diversity_score": round(diversity_score, 3),
        "coverage": round(coverage, 3),
        "precision": round(precision, 3),
    }


def calculate_diversity_score(results: List[Edge]) -> float:
    """
    计算结果多样性分数
    
    基于节点类型的多样性。
    
    Args:
        results: 检索结果列表
        
    Returns:
        多样性分数（0-1之间）
    """
    if not results:
        return 0.0
    
    # 统计节点类型
    node_types = set()
    for edge in results:
        node1_type = edge.node1.attributes.get("type", "unknown")
        node2_type = edge.node2.attributes.get("type", "unknown")
        node_types.add(node1_type)
        node_types.add(node2_type)
    
    # 多样性分数 = 类型数量 / 最大可能类型数（假设最多10种类型）
    max_types = min(len(results) * 2, 10)  # 每个结果最多2个节点类型
    diversity = len(node_types) / max_types if max_types > 0 else 0.0
    
    return min(diversity, 1.0)


def calculate_coverage(
    query: str,
    results: List[Edge],
    answer: str,
) -> float:
    """
    计算覆盖率
    
    检查答案中提到的实体是否在检索结果中。
    
    Args:
        query: 查询文本
        results: 检索结果列表
        answer: 答案文本
        
    Returns:
        覆盖率（0-1之间）
    """
    # 简化实现：检查答案中的关键词是否在结果节点名称中出现
    # 实际实现可能需要更复杂的实体提取和匹配
    
    if not results or not answer:
        return 0.0
    
    # 提取结果中的节点名称
    result_names = set()
    for edge in results:
        name1 = edge.node1.attributes.get("name", "")
        name2 = edge.node2.attributes.get("name", "")
        if name1:
            result_names.add(str(name1).lower())
        if name2:
            result_names.add(str(name2).lower())
    
    # 检查答案中的关键词（简化处理）
    answer_words = set(answer.lower().split())
    
    # 计算匹配的关键词数量
    matched_words = answer_words & result_names
    
    coverage = len(matched_words) / len(answer_words) if answer_words else 0.0
    
    return min(coverage, 1.0)


def calculate_precision(query: str, results: List[Edge]) -> float:
    """
    计算精确度
    
    基于结果的相关性分数计算精确度。
    
    Args:
        query: 查询文本
        results: 检索结果列表
        
    Returns:
        精确度（0-1之间）
    """
    if not results:
        return 0.0
    
    # 计算每个结果的相关性分数
    relevance_scores = []
    for edge in results:
        score1 = calculate_result_relevance_score(query, edge.node1, edge)
        score2 = calculate_result_relevance_score(query, edge.node2, edge)
        avg_score = (score1 + score2) / 2
        relevance_scores.append(avg_score)
    
    # 精确度 = 平均相关性分数
    precision = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    
    return precision

