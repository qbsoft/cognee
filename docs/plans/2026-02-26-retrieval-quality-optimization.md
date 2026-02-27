# 检索质量与图谱质量优化方案

**日期**: 2026-02-26
**目标**: 解决检索数据质量和知识图谱质量低的问题，达到高精准度检索要求
**适用场景**: 中文业务文档（合同、报告、通知、会议纪要等）

---

## 问题诊断

### 致命级缺陷（3 个）

| 编号 | 问题 | 影响 |
|------|------|------|
| F1 | Temperature 参数未实际传递给 LLM | 实体提取不稳定、产生幻觉 |
| F2 | BGE-Reranker 未接入生产管道 | 检索结果未经重排序 |
| F3 | Entity 向量索引只索引 name 字段 | 语义搜索无法利用描述信息 |

### 严重级缺陷（5 个）

| 编号 | 问题 | 影响 |
|------|------|------|
| S1 | 默认 chunk_size=8191 tokens 过大 | LLM 提取实体遗漏率高 |
| S2 | 提取 Prompt 不适合中文业务文档 | 实体类型和关系名不规范 |
| S3 | HYBRID_SEARCH 缺少 get_context() | 走 unknown_tool 路径，context 为空 |
| S4 | 中文实体消歧效果差 | "张明总经理" vs "张总" 无法合并 |
| S5 | similarity_threshold=0.5 过宽 + 全量扫描 | 大量噪声 + 性能低 |

### 改进级问题（4 个）

| 编号 | 问题 | 影响 |
|------|------|------|
| I1 | 回答 Prompt 过于简单 | 回答质量低 |
| I2 | search.yaml 配置与代码脱节 | 配置系统无效 |
| I3 | Embedding 模型对中文优化不足 | 建议评估替换 |
| I4 | 调试残留代码 | print 输出污染 |

---

## 已实施的修复

### A1. 修复 Temperature 参数传递 (F1) — ✅ 已完成

**修改文件** (6 个 adapter):
- `cognee/infrastructure/llm/structured_output_framework/litellm_instructor/llm/openai/adapter.py`
- `cognee/infrastructure/llm/structured_output_framework/litellm_instructor/llm/anthropic/adapter.py`
- `cognee/infrastructure/llm/structured_output_framework/litellm_instructor/llm/gemini/adapter.py`
- `cognee/infrastructure/llm/structured_output_framework/litellm_instructor/llm/mistral/adapter.py`
- `cognee/infrastructure/llm/structured_output_framework/litellm_instructor/llm/ollama/adapter.py`
- `cognee/infrastructure/llm/structured_output_framework/litellm_instructor/llm/generic_llm_api/adapter.py`

**改动**: 在每个 adapter 的 `acreate_structured_output()` 和 `create_structured_output()` 的 LLM 调用中添加 `temperature=get_llm_config().llm_temperature` 参数。

**效果**: LLM 提取实体时使用 temperature=0.0（确定性输出），消除随机性和幻觉。

---

### B2. 扩展 Entity 向量索引字段 (F3) — ✅ 已完成

**修改文件**:
- `cognee/modules/engine/models/Entity.py`
- `cognee/modules/engine/models/EntityType.py`

**改动**: `metadata.index_fields` 从 `["name"]` 扩展为 `["name", "description"]`

**效果**: 语义搜索时不仅匹配实体名称，也匹配描述信息。例如搜索 "负责审计工作的人" 可以通过 description 字段匹配到相关实体。

**注意**: 修改后需要**重新摄入数据**以重建向量索引。

---

### A2. 优化中文分块策略 (S1) — ✅ 已完成

**修改文件**:
- `cognee/api/v1/cognify/cognify.py` — `get_default_tasks()` 从 YAML 读取 chunk_size
- `config/chunking.yaml` — 新建配置文件

**改动**:
- 默认 chunk_size 从 8191 tokens 降为 **512 tokens**（约 300-400 中文字）
- chunk_overlap 设为 50
- 通过 YAML 配置可灵活调整

**效果**: 更小的 chunk 让 LLM 能更精确地提取每段文本中的实体和关系。

---

### A3. 创建中文业务文档专用提取 Prompt (S2) — ✅ 已完成

**新建文件**: `cognee/infrastructure/llm/prompts/generate_graph_prompt_chinese_business.txt`

**内容**: 针对中文商业文档的专用知识图谱提取 Prompt，包含：
- 9 种标准化中文实体类型（人物、组织、文档、金额、日期、地点、条款、产品、事件）
- 23 种中文关系类型（签署、审批、负责、隶属于等）
- 7 条提取规则（完整名称、共指消解、日期标准化、金额标准化等）

**使用方式**: 在 `.env` 中设置：
```
GRAPH_PROMPT_PATH=generate_graph_prompt_chinese_business.txt
```

---

### B3. 修复 HYBRID_SEARCH 返回路径 (S3) — ✅ 已完成

**修改文件**:
- `cognee/modules/search/retrievers/HybridRetriever.py` — 添加 `get_context()` 方法
- `cognee/modules/search/methods/get_search_type_tools.py` — 注册 `get_context` 到工具列表

**效果**: HYBRID_SEARCH 不再走 `unknown_tool` 路径，可正确返回 graphs 和 context 数据。

---

### A4. 增强中文实体消歧 (S4) — ✅ 已完成

**修改文件**:
- `cognee/modules/graph/utils/entity_normalization.py`
- `cognee/tasks/entity_resolution/resolve_entities.py`

**新增功能**:
- `CHINESE_TITLE_SUFFIXES` — 46 个中文职务后缀列表
- `extract_chinese_core_name()` — 从 "张明总经理" 提取核心人名 "张明"
- 全角字符自动转半角
- 中文人名核心匹配：去除职务后缀后相同 → 相似度 0.95
- 单字姓氏前缀匹配："张总" vs "张明" → 相似度 0.85

**效果**: "张明总经理"、"张总"、"张明" 将被正确识别为同一实体。

---

### B4. 收紧搜索阈值 + 限制全量扫描 (S5) — ✅ 已完成

**修改文件**: `cognee/modules/retrieval/utils/brute_force_triplet_search.py`

**改动**:
- `similarity_threshold` 默认值从 0.5 提高到 **0.7**
- 向量搜索 `limit` 从 `None`（全量扫描）改为 `max(top_k * 10, 50)`

**效果**: 过滤掉更多不相关三元组，搜索性能提升。

---

### B1. 接入 BGE-Reranker 到检索管道 (F2) — ✅ 已完成

**修改文件**: `cognee/modules/retrieval/utils/brute_force_triplet_search.py`

**改动**: 在质量评分和多样性过滤之后、最终截断之前插入 reranking 步骤：
1. 从 `search.yaml` 读取 `reranking.enabled` 配置
2. 将 Edge 对象转换为 `{text, edge}` 字典格式
3. 调用 `rerank()` 进行交叉编码器精排
4. 包含 ImportError 和通用异常的 graceful degradation

**依赖**: 需要安装 FlagEmbedding: `pip install FlagEmbedding`

---

### B5. 优化回答生成 Prompt (I1) — ✅ 已完成

**修改文件**: `cognee/infrastructure/llm/prompts/answer_simple_question.txt`

**改动**: 从一句话的英文 prompt 替换为专业的中文回答 prompt，包含：
- 6 条回答规则（禁止外部知识、处理矛盾信息、标注来源等）
- 回答格式要求（直接答案 + 关键细节 + 信息出处）

---

### B6. 连通 search.yaml 配置到代码 (I2) — ✅ 已完成

**修改文件**: `cognee/modules/search/methods/get_search_type_tools.py`

**改动**: HYBRID_SEARCH 的 `HybridRetriever` 初始化现在从 `search.yaml` 读取：
- 各检索策略权重 (vector/graph/lexical)
- hybrid top_k
- 取代原来的硬编码默认值

---

### I4. 清理调试残留代码 — ✅ 已完成

**修改文件**: `cognee/modules/retrieval/utils/brute_force_triplet_search.py`

**改动**: 移除 `format_triplets()` 中的 `print("\n\n\n")` 调试代码。

---

## 开发者使用指南

### 启用中文业务 Prompt

在 `.env` 文件中添加:
```
GRAPH_PROMPT_PATH=generate_graph_prompt_chinese_business.txt
```

### 启用 BGE-Reranker

1. 安装依赖: `pip install FlagEmbedding`
2. `config/search.yaml` 中 `reranking.enabled` 已设为 `true`
3. 首次运行会自动下载 `BAAI/bge-reranker-v2-m3` 模型

### 调整分块大小

编辑 `config/chunking.yaml`:
```yaml
chunking:
  chunk_size: 512      # 调大=更多上下文，调小=更精确提取
  chunk_overlap: 50    # 块间重叠字符数
```

### 调整搜索权重

编辑 `config/search.yaml`:
```yaml
search:
  hybrid:
    strategies:
      vector:
        weight: 0.4    # 向量检索权重
      graph:
        weight: 0.3    # 图谱检索权重
      lexical:
        weight: 0.3    # 词法检索权重
```

### 重新摄入数据

修改 Entity 索引字段后，需要重新处理数据:
```python
import cognee
await cognee.prune.prune_data()
await cognee.prune.prune_system(metadata=True)
await cognee.add("your_data.pdf")
await cognee.cognify()
```

---

## 修改文件清单

| 文件 | 修改类型 | 对应任务 |
|------|----------|----------|
| `openai/adapter.py` | 修改 | A1 |
| `anthropic/adapter.py` | 修改 | A1 |
| `gemini/adapter.py` | 修改 | A1 |
| `mistral/adapter.py` | 修改 | A1 |
| `ollama/adapter.py` | 修改 | A1 |
| `generic_llm_api/adapter.py` | 修改 | A1 |
| `models/Entity.py` | 修改 | B2 |
| `models/EntityType.py` | 修改 | B2 |
| `cognify.py` | 修改 | A2 |
| `config/chunking.yaml` | 新建 | A2 |
| `generate_graph_prompt_chinese_business.txt` | 新建 | A3 |
| `HybridRetriever.py` | 修改 | B3 |
| `get_search_type_tools.py` | 修改 | B3, B6 |
| `entity_normalization.py` | 修改 | A4 |
| `resolve_entities.py` | 修改 | A4 |
| `brute_force_triplet_search.py` | 修改 | B1, B4, I4 |
| `answer_simple_question.txt` | 修改 | B5 |

**共计**: 15 个文件修改 + 2 个新建文件
