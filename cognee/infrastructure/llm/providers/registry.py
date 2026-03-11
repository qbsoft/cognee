"""Built-in model provider registry.

All provider definitions are code-level constants — no external downloads needed.
This supports air-gapped / LAN deployments out of the box.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace as _dc_replace
from typing import Optional


@dataclass(frozen=True)
class ConfigField:
    """Describes one field in a provider's configuration form."""
    key: str
    label: str
    label_en: str
    type: str           # "secret" | "text" | "url"
    required: bool
    placeholder: str = ""
    help_text: str = ""
    help_text_en: str = ""


@dataclass(frozen=True)
class ModelInfo:
    """A single model offered by a provider."""
    id: str
    name: str
    capabilities: tuple[str, ...] = ("chat",)
    max_tokens: int = 8192
    is_default: bool = False


@dataclass(frozen=True)
class ProviderDefinition:
    """Immutable definition of a model provider."""
    id: str
    name: str
    name_en: str
    category: str               # "cloud_cn" | "cloud_intl" | "local"
    icon: str                   # filename under /icons/providers/
    default_base_url: str
    is_openai_compatible: bool
    auth_type: str              # "api_key" | "none"
    capabilities: tuple[str, ...] = ("chat",)
    default_models: tuple[ModelInfo, ...] = ()
    config_fields: tuple[ConfigField, ...] = ()
    notes: str = ""
    notes_en: str = ""


# ---------------------------------------------------------------------------
# Field templates (reused across many providers)
# ---------------------------------------------------------------------------
_API_KEY_FIELD = ConfigField(
    key="api_key", label="API Key", label_en="API Key",
    type="secret", required=True, placeholder="sk-...",
    help_text="在提供商控制台获取", help_text_en="Get from provider console",
)

_BASE_URL_FIELD = ConfigField(
    key="base_url", label="API 端点", label_en="API Endpoint",
    type="url", required=False, placeholder="https://...",
    help_text="留空使用默认端点", help_text_en="Leave empty for default",
)

_LOCAL_URL_FIELD = ConfigField(
    key="base_url", label="服务地址", label_en="Server URL",
    type="url", required=True, placeholder="http://localhost:11434",
    help_text="本地模型服务的 HTTP 地址", help_text_en="HTTP address of local model server",
)


# ===================================================================
# Provider definitions
# ===================================================================

# --- Chinese Cloud Providers -------------------------------------------

DASHSCOPE = ProviderDefinition(
    id="dashscope",
    name="阿里云 DashScope",
    name_en="Alibaba DashScope",
    category="cloud_cn",
    icon="dashscope.svg",
    default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    is_openai_compatible=True,
    auth_type="api_key",
    capabilities=("chat", "embedding", "vision"),
    default_models=(
        ModelInfo("qwen-plus", "通义千问-Plus", ("chat", "vision"), 131072, True),
        ModelInfo("qwen-turbo", "通义千问-Turbo", ("chat",), 131072),
        ModelInfo("qwen-max", "通义千问-Max", ("chat", "vision"), 32768),
        ModelInfo("qwen-long", "通义千问-Long", ("chat",), 1000000),
        ModelInfo("text-embedding-v3", "文本嵌入-V3", ("embedding",), 8192),
        ModelInfo("text-embedding-v2", "文本嵌入-V2", ("embedding",), 2048),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
    notes="支持 OpenAI 兼容协议，模型名前缀可省略 openai/",
)

DEEPSEEK = ProviderDefinition(
    id="deepseek",
    name="DeepSeek",
    name_en="DeepSeek",
    category="cloud_cn",
    icon="deepseek.svg",
    default_base_url="https://api.deepseek.com/v1",
    is_openai_compatible=True,
    auth_type="api_key",
    capabilities=("chat",),
    default_models=(
        ModelInfo("deepseek-chat", "DeepSeek-V3", ("chat",), 65536, True),
        ModelInfo("deepseek-reasoner", "DeepSeek-R1", ("chat",), 65536),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
)

ZHIPU = ProviderDefinition(
    id="zhipu",
    name="智谱 AI",
    name_en="Zhipu AI (ChatGLM)",
    category="cloud_cn",
    icon="zhipu.svg",
    default_base_url="https://open.bigmodel.cn/api/paas/v4",
    is_openai_compatible=True,
    auth_type="api_key",
    capabilities=("chat", "embedding"),
    default_models=(
        ModelInfo("glm-4-plus", "GLM-4-Plus", ("chat",), 128000, True),
        ModelInfo("glm-4-flash", "GLM-4-Flash", ("chat",), 128000),
        ModelInfo("embedding-3", "Embedding-3", ("embedding",), 8192),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
)

MOONSHOT = ProviderDefinition(
    id="moonshot",
    name="月之暗面 Kimi",
    name_en="Moonshot (Kimi)",
    category="cloud_cn",
    icon="moonshot.svg",
    default_base_url="https://api.moonshot.cn/v1",
    is_openai_compatible=True,
    auth_type="api_key",
    capabilities=("chat",),
    default_models=(
        ModelInfo("moonshot-v1-128k", "Moonshot-V1-128K", ("chat",), 128000, True),
        ModelInfo("moonshot-v1-32k", "Moonshot-V1-32K", ("chat",), 32000),
        ModelInfo("moonshot-v1-8k", "Moonshot-V1-8K", ("chat",), 8000),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
)

DOUBAO = ProviderDefinition(
    id="doubao",
    name="字节豆包",
    name_en="ByteDance Doubao",
    category="cloud_cn",
    icon="doubao.svg",
    default_base_url="https://ark.cn-beijing.volces.com/api/v3",
    is_openai_compatible=True,
    auth_type="api_key",
    capabilities=("chat", "embedding"),
    default_models=(
        ModelInfo("doubao-pro-32k", "豆包-Pro-32K", ("chat",), 32768, True),
        ModelInfo("doubao-lite-32k", "豆包-Lite-32K", ("chat",), 32768),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
    notes="需要在火山引擎控制台创建推理接入点",
)

SILICONFLOW = ProviderDefinition(
    id="siliconflow",
    name="硅基流动",
    name_en="SiliconFlow",
    category="cloud_cn",
    icon="siliconflow.svg",
    default_base_url="https://api.siliconflow.cn/v1",
    is_openai_compatible=True,
    auth_type="api_key",
    capabilities=("chat", "embedding"),
    default_models=(
        ModelInfo("Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B", ("chat",), 32768, True),
        ModelInfo("deepseek-ai/DeepSeek-V3", "DeepSeek-V3", ("chat",), 65536),
        ModelInfo("BAAI/bge-m3", "BGE-M3", ("embedding",), 8192),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
    notes="聚合多家模型，统一 API 调用",
)

BAIDU = ProviderDefinition(
    id="baidu",
    name="百度文心",
    name_en="Baidu ERNIE",
    category="cloud_cn",
    icon="baidu.svg",
    default_base_url="https://aip.baidubce.com",
    is_openai_compatible=False,
    auth_type="api_key",
    capabilities=("chat", "embedding"),
    default_models=(
        ModelInfo("ernie-4.0-8k", "ERNIE 4.0", ("chat",), 8192, True),
        ModelInfo("ernie-3.5-128k", "ERNIE 3.5-128K", ("chat",), 128000),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
    notes="百度文心使用自有协议，需专用适配器",
    notes_en="Uses proprietary API, requires dedicated adapter",
)


# --- International Cloud Providers ------------------------------------

OPENAI = ProviderDefinition(
    id="openai",
    name="OpenAI",
    name_en="OpenAI",
    category="cloud_intl",
    icon="openai.svg",
    default_base_url="https://api.openai.com/v1",
    is_openai_compatible=True,
    auth_type="api_key",
    capabilities=("chat", "embedding", "vision", "audio"),
    default_models=(
        ModelInfo("gpt-4o", "GPT-4o", ("chat", "vision"), 128000, True),
        ModelInfo("gpt-4o-mini", "GPT-4o Mini", ("chat", "vision"), 128000),
        ModelInfo("o3-mini", "o3-mini", ("chat",), 200000),
        ModelInfo("text-embedding-3-large", "text-embedding-3-large", ("embedding",), 8191),
        ModelInfo("text-embedding-3-small", "text-embedding-3-small", ("embedding",), 8191),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
)

ANTHROPIC = ProviderDefinition(
    id="anthropic",
    name="Anthropic",
    name_en="Anthropic",
    category="cloud_intl",
    icon="anthropic.svg",
    default_base_url="https://api.anthropic.com",
    is_openai_compatible=False,
    auth_type="api_key",
    capabilities=("chat", "vision"),
    default_models=(
        ModelInfo("claude-sonnet-4-5-20250514", "Claude Sonnet 4.5", ("chat", "vision"), 200000, True),
        ModelInfo("claude-haiku-4-5-20251001", "Claude Haiku 4.5", ("chat", "vision"), 200000),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
    notes="使用 Anthropic 原生协议",
)

GEMINI = ProviderDefinition(
    id="gemini",
    name="Google Gemini",
    name_en="Google Gemini",
    category="cloud_intl",
    icon="gemini.svg",
    default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    is_openai_compatible=True,
    auth_type="api_key",
    capabilities=("chat", "vision"),
    default_models=(
        ModelInfo("gemini-2.0-flash", "Gemini 2.0 Flash", ("chat", "vision"), 1048576, True),
        ModelInfo("gemini-2.5-pro-preview", "Gemini 2.5 Pro", ("chat", "vision"), 1048576),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
)

MISTRAL = ProviderDefinition(
    id="mistral",
    name="Mistral AI",
    name_en="Mistral AI",
    category="cloud_intl",
    icon="mistral.svg",
    default_base_url="https://api.mistral.ai/v1",
    is_openai_compatible=True,
    auth_type="api_key",
    capabilities=("chat", "embedding"),
    default_models=(
        ModelInfo("mistral-large-latest", "Mistral Large", ("chat",), 131072, True),
        ModelInfo("mistral-small-latest", "Mistral Small", ("chat",), 131072),
        ModelInfo("mistral-embed", "Mistral Embed", ("embedding",), 8192),
    ),
    config_fields=(_API_KEY_FIELD, _BASE_URL_FIELD),
)


# --- Local Model Providers --------------------------------------------

OLLAMA = ProviderDefinition(
    id="ollama",
    name="Ollama",
    name_en="Ollama",
    category="local",
    icon="ollama.svg",
    default_base_url="http://localhost:11434/v1",
    is_openai_compatible=True,
    auth_type="none",
    capabilities=("chat", "embedding"),
    default_models=(
        ModelInfo("qwen2.5:7b", "Qwen 2.5 7B", ("chat",), 32768, True),
        ModelInfo("llama3.1:8b", "Llama 3.1 8B", ("chat",), 131072),
        ModelInfo("deepseek-r1:7b", "DeepSeek-R1 7B", ("chat",), 65536),
        ModelInfo("nomic-embed-text", "Nomic Embed Text", ("embedding",), 8192),
    ),
    config_fields=(_LOCAL_URL_FIELD,),
    notes="本地运行大模型，无需 API Key",
    notes_en="Run models locally, no API key needed",
)

VLLM = ProviderDefinition(
    id="vllm",
    name="vLLM",
    name_en="vLLM",
    category="local",
    icon="vllm.svg",
    default_base_url="http://localhost:8000/v1",
    is_openai_compatible=True,
    auth_type="none",
    capabilities=("chat", "embedding"),
    default_models=(),
    config_fields=(_LOCAL_URL_FIELD,),
    notes="高性能推理服务，需手动输入模型名称",
    notes_en="High-performance inference, enter model name manually",
)

CUSTOM = ProviderDefinition(
    id="custom",
    name="自定义 API",
    name_en="Custom API",
    category="local",
    icon="custom.svg",
    default_base_url="",
    is_openai_compatible=True,
    auth_type="api_key",
    capabilities=("chat", "embedding"),
    default_models=(),
    config_fields=(
        _dc_replace(_LOCAL_URL_FIELD, required=True, placeholder="http://your-server/v1"),
        _dc_replace(_API_KEY_FIELD, required=False),
    ),
    notes="任何兼容 OpenAI 协议的 API 端点",
    notes_en="Any OpenAI-compatible API endpoint",
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_ALL_PROVIDERS: dict[str, ProviderDefinition] = {}


def _register(*providers: ProviderDefinition) -> None:
    for p in providers:
        _ALL_PROVIDERS[p.id] = p


_register(
    # Cloud CN
    DASHSCOPE, DEEPSEEK, ZHIPU, MOONSHOT, DOUBAO, SILICONFLOW, BAIDU,
    # Cloud Intl
    OPENAI, ANTHROPIC, GEMINI, MISTRAL,
    # Local
    OLLAMA, VLLM, CUSTOM,
)


def get_all_providers() -> list[ProviderDefinition]:
    """Return all registered providers in display order."""
    return list(_ALL_PROVIDERS.values())


def get_provider(provider_id: str) -> Optional[ProviderDefinition]:
    """Return a single provider by ID, or None."""
    return _ALL_PROVIDERS.get(provider_id)


def get_providers_by_category(category: str) -> list[ProviderDefinition]:
    """Return providers in a given category."""
    return [p for p in _ALL_PROVIDERS.values() if p.category == category]
