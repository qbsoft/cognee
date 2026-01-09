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


def transform_context_to_graph(context: List[Edge]):
    nodes = {}
    edges = {}

    for triplet in context:
        # 处理节点1
        node1_label = _get_node_label(triplet.node1.attributes, triplet.node1.id)
        nodes[triplet.node1.id] = {
            "id": triplet.node1.id,
            "label": node1_label,
            "type": triplet.node1.attributes.get("type", "unknown"),
            "attributes": triplet.node1.attributes,
        }
        
        # 处理节点2
        node2_label = _get_node_label(triplet.node2.attributes, triplet.node2.id)
        nodes[triplet.node2.id] = {
            "id": triplet.node2.id,
            "label": node2_label,
            "type": triplet.node2.attributes.get("type", "unknown"),
            "attributes": triplet.node2.attributes,
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
