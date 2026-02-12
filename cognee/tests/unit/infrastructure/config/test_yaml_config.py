import pytest
import yaml
from pathlib import Path


class TestYamlConfigLoader:
    """测试 YAML 配置加载器"""

    def test_load_yaml_config_file_exists(self, tmp_path):
        """测试加载存在的 YAML 文件"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml.dump({"key": "value", "nested": {"a": 1}}))

        from cognee.infrastructure.config.yaml_config import load_yaml_config

        config = load_yaml_config(str(config_file))
        assert config["key"] == "value"
        assert config["nested"]["a"] == 1

    def test_load_yaml_config_file_not_exists(self):
        """测试加载不存在的 YAML 文件返回空字典"""
        from cognee.infrastructure.config.yaml_config import load_yaml_config

        config = load_yaml_config("/nonexistent/path/config.yaml")
        assert config == {}

    def test_load_yaml_config_empty_file(self, tmp_path):
        """测试加载空 YAML 文件返回空字典"""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        from cognee.infrastructure.config.yaml_config import load_yaml_config

        config = load_yaml_config(str(config_file))
        assert config == {}

    def test_get_config_with_defaults(self, tmp_path):
        """测试带默认值的配置获取"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml.dump({"chunk_size": 2000}))

        from cognee.infrastructure.config.yaml_config import get_config_value

        assert get_config_value(str(config_file), "chunk_size", default=1500) == 2000
        assert get_config_value(str(config_file), "missing_key", default="fallback") == "fallback"

    def test_get_nested_config_value(self, tmp_path):
        """测试获取嵌套配置值"""
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml.dump({
            "parsers": {
                "pdf": {
                    "default": "docling",
                    "fallback": "pypdf"
                }
            }
        }))

        from cognee.infrastructure.config.yaml_config import get_nested_config_value

        assert get_nested_config_value(str(config_file), "parsers.pdf.default", default="unknown") == "docling"
        assert get_nested_config_value(str(config_file), "parsers.pdf.missing", default="none") == "none"
        assert get_nested_config_value(str(config_file), "nonexistent.path", default="x") == "x"

    def test_get_config_dir(self):
        """测试获取配置目录路径"""
        from cognee.infrastructure.config.yaml_config import get_config_dir

        config_dir = get_config_dir()
        assert isinstance(config_dir, Path)

    def test_get_module_config(self, tmp_path, monkeypatch):
        """测试按模块名获取配置"""
        config_file = tmp_path / "parsers.yaml"
        config_file.write_text(yaml.dump({
            "parsers": {
                "pdf": {"default": "docling"}
            }
        }))

        from cognee.infrastructure.config.yaml_config import get_module_config, reload_config

        # 清除可能由其他测试留下的缓存
        reload_config()

        monkeypatch.setattr(
            "cognee.infrastructure.config.yaml_config.get_config_dir",
            lambda: tmp_path
        )

        config = get_module_config("parsers")
        assert config["parsers"]["pdf"]["default"] == "docling"

    def test_reload_config_clears_cache(self, tmp_path, monkeypatch):
        """测试重新加载配置会清除缓存"""
        config_file = tmp_path / "parsers.yaml"
        config_file.write_text(yaml.dump({"version": 1}))

        from cognee.infrastructure.config.yaml_config import (
            get_module_config,
            reload_config,
        )

        # 先清除可能由其他测试留下的缓存
        reload_config()

        monkeypatch.setattr(
            "cognee.infrastructure.config.yaml_config.get_config_dir",
            lambda: tmp_path
        )

        config1 = get_module_config("parsers")
        assert config1["version"] == 1

        config_file.write_text(yaml.dump({"version": 2}))
        reload_config()

        config2 = get_module_config("parsers")
        assert config2["version"] == 2
