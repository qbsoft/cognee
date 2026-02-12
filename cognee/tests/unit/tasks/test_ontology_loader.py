import pytest
import os
import tempfile
import yaml


class TestOntologyLoader:
    """测试领域本体加载器"""

    def test_load_ontology_from_yaml(self):
        """从 YAML 文件加载本体定义"""
        from cognee.tasks.ontology.ontology_loader import load_ontology

        ontology = load_ontology()
        assert isinstance(ontology, dict)
        assert "entity_types" in ontology
        assert "relation_types" in ontology

    def test_load_ontology_entity_types(self):
        """验证实体类型正确加载"""
        from cognee.tasks.ontology.ontology_loader import load_ontology

        ontology = load_ontology()
        entity_types = ontology.get("entity_types", [])
        assert len(entity_types) > 0
        for et in entity_types:
            assert "name" in et
            assert "description" in et

    def test_load_ontology_relation_types(self):
        """验证关系类型正确加载"""
        from cognee.tasks.ontology.ontology_loader import load_ontology

        ontology = load_ontology()
        relation_types = ontology.get("relation_types", [])
        assert len(relation_types) > 0
        for rt in relation_types:
            assert "name" in rt
            assert "source_type" in rt
            assert "target_type" in rt

    def test_get_allowed_entity_types(self):
        """测试获取白名单实体类型"""
        from cognee.tasks.ontology.ontology_loader import get_allowed_entity_types

        allowed = get_allowed_entity_types()
        # 默认 enabled=false 时返回 None（不约束）
        assert allowed is None

    def test_get_allowed_entity_types_with_custom_config(self):
        """测试使用自定义配置获取白名单"""
        from cognee.tasks.ontology.ontology_loader import get_allowed_entity_types

        custom = {
            "enabled": True,
            "entity_types": [
                {"name": "Person", "description": "test"},
                {"name": "Company", "description": "test"},
            ],
        }
        allowed = get_allowed_entity_types(ontology_config=custom)
        assert allowed == {"Person", "Company"}

    def test_get_allowed_relation_types(self):
        """测试获取白名单关系类型"""
        from cognee.tasks.ontology.ontology_loader import get_allowed_relation_types

        allowed = get_allowed_relation_types()
        # 默认 enabled=false 时返回 None（不约束）
        assert allowed is None

    def test_get_allowed_relation_types_with_custom_config(self):
        """测试使用自定义配置获取关系白名单"""
        from cognee.tasks.ontology.ontology_loader import get_allowed_relation_types

        custom = {
            "enabled": True,
            "relation_types": [
                {
                    "name": "works_at",
                    "source_type": "Person",
                    "target_type": "Organization",
                },
            ],
        }
        allowed = get_allowed_relation_types(ontology_config=custom)
        assert allowed == {"works_at"}
