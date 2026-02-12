"""
跨文档实体消歧和去重。

合并规则:
1. 同类型实体，名称相似度超过阈值 -> 合并
2. 实体名称出现在另一实体的别名列表中 -> 合并
3. 不同类型的实体即使名称相同也不合并
"""
import logging
from typing import List, Dict, Any, Set
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


async def resolve_entities(
    entities: List[Dict[str, Any]],
    fuzzy_threshold: float = 0.85,
    embedding_threshold: float = 0.9,
    embedding_func=None,
) -> List[Dict[str, Any]]:
    if not entities or len(entities) <= 1:
        return entities

    n = len(entities)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if _should_merge(entities[i], entities[j], fuzzy_threshold):
                union(i, j)

    groups: Dict[int, List[int]] = {}
    for i in range(n):
        root = find(i)
        if root not in groups:
            groups[root] = []
        groups[root].append(i)

    result = []
    for indices in groups.values():
        if len(indices) == 1:
            result.append(entities[indices[0]].copy())
        else:
            merged = _merge_entity_group([entities[i] for i in indices])
            result.append(merged)

    logger.info(f"实体消歧: {n} 个实体 -> {len(result)} 个唯一实体")
    return result


def _should_merge(entity_a: Dict, entity_b: Dict, threshold: float) -> bool:
    type_a = entity_a.get("type", "").lower()
    type_b = entity_b.get("type", "").lower()
    if type_a and type_b and type_a != type_b:
        return False

    name_a = entity_a.get("name", "")
    name_b = entity_b.get("name", "")
    aliases_a = set(entity_a.get("aliases", []))
    aliases_b = set(entity_b.get("aliases", []))

    if name_a == name_b:
        return True

    all_names_a = {name_a} | aliases_a
    all_names_b = {name_b} | aliases_b
    if all_names_a & all_names_b:
        return True

    similarity = _name_similarity(name_a, name_b)
    if similarity >= threshold:
        return True

    for alias_b in aliases_b:
        if _name_similarity(name_a, alias_b) >= threshold:
            return True
    for alias_a in aliases_a:
        if _name_similarity(alias_a, name_b) >= threshold:
            return True

    return False


def _name_similarity(name_a: str, name_b: str) -> float:
    if not name_a or not name_b:
        return 0.0
    return SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio()


def _merge_entity_group(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    primary = max(entities, key=lambda e: len(e.get("name", "")))
    merged = primary.copy()
    all_names: Set[str] = set()
    for e in entities:
        all_names.add(e.get("name", ""))
        all_names.update(e.get("aliases", []))
    all_names.discard(merged["name"])
    all_names.discard("")
    merged["aliases"] = sorted(all_names)
    merged["merged_from"] = [e.get("id", "") for e in entities]
    return merged
