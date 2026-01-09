"""
关系合理性验证工具

验证知识图谱中关系的合理性，过滤无效关系。
"""
from typing import Tuple, List, Dict, Optional
from cognee.modules.graph.cognee_graph.CogneeGraphElements import Edge
from cognee.shared.logging_utils import get_logger

logger = get_logger("relationship_validator")


# 定义关系规则：每种关系类型允许的源节点类型和目标节点类型
RELATIONSHIP_RULES: Dict[str, Dict[str, List[str]]] = {
    "contains": {
        "allowed_source_types": ["DocumentChunk", "Entity", "NodeSet"],
        "allowed_target_types": ["Entity", "DocumentChunk", "TextSummary"],
    },
    "is_part_of": {
        "allowed_source_types": ["Entity", "DocumentChunk"],
        "allowed_target_types": ["Entity", "DocumentChunk", "NodeSet"],
    },
    "is_a": {
        "allowed_source_types": ["Entity"],
        "allowed_target_types": ["EntityType", "Entity"],
    },
    "mentioned_in": {
        "allowed_source_types": ["Entity"],
        "allowed_target_types": ["DocumentChunk", "TextSummary"],
    },
    "exists_in": {
        "allowed_source_types": ["EntityType", "Entity"],
        "allowed_target_types": ["DocumentChunk", "NodeSet"],
    },
    "made_from": {
        "allowed_source_types": ["Entity"],
        "allowed_target_types": ["Entity", "DocumentChunk"],
    },
    "belongs_to_set": {
        "allowed_source_types": ["Entity", "EntityType"],
        "allowed_target_types": ["NodeSet"],
    },
    # 添加更多关系规则...
}

# 定义单向关系（这些关系不应该有反向关系）
UNIDIRECTIONAL_RELATIONSHIPS: List[str] = [
    "is_a",  # A is_a B 不应该有 B is_a A
    "contains",  # A contains B 通常不应该有 B contains A（除非是特殊情况）
    "belongs_to_set",  # A belongs_to_set B 不应该有 B belongs_to_set A
]

# 定义禁止的关系组合（如果存在A->B的关系，则不应该存在B->A的关系）
FORBIDDEN_REVERSE_PAIRS: List[Tuple[str, str]] = [
    ("contains", "is_part_of"),  # 如果 A contains B，则不应该有 B is_part_of A（语义重复）
    ("is_a", "is_a"),  # 如果 A is_a B，则不应该有 B is_a A（除非是特殊情况，但通常不允许）
]


def validate_relationship(
    source_type: str,
    relationship: str,
    target_type: str,
    existing_relationships: Optional[Dict[str, bool]] = None,
    source_id: Optional[str] = None,
    target_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    验证关系是否合理
    
    检查关系类型是否适合源节点和目标节点类型，检查是否有循环关系等。
    
    Args:
        source_type: 源节点类型
        relationship: 关系名称
        target_type: 目标节点类型
        existing_relationships: 已有关系映射（用于检查循环关系）
        source_id: 源节点ID（用于检查循环关系）
        target_id: 目标节点ID（用于检查循环关系）
        
    Returns:
        (是否有效, 错误信息)
    """
    # 检查基本参数
    if not source_type or not relationship or not target_type:
        return False, "源节点类型、关系名称或目标节点类型为空"
    
    # 检查关系规则
    if relationship in RELATIONSHIP_RULES:
        rules = RELATIONSHIP_RULES[relationship]
        allowed_source_types = rules.get("allowed_source_types", [])
        allowed_target_types = rules.get("allowed_target_types", [])
        
        # 检查源节点类型
        if allowed_source_types and source_type not in allowed_source_types:
            return False, (
                f"关系 '{relationship}' 不允许源节点类型 '{source_type}'。"
                f"允许的类型: {allowed_source_types}"
            )
        
        # 检查目标节点类型
        if allowed_target_types and target_type not in allowed_target_types:
            return False, (
                f"关系 '{relationship}' 不允许目标节点类型 '{target_type}'。"
                f"允许的类型: {allowed_target_types}"
            )
    
    # 检查单向关系的反向关系
    if relationship in UNIDIRECTIONAL_RELATIONSHIPS and existing_relationships and source_id and target_id:
        # 检查是否存在反向关系
        reverse_key = f"{target_id}_{source_id}_{relationship}"
        if reverse_key in existing_relationships:
            return False, (
                f"关系 '{relationship}' 是单向关系，但已存在反向关系 "
                f"({target_id} -> {source_id})"
            )
    
    # 检查禁止的关系组合
    if existing_relationships and source_id and target_id:
        for forbidden_rel, reverse_rel in FORBIDDEN_REVERSE_PAIRS:
            if relationship == forbidden_rel:
                # 检查是否存在禁止的反向关系
                reverse_key = f"{target_id}_{source_id}_{reverse_rel}"
                if reverse_key in existing_relationships:
                    return False, (
                        f"关系 '{relationship}' 与反向关系 '{reverse_rel}' 冲突 "
                        f"({target_id} -> {source_id})"
                    )
    
    # 检查自循环（节点指向自己）
    if source_id and target_id and source_id == target_id:
        # 某些关系允许自循环（如"is_a"），但大多数不允许
        if relationship not in ["is_a"]:  # 可以根据需要扩展允许自循环的关系
            return False, f"关系 '{relationship}' 不允许自循环（节点指向自己）"
    
    return True, ""


def filter_invalid_relationships(
    edges: List[Edge],
    existing_relationships: Optional[Dict[str, bool]] = None,
) -> List[Edge]:
    """
    批量验证关系列表，过滤无效关系
    
    Args:
        edges: 边列表
        existing_relationships: 已有关系映射（用于检查循环关系）
        
    Returns:
        过滤后的有效边列表
    """
    if existing_relationships is None:
        existing_relationships = {}
    
    valid_edges = []
    invalid_count = 0
    
    for edge in edges:
        source_type = edge.node1.attributes.get("type", "unknown")
        target_type = edge.node2.attributes.get("type", "unknown")
        relationship = edge.attributes.get("relationship_name", "")
        source_id = edge.node1.id
        target_id = edge.node2.id
        
        is_valid, error_msg = validate_relationship(
            source_type=source_type,
            relationship=relationship,
            target_type=target_type,
            existing_relationships=existing_relationships,
            source_id=source_id,
            target_id=target_id,
        )
        
        if is_valid:
            valid_edges.append(edge)
            # 更新已有关系映射
            edge_key = f"{source_id}_{target_id}_{relationship}"
            existing_relationships[edge_key] = True
        else:
            invalid_count += 1
            logger.warning(
                f"过滤无效关系: {source_id} --[{relationship}]--> {target_id}. "
                f"原因: {error_msg}"
            )
    
    if invalid_count > 0:
        logger.info(f"过滤了 {invalid_count} 个无效关系，保留了 {len(valid_edges)} 个有效关系")
    
    return valid_edges

