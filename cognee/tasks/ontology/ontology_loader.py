"""
领域本体加载器。

从 config/ontology.yaml 加载领域本体定义，提供白名单约束：
- enabled=true 时，返回实体类型和关系类型的白名单集合
- enabled=false 或未配置时，返回 None（不施加约束，向后兼容）
"""
import logging
from typing import Optional, Set, Dict, Any

logger = logging.getLogger(__name__)


def load_ontology(config_path: Optional[str] = None) -> dict:
    """
    加载本体配置。

    Args:
        config_path: 可选的配置文件路径，默认从 config/ontology.yaml 加载

    Returns:
        本体配置字典
    """
    from cognee.infrastructure.config import load_yaml_config, get_module_config

    if config_path:
        return load_yaml_config(config_path)

    return get_module_config("ontology")


def get_allowed_entity_types(
    ontology_config: Optional[Dict[str, Any]] = None,
) -> Optional[Set[str]]:
    """
    获取白名单实体类型集合。

    Args:
        ontology_config: 可选的本体配置字典，None 时自动加载

    Returns:
        白名单实体类型名称集合，或 None（不约束）
    """
    if ontology_config is None:
        ontology_config = load_ontology()

    if not ontology_config.get("enabled", False):
        return None

    entity_types = ontology_config.get("entity_types", [])
    if not entity_types:
        return None

    return {et["name"] for et in entity_types if "name" in et}


def get_allowed_relation_types(
    ontology_config: Optional[Dict[str, Any]] = None,
) -> Optional[Set[str]]:
    """
    获取白名单关系类型集合。

    Args:
        ontology_config: 可选的本体配置字典，None 时自动加载

    Returns:
        白名单关系类型名称集合，或 None（不约束）
    """
    if ontology_config is None:
        ontology_config = load_ontology()

    if not ontology_config.get("enabled", False):
        return None

    relation_types = ontology_config.get("relation_types", [])
    if not relation_types:
        return None

    return {rt["name"] for rt in relation_types if "name" in rt}
