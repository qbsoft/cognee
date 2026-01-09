"""
实体质量评分工具

为每个实体计算质量分数，用于过滤低质量实体。
"""
from typing import List, Optional
from cognee.modules.engine.models import Entity
from cognee.shared.logging_utils import get_logger

logger = get_logger("entity_quality_scorer")


def calculate_entity_quality_score(entity: Entity) -> float:
    """
    计算实体质量分数（0-1之间）
    
    评分维度：
    - 名称完整性（0.3）：检查名称是否非空且有意义
    - 描述完整性（0.2）：检查是否有描述信息
    - 类型准确性（0.2）：检查类型是否合理（非空、非"NodeSet"）
    - 连接度（0.2）：计算与其他节点的连接数（归一化，需要外部提供）
    - 本体验证（0.1）：是否通过本体验证
    
    Args:
        entity: 实体对象
        
    Returns:
        质量分数（0-1之间）
    """
    score = 0.0
    
    # 1. 名称完整性（0.3）
    name = getattr(entity, 'name', None)
    if name and str(name).strip():
        name_str = str(name).strip()
        # 检查名称是否有意义（长度至少为1，不是纯空格）
        if len(name_str) > 0:
            # 如果名称长度合理（1-100个字符），给满分
            if 1 <= len(name_str) <= 100:
                score += 0.3
            # 如果名称过长，适当扣分
            elif len(name_str) > 100:
                score += 0.2
        else:
            score += 0.0
    else:
        score += 0.0
    
    # 2. 描述完整性（0.2）
    description = getattr(entity, 'description', None)
    if description and str(description).strip():
        desc_str = str(description).strip()
        # 如果描述长度合理（至少5个字符），给满分
        if len(desc_str) >= 5:
            score += 0.2
        # 如果描述太短，适当扣分
        elif len(desc_str) > 0:
            score += 0.1
    else:
        score += 0.0
    
    # 3. 类型准确性（0.2）
    entity_type = getattr(entity, 'is_a', None)
    if entity_type:
        type_name = getattr(entity_type, 'name', None) or getattr(entity_type, 'type', None)
        if type_name and str(type_name).strip():
            type_str = str(type_name).strip().lower()
            # 检查类型是否合理（不是"NodeSet"等系统类型）
            if type_str not in ["nodeset", "unknown", ""]:
                score += 0.2
            else:
                score += 0.1
        else:
            score += 0.1
    else:
        score += 0.0
    
    # 4. 连接度（0.2）
    # 注意：连接度需要从外部提供，因为实体对象本身可能不包含连接信息
    # 这里我们使用一个默认值，实际使用时应该从图结构中获取
    # 暂时给一个中等分数，实际使用时需要传入连接数
    connection_score = 0.1  # 默认中等连接度
    # 如果实体有belongs_to_set，说明至少有一个连接
    if hasattr(entity, 'belongs_to_set') and entity.belongs_to_set:
        connection_score = 0.15
    score += connection_score
    
    # 5. 本体验证（0.1）
    ontology_valid = getattr(entity, 'ontology_valid', False)
    if ontology_valid:
        score += 0.1
    else:
        score += 0.0
    
    return min(score, 1.0)  # 确保分数不超过1.0


def calculate_entity_quality_score_with_connections(
    entity: Entity,
    connection_count: int = 0,
    max_connections: int = 100,
) -> float:
    """
    计算实体质量分数（包含连接度信息）
    
    Args:
        entity: 实体对象
        connection_count: 实体的连接数
        max_connections: 最大连接数（用于归一化）
        
    Returns:
        质量分数（0-1之间）
    """
    score = 0.0
    
    # 1. 名称完整性（0.3）
    name = getattr(entity, 'name', None)
    if name and str(name).strip():
        name_str = str(name).strip()
        if 1 <= len(name_str) <= 100:
            score += 0.3
        elif len(name_str) > 100:
            score += 0.2
    else:
        score += 0.0
    
    # 2. 描述完整性（0.2）
    description = getattr(entity, 'description', None)
    if description and str(description).strip():
        desc_str = str(description).strip()
        if len(desc_str) >= 5:
            score += 0.2
        elif len(desc_str) > 0:
            score += 0.1
    else:
        score += 0.0
    
    # 3. 类型准确性（0.2）
    entity_type = getattr(entity, 'is_a', None)
    if entity_type:
        type_name = getattr(entity_type, 'name', None) or getattr(entity_type, 'type', None)
        if type_name and str(type_name).strip():
            type_str = str(type_name).strip().lower()
            if type_str not in ["nodeset", "unknown", ""]:
                score += 0.2
            else:
                score += 0.1
        else:
            score += 0.1
    else:
        score += 0.0
    
    # 4. 连接度（0.2）- 使用实际连接数
    if max_connections > 0:
        normalized_connections = min(connection_count / max_connections, 1.0)
        connection_score = normalized_connections * 0.2
    else:
        # 如果没有连接信息，给一个默认值
        connection_score = 0.1 if connection_count > 0 else 0.0
    score += connection_score
    
    # 5. 本体验证（0.1）
    ontology_valid = getattr(entity, 'ontology_valid', False)
    if ontology_valid:
        score += 0.1
    else:
        score += 0.0
    
    return min(score, 1.0)


def filter_low_quality_entities(
    entities: List[Entity],
    min_score: float = 0.5,
    connection_counts: Optional[dict] = None,
    max_connections: int = 100,
) -> List[Entity]:
    """
    根据质量分数过滤实体
    
    Args:
        entities: 实体列表
        min_score: 最低质量阈值（默认0.5）
        connection_counts: 实体连接数字典（可选，用于更准确的质量评分）
        max_connections: 最大连接数（用于归一化）
        
    Returns:
        过滤后的高质量实体列表
    """
    filtered_entities = []
    removed_count = 0
    
    for entity in entities:
        if connection_counts and hasattr(entity, 'id'):
            entity_id = str(getattr(entity, 'id', ''))
            connection_count = connection_counts.get(entity_id, 0)
            score = calculate_entity_quality_score_with_connections(
                entity, connection_count, max_connections
            )
        else:
            score = calculate_entity_quality_score(entity)
        
        if score >= min_score:
            filtered_entities.append(entity)
            # 将质量分数存储在实体属性中（如果实体支持动态属性）
            if hasattr(entity, '__dict__'):
                entity.__dict__['quality_score'] = score
        else:
            removed_count += 1
            entity_name = getattr(entity, 'name', 'Unknown')
            logger.debug(
                f"过滤低质量实体: '{entity_name}' (质量分数: {score:.2f} < {min_score})"
            )
    
    if removed_count > 0:
        logger.info(
            f"过滤了 {removed_count} 个低质量实体，保留了 {len(filtered_entities)} 个高质量实体"
        )
    
    return filtered_entities

