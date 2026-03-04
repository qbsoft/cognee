from typing import List

from cognee.modules.graph.cognee_graph.CogneeGraphElements import Edge
from cognee.modules.engine.utils import translate_relationship_name


def _get_node_label(node_attributes: dict, node_id: str) -> str:
    """
    获取节点标签，处理空名称的情况
    
    优先级：
    1. name 属性
    2. text 属性的前30个字符（去除换行）
    3. description 属性的前30个字符
    4. type + ID 前8位
    5. 节点_ + ID 前8位
    """
    if not node_attributes:
        return f"节点_{str(node_id)[:8]}"
    
    # 优先使用 name 字段
    name = node_attributes.get("name")
    if name and name != "" and str(name).strip():
        return str(name).strip()
    
    # 其次使用 text 字段的前几个词（对于 DocumentChunk）
    text = node_attributes.get("text")
    # 处理 None、空字符串或空值的情况
    if text and text != "" and str(text).strip():
        # 取前30个字符作为标签
        text_str = str(text).strip()
        # 如果包含换行，取第一行
        first_line = text_str.split('\n')[0] if '\n' in text_str else text_str
        # 限制长度
        if len(first_line) > 30:
            return first_line[:30] + "..."
        return first_line
    
    # 如果 text 为空，尝试从嵌套的 attributes 中获取
    if isinstance(node_attributes.get("attributes"), dict):
        nested_text = node_attributes["attributes"].get("text")
        if nested_text and nested_text != "" and str(nested_text).strip():
            text_str = str(nested_text).strip()
            first_line = text_str.split('\n')[0] if '\n' in text_str else text_str
            if len(first_line) > 30:
                return first_line[:30] + "..."
            return first_line
    
    # 使用 description 字段
    description = node_attributes.get("description")
    if description and description != "" and str(description).strip():
        desc_str = str(description).strip()
        if len(desc_str) > 30:
            return desc_str[:30] + "..."
        return desc_str
    
    # 使用 type 字段
    node_type = node_attributes.get("type", "unknown")
    if node_type and node_type != "unknown":
        type_translations = {
            "DocumentChunk": "文档片段",
            "TextDocument": "文档",
            "Entity": "实体",
            "EntityType": "实体类型",
            "TextSummary": "摘要",
            "person": "人员",
            "organization": "组织",
            "location": "位置",
            "date": "日期",
            "event": "事件",
            "work": "作品",
            "product": "产品",
            "concept": "概念",
            "documentchunk": "文档片段",
            "document": "文档",
            "entity": "实体",
            "entitytype": "实体类型",
            "textsummary": "摘要",
        }
        translated_type = type_translations.get(node_type, node_type)
        return f"{translated_type}_{str(node_id)[:8]}"
    
    # 最后使用 ID 的前8位
    return f"节点_{str(node_id)[:8]}"



# Internal/structural node types that should be hidden from graph visualization.
# These are infrastructure nodes that clutter the graph without user value.
# - NodeSet: container nodes for grouping data points
# - KnowledgeDistillation: auto-generated knowledge summaries
# - Timestamp: temporal metadata nodes
# - DocumentChunk: raw text segments (end users see "文档片段" which is confusing)
# - TextSummary: auto-generated chunk summaries
_HIDDEN_NODE_TYPES = {
    "NodeSet", "nodeset",
    "KnowledgeDistillation", "knowledgedistillation",
    "Timestamp", "timestamp",
    "DocumentChunk", "documentchunk",
    "TextSummary", "textsummary",
}


def transform_context_to_graph(context: List[Edge]):
    nodes = {}
    edges = {}

    # Internal attribute keys that should not be exposed to the frontend
    _internal_keys = {"_kd_marker", "_viz_only"}

    for triplet in context:
        # Skip KD self-loop edges (node1.id == node2.id) — they create isolated nodes
        if triplet.node1.id == triplet.node2.id:
            continue

        # Skip edges where either node is an internal/structural type
        n1_type = triplet.node1.attributes.get("type", "")
        n2_type = triplet.node2.attributes.get("type", "")
        if n1_type in _HIDDEN_NODE_TYPES or n2_type in _HIDDEN_NODE_TYPES:
            continue

        # 处理节点1
        node1_attrs = {k: v for k, v in triplet.node1.attributes.items() if k not in _internal_keys}
        node1_label = _get_node_label(node1_attrs, triplet.node1.id)
        nodes[triplet.node1.id] = {
            "id": triplet.node1.id,
            "label": node1_label,
            "type": node1_attrs.get("type", "unknown"),
            "attributes": node1_attrs,
        }

        # 处理节点2
        node2_attrs = {k: v for k, v in triplet.node2.attributes.items() if k not in _internal_keys}
        node2_label = _get_node_label(node2_attrs, triplet.node2.id)
        nodes[triplet.node2.id] = {
            "id": triplet.node2.id,
            "label": node2_label,
            "type": node2_attrs.get("type", "unknown"),
            "attributes": node2_attrs,
        }
        
        # 翻译关系名称
        # 尝试多个可能的关系名称键
        relationship_name = (
            triplet.attributes.get("relationship_name") or
            triplet.attributes.get("relationship_type") or
            "关联"
        )
        translated_label = translate_relationship_name(str(relationship_name))
        
        edges[
            f"{triplet.node1.id}_{relationship_name}_{triplet.node2.id}"
        ] = {
            "source": triplet.node1.id,
            "target": triplet.node2.id,
            "label": translated_label,
        }

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }
