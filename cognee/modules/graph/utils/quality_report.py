"""
数据质量报告工具

生成数据质量报告，提供改进建议。
"""
from uuid import UUID
from typing import Dict, Any, List
from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.graph.utils.data_integrity_checker import (
    generate_integrity_report,
    check_graph_integrity,
)
from cognee.modules.graph.utils.entity_quality_scorer import (
    calculate_entity_quality_score,
)
from cognee.shared.logging_utils import get_logger

logger = get_logger("quality_report")


async def generate_quality_report(dataset_id: UUID) -> Dict[str, Any]:
    """
    生成数据质量报告
    
    包括：
    - 节点质量统计
    - 边质量统计
    - 完整性统计
    - 建议改进项
    
    Args:
        dataset_id: 数据集ID
        
    Returns:
        质量报告字典
    """
    graph_engine = await get_graph_engine()
    
    # 获取图谱数据
    try:
        nodes_data, edges_data = await graph_engine.get_graph_data()
    except Exception as e:
        logger.error(f"获取图谱数据失败: {str(e)}")
        return {
            "error": f"无法获取图谱数据: {str(e)}",
            "summary": {},
            "details": {},
        }
    
    # 转换为节点和边对象（简化处理）
    # 注意：这里需要根据实际的图数据库返回格式进行调整
    from cognee.modules.graph.cognee_graph.CogneeGraphElements import Node, Edge
    
    nodes = []
    edges = []
    
    # 处理节点数据
    for node_data in nodes_data:
        node_id = node_data[0] if isinstance(node_data, tuple) else node_data.get("id")
        node_attrs = node_data[1] if isinstance(node_data, tuple) else node_data
        node = Node(node_id, node_attrs)
        nodes.append(node)
    
    # 处理边数据（简化处理，实际可能需要更复杂的转换）
    # 这里假设edges_data是边元组列表
    for edge_data in edges_data:
        if isinstance(edge_data, tuple) and len(edge_data) >= 3:
            source_id = edge_data[0]
            target_id = edge_data[1]
            relationship = edge_data[2]
            # 创建简化的边对象
            # 注意：这里需要根据实际结构创建Edge对象
            # 暂时跳过边的详细处理
    
    # 生成完整性报告
    integrity_report = generate_integrity_report(nodes, edges)
    
    # 计算节点质量统计
    quality_scores = []
    high_quality_count = 0
    medium_quality_count = 0
    low_quality_count = 0
    empty_names_count = 0
    
    for node in nodes:
        # 尝试计算质量分数（如果是Entity类型）
        from cognee.modules.engine.models import Entity
        if isinstance(node, Entity) or node.attributes.get("type") == "Entity":
            try:
                # 创建临时Entity对象用于质量评分
                temp_entity = Entity(
                    id=node.id,
                    name=node.attributes.get("name", ""),
                    description=node.attributes.get("description", ""),
                    is_a=None,  # 简化处理
                    ontology_valid=node.attributes.get("ontology_valid", False),
                )
                score = calculate_entity_quality_score(temp_entity)
                quality_scores.append(score)
                
                if score >= 0.8:
                    high_quality_count += 1
                elif score >= 0.5:
                    medium_quality_count += 1
                else:
                    low_quality_count += 1
            except Exception as e:
                logger.debug(f"计算节点质量分数失败: {str(e)}")
        
        # 检查空名称
        name = node.attributes.get("name")
        if not name or not str(name).strip():
            empty_names_count += 1
    
    avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    
    # 生成报告
    report = {
        "dataset_id": str(dataset_id),
        "summary": {
            "node_quality": {
                "total": len(nodes),
                "high_quality": high_quality_count,  # score > 0.8
                "medium_quality": medium_quality_count,  # 0.5 < score <= 0.8
                "low_quality": low_quality_count,  # score <= 0.5
                "empty_names": empty_names_count,
                "average_quality_score": round(avg_quality_score, 3),
            },
            "edge_quality": {
                "total": len(edges),
                "valid": len(edges) - len(integrity_report["issues"]["dangling_edges"]),
                "invalid": len(integrity_report["issues"]["dangling_edges"]),
            },
            "integrity": {
                "orphan_nodes": len(integrity_report["issues"]["orphan_nodes"]),
                "dangling_edges": len(integrity_report["issues"]["dangling_edges"]),
                "health_score": round(integrity_report["health_score"], 3),
            },
        },
        "details": {
            "integrity_issues": integrity_report["issues"],
            "recommendations": generate_recommendations(
                high_quality_count,
                medium_quality_count,
                low_quality_count,
                empty_names_count,
                len(integrity_report["issues"]["orphan_nodes"]),
                len(integrity_report["issues"]["dangling_edges"]),
            ),
        },
    }
    
    return report


def generate_recommendations(
    high_quality: int,
    medium_quality: int,
    low_quality: int,
    empty_names: int,
    orphan_nodes: int,
    dangling_edges: int,
) -> List[str]:
    """
    生成改进建议
    
    Args:
        high_quality: 高质量节点数
        medium_quality: 中等质量节点数
        low_quality: 低质量节点数
        empty_names: 空名称节点数
        orphan_nodes: 孤立节点数
        dangling_edges: 悬空边数
        
    Returns:
        建议列表
    """
    recommendations = []
    
    if low_quality > 0:
        recommendations.append(
            f"发现 {low_quality} 个低质量节点，建议检查并完善节点属性（名称、描述等）"
        )
    
    if empty_names > 0:
        recommendations.append(
            f"发现 {empty_names} 个空名称节点，建议补充节点名称或从描述中提取"
        )
    
    if orphan_nodes > 0:
        recommendations.append(
            f"发现 {orphan_nodes} 个孤立节点，建议检查这些节点是否需要连接到图谱中"
        )
    
    if dangling_edges > 0:
        recommendations.append(
            f"发现 {dangling_edges} 个悬空边，建议检查边的源节点和目标节点是否存在"
        )
    
    if medium_quality > 0:
        recommendations.append(
            f"有 {medium_quality} 个中等质量节点，建议完善这些节点的描述信息以提升质量"
        )
    
    if not recommendations:
        recommendations.append("图谱数据质量良好，无需特别改进")
    
    return recommendations

