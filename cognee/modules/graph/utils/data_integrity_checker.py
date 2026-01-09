"""
数据完整性检查工具

检查图谱数据完整性，发现数据问题。
"""
from typing import List, Dict, Set
from cognee.modules.graph.cognee_graph.CogneeGraphElements import Node, Edge
from cognee.modules.engine.models import Entity, EntityType
from cognee.shared.logging_utils import get_logger

logger = get_logger("data_integrity_checker")


def check_node_integrity(node: Node) -> List[str]:
    """
    检查节点完整性，返回问题列表
    
    Args:
        node: 节点对象
        
    Returns:
        问题列表
    """
    issues = []
    
    # 检查名称
    name = node.attributes.get("name")
    if not name or not str(name).strip():
        issues.append("节点名称为空")
    
    # 检查类型
    node_type = node.attributes.get("type")
    if not node_type:
        issues.append("节点类型缺失")
    
    # 检查必需属性（根据节点类型）
    if node_type == "DocumentChunk":
        if not node.attributes.get("text"):
            issues.append("DocumentChunk节点缺少text属性")
    elif node_type == "Entity":
        if not node.attributes.get("description"):
            issues.append("Entity节点缺少description属性")
    
    return issues


def check_graph_integrity(
    nodes: List[Node],
    edges: List[Edge],
) -> Dict[str, List[str]]:
    """
    检查图谱完整性
    
    检查孤立节点、悬空边、节点属性缺失等问题。
    
    Args:
        nodes: 节点列表
        edges: 边列表
        
    Returns:
        包含各种问题的字典
    """
    issues = {
        "orphan_nodes": [],  # 孤立节点（没有连接的节点）
        "dangling_edges": [],  # 悬空边（边的节点不存在）
        "missing_attributes": [],  # 节点属性缺失
        "empty_names": [],  # 空名称节点
    }
    
    # 创建节点ID集合
    node_ids: Set[str] = {node.id for node in nodes}
    
    # 创建节点连接计数
    node_connections: Dict[str, int] = {node.id: 0 for node in nodes}
    
    # 检查边和节点连接
    for edge in edges:
        source_id = edge.node1.id if hasattr(edge, 'node1') else None
        target_id = edge.node2.id if hasattr(edge, 'node2') else None
        
        # 检查悬空边
        if source_id and source_id not in node_ids:
            issues["dangling_edges"].append(
                f"边 {edge} 的源节点 {source_id} 不存在"
            )
        if target_id and target_id not in node_ids:
            issues["dangling_edges"].append(
                f"边 {edge} 的目标节点 {target_id} 不存在"
            )
        
        # 更新连接计数
        if source_id and source_id in node_ids:
            node_connections[source_id] = node_connections.get(source_id, 0) + 1
        if target_id and target_id in node_ids:
            node_connections[target_id] = node_connections.get(target_id, 0) + 1
    
    # 检查孤立节点
    for node in nodes:
        connection_count = node_connections.get(node.id, 0)
        if connection_count == 0:
            node_name = node.attributes.get("name", "Unknown")
            issues["orphan_nodes"].append(
                f"节点 {node.id} ({node_name}) 是孤立节点（没有连接）"
            )
        
        # 检查节点完整性
        node_issues = check_node_integrity(node)
        if node_issues:
            node_name = node.attributes.get("name", "Unknown")
            issues["missing_attributes"].append(
                f"节点 {node.id} ({node_name}): {', '.join(node_issues)}"
            )
        
        # 检查空名称
        name = node.attributes.get("name")
        if not name or not str(name).strip():
            issues["empty_names"].append(f"节点 {node.id} 名称为空")
    
    return issues


def generate_integrity_report(
    nodes: List[Node],
    edges: List[Edge],
) -> Dict[str, any]:
    """
    生成完整性报告
    
    Args:
        nodes: 节点列表
        edges: 边列表
        
    Returns:
        完整性报告字典
    """
    issues = check_graph_integrity(nodes, edges)
    
    total_nodes = len(nodes)
    total_edges = len(edges)
    
    orphan_count = len(issues["orphan_nodes"])
    dangling_count = len(issues["dangling_edges"])
    missing_attr_count = len(issues["missing_attributes"])
    empty_name_count = len(issues["empty_names"])
    
    report = {
        "summary": {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "orphan_nodes": orphan_count,
            "dangling_edges": dangling_count,
            "missing_attributes": missing_attr_count,
            "empty_names": empty_name_count,
        },
        "issues": issues,
        "health_score": calculate_health_score(
            total_nodes, total_edges, orphan_count, dangling_count, missing_attr_count, empty_name_count
        ),
    }
    
    return report


def calculate_health_score(
    total_nodes: int,
    total_edges: int,
    orphan_count: int,
    dangling_count: int,
    missing_attr_count: int,
    empty_name_count: int,
) -> float:
    """
    计算图谱健康分数（0-1之间）
    
    Args:
        total_nodes: 总节点数
        total_edges: 总边数
        orphan_count: 孤立节点数
        dangling_count: 悬空边数
        missing_attr_count: 缺失属性节点数
        empty_name_count: 空名称节点数
        
    Returns:
        健康分数（0-1之间）
    """
    if total_nodes == 0:
        return 0.0
    
    score = 1.0
    
    # 孤立节点扣分（每个扣0.1，最多扣0.3）
    if total_nodes > 0:
        orphan_ratio = orphan_count / total_nodes
        score -= min(orphan_ratio * 0.3, 0.3)
    
    # 悬空边扣分（每个扣0.05，最多扣0.2）
    if total_edges > 0:
        dangling_ratio = dangling_count / total_edges
        score -= min(dangling_ratio * 0.2, 0.2)
    
    # 缺失属性扣分（每个扣0.02，最多扣0.3）
    if total_nodes > 0:
        missing_ratio = missing_attr_count / total_nodes
        score -= min(missing_ratio * 0.3, 0.3)
    
    # 空名称扣分（每个扣0.01，最多扣0.2）
    if total_nodes > 0:
        empty_ratio = empty_name_count / total_nodes
        score -= min(empty_ratio * 0.2, 0.2)
    
    return max(score, 0.0)  # 确保分数不为负

