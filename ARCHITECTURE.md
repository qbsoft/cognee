# Cognee 架构设计与详细设计文档

> 本文档面向开发人员，帮助快速理解 Cognee 项目的整体架构、模块划分、文件职责和核心方法。

**文档版本**: 2026-02-26 | **适用代码**: main 分支最新

---

## 目录

1. [系统概述](#1-系统概述)
2. [分层架构](#2-分层架构)
3. [顶层目录结构](#3-顶层目录结构)
4. [核心数据流](#4-核心数据流)
5. [API 接口层详解](#5-api-接口层详解)
6. [CLI 命令层详解](#6-cli-命令层详解)
7. [模块层详解 (modules/)](#7-模块层详解)
8. [任务层详解 (tasks/)](#8-任务层详解)
9. [基础设施层详解 (infrastructure/)](#9-基础设施层详解)
10. [共享层详解 (shared/)](#10-共享层详解)
11. [配置系统](#11-配置系统)
12. [异常处理体系](#12-异常处理体系)
13. [关键设计模式](#13-关键设计模式)

---

## 1. 系统概述

Cognee 是一个**企业级知识图谱构建与语义搜索系统**。核心能力：

```
用户输入（文本/文件/URL）
    ↓
数据摄入 → 文档解析 → 文本分块
    ↓
LLM 实体抽取 → 关系构建 → 知识图谱
    ↓
多模式搜索（向量/图谱/混合）→ LLM 生成回答
```

**技术栈**：
- **后端框架**: FastAPI (异步)
- **数据库**: PostgreSQL (关系型) + Kuzu/Neo4j (图) + LanceDB/PGVector (向量)
- **LLM**: 支持 OpenAI / DashScope / Anthropic / Ollama 等
- **前端**: Next.js (独立仓库 cognee-frontend/)

---

## 2. 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    接口层 (Interface Layer)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ REST API │  │   CLI    │  │ MCP 服务  │  │ Python SDK│  │
│  │ (FastAPI)│  │(argparse)│  │  (SSE)   │  │ (cognee.*)│  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       └──────────────┼─────────────┼──────────────┘         │
├──────────────────────┼─────────────┼────────────────────────┤
│                    模块层 (Module Layer)                      │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐   │
│  │  data   │  │ chunking │  │  graph   │  │ retrieval │   │
│  │(数据管理)│  │ (分块)   │  │ (图谱)   │  │  (检索)   │   │
│  ├─────────┤  ├──────────┤  ├──────────┤  ├───────────┤   │
│  │ingestion│  │ cognify  │  │  search  │  │   users   │   │
│  │(数据摄入)│  │(认知化)  │  │  (搜索)  │  │ (用户管理)│   │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘   │
├───────┼────────────┼─────────────┼───────────────┼──────────┤
│                    任务层 (Task Layer)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │documents │  │  graph   │  │ storage  │  │summarize  │  │
│  │(文档处理)│  │(图提取)  │  │(数据存储)│  │  (总结)   │  │
│  ├──────────┤  ├──────────┤  ├──────────┤  ├───────────┤  │
│  │ingestion │  │Entity   │  │ temporal │  │ feedback  │  │
│  │ (摄入)   │  │Resolution│  │ (时间图) │  │  (反馈)   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
├───────┼────────────┼─────────────┼───────────────┼──────────┤
│                基础设施层 (Infrastructure Layer)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │databases │  │   llm    │  │ loaders  │  │  files    │  │
│  │(数据库)  │  │(大模型)  │  │(文件加载)│  │  (存储)   │  │
│  ├──────────┤  ├──────────┤  ├──────────┤  ├───────────┤  │
│  │  graph   │  │ vector   │  │relational│  │  engine   │  │
│  │ (图DB)   │  │ (向量DB) │  │ (关系DB) │  │(数据模型) │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**依赖规则**：上层可以调用下层，下层不能调用上层。同层之间通过接口通信。

---

## 3. 顶层目录结构

```
cognee/
├── __init__.py                  # 主入口，导出公共 API (add, cognify, search 等)
├── base_config.py               # 基础配置类 (BaseConfig)
├── version.py                   # 版本号管理
├── context_global_variables.py  # 全局上下文变量 (租户/数据库切换)
├── root_dir.py                  # 项目根目录定位
│
├── api/                         # 【接口层】REST API 路由和处理器
│   ├── client.py                #   FastAPI 应用入口 + 中间件
│   ├── health.py                #   健康检查端点
│   ├── DTO.py                   #   数据传输对象基类 (snake_case ↔ camelCase)
│   └── v1/                      #   API v1 版本路由
│       ├── add/                 #     数据添加端点
│       ├── cognify/             #     知识图谱生成端点
│       ├── search/              #     搜索端点
│       ├── datasets/            #     数据集管理端点
│       ├── delete/              #     删除端点
│       ├── update/              #     更新端点
│       ├── users/               #     用户认证端点
│       ├── permissions/         #     权限管理端点
│       ├── settings/            #     配置管理端点
│       ├── sync/                #     云同步端点
│       ├── visualize/           #     可视化端点
│       └── responses/           #     AI 响应端点
│
├── cli/                         # 【接口层】命令行界面
│   ├── _cognee.py               #   CLI 主入口
│   └── commands/                #   子命令实现
│       ├── add_command.py       #     cognee add
│       ├── cognify_command.py   #     cognee cognify
│       ├── search_command.py    #     cognee search
│       ├── delete_command.py    #     cognee delete
│       └── config_command.py    #     cognee config
│
├── modules/                     # 【模块层】核心业务逻辑
│   ├── data/                    #   数据管理 (Dataset, Data 模型)
│   ├── chunking/                #   文本分块 (TextChunker, SemanticChunker)
│   ├── cognify/                 #   认知化配置
│   ├── graph/                   #   图谱操作 (CogneeGraph)
│   ├── search/                  #   搜索调度 (SearchType, HybridRetriever)
│   ├── retrieval/               #   检索器实现 (10+ 种检索策略)
│   ├── ingestion/               #   数据分类和标识
│   ├── users/                   #   用户/租户/角色/权限模型
│   ├── pipelines/               #   管道执行引擎
│   ├── engine/                  #   DataPoint 核心数据模型
│   ├── ontology/                #   领域本体解析
│   ├── settings/                #   运行时配置管理
│   └── metrics/                 #   图谱指标计算
│
├── tasks/                       # 【任务层】原子级可复用任务
│   ├── documents/               #   文档分类和分块任务
│   ├── graph/                   #   图谱提取任务 (LLM 实体抽取)
│   ├── graph_validation/        #   图谱多轮验证任务
│   ├── entity_resolution/       #   实体消歧任务
│   ├── ingestion/               #   数据摄入任务
│   ├── storage/                 #   数据点存储任务
│   ├── summarization/           #   文本总结任务
│   ├── chunks/                  #   分块工具任务
│   ├── temporal_graph/          #   时间图谱任务
│   ├── temporal_awareness/      #   时间感知任务
│   ├── feedback/                #   用户反馈任务
│   └── web_scraper/             #   网页抓取任务
│
├── infrastructure/              # 【基础设施层】底层服务
│   ├── databases/               #   数据库适配器
│   │   ├── relational/          #     关系数据库 (SQLAlchemy)
│   │   ├── graph/               #     图数据库 (Kuzu, Neo4j, Neptune)
│   │   └── vector/              #     向量数据库 (LanceDB, PGVector, Chroma)
│   ├── llm/                     #   大语言模型集成
│   │   ├── config.py            #     LLM 配置
│   │   ├── LLMGateway.py        #     统一 LLM 网关
│   │   ├── extraction/          #     内容提取 (图谱/摘要/分类)
│   │   ├── prompts/             #     提示词管理
│   │   └── tokenizer/           #     分词器适配器
│   ├── loaders/                 #   文件加载器
│   │   ├── LoaderEngine.py      #     加载器管理引擎
│   │   ├── LoaderInterface.py   #     加载器接口
│   │   ├── core/                #     内置加载器 (文本/图像/音频)
│   │   ├── docling_loader/      #     Docling 高精度解析器
│   │   └── external/            #     外部加载器 (PyPDF/Unstructured)
│   ├── files/                   #   文件存储
│   │   ├── storage/             #     存储后端 (本地/S3)
│   │   └── utils/               #     文件工具函数
│   ├── engine/                  #   核心数据模型
│   │   └── models/              #     DataPoint, Edge 等
│   └── config/                  #   YAML 配置系统
│
├── shared/                      # 【共享层】跨模块工具
│   ├── data_models.py           #   KnowledgeGraph, Node, Edge
│   ├── logging_utils.py         #   日志工具
│   └── exceptions/              #   异常基类
│
└── tests/                       # 测试套件
    ├── unit/                    #   单元测试 (1311+)
    └── integration/             #   集成测试
```

---

## 4. 核心数据流

### 4.1 数据摄入流 (add)

```
用户输入 (文本/文件/URL)
    │
    ▼
┌─────────────────────────────────────────────────┐
│ api/v1/add/add.py                               │
│ async add(data, dataset_name, user, ...)        │
│   → 解析输入格式、验证权限                       │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│ tasks/ingestion/ingest_data.py                  │
│ async ingest_data(data, dataset_name, user)     │
│   → 分类数据类型 (classify)                      │
│   → 去重检查 (content_hash)                      │
│   → 转换为文本文件 (data_item_to_text_file)      │
│   → 保存到 cognee 数据存储                       │
│   → 创建 Data 记录到关系数据库                    │
└────────────────────┬────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────┐
│ infrastructure/loaders/LoaderEngine.py           │
│ get_loader(file_path) → 选择合适的加载器          │
│   优先级: docling → text → pypdf → unstructured  │
│   → loader.load(file_path) → 返回文本文件路径     │
└─────────────────────────────────────────────────┘
```

### 4.2 知识图谱构建流 (cognify)

```
已摄入的数据集
    │
    ▼
┌──────────────────────────────────────────────────┐
│ api/v1/cognify/cognify.py                        │
│ async cognify(datasets, user, graph_model, ...)  │
│   → 构建管道任务列表                              │
│   → 提交管道执行                                  │
└────────────────────┬─────────────────────────────┘
                     ▼
    ┌────────────────────────────────────┐
    │      管道任务执行顺序               │
    │                                    │
    │  1. classify_documents()           │  → 文档分类
    │          ↓                         │
    │  2. extract_chunks_from_documents()│  → 文本分块
    │          ↓                         │
    │  3. extract_graph_from_data()      │  → LLM 实体/关系抽取
    │          ↓                         │
    │  4. validate_extracted_graph()     │  → [可选] 多轮验证
    │          ↓                         │
    │  5. resolve_entities()            │  → [可选] 实体消歧
    │          ↓                         │
    │  6. summarize_text()              │  → 文本摘要生成
    │          ↓                         │
    │  7. add_data_points()             │  → 存入图DB + 向量DB
    │                                    │
    └────────────────────────────────────┘
```

### 4.3 搜索检索流 (search)

```
用户查询
    │
    ▼
┌──────────────────────────────────────────────────┐
│ api/v1/search/search.py                          │
│ async search(query_text, query_type, user, ...)  │
│   → 权限验证                                      │
│   → 按 SearchType 分发到对应检索器                 │
└────────────────────┬─────────────────────────────┘
                     ▼
    ┌────────────────────────────────────┐
    │   检索器选择 (SearchType)           │
    │                                    │
    │  GRAPH_COMPLETION                  │  → GraphCompletionRetriever
    │    - 向量搜索找相关节点             │     (图遍历 + LLM 生成)
    │    - 图遍历获取三元组               │
    │    - LLM 生成最终回答              │
    │                                    │
    │  RAG_COMPLETION                    │  → ChunksRetriever
    │    - 向量搜索找文本块              │     (向量搜索 + LLM 生成)
    │    - LLM 生成回答                  │
    │                                    │
    │  HYBRID_SEARCH                     │  → HybridRetriever
    │    - 同时运行向量/图/词汇检索       │     (RRF 融合 3 种结果)
    │    - RRF 融合排序                  │
    │    - LLM 生成回答                  │
    │                                    │
    │  NATURAL_LANGUAGE                  │  → NaturalLanguageRetriever
    │    - LLM 生成 Cypher 查询          │     (LLM→Cypher→图DB)
    │    - 直接查询图数据库              │
    │                                    │
    └────────────────────────────────────┘
```

---

## 5. API 接口层详解

### 5.1 FastAPI 应用入口

**文件**: `cognee/api/client.py`

```python
# 核心职责:
# 1. 创建 FastAPI 应用实例
# 2. 配置 CORS、认证、异常处理中间件
# 3. 注册所有路由
# 4. lifespan 生命周期管理 (数据库初始化、默认用户创建)

app = FastAPI(lifespan=lifespan)

# 关键函数:
def start_api_server(host, port)  # 启动 Uvicorn 服务器
async def lifespan(app)           # 应用启动/关闭时的初始化
```

### 5.2 数据添加 API

**目录**: `cognee/api/v1/add/`

| 文件 | 职责 | 关键函数 |
|------|------|---------|
| `add.py` | 数据添加核心逻辑 | `async add(data, dataset_name, user, node_set, preferred_loaders, ...)` |
| `get_add_router.py` | 路由定义 | `POST /api/v1/add` — 接受 UploadFile 列表 |

```python
# add.py 的核心签名:
async def add(
    data: Union[BinaryIO, list[BinaryIO], str, list[str]],
    dataset_name: str = "main_dataset",   # 数据集名称
    user: User = None,                     # 认证用户
    node_set: Optional[List[str]] = None,  # 节点集合过滤
    preferred_loaders: dict = None,        # 首选加载器
    incremental_loading: bool = True,      # 增量加载（跳过已处理）
    data_per_batch: int = 20,              # 批处理大小
) -> PipelineRunInfo
```

### 5.3 知识图谱生成 API

**目录**: `cognee/api/v1/cognify/`

| 文件 | 职责 | 关键函数 |
|------|------|---------|
| `cognify.py` | 图谱构建核心逻辑 | `async cognify(datasets, graph_model, chunk_size, ...)` |
| `get_cognify_router.py` | 路由 + WebSocket | `POST /api/v1/cognify` + `WS /subscribe/{run_id}` |

```python
# cognify.py 的核心签名:
async def cognify(
    datasets: Union[str, list[str]] = None,  # 数据集
    graph_model: BaseModel = KnowledgeGraph,  # 图谱模型
    chunker = TextChunker,                    # 分块器
    chunk_size: int = None,                   # 分块大小
    run_in_background: bool = False,          # 后台运行
    custom_prompt: Optional[str] = None,      # 自定义提示词
    temporal_cognify: bool = False,           # 时间图谱模式
) -> Union[dict, list[PipelineRunInfo]]

# WebSocket 端点提供实时进度推送
```

### 5.4 搜索 API

**目录**: `cognee/api/v1/search/`

| 文件 | 职责 | 关键函数 |
|------|------|---------|
| `search.py` | 搜索核心逻辑 | `async search(query_text, query_type, user, ...)` |
| `get_search_router.py` | 路由定义 | `POST /api/v1/search` + `GET /api/v1/search` (历史) |

```python
# search.py 的核心签名:
async def search(
    query_text: str,                              # 查询文本
    query_type: SearchType = SearchType.GRAPH_COMPLETION,  # 搜索类型
    user: Optional[User] = None,                  # 认证用户
    datasets: Optional[list[str]] = None,         # 数据集过滤
    top_k: int = 10,                              # 返回结果数
    only_context: bool = False,                   # 仅返回上下文
    session_id: Optional[str] = None,             # 会话 ID (多轮对话)
) -> Union[List[SearchResult], CombinedSearchResult]
```

### 5.5 数据集管理 API

**目录**: `cognee/api/v1/datasets/`

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v1/datasets` | GET | 获取用户所有数据集 |
| `/api/v1/datasets` | POST | 创建数据集 |
| `/api/v1/datasets/{id}` | DELETE | 删除数据集 |
| `/api/v1/datasets/{id}/data` | GET | 获取数据集下的数据列表 |
| `/api/v1/datasets/{id}/graph` | GET | 获取数据集的知识图谱 |
| `/api/v1/datasets/{id}/data/{data_id}/raw` | GET | 下载原始文件 |
| `/api/v1/datasets/status` | GET | 查询管道处理状态 |

### 5.6 健康检查

**文件**: `cognee/api/health.py`

```python
# 检查所有组件的健康状态:
async def check_relational_db()     # 关系数据库连接
async def check_vector_db()         # 向量数据库连接
async def check_graph_db()          # 图数据库连接
async def check_file_storage()      # 文件存储读写
async def check_llm_provider()      # LLM API 可用性
async def check_embedding_service() # 嵌入服务可用性

# 返回状态: "healthy" / "degraded" / "unhealthy"
```

### 5.7 DTO 模型

**文件**: `cognee/api/DTO.py`

```python
class OutDTO(BaseModel):
    """出站响应 — 自动将 snake_case 转为 camelCase"""
    model_config = ConfigDict(alias_generator=to_camel)

class InDTO(BaseModel):
    """入站请求 — 自动将 camelCase 转为 snake_case"""

# 示例: dataset_name ↔ datasetName
```

---

## 6. CLI 命令层详解

**目录**: `cognee/cli/`

### 6.1 主入口

**文件**: `cognee/cli/_cognee.py`

```python
def main() -> int:
    """CLI 主入口。使用 argparse 解析命令。"""
    # 动态发现并注册命令:
    # AddCommand, CognifyCommand, SearchCommand, DeleteCommand, ConfigCommand

# 全局参数:
# --version     显示版本
# --debug       启用调试模式
# -ui           启动 Web UI (前端 + 后端 + MCP)
```

### 6.2 命令列表

| 命令 | 文件 | 用法 | 说明 |
|------|------|------|------|
| `cognee add` | `commands/add_command.py` | `cognee add "文本" -d 数据集名` | 添加文本/文件 |
| `cognee cognify` | `commands/cognify_command.py` | `cognee cognify -d 数据集名 --background` | 构建知识图谱 |
| `cognee search` | `commands/search_command.py` | `cognee search "查询" -t GRAPH_COMPLETION` | 搜索查询 |
| `cognee delete` | `commands/delete_command.py` | `cognee delete -d 数据集名 --force` | 删除数据 |
| `cognee config` | `commands/config_command.py` | `cognee config get llm_model` | 配置管理 |

### 6.3 config 子命令

```bash
cognee config get [key]        # 获取配置 (不带 key 显示全部)
cognee config set <key> <val>  # 设置配置
cognee config list             # 列出所有配置键
cognee config unset <key>      # 重置为默认值
cognee config reset            # 全部重置
```

---

## 7. 模块层详解

### 7.1 data — 数据管理模块

**目录**: `cognee/modules/data/`

```
data/
├── models/                          # ORM 模型
│   ├── Data.py                      #   单条数据记录
│   ├── Dataset.py                   #   数据集容器
│   ├── DatasetData.py               #   数据-数据集关联 (多对多)
│   └── GraphMetrics.py              #   图谱统计指标
├── methods/                         # 业务方法
│   ├── create_dataset.py            #   创建数据集
│   ├── get_dataset.py               #   查询数据集
│   ├── delete_dataset.py            #   删除数据集
│   └── get_authorized_dataset.py    #   权限过滤查询
└── processing/
    └── document_types/              # 文档类型定义
        ├── Document.py              #   文档基类 (抽象)
        ├── TextDocument.py          #   文本文档
        ├── PdfDocument.py           #   PDF 文档
        ├── ImageDocument.py         #   图像文档
        └── AudioDocument.py         #   音频文档
```

**关键模型**:

```python
class Data:
    """表示一条摄入的数据。"""
    id: UUID                    # 主键
    name: str                   # 文件名
    extension: str              # 文件扩展名
    mime_type: str              # MIME 类型
    owner_id: UUID              # 所有者 (用户)
    tenant_id: UUID             # 租户
    content_hash: str           # 内容哈希 (去重用)
    raw_data_location: str      # 原始文件存储路径
    pipeline_status: str        # 处理状态 (pending/completed/failed)
    token_count: int            # token 数量

class Dataset:
    """数据集 — Data 的逻辑分组。"""
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime
```

### 7.2 chunking — 文本分块模块

**目录**: `cognee/modules/chunking/`

```
chunking/
├── Chunker.py                  # 分块器抽象基类
├── TextChunker.py              # 【默认】按段落分块，追踪行号和字符偏移
├── SemanticChunker.py          # 语义感知分块 (识别标题/代码块/表格)
├── LLMEnhancedChunker.py       # LLM 增强分块 (使用 LLM 优化分块边界)
├── LangchainChunker.py         # Langchain 递归字符分割
└── models/
    └── DocumentChunk.py        # 分块数据模型 (DataPoint 子类)
```

**关键类**:

```python
class Chunker(ABC):
    """分块器抽象基类。所有分块器必须实现 read() 方法。"""
    def __init__(self, document, get_text, max_chunk_size): ...
    async def read(self) -> AsyncGenerator[DocumentChunk]: ...

class DocumentChunk(DataPoint):
    """一个文本分块，继承自 DataPoint，可被存入图谱和向量库。"""
    text: str                    # 分块文本内容
    chunk_size: int              # token 数量
    chunk_index: int             # 在文档中的序号
    cut_type: str                # 切割类型 (paragraph_end 等)
    is_part_of: Document         # 所属文档 (图谱关系)
    # 溯源字段:
    source_data_id: UUID         # 原始数据 ID
    source_file_path: str        # 原始文件路径
    start_line: int              # 起始行号
    end_line: int                # 结束行号
    page_number: int             # 页码
```

### 7.3 graph — 图谱操作模块

**目录**: `cognee/modules/graph/`

```
graph/
├── cognee_graph/
│   ├── CogneeGraph.py          # 图谱实现 (节点/边管理 + DB 投影)
│   └── CogneeGraphElements.py  # 图元素 (Node, Edge 类)
└── utils/
    ├── get_graph_from_model.py          # 从 DataPoint 提取图结构
    ├── deduplicate_nodes_and_edges.py   # 去重
    ├── expand_with_nodes_and_edges.py   # 扩展 (本体验证)
    ├── entity_normalization.py          # 实体名规范化
    ├── entity_quality_scorer.py         # 实体质量评分
    ├── relationship_validator.py        # 关系验证
    └── data_integrity_checker.py        # 数据完整性检查
```

**关键方法**:

```python
class CogneeGraph:
    """内存图谱，用于搜索时的图计算。"""
    nodes: Dict[str, Node]
    edges: List[Edge]

    async def project_graph_from_db()                      # 从数据库加载图谱到内存
    async def map_vector_distances_to_graph_nodes(query)    # 向量距离映射到节点
    async def calculate_top_triplet_importances(top_k)      # 计算 top-k 重要三元组
```

### 7.4 search — 搜索调度模块

**目录**: `cognee/modules/search/`

```
search/
├── methods/
│   └── search.py                    # 搜索主入口 (权限检查 + 数据集过滤)
├── types/
│   ├── SearchType.py                # 搜索类型枚举 (16 种)
│   └── SearchResult.py              # 搜索结果模型
├── operations/
│   ├── select_search_type.py        # 类型分发 → 对应检索器
│   ├── log_query.py                 # 记录查询日志
│   └── log_result.py                # 记录结果日志
├── retrievers/
│   └── HybridRetriever.py           # 混合检索 (RRF 融合)
└── reranking/
    └── reranker.py                  # BGE-Reranker 重排
```

**SearchType 枚举** (常用):

| 类型 | 说明 | 检索器 |
|------|------|--------|
| `GRAPH_COMPLETION` | 图谱补全 Q&A (默认) | GraphCompletionRetriever |
| `RAG_COMPLETION` | 传统 RAG | ChunksRetriever |
| `CHUNKS` | 纯文本块匹配 | ChunksRetriever (无 LLM) |
| `NATURAL_LANGUAGE` | LLM 生成 Cypher | NaturalLanguageRetriever |
| `HYBRID_SEARCH` | 混合搜索 (RRF) | HybridRetriever |
| `GRAPH_COMPLETION_COT` | 链式推理 | GraphCompletionCotRetriever |
| `CODE` | 代码搜索 | CodeRetriever |
| `TEMPORAL` | 时间感知搜索 | TemporalRetriever |

### 7.5 retrieval — 检索器模块

**目录**: `cognee/modules/retrieval/`

```
retrieval/
├── base_retriever.py                     # 检索器抽象基类
├── chunks_retriever.py                   # 文本块检索 (向量搜索)
├── graph_completion_retriever.py         # 图补全检索 (向量+图遍历+LLM)
├── graph_completion_cot_retriever.py     # 链式推理检索 (CoT)
├── natural_language_retriever.py         # 自然语言→Cypher 检索
├── lexical_retriever.py                  # 词汇检索 (BM25 风格)
├── temporal_retriever.py                 # 时间感知检索
├── code_retriever.py                     # 代码检索
├── context_providers/                    # 上下文提供器
│   ├── TripletSearchContextProvider.py   #   三元组搜索
│   └── SummarizedTripletSearchContextProvider.py  # 摘要三元组
└── utils/
    ├── brute_force_triplet_search.py     # BFS 图遍历 + 向量打分
    ├── completion.py                     # LLM 补全生成
    ├── session_cache.py                  # 会话缓存 (多轮对话)
    └── result_quality_scorer.py          # 结果质量排序
```

**关键检索器**:

```python
class BaseRetriever(ABC):
    """所有检索器的基类。"""
    async def get_context(self, query: str) -> Any:
        """获取查询上下文（三元组/文本块等）。"""
    async def get_completion(self, query: str, context, session_id) -> str:
        """基于上下文生成回答。"""

class GraphCompletionRetriever(BaseGraphRetriever):
    """图谱补全检索器 — 最常用的检索策略。"""
    def __init__(self, top_k=5, similarity_threshold=0.5, ...): ...

    async def get_triplets(self, query) -> List[Edge]:
        """
        核心搜索流程:
        1. 将查询向量化
        2. 在向量库搜索相关节点
        3. 在图库中 BFS 遍历获取三元组 (node-edge-node)
        4. 按相似度 + 质量评分排序
        5. 返回 top_k 个三元组
        """

    async def get_completion(self, query, context, session_id) -> List[str]:
        """将三元组格式化为上下文，调用 LLM 生成回答。"""

class HybridRetriever:
    """混合检索器 — RRF 融合多种检索结果。"""
    def __init__(self, vector_retriever, graph_retriever,
                 lexical_retriever, weights, top_k): ...
    # weights 默认: {vector: 0.4, graph: 0.3, lexical: 0.3}
    # RRF 公式: score = sum(weight_i / (k + rank_i))
```

### 7.6 ingestion — 数据摄入模块

**目录**: `cognee/modules/ingestion/`

```
ingestion/
├── classify.py              # 数据分类 (文本/二进制/S3)
├── identify.py              # 数据标识 (content_hash → UUID)
├── data_types/
│   ├── IngestionData.py     # 摄入数据协议
│   ├── TextData.py          # 文本数据包装
│   ├── BinaryData.py        # 二进制数据包装
│   └── S3BinaryData.py      # S3 数据包装
└── save_data_to_file.py     # 保存到文件存储
```

```python
async def classify(data, filename=None) -> IngestionData:
    """分类输入数据为 TextData / BinaryData / S3BinaryData。"""

async def identify(data: IngestionData, user: User) -> UUID:
    """根据 content_hash + user_id 生成唯一 UUID，用于去重。"""
```

### 7.7 users — 用户管理模块

**目录**: `cognee/modules/users/`

```
users/
├── models/
│   ├── User.py              # 用户模型 (FastAPI-Users 扩展)
│   ├── Tenant.py            # 租户模型 (6 位唯一编码)
│   ├── Role.py              # 角色模型
│   ├── Permission.py        # 权限模型 (read/write/delete/admin)
│   ├── ACL.py               # 访问控制列表 (Principal × Permission × Dataset)
│   ├── Principal.py         # 多态主体基类 (User/Tenant/Role 共用)
│   ├── ApiKey.py            # API 密钥
│   └── InviteToken.py       # 邀请令牌
├── methods/
│   ├── create_user.py       # 创建用户
│   ├── get_default_user.py  # 获取默认用户 (无认证模式)
│   └── get_authenticated_user.py  # 获取已认证用户
├── permissions/
│   ├── methods/
│   │   ├── check_permission_on_dataset.py    # 检查权限
│   │   └── give_permission_on_dataset.py     # 授予权限
│   └── permission_types.py  # 权限类型定义
└── authentication/
    ├── default/default_jwt_strategy.py   # JWT 认证
    └── api_bearer/api_jwt_strategy.py    # API Key 认证
```

**权限模型**:

```
Principal (User/Role/Tenant)
    ×
Permission (read/write/delete/share)
    ×
Dataset
    =
ACL 记录 (访问控制列表)

示例: User("alice") + Permission("write") + Dataset("my_docs") = 允许写入
```

### 7.8 pipelines — 管道执行模块

**目录**: `cognee/modules/pipelines/`

```
pipelines/
├── operations/
│   ├── pipeline.py               # run_pipeline() — 管道主入口
│   ├── run_tasks.py              # 任务顺序执行
│   ├── run_tasks_distributed.py  # 分布式执行 (Modal)
│   └── run_parallel.py           # 并行执行
├── tasks/
│   └── task.py                   # Task 类 — 管道中的任务单元
├── models/
│   ├── Pipeline.py               # 管道模型
│   ├── PipelineRun.py            # 管道执行记录
│   └── PipelineTask.py           # 管道任务记录
└── layers/
    ├── setup_and_check_environment.py         # 环境检查
    ├── resolve_authorized_user_datasets.py    # 权限验证
    ├── validate_pipeline_tasks.py             # 任务校验
    ├── pipeline_execution_mode.py             # 执行模式选择
    └── check_pipeline_run_qualification.py    # 增量加载检查
```

```python
async def run_pipeline(tasks: list[Task], data, ...):
    """
    管道引擎 — 按顺序执行任务列表。
    每个 Task 接收上一个 Task 的输出作为输入。
    支持: 顺序执行、并行执行、分布式执行。
    """
```

### 7.9 engine — 核心数据模型

**目录**: `cognee/modules/engine/` + `cognee/infrastructure/engine/`

```python
class DataPoint(BaseModel):
    """
    所有图谱数据的基类。Cognee 中的节点和关系都继承自 DataPoint。
    存储到图数据库和向量数据库时都使用 DataPoint。
    """
    id: UUID                          # 唯一标识
    created_at: int                   # 创建时间 (毫秒)
    updated_at: int                   # 更新时间 (毫秒)
    version: int = 1                  # 版本号 (自动递增)
    metadata: Optional[MetaData]      # 元数据 (含 index_fields)
    type: str                         # 类型名 (默认为类名)

    def get_embeddable_data(self):
        """获取用于向量化的字段值。基于 metadata.index_fields。"""

    def to_dict(self):
        """序列化为字典，用于存入数据库。"""

class Edge(BaseModel):
    """图谱边 (关系) 的属性模型。"""
    weight: Optional[float]           # 边权重
    weights: Optional[Dict[str, float]]  # 多维权重
    relationship_type: Optional[str]  # 关系类型
    properties: Optional[Dict]        # 附加属性
```

---

## 8. 任务层详解

任务层提供**原子级、可复用的处理单元**，由管道引擎调度执行。

### 8.1 文档处理任务

**目录**: `cognee/tasks/documents/`

| 文件 | 函数 | 说明 |
|------|------|------|
| `classify_documents.py` | `classify_documents(data)` | 将 Data 记录转为对应 Document 类型 |
| `extract_chunks_from_documents.py` | `extract_chunks_from_documents(documents, chunk_size, chunker)` | 调用分块器将文档切分为 DocumentChunk |

### 8.2 图谱提取任务

**目录**: `cognee/tasks/graph/`

| 文件 | 函数 | 说明 |
|------|------|------|
| `extract_graph_from_data.py` | `extract_graph_from_data(chunks, graph_model)` | 使用 LLM 从文本块中提取实体和关系 |
| `extract_graph_from_data_v2.py` | `extract_graph_from_data(chunks, n_rounds)` | V2 版本：级联提取 (节点→边→三元组) |

```python
async def extract_graph_from_data(data_chunks, graph_model, config, custom_prompt):
    """
    核心图谱提取流程:
    1. 将每个文本块发送给 LLM
    2. LLM 返回 KnowledgeGraph (节点 + 边)
    3. 过滤无效边 (缺少源/目标节点)
    4. 实体质量过滤
    5. 返回 DataPoint 列表 (可存入图DB)
    """
```

### 8.3 图谱验证任务

**目录**: `cognee/tasks/graph_validation/`

| 文件 | 函数 | 说明 |
|------|------|------|
| `validate_extracted_graph.py` | `validate_extracted_graph(data, llm_client, confidence_threshold)` | LLM 二次验证，为关系打置信度分数 |

```python
async def validate_extracted_graph(extracted_data, llm_client=None,
                                    confidence_threshold=0.7):
    """
    多轮验证流程:
    1. 取出提取的三元组
    2. 让 LLM 对每个关系打分 (0.0 ~ 1.0)
    3. 过滤低于 confidence_threshold 的关系
    4. LLM 不可用时降级为默认分数 0.5
    """
```

### 8.4 实体消歧任务

**目录**: `cognee/tasks/entity_resolution/`

| 文件 | 函数 | 说明 |
|------|------|------|
| `resolve_entities.py` | `resolve_entities(entities, fuzzy_threshold, embedding_threshold)` | Union-Find 算法合并重复实体 |

```python
async def resolve_entities(entities, fuzzy_threshold=0.85,
                           embedding_threshold=0.9):
    """
    实体消歧流程:
    1. 精确名称匹配 → 合并
    2. 别名匹配 → 合并
    3. 模糊匹配 (Levenshtein) > threshold → 合并
    4. 类型不一致 → 阻止合并
    5. 使用 Union-Find 算法生成合并集
    6. 输出去重后的实体列表
    """
```

### 8.5 数据存储任务

**目录**: `cognee/tasks/storage/`

| 文件 | 函数 | 说明 |
|------|------|------|
| `add_data_points.py` | `add_data_points(data_points)` | 将 DataPoint 存入图DB + 向量DB |

```python
async def add_data_points(data_points: List[DataPoint]):
    """
    存储流程:
    1. 验证输入类型
    2. 从每个 DataPoint 提取图结构 (get_graph_from_model)
    3. 全局去重 (deduplicate_nodes_and_edges)
    4. 并行写入: 图数据库 (add_nodes + add_edges)
    5. 并行索引: 向量数据库 (index_data_points)
    """
```

### 8.6 数据摄入任务

**目录**: `cognee/tasks/ingestion/`

| 文件 | 函数 | 说明 |
|------|------|------|
| `ingest_data.py` | `ingest_data(data, dataset_name, user)` | 完整摄入流程 |
| `data_item_to_text_file.py` | `data_item_to_text_file(data_item)` | 调用 LoaderEngine 转换为文本 |
| `save_data_item_to_storage.py` | `save_data_item_to_storage(data_item)` | 保存到文件存储 |
| `resolve_data_directories.py` | `resolve_data_directories(data)` | 解析目录/文件路径 |

### 8.7 其他任务

| 目录 | 说明 |
|------|------|
| `tasks/summarization/` | 文本/代码摘要 (LLM) |
| `tasks/temporal_graph/` | 时间图谱构建 (事件提取) |
| `tasks/temporal_awareness/` | 时间感知搜索 (Graphiti) |
| `tasks/chunks/` | 底层分块工具 (按句/段/词) |
| `tasks/feedback/` | 用户反馈和答案改进 |
| `tasks/web_scraper/` | 网页抓取任务 |
| `tasks/code/` | 代码依赖分析 |

---

## 9. 基础设施层详解

### 9.1 数据库适配器

#### 9.1.1 图数据库

**目录**: `cognee/infrastructure/databases/graph/`

```
graph/
├── graph_db_interface.py      # 图DB 抽象接口
├── kuzu/
│   └── adapter.py             # KuzuAdapter — 默认，文件型，零配置
├── neo4j_driver/
│   └── adapter.py             # Neo4jAdapter — 生产级，分布式
└── neptune_driver/
    └── adapter.py             # NeptuneAdapter — AWS 托管
```

```python
class GraphDBInterface(ABC):
    """图数据库统一接口。所有图DB适配器必须实现。"""

    # 节点操作
    async def add_nodes(self, nodes: List[DataPoint]): ...
    async def get_node(self, node_id: str) -> Optional[NodeData]: ...
    async def delete_node(self, node_id: str): ...

    # 边操作
    async def add_edges(self, edges: List[EdgeData]): ...
    async def has_edge(self, src, tgt, rel) -> bool: ...
    async def get_edges(self, node_id: str) -> List[EdgeData]: ...

    # 查询
    async def query(self, query: str, params: dict) -> List: ...
    async def get_graph_data(self) -> Tuple[List[Node], List[EdgeData]]: ...
    async def get_neighbors(self, node_id) -> List[NodeData]: ...
    async def get_connections(self, node_id) -> List[Tuple]: ...

    # 指标
    async def get_graph_metrics(self, include_optional) -> Dict: ...
```

#### 9.1.2 向量数据库

**目录**: `cognee/infrastructure/databases/vector/`

```
vector/
├── vector_db_interface.py     # 向量DB 接口协议
├── lancedb/
│   └── LanceDBAdapter.py      # LanceDB — 默认，文件型，零配置
├── pgvector/
│   └── PGVectorAdapter.py     # PGVector — PostgreSQL 扩展
├── chromadb/
│   └── ChromaDBAdapter.py     # ChromaDB — 独立向量DB
└── embeddings/
    ├── EmbeddingEngine.py     # 嵌入引擎协议
    ├── LiteLLMEmbeddingEngine.py  # 通过 LiteLLM 调用嵌入 API
    ├── FastembedEmbeddingEngine.py # 本地 FastEmbed
    └── embedding_rate_limiter.py  # 嵌入 API 速率限制
```

```python
class VectorDBInterface(Protocol):
    """向量数据库统一协议。"""
    async def create_collection(self, name, schema): ...
    async def create_data_points(self, collection, points): ...
    async def search(self, collection, query_text, query_vector, limit): ...
    async def batch_search(self, collection, queries, limit): ...
    async def delete_data_points(self, collection, ids): ...
    async def embed_data(self, data: List[str]) -> List[List[float]]: ...
```

#### 9.1.3 关系数据库

**目录**: `cognee/infrastructure/databases/relational/`

```
relational/
├── SqlAlchemyAdapter.py       # SQLAlchemy 异步适配器
├── ModelBase.py               # ORM 基类 (DeclarativeBase)
├── create_db_and_tables.py    # 数据库初始化
├── create_relational_engine.py # 引擎工厂
└── config.py                  # 连接字符串配置
```

```python
class SqlAlchemyAdapter:
    """关系数据库适配器。支持 PostgreSQL/SQLite/MySQL。"""
    async def get_async_session(self) -> AsyncGenerator[AsyncSession]: ...
    async def get_datasets(self) -> List[Dataset]: ...
    async def create_table(self, schema, name, config): ...
```

### 9.2 LLM 集成

**目录**: `cognee/infrastructure/llm/`

```
llm/
├── config.py                  # LLMConfig — LLM 全局配置
├── LLMGateway.py              # 统一 LLM 网关 (路由到 BAML 或 LiteLLM)
│
├── structured_output_framework/
│   ├── baml/                  # BAML 结构化输出框架
│   │   └── baml_client/       #   BAML 客户端 (类型安全提取)
│   └── litellm_instructor/    # LiteLLM + Instructor 框架
│       └── llm/
│           ├── openai/adapter.py      # OpenAI 适配器
│           ├── anthropic/adapter.py   # Claude 适配器
│           ├── gemini/adapter.py      # Gemini 适配器
│           ├── ollama/adapter.py      # Ollama 适配器
│           ├── mistral/adapter.py     # Mistral 适配器
│           └── rate_limiter.py        # LLM API 速率限制
│
├── extraction/                # 内容提取
│   ├── extract_categories.py  #   分类提取
│   ├── extract_summary.py     #   摘要提取
│   └── knowledge_graph/       #   图谱提取
│       ├── extract_content_graph.py   # 内容图谱
│       └── extract_event_graph.py     # 事件图谱
│
├── tokenizer/                 # 分词器
│   ├── TikToken/adapter.py    #   OpenAI 分词
│   ├── HuggingFace/adapter.py #   HF 分词
│   └── Mistral/adapter.py     #   Mistral 分词
│
└── prompts/                   # 提示词管理
    ├── read_query_prompt.py   #   读取提示词文件
    └── render_prompt.py       #   渲染提示词模板
```

```python
class LLMGateway:
    """统一 LLM 网关。所有 LLM 调用都经过此网关。"""

    @staticmethod
    async def acreate_structured_output(
        text_input: str,
        system_prompt: str,
        response_model: BaseModel
    ):
        """
        结构化输出提取:
        1. 根据配置选择框架 (BAML 或 LiteLLM Instructor)
        2. 发送请求到 LLM
        3. 解析响应为 Pydantic 模型
        """

class LLMConfig(BaseSettings):
    """LLM 配置。从环境变量自动加载。"""
    llm_provider: str = "openai"
    llm_model: str = "openai/gpt-5-mini"
    llm_endpoint: str = ""
    llm_api_key: Optional[str] = None
    llm_temperature: float = 0.0
    llm_rate_limit_enabled: bool = False
    llm_rate_limit_requests: int = 60       # 每分钟请求数
    embedding_rate_limit_enabled: bool = False
```

### 9.3 文件加载器

**目录**: `cognee/infrastructure/loaders/`

```
loaders/
├── LoaderInterface.py          # 加载器抽象接口
├── LoaderEngine.py             # 加载器管理引擎 (注册 + 选择)
│
├── core/                       # 内置加载器
│   ├── text_loader.py          #   TextLoader — txt/md/csv/json/xml/yaml
│   ├── image_loader.py         #   ImageLoader — jpg/png/gif
│   ├── audio_loader.py         #   AudioLoader — mp3/wav
│   └── ocr_enhanced_image_loader.py  # OCR 增强图像加载
│
├── docling_loader/             # Docling 高精度解析
│   └── DoclingLoader.py        #   DoclingLoader — pdf/docx/pptx/xlsx
│
└── external/                   # 外部库加载器
    ├── pypdf_loader.py         #   PyPdfLoader — PDF
    ├── unstructured_loader.py  #   UnstructuredLoader — doc/ppt/epub 等
    └── beautiful_soup_loader.py #  BeautifulSoupLoader — HTML
```

```python
class LoaderInterface(ABC):
    """加载器接口。所有加载器必须实现。"""
    @property
    def supported_extensions(self) -> List[str]: ...   # 如 ["pdf", "docx"]
    @property
    def supported_mime_types(self) -> List[str]: ...    # 如 ["application/pdf"]
    @property
    def loader_name(self) -> str: ...                  # 如 "docling_loader"
    def can_handle(self, extension, mime_type) -> bool: ...
    async def load(self, file_path, **kwargs) -> Optional[str]: ...
    # load() 返回文本文件路径 (存入 cognee 数据存储后的路径)

class LoaderEngine:
    """加载器管理引擎。按优先级选择合适的加载器。"""
    default_loader_priority = [
        "docling_loader",      # 最高优先级 — 高精度
        "text_loader",         # 文本格式
        "pypdf_loader",        # PDF 备选
        "image_loader",        # 图像
        "audio_loader",        # 音频
        "unstructured_loader", # 旧格式兜底
        "advanced_pdf_loader", # 高级 PDF
    ]

    def register_loader(self, loader): ...   # 注册加载器
    def get_loader(self, file_path): ...     # 按优先级匹配加载器
    async def load_file(self, file_path): ... # 加载文件
```

### 9.4 文件存储

**目录**: `cognee/infrastructure/files/`

```
files/
├── storage/
│   ├── storage.py              # Storage 协议接口
│   ├── LocalFileStorage.py     # 本地文件存储
│   ├── S3FileStorage.py        # AWS S3 存储
│   ├── StorageManager.py       # 存储管理器 (自动检测同步/异步)
│   └── get_file_storage.py     # 工厂函数 (自动检测本地/S3)
└── utils/
    ├── get_file_metadata.py    # 获取文件元数据 (content_hash)
    ├── get_file_content_hash.py # 计算内容哈希 (MD5)
    ├── guess_file_type.py      # 检测文件类型 (扩展名 + MIME)
    ├── extract_text_from_file.py # 提取文本内容
    └── is_text_content.py      # 判断是否为文本文件
```

```python
class Storage(Protocol):
    """存储后端协议。"""
    def store(self, file_path, data, overwrite=False) -> str: ...
    def open(self, file_path, mode="r"): ...
    def file_exists(self, file_path) -> bool: ...
    def remove(self, file_path): ...
    def list_files(self, dir_path, recursive=False) -> List[str]: ...
```

### 9.5 YAML 配置系统

**文件**: `cognee/infrastructure/config/yaml_config.py`

```python
def get_config_dir() -> Path:
    """获取配置目录。优先 COGNEE_CONFIG_DIR 环境变量，否则用 <项目>/config/"""

def load_yaml_config(file_path: str) -> dict:
    """加载单个 YAML 文件。"""

def get_module_config(module_name: str) -> dict:
    """按模块名获取配置。对应 config/<module_name>.yaml 文件。带缓存。"""

def get_nested_config_value(file_path, dotted_key, default=None):
    """获取嵌套配置值。如 get_nested_config_value(f, 'parsers.pdf.default')"""
```

**配置优先级**: 环境变量 > .env > YAML > 代码默认值

---

## 10. 共享层详解

**目录**: `cognee/shared/`

| 文件 | 说明 |
|------|------|
| `data_models.py` | `KnowledgeGraph`, `Node`, `Edge` — LLM 输出的图谱数据模型 |
| `logging_utils.py` | `get_logger()` — 统一日志工具 |
| `utils.py` | 通用工具函数 |
| `encode_uuid.py` | UUID 编码/序列化 |
| `exceptions/exceptions.py` | 异常基类 |
| `CodeGraphEntities.py` | 代码图谱实体模型 |
| `SourceCodeGraph.py` | 源代码图谱模型 |

```python
# data_models.py — LLM 的输出格式:

class Node(BaseModel):
    id: str
    name: str
    type: str
    description: str

class Edge(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship_name: str

class KnowledgeGraph(BaseModel):
    """LLM 输出的知识图谱。cognify 管道中使用。"""
    nodes: List[Node]
    edges: List[Edge]
```

---

## 11. 配置系统

### 11.1 环境变量 (.env)

| 类别 | 变量 | 说明 | 默认值 |
|------|------|------|--------|
| **LLM** | `LLM_API_KEY` | API 密钥 | - |
| | `LLM_MODEL` | 模型名 | `openai/gpt-5-mini` |
| | `LLM_PROVIDER` | 提供商 | `openai` |
| | `LLM_ENDPOINT` | 自定义端点 | - |
| **嵌入** | `EMBEDDING_MODEL` | 嵌入模型 | - |
| | `EMBEDDING_DIMENSIONS` | 向量维度 | `1024` |
| **数据库** | `DB_PROVIDER` | 关系DB | `sqlite` |
| | `GRAPH_DATABASE_PROVIDER` | 图DB | `kuzu` |
| | `VECTOR_DB_PROVIDER` | 向量DB | `lancedb` |
| **认证** | `REQUIRE_AUTHENTICATION` | 是否强制认证 | `False` |
| **日志** | `LOG_LEVEL` | 日志级别 | `INFO` |

### 11.2 YAML 配置 (config/)

```yaml
# config/graph_builder.yaml — 图谱构建配置
graph_builder:
  extraction:
    multi_round_validation: true       # 是否启用多轮验证
    confidence_threshold: 0.7          # 置信度阈值
  entity_resolution:
    enabled: true                      # 是否启用实体消歧
    fuzzy_threshold: 0.85              # 模糊匹配阈值
    embedding_threshold: 0.9           # 嵌入匹配阈值
```

### 11.3 配置优先级

```
1. 环境变量 (os.environ)    ← 最高优先级
2. .env 文件
3. YAML 配置文件
4. 代码中的默认值           ← 最低优先级
```

---

## 12. 异常处理体系

```
CogneeApiError (基类)
├── CogneeSystemError         (HTTP 500) — 系统内部错误
├── CogneeValidationError     (HTTP 422) — 输入验证失败
├── CogneeConfigurationError  (HTTP 500) — 配置错误
└── CogneeTransientError      (HTTP 503) — 临时性故障 (可重试)

API 特定异常:
├── InvalidConfigAttributeError   (400) — 无效配置属性
├── DocumentNotFoundError         (404) — 文档未找到
├── DatasetNotFoundError          (404) — 数据集未找到
└── DataNotFoundError             (404) — 数据未找到

CLI 异常:
├── CliCommandException           — 命令执行失败
└── CliCommandInnerException      — 内部异常包装
```

---

## 13. 关键设计模式

### 13.1 适配器模式 (Adapter Pattern)

所有外部服务都通过统一接口访问，可自由切换实现:

```
GraphDBInterface  →  KuzuAdapter / Neo4jAdapter / NeptuneAdapter
VectorDBInterface →  LanceDBAdapter / PGVectorAdapter / ChromaDBAdapter
Storage           →  LocalFileStorage / S3FileStorage
LoaderInterface   →  DoclingLoader / TextLoader / PyPdfLoader
EmbeddingEngine   →  LiteLLMEmbeddingEngine / FastembedEmbeddingEngine
```

### 13.2 管道模式 (Pipeline Pattern)

```python
# cognify 管道示例:
tasks = [
    Task(classify_documents),                    # 步骤 1
    Task(extract_chunks_from_documents, chunk_size=1024),  # 步骤 2
    Task(extract_graph_from_data),               # 步骤 3
    Task(validate_extracted_graph),              # 步骤 4 (条件注入)
    Task(resolve_entities),                      # 步骤 5 (条件注入)
    Task(summarize_text),                        # 步骤 6
    Task(add_data_points),                       # 步骤 7
]
await run_pipeline(tasks, data=documents, user=user)
```

### 13.3 DataPoint 继承体系

```
DataPoint (基类)
├── DocumentChunk       — 文本分块
├── Document            — 文档
├── NodeSet             — 节点集合
├── SummarizedContent   — 摘要内容
├── EntityNode          — 实体节点
└── ... (用户自定义)
```

所有 DataPoint 子类都可以:
- 存入图数据库 (自动生成节点和边)
- 存入向量数据库 (基于 `metadata.index_fields` 向量化)
- 版本追踪 (`version`, `created_at`, `updated_at`)

### 13.4 多租户隔离

```
请求 → 认证 (JWT/API Key) → 解析 User + Tenant
                                    ↓
                            ACL 权限检查
                                    ↓
                    切换到租户数据库上下文
                    (context_global_variables)
                                    ↓
                          操作隔离的数据
```

### 13.5 优雅降级

```python
# 加载器降级: DoclingLoader 失败 → 自动尝试 PyPdfLoader → Unstructured
# LLM 降级: 验证任务 LLM 调用失败 → 使用默认置信度 0.5
# 分块降级: LLMEnhancedChunker 失败 → 降级为基础 TextChunker
# 数据库降级: 健康检查显示 degraded 状态但服务仍可用
```

---

## 附录: 快速参考

### 常用入口点

| 场景 | 入口文件 | 关键函数 |
|------|---------|---------|
| 添加数据 | `cognee/__init__.py` | `cognee.add(data, dataset_name)` |
| 构建图谱 | `cognee/__init__.py` | `cognee.cognify(datasets)` |
| 搜索 | `cognee/__init__.py` | `cognee.search(query, query_type)` |
| 启动 API | `cognee/api/client.py` | `start_api_server(host, port)` |
| CLI | `cognee/cli/_cognee.py` | `main()` |
| 配置 LLM | `cognee/infrastructure/llm/config.py` | `get_llm_config()` |
| 获取图DB | `cognee/infrastructure/databases/graph/` | `get_graph_engine()` |
| 获取向量DB | `cognee/infrastructure/databases/vector/` | `get_vectordb_adapter()` |

### 新增功能的典型路径

1. **新增加载器**: 实现 `LoaderInterface` → 注册到 `LoaderEngine`
2. **新增搜索类型**: 实现 `BaseRetriever` → 注册到 `SearchType` → 更新 `select_search_type()`
3. **新增管道任务**: 在 `tasks/` 创建异步函数 → 在 `cognify.py` 中添加到任务列表
4. **新增数据库后端**: 实现对应接口 (`GraphDBInterface` / `VectorDBInterface`) → 注册到工厂函数

---

*文档版本: 2026-02-26 | 基于 1311+ 测试验证的代码分析*
