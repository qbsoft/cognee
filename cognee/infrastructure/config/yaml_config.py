"""
YAML 配置加载器。

提供分模块的 YAML 配置加载，支持嵌套键访问、默认值、缓存和热重载。
配置优先级: 环境变量 > .env > YAML > 代码默认值
"""
import os
import yaml
from pathlib import Path
from typing import Any


def get_config_dir() -> Path:
    """获取配置目录路径。优先使用环境变量 COGNEE_CONFIG_DIR，否则使用项目根目录下的 config/"""
    env_dir = os.environ.get("COGNEE_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent / "config"
    return Path.cwd() / "config"


def load_yaml_config(file_path: str) -> dict:
    """加载单个 YAML 配置文件。文件不存在或为空时返回空字典。"""
    path = Path(file_path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, IOError):
        return {}


def get_config_value(file_path: str, key: str, default: Any = None) -> Any:
    """从 YAML 配置文件获取顶层键的值。"""
    config = load_yaml_config(file_path)
    return config.get(key, default)


def get_nested_config_value(file_path: str, dotted_key: str, default: Any = None) -> Any:
    """从 YAML 配置文件获取嵌套键的值。键使用点号分隔，如 'parsers.pdf.default'。"""
    config = load_yaml_config(file_path)
    keys = dotted_key.split(".")
    current = config
    for k in keys:
        if not isinstance(current, dict) or k not in current:
            return default
        current = current[k]
    return current


_config_cache: dict[str, dict] = {}


def get_module_config(module_name: str) -> dict:
    """按模块名获取配置。模块名对应 config/ 目录下的 YAML 文件名（不含扩展名）。"""
    if module_name in _config_cache:
        return _config_cache[module_name]

    config_dir = get_config_dir()
    config_file = config_dir / f"{module_name}.yaml"
    config = load_yaml_config(str(config_file))
    _config_cache[module_name] = config
    return config


def reload_config() -> None:
    """清除配置缓存，强制下次调用时重新加载。"""
    _config_cache.clear()
