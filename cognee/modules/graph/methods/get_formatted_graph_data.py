from uuid import UUID
from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.context_global_variables import set_database_global_context_variables
from cognee.modules.data.exceptions.exceptions import DatasetNotFoundError
from cognee.modules.data.methods import get_authorized_dataset
from cognee.modules.users.models import User
from cognee.modules.engine.utils import translate_relationship_name


def _get_node_label(node_data: dict, node_id: str) -> str:
    """
    获取节点标签，处理空名称的情况
    
    优先级：
    1. name 属性
    2. text 属性的前30个字符（去除换行）
    3. description 属性的前30个字符
    4. type + ID 前8位
    5. 节点_ + ID 前8位
    """
    if not node_data:
        return f"节点_{str(node_id)[:8]}"
    
    # 优先使用 name 字段
    name = node_data.get("name")
    if name and name != "" and str(name).strip():
        return str(name).strip()
    
    # 其次使用 text 字段的前几个词（对于 DocumentChunk）
    text = node_data.get("text")
    if text and text != "" and str(text).strip():
        text_str = str(text).strip()
        # 如果包含换行，取第一行
        first_line = text_str.split('\n')[0] if '\n' in text_str else text_str
        # 限制长度为30个字符
        if len(first_line) > 30:
            return first_line[:30] + "..."
        return first_line
    
    # 使用 description 字段
    description = node_data.get("description")
    if description and description != "" and str(description).strip():
        desc_str = str(description).strip()
        if len(desc_str) > 30:
            return desc_str[:30] + "..."
        return desc_str
    
    # 使用 type 字段
    node_type = node_data.get("type", "unknown")
    if node_type and node_type != "unknown":
        type_name = str(node_type).strip()
        # 如果 type 是英文，尝试翻译
        type_translations = {
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
            "DocumentChunk": "文档片段",
            "TextDocument": "文档",
            "Entity": "实体",
            "EntityType": "实体类型",
            "TextSummary": "摘要",
        }
        translated_type = type_translations.get(type_name, type_name)
        return f"{translated_type}_{str(node_id)[:8]}"
    
    # 最后使用 ID 的前8位
    return f"节点_{str(node_id)[:8]}"


async def get_formatted_graph_data(dataset_id: UUID, user: User):
    dataset = await get_authorized_dataset(user, dataset_id)
    if not dataset:
        raise DatasetNotFoundError(message="Dataset not found.")

    await set_database_global_context_variables(dataset_id, dataset.owner_id)

    graph_client = await get_graph_engine()
    (nodes, edges) = await graph_client.get_graph_data()

    return {
        "nodes": list(
            map(
                lambda node: {
                    "id": str(node[0]),
                    "label": _get_node_label(node[1], node[0]),
                    "type": node[1].get("type", "unknown"),
                    "properties": {
                        key: value
                        for key, value in node[1].items()
                        if key not in ["id", "type", "name", "created_at", "updated_at"]
                        and value is not None
                    },
                },
                nodes,
            )
        ),
        "edges": list(
            map(
                lambda edge: {
                    "source": str(edge[0]),
                    "target": str(edge[1]),
                    "label": translate_relationship_name(str(edge[2])),
                },
                edges,
            )
        ),
    }
