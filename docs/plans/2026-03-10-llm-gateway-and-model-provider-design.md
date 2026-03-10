# LLM Gateway 重构 + 模型提供商配置界面 设计文档

**日期**: 2026-03-10
**状态**: 设计评审中
**优先级**: 中等（非核心功能，但影响架构扩展性）

---

## 1. 问题分析

### 1.1 当前 LiteLLM 的问题

| 问题 | 影响 | 严重程度 |
|------|------|---------|
| **依赖过重** | litellm 包 ~50MB+，导入慢，带入大量不需要的子依赖 | 中 |
| **网络初始化** | TikToken/HuggingFace tokenizer 首次使用时下载，局域网环境报错 | 高 |
| **功能浪费** | 支持 100+ 提供商，我们只用 6 个；路由/批处理/缓存功能全未使用 | 低 |
| **调试困难** | 错误堆栈深，日志噪音大（需专门代码抑制 20+ logger） | 中 |
| **API 不稳定** | 版本升级常破坏接口（如 qdrant-client v1.17 的 search→query_points） | 中 |
| **局域网不友好** | 内部可能尝试访问外部服务（模型列表、token计费等） | 高 |

### 1.2 当前架构中 LiteLLM 的实际使用面

经过代码审计，LiteLLM 在 cognee 中的实际使用仅限于：

```
使用的功能（6个）：
├─ litellm.acompletion()        → 异步聊天完成（4处调用）
├─ litellm.completion()         → 同步聊天完成（1处调用）
├─ litellm.aembedding()         → 异步向量化（1处调用）
├─ litellm.transcription()      → 音频转录（1处调用）
├─ litellm.model_cost           → 模型 token 上限查询（1处调用）
└─ litellm.exceptions.*         → 异常类型（5种）

未使用的功能：
├─ litellm.router               → 负载均衡路由
├─ litellm.fallback             → 内置回退
├─ litellm.batch_completion     → 批量请求
├─ litellm.cache                → 内置缓存
└─ 90+ 其他提供商适配器
```

**关键发现**：Anthropic 和 Ollama 适配器已经**绑过 LiteLLM**，直接使用原生 SDK。
这说明移除 LiteLLM 是可行的——逐个替换即可。

### 1.3 用户需求

1. **模型提供商配置界面**：类似 Dify/LobeChat 的卡片式提供商管理
2. **国内模型支持**：DashScope(通义千问)、DeepSeek、智谱、月之暗面等
3. **本地模型支持**：Ollama、vLLM、本地部署的 API 服务
4. **每用户独立配置**：每个用户可以配置自己的 API Key 和默认模型
5. **局域网部署**：企业内网环境，无外网访问能力
6. **双网络模式**：同时支持外网 API 和内网本地模型

---

## 2. 设计原则

- **统一规划，分步实施**：架构一次设计到位，实现分 3 个 Phase
- **最小替换**：不大改现有代码，在现有适配器层之上加一层路由
- **接口优先**：先定义好 Protocol/Interface，再逐步替换实现
- **向后兼容**：.env 配置方式继续有效，UI 配置是增强而非替代
- **离线优先**：所有功能在无外网时也能正常工作

---

## 3. 架构总览

```
┌──────────────────────────────────────────────────────────┐
│                    前端 (Next.js)                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ 提供商管理卡片 │  │ 模型选择下拉  │  │ 连接测试按钮   │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
│         │                │                   │           │
└─────────┼────────────────┼───────────────────┼───────────┘
          │                │                   │
┌─────────┼────────────────┼───────────────────┼───────────┐
│         ▼                ▼                   ▼           │
│  ┌─────────────────────────────────────────────────┐     │
│  │          /api/v1/model-providers (新增)           │     │
│  │  GET  /              → 列出所有可用提供商         │     │
│  │  POST /{id}/config   → 保存用户的提供商配置       │     │
│  │  POST /{id}/test     → 测试连接                  │     │
│  │  GET  /user/defaults → 获取用户默认模型           │     │
│  │  PUT  /user/defaults → 设置用户默认模型           │     │
│  └──────────────────────┬──────────────────────────┘     │
│                         │                                │
│  ┌──────────────────────▼──────────────────────────┐     │
│  │            ModelProviderService (新增)            │     │
│  │  - 提供商注册表（内置 + 自定义）                    │     │
│  │  - 用户配置 CRUD                                  │     │
│  │  - 连接测试                                       │     │
│  │  - 默认模型解析                                    │     │
│  └──────────────────────┬──────────────────────────┘     │
│                         │                                │
│  ┌──────────────────────▼──────────────────────────┐     │
│  │            UnifiedLLMGateway (重构)               │     │
│  │  现有 LLMGateway + 用户模型配置解析                 │     │
│  │  - resolve_model_config(user_id, task_type)      │     │
│  │  - 优先级: 用户配置 > YAML > .env > 默认值         │     │
│  └──────────────────────┬──────────────────────────┘     │
│                         │                                │
│  ┌──────────────────────▼──────────────────────────┐     │
│  │          现有适配器层 (保持不变)                     │     │
│  │  OpenAI / Anthropic / Gemini / Mistral /         │     │
│  │  Ollama / GenericAPI (OpenAI 兼容)               │     │
│  │                                                  │     │
│  │  Phase 2: 逐步移除 LiteLLM，改用 httpx 直连       │     │
│  └──────────────────────────────────────────────────┘     │
│                     后端 (FastAPI)                        │
└──────────────────────────────────────────────────────────┘
```

---

## 4. 数据模型

### 4.1 内置提供商注册表（代码中定义，不存数据库）

```python
# cognee/infrastructure/llm/providers/registry.py

@dataclass
class ProviderDefinition:
    """提供商定义（内置，不可修改）"""
    id: str                          # "dashscope", "openai", "ollama"
    name: str                        # 显示名称 "阿里云 DashScope"
    name_en: str                     # "Alibaba DashScope"
    category: str                    # "cloud" | "local" | "custom"
    icon: str                        # 图标文件名 "dashscope.svg"
    default_base_url: str            # 默认 API 端点
    is_openai_compatible: bool       # 是否兼容 OpenAI 协议
    auth_type: str                   # "api_key" | "none" | "bearer"
    capabilities: list[str]          # ["chat", "embedding", "vision"]
    default_models: list[ModelInfo]  # 预置模型列表
    config_fields: list[ConfigField] # 配置表单字段定义
    notes: str                       # 备注（显示在 UI 上）

@dataclass
class ModelInfo:
    """模型信息"""
    id: str                    # "qwen-plus"
    name: str                  # "通义千问-Plus"
    capabilities: list[str]    # ["chat", "vision"]
    max_tokens: int            # 最大上下文
    is_default: bool           # 是否为该提供商的默认模型

@dataclass
class ConfigField:
    """配置表单字段"""
    key: str           # "api_key"
    label: str         # "API Key"
    type: str          # "secret" | "text" | "url" | "select"
    required: bool     # True
    placeholder: str   # "sk-..."
    help_text: str     # "在 DashScope 控制台获取"
```

### 4.2 用户模型配置（存数据库）

```python
# cognee/modules/settings/models/UserModelConfig.py

class UserModelConfig(Base):
    """用户的提供商配置（每个用户每个提供商一条记录）"""
    __tablename__ = "user_model_configs"

    id: UUID = Column(UUID, primary_key=True, default=uuid4)
    user_id: UUID = Column(UUID, ForeignKey("users.id"), nullable=False)
    tenant_id: UUID = Column(UUID, ForeignKey("tenants.id"), nullable=True)
    provider_id: str = Column(String(50), nullable=False)   # "dashscope"
    api_key_encrypted: str = Column(Text, nullable=True)     # AES 加密
    base_url: str = Column(String(500), nullable=True)       # 自定义端点
    custom_params: dict = Column(JSON, default={})           # 额外参数
    enabled: bool = Column(Boolean, default=True)
    created_at: datetime = Column(DateTime, default=func.now())
    updated_at: datetime = Column(DateTime, onupdate=func.now())

    # 唯一约束：每用户每提供商只有一条配置
    __table_args__ = (
        UniqueConstraint("user_id", "provider_id"),
    )


class UserDefaultModel(Base):
    """用户的默认模型选择（按任务类型）"""
    __tablename__ = "user_default_models"

    id: UUID = Column(UUID, primary_key=True, default=uuid4)
    user_id: UUID = Column(UUID, ForeignKey("users.id"), nullable=False)
    task_type: str = Column(String(30), nullable=False)   # "chat" / "extraction" / "embedding"
    provider_id: str = Column(String(50), nullable=False)  # "dashscope"
    model_id: str = Column(String(100), nullable=False)    # "qwen-plus"

    __table_args__ = (
        UniqueConstraint("user_id", "task_type"),
    )
```

### 4.3 租户级默认配置（可选，Phase 3）

```python
class TenantModelConfig(Base):
    """租户级的模型配置（管理员设置的全局默认）"""
    __tablename__ = "tenant_model_configs"
    # 结构同 UserModelConfig，但 user_id 替换为 tenant_id
    # 优先级: 用户配置 > 租户配置 > .env 配置
```

---

## 5. 内置提供商列表

### 5.1 国内云端提供商

| ID | 名称 | 协议 | 默认端点 | 主要模型 |
|----|------|------|---------|---------|
| `dashscope` | 阿里云 DashScope | OpenAI 兼容 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-plus, qwen-turbo, qwen-max, text-embedding-v3 |
| `deepseek` | DeepSeek | OpenAI 兼容 | `https://api.deepseek.com/v1` | deepseek-chat, deepseek-coder, deepseek-reasoner |
| `zhipu` | 智谱 AI | OpenAI 兼容 | `https://open.bigmodel.cn/api/paas/v4` | glm-4-plus, glm-4-flash, embedding-3 |
| `moonshot` | 月之暗面 | OpenAI 兼容 | `https://api.moonshot.cn/v1` | moonshot-v1-128k, moonshot-v1-32k |
| `doubao` | 字节豆包 | OpenAI 兼容 | `https://ark.cn-beijing.volces.com/api/v3` | doubao-pro-32k, doubao-lite-32k |
| `baidu` | 百度文心 | 自有协议 | `https://aip.baidubce.com` | ernie-4.0, ernie-3.5-turbo |
| `siliconflow` | 硅基流动 | OpenAI 兼容 | `https://api.siliconflow.cn/v1` | 聚合多家模型 |

### 5.2 国际云端提供商

| ID | 名称 | 协议 | 默认端点 |
|----|------|------|---------|
| `openai` | OpenAI | 原生 | `https://api.openai.com/v1` |
| `anthropic` | Anthropic | 原生 | `https://api.anthropic.com` |
| `gemini` | Google Gemini | OpenAI 兼容 | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `mistral` | Mistral | OpenAI 兼容 | `https://api.mistral.ai/v1` |

### 5.3 本地模型提供商

| ID | 名称 | 协议 | 默认端点 | 说明 |
|----|------|------|---------|------|
| `ollama` | Ollama | OpenAI 兼容 | `http://localhost:11434/v1` | 最流行的本地模型运行时 |
| `vllm` | vLLM | OpenAI 兼容 | `http://localhost:8000/v1` | 高性能推理服务 |
| `localai` | LocalAI | OpenAI 兼容 | `http://localhost:8080/v1` | 本地 AI 服务 |
| `custom` | 自定义 API | OpenAI 兼容 | 用户填写 | 任何 OpenAI 兼容端点 |

### 5.4 关键洞察

> 绝大多数国内外提供商现在都支持 **OpenAI 兼容协议**。
> 这意味着我们不需要为每个提供商写专用适配器——
> **一个 OpenAI 兼容适配器 + 不同的 base_url 就能覆盖 90% 的场景。**
>
> 只有 Anthropic（原生协议）和百度文心（自有协议）需要专用适配器。

---

## 6. 配置优先级

```
用户个人配置（数据库 UserDefaultModel + UserModelConfig）
    ↓ 未设置时回退
租户级配置（数据库 TenantModelConfig，Phase 3）
    ↓ 未设置时回退
YAML 任务配置（config/model_selection.yaml）
    ↓ 未设置时回退
环境变量（.env LLM_MODEL / LLM_PROVIDER）
    ↓ 未设置时回退
系统默认值（代码中硬编码 openai/gpt-5-mini）
```

**向后兼容性**：没有配置 UI 时，系统行为与当前完全一致（.env 和 YAML 驱动）。

---

## 7. API 设计

### 7.1 提供商管理 API

```
GET  /api/v1/model-providers
  → 返回所有可用提供商列表（含用户的启用状态）
  Response: [{
    id: "dashscope",
    name: "阿里云 DashScope",
    category: "cloud",
    icon_url: "/static/icons/dashscope.svg",
    is_configured: true,     // 该用户是否已配置
    is_enabled: true,        // 该用户是否启用
    capabilities: ["chat", "embedding"],
    models: [
      { id: "qwen-plus", name: "通义千问-Plus", capabilities: ["chat"], is_default: true },
      { id: "qwen-turbo", name: "通义千问-Turbo", capabilities: ["chat"] },
      { id: "text-embedding-v3", name: "文本嵌入V3", capabilities: ["embedding"] },
    ],
    config_fields: [
      { key: "api_key", label: "API Key", type: "secret", required: true, placeholder: "sk-..." },
    ]
  }]

GET  /api/v1/model-providers/{provider_id}
  → 返回单个提供商的详细信息 + 用户配置

POST /api/v1/model-providers/{provider_id}/config
  → 保存用户的提供商配置
  Body: { api_key: "sk-...", base_url: "https://...", custom_params: {} }

DELETE /api/v1/model-providers/{provider_id}/config
  → 删除用户的提供商配置

POST /api/v1/model-providers/{provider_id}/test
  → 测试连接（发送一个简单的 chat completion 请求）
  Response: { success: true, latency_ms: 320, model_list: ["qwen-plus", ...] }
```

### 7.2 默认模型 API

```
GET  /api/v1/user/default-models
  → 返回用户的默认模型配置
  Response: {
    chat: { provider_id: "dashscope", model_id: "qwen-plus" },
    extraction: { provider_id: "dashscope", model_id: "qwen-turbo" },
    embedding: { provider_id: "dashscope", model_id: "text-embedding-v3" },
  }

PUT  /api/v1/user/default-models
  → 设置用户的默认模型
  Body: {
    chat: { provider_id: "dashscope", model_id: "qwen-plus" },
    extraction: { provider_id: "dashscope", model_id: "qwen-turbo" },
  }
```

---

## 8. 前端 UI 设计

### 8.1 页面结构

```
/settings/models  (新页面)
├── 顶部标签: "模型提供商" | "默认模型" | "高级设置"
│
├── Tab 1: 模型提供商
│   ├── 分类标题: "本地模型" / "国内云端" / "国际云端"
│   ├── 提供商卡片网格（每行 3-4 个）
│   │   ┌──────────────┐
│   │   │  [logo]      │
│   │   │  DashScope   │
│   │   │  ● 已连接    │  ← 绿色/灰色状态指示
│   │   │  [配置]      │
│   │   └──────────────┘
│   └── 点击"配置" → 展开/弹窗显示配置表单
│       ├── API Key 输入框
│       ├── Base URL（可选，高级）
│       ├── [测试连接] 按钮
│       └── [保存] / [删除配置]
│
├── Tab 2: 默认模型
│   ├── "对话/回答" → 提供商下拉 + 模型下拉
│   ├── "知识提取"   → 提供商下拉 + 模型下拉
│   ├── "向量嵌入"   → 提供商下拉 + 模型下拉
│   └── 提示: "未设置时使用系统默认配置"
│
└── Tab 3: 高级设置
    ├── Temperature 滑块
    ├── 最大 Token 数
    ├── 速率限制配置
    └── 缓存开关
```

### 8.2 关键交互

1. **首次使用引导**：未配置任何提供商时，显示引导卡片
2. **连接测试**：点击"测试"按钮，发送轻量请求验证凭证有效
3. **模型自动发现**：对支持 `/models` 端点的提供商（如 Ollama），自动拉取可用模型列表
4. **密钥保护**：API Key 显示为 `sk-****f1` 格式，不暴露完整密钥

---

## 9. 局域网/离线环境支持

### 9.1 设计要点

| 场景 | 处理方式 |
|------|---------|
| **无外网** | 提供商注册表内置在代码中，不需要从外部加载 |
| **Tokenizer** | Phase 2 时替换为内置 tiktoken 编码，预打包 cl100k_base |
| **模型列表** | 内置默认列表 + 支持手动输入模型 ID（不依赖 /models API） |
| **Ollama** | 默认连接 localhost:11434，支持自定义局域网 IP |
| **vLLM** | 同上，OpenAI 兼容协议 |
| **Docker 部署** | 提供 docker-compose.yml 包含 Ollama + cognee |
| **图标/Logo** | 内置到前端 static 资源，不从 CDN 加载 |

### 9.2 网络检测

```python
async def check_network_mode() -> str:
    """检测当前网络环境"""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.head("https://api.openai.com")
        return "internet"   # 有外网
    except:
        return "lan"        # 局域网/离线
```

前端根据网络模式调整 UI：
- **internet 模式**：显示所有提供商
- **lan 模式**：高亮本地提供商（Ollama/vLLM），云端提供商标记为"需要外网"

---

## 10. LiteLLM 替换路径

### Phase 1（当前）：加层不替换

```
新增 ModelProviderService + API + 前端
    ↓
UnifiedLLMGateway（在现有 LLMGateway 之上）
    ↓
现有适配器（保留 LiteLLM 依赖）
```

**工作量**：~3-5 天
**风险**：极低（不改现有调用链）

### Phase 2（后续）：逐步替换 LiteLLM

替换顺序（按影响范围从小到大）：

```
1. litellm.aembedding() → httpx 直接调用 OpenAI 兼容 /embeddings
   - 仅 1 个文件 (LiteLLMEmbeddingEngine.py)
   - 最简单，先验证替换思路

2. litellm.acompletion() 流式调用 → httpx SSE 读取
   - 4 处调用 (distill_knowledge.py, graph_completion_retriever.py)
   - 替换为 httpx + SSE 解析

3. instructor.from_litellm() → instructor.from_openai() 或 instructor.patch()
   - 6 个适配器中的 4 个使用 litellm
   - Anthropic/Ollama 已经不用 litellm
   - 改用 instructor.from_openai(AsyncOpenAI(base_url=...))

4. litellm.model_cost → 内置模型信息表
   - 1 处调用 (utils.py)
   - 用提供商注册表中的 max_tokens 替代

5. litellm.exceptions.* → 自定义异常
   - 约 5 种异常类型
   - 替换为 httpx 异常 + 自定义包装

6. 移除 litellm 依赖
   - pyproject.toml 中删除 litellm
```

**工作量**：~5-8 天
**风险**：中等（需要逐个测试适配器）

### Phase 3（远期）：完整企业化

- 租户级模型配置
- 用量统计和计费
- 模型负载均衡
- API Key 轮换

---

## 11. 实施计划

### Phase 1: 模型提供商配置界面 + Gateway 抽象层

**目标**：用户可以在 UI 上配置模型提供商，选择默认模型

**步骤**：

| # | 任务 | 预计工作量 |
|---|------|----------|
| 1.1 | 创建 `providers/registry.py` 内置提供商注册表 | 0.5 天 |
| 1.2 | 创建数据库模型 `UserModelConfig` + `UserDefaultModel` + migration | 0.5 天 |
| 1.3 | 创建 `ModelProviderService` 业务逻辑层 | 1 天 |
| 1.4 | 创建 `/api/v1/model-providers` API 路由 | 0.5 天 |
| 1.5 | 重构 `LLMGateway` 添加用户配置解析 | 0.5 天 |
| 1.6 | 前端：模型提供商管理页面 | 1-2 天 |
| 1.7 | 前端：默认模型选择页面 | 0.5 天 |
| 1.8 | 连接测试功能 | 0.5 天 |
| **合计** | | **~5-6 天** |

**交付物**：
- 用户可通过 UI 配置模型提供商（API Key + 端点）
- 用户可选择默认模型（按任务类型）
- 连接测试功能
- 向后兼容：不配置 UI 时行为不变

### Phase 2: 移除 LiteLLM 依赖

**目标**：所有 LLM/Embedding 调用改为直接 HTTP 请求，移除 litellm 包

**步骤**：
| # | 任务 | 预计工作量 |
|---|------|----------|
| 2.1 | Embedding 调用替换 (litellm.aembedding → httpx) | 1 天 |
| 2.2 | 流式调用替换 (litellm.acompletion → httpx SSE) | 1 天 |
| 2.3 | 适配器替换 (instructor.from_litellm → from_openai) | 2 天 |
| 2.4 | 异常类和工具函数替换 | 0.5 天 |
| 2.5 | Tokenizer 离线化 (预打包 tiktoken 编码) | 0.5 天 |
| 2.6 | 移除 litellm 依赖 + 全面回归测试 | 1 天 |
| **合计** | | **~6 天** |

### Phase 3: 企业增强（按需）

- 租户级配置
- 用量统计
- 审计日志

---

## 12. 关键接口定义

### 12.1 ProviderAdapter Protocol（保持现有，不改）

```python
class LLMInterface(Protocol):
    """现有接口，保持不变"""
    async def acreate_structured_output(
        self, text_input: str, system_prompt: str, response_model: Type[BaseModel]
    ) -> BaseModel: ...
```

### 12.2 ModelProviderService（新增）

```python
class ModelProviderService:
    """模型提供商管理服务"""

    def list_providers(self) -> list[ProviderDefinition]:
        """列出所有可用提供商"""

    async def get_user_configs(self, user_id: UUID) -> list[UserModelConfig]:
        """获取用户的所有提供商配置"""

    async def save_user_config(self, user_id: UUID, provider_id: str,
                                api_key: str, base_url: str = None) -> UserModelConfig:
        """保存/更新用户的提供商配置"""

    async def test_connection(self, provider_id: str, api_key: str,
                               base_url: str = None) -> ConnectionTestResult:
        """测试提供商连接"""

    async def resolve_model_config(self, user_id: UUID, task_type: str) -> ResolvedModelConfig:
        """解析用户应该使用的模型配置（按优先级链）"""
```

### 12.3 ResolvedModelConfig（新增）

```python
@dataclass
class ResolvedModelConfig:
    """解析后的模型配置（包含调用 LLM 所需的所有信息）"""
    provider_id: str       # "dashscope"
    model_id: str          # "qwen-plus"
    api_key: str           # 解密后的 API Key
    base_url: str          # API 端点
    source: str            # "user" | "tenant" | "yaml" | "env" | "default"
```

---

## 13. 安全考虑

| 方面 | 设计 |
|------|------|
| **API Key 存储** | AES-256 加密存储到数据库，密钥从环境变量读取 |
| **API Key 展示** | 前端只显示 `sk-****f1` 格式，完整密钥只在保存时传输 |
| **HTTPS** | 所有外部 API 调用强制 HTTPS（localhost 除外） |
| **权限控制** | 用户只能管理自己的配置，管理员可管理租户级配置 |
| **审计日志** | Phase 3 添加模型调用审计（谁、何时、调用了什么模型） |

---

## 14. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Phase 1 改动影响现有功能 | 低 | 高 | 纯新增代码，不修改现有调用链 |
| Phase 2 移除 LiteLLM 导致回归 | 中 | 高 | 逐个适配器替换 + 每步 RAGAS 回归测试 |
| 国内提供商 API 不兼容 | 低 | 中 | 大多数支持 OpenAI 协议；百度单独适配 |
| 局域网环境缺少依赖 | 低 | 中 | Docker 镜像预打包所有依赖 |

---

## 15. 与现有代码的关系

### 不修改的文件
- `cognee/infrastructure/llm/structured_output_framework/` — 所有现有适配器保持不变
- `cognee/infrastructure/databases/vector/embeddings/` — 保持不变
- `cognee/tasks/distillation/distill_knowledge.py` — Phase 1 不改
- `cognee/modules/retrieval/graph_completion_retriever.py` — Phase 1 不改

### Phase 1 新增的文件
```
cognee/infrastructure/llm/providers/
├── __init__.py
├── registry.py                    # 内置提供商注册表
├── definitions/                   # 提供商定义
│   ├── cloud_cn.py               # 国内云端提供商
│   ├── cloud_intl.py             # 国际云端提供商
│   └── local.py                  # 本地提供商
└── service.py                     # ModelProviderService

cognee/modules/settings/models/
├── UserModelConfig.py             # 数据库模型
└── UserDefaultModel.py

cognee/api/v1/model_providers/
├── __init__.py
└── routers/
    └── model_provider_router.py   # API 路由

cognee-frontend/src/app/settings/
├── models/
│   ├── page.tsx                   # 模型设置页面
│   ├── ProviderCard.tsx           # 提供商卡片组件
│   ├── ProviderConfigForm.tsx     # 配置表单组件
│   └── DefaultModelSelector.tsx   # 默认模型选择器
```

### Phase 1 修改的文件
```
cognee/infrastructure/llm/LLMGateway.py     # 添加 resolve_model_config 调用
cognee/api/v1/routers.py                     # 注册新路由
cognee-frontend/src/app/layout.tsx           # 添加设置导航入口
```

---

## 附录 A: 国内主流提供商 OpenAI 兼容性对照

| 提供商 | Chat Completion | Embedding | Function Calling | 流式 | 模型列表 API |
|--------|:-:|:-:|:-:|:-:|:-:|
| DashScope | /v1/chat/completions | /v1/embeddings | tools 参数 | SSE | /v1/models |
| DeepSeek | /v1/chat/completions | - | tools 参数 | SSE | /v1/models |
| 智谱 | /v4/chat/completions | /v4/embeddings | tools 参数 | SSE | - |
| 月之暗面 | /v1/chat/completions | - | tools 参数 | SSE | /v1/models |
| 硅基流动 | /v1/chat/completions | /v1/embeddings | tools 参数 | SSE | /v1/models |
| 百度文心 | 自有路径 | 自有路径 | 自有格式 | SSE | 自有 |

> 结论：除百度外，其他 5 家都可以用 OpenAI 兼容适配器直接接入。
