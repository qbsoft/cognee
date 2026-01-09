"""
实体名称规范化与相似实体查找工具

提供实体名称规范化、相似实体查找和合并功能，用于减少重复节点。
"""
import re
from typing import List, Optional, Dict
from difflib import SequenceMatcher

from cognee.modules.engine.models import Entity
from cognee.shared.logging_utils import get_logger

logger = get_logger("entity_normalization")


def normalize_entity_name(name: str) -> str:
    """
    规范化实体名称：
    - 去除前后空格
    - 统一标点符号处理（中文/英文标点）
    - 处理常见变体
    - 统一大小写（中文不受影响）
    
    Args:
        name: 原始实体名称
        
    Returns:
        规范化后的实体名称
    """
    if not name or not isinstance(name, str):
        return ""
    
    # 去除前后空格
    normalized = name.strip()
    
    # 如果为空，直接返回
    if not normalized:
        return ""
    
    # 统一标点符号：将中文标点转换为英文标点（某些情况下）
    # 注意：对于中文实体，我们保留中文标点，只处理明显的错误
    # 统一空格：多个连续空格合并为一个
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # 去除首尾的标点符号（如果存在）
    normalized = normalized.strip('.,;:!?。，；：！？')
    
    # 统一大小写：对于英文，转换为小写；中文不受影响
    # 检查是否包含中文字符
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', normalized))
    if not has_chinese:
        # 纯英文，转换为小写
        normalized = normalized.lower()
    
    return normalized


def calculate_string_similarity(str1: str, str2: str) -> float:
    """
    计算两个字符串的相似度（0-1之间）
    
    使用多种方法计算相似度：
    1. SequenceMatcher（基于最长公共子序列）
    2. Jaccard相似度（基于字符集合）
    3. 取两者的平均值
    
    Args:
        str1: 第一个字符串
        str2: 第二个字符串
        
    Returns:
        相似度分数（0-1之间）
    """
    if not str1 or not str2:
        return 0.0
    
    if str1 == str2:
        return 1.0
    
    # 方法1：SequenceMatcher相似度
    seq_similarity = SequenceMatcher(None, str1, str2).ratio()
    
    # 方法2：Jaccard相似度（基于字符集合）
    set1 = set(str1)
    set2 = set(str2)
    if not set1 or not set2:
        jaccard_similarity = 0.0
    else:
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        jaccard_similarity = intersection / union if union > 0 else 0.0
    
    # 对于中文，使用字符级别的Jaccard
    if bool(re.search(r'[\u4e00-\u9fff]', str1)) or bool(re.search(r'[\u4e00-\u9fff]', str2)):
        # 中文使用字符级别的相似度
        chars1 = set(str1)
        chars2 = set(str2)
        if chars1 and chars2:
            char_intersection = len(chars1 & chars2)
            char_union = len(chars1 | chars2)
            char_jaccard = char_intersection / char_union if char_union > 0 else 0.0
            # 对于中文，更重视字符级别的相似度
            jaccard_similarity = (jaccard_similarity + char_jaccard) / 2
    
    # 取平均值
    similarity = (seq_similarity + jaccard_similarity) / 2
    
    return similarity


def find_similar_entities(
    entity_name: str,
    existing_entities: List[Entity],
    threshold: float = 0.85,
    normalized_name_cache: Optional[Dict[str, str]] = None
) -> Optional[Entity]:
    """
    在已有实体列表中查找相似实体
    
    使用字符串相似度算法找到相似实体。如果相似度超过阈值，返回已有实体（用于合并）。
    
    Args:
        entity_name: 要查找的实体名称
        existing_entities: 已有实体列表
        threshold: 相似度阈值（默认0.85）
        normalized_name_cache: 规范化名称缓存，用于加速查找
        
    Returns:
        如果找到相似实体，返回该实体；否则返回None
    """
    if not entity_name or not existing_entities:
        return None
    
    # 规范化输入名称
    normalized_input = normalize_entity_name(entity_name)
    if not normalized_input:
        return None
    
    # 如果提供了缓存，使用缓存；否则创建新的缓存
    if normalized_name_cache is None:
        normalized_name_cache = {}
    
    best_match = None
    best_similarity = 0.0
    
    for entity in existing_entities:
        # 获取实体名称
        entity_name_to_check = getattr(entity, 'name', None)
        if not entity_name_to_check:
            continue
        
        # 规范化实体名称（使用缓存）
        cache_key = str(id(entity))
        if cache_key not in normalized_name_cache:
            normalized_name_cache[cache_key] = normalize_entity_name(str(entity_name_to_check))
        normalized_entity_name = normalized_name_cache[cache_key]
        
        if not normalized_entity_name:
            continue
        
        # 如果规范化后的名称完全相同，直接返回
        if normalized_input == normalized_entity_name:
            return entity
        
        # 计算相似度
        similarity = calculate_string_similarity(normalized_input, normalized_entity_name)
        
        # 检查是否是包含关系（如"临时冻结"和"临时冻结措施"）
        if normalized_input in normalized_entity_name or normalized_entity_name in normalized_input:
            # 如果一个是另一个的子串，提高相似度
            shorter = min(len(normalized_input), len(normalized_entity_name))
            longer = max(len(normalized_input), len(normalized_entity_name))
            if shorter > 0:
                containment_ratio = shorter / longer
                # 如果较短的字符串占较长的80%以上，认为是相似的
                if containment_ratio >= 0.8:
                    similarity = max(similarity, 0.9)
        
        if similarity > best_similarity and similarity >= threshold:
            best_similarity = similarity
            best_match = entity
    
    if best_match:
        logger.debug(
            f"找到相似实体: '{entity_name}' 与 '{best_match.name}' "
            f"(相似度: {best_similarity:.2f})"
        )
    
    return best_match


def merge_entity_attributes(source_entity: Entity, target_entity: Entity) -> Entity:
    """
    合并两个实体的属性
    
    将source_entity的属性合并到target_entity中，保留target_entity的ID和主要属性。
    
    Args:
        source_entity: 源实体（将被合并的实体）
        target_entity: 目标实体（保留的实体）
        
    Returns:
        合并后的目标实体
    """
    # 如果源实体有描述而目标实体没有，使用源实体的描述
    if not target_entity.description and source_entity.description:
        target_entity.description = source_entity.description
    
    # 如果源实体通过本体验证而目标实体没有，更新本体验证状态
    if source_entity.ontology_valid and not target_entity.ontology_valid:
        target_entity.ontology_valid = True
    
    # 合并其他属性（如果有的话）
    # 这里可以根据需要扩展
    
    logger.debug(f"合并实体属性: '{source_entity.name}' -> '{target_entity.name}'")
    
    return target_entity

