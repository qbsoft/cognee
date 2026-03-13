# 企业级 RAG 产品化重构设计文档

**日期**: 2026-03-14
**目标**: 将 cognee 从"精心调优的 demo"重构为可交付企业客户的生产级 RAG 产品
**精度要求**: 逐步稳定在 97%（RAGAS LLM-as-Judge）
**目标客户**: 中国企业，主要处理中文业务文档

---

## 问题总结

经第三方视角审视，当前系统存在三层根本性问题：

1. **分块层为中文文档基本不工作**：基于英文假设（空格分词、大写字母段落边界、句号后空格断句）
2. **知识图谱在大数据集下被废弃**：文档数 >5 时 `triplets = []`，图谱不参与检索
3. **蒸馏层（KD）承担了"修补分块质量差"的角色**：本应是增强层，实际成了主力，且自身不够健壮

当前 96.9% 的精度建立在 KD 绕过分块问题之上，一旦 KD 出问题没有兜底。

---

## 重构分四个 Phase

### Phase A: 分块层重构（地基）

**目标**: 中文文档能被正确分块，chunk 质量支撑 DC 回归检索主力

#### A1: 语言感知路由

在 `DefaultChunkEngine` 之上新增语言检测路由：
- 基于字符 Unicode 范围比例检测语言（CJK 字符占比 > 30% → 中文路径）
- 无需外部模型，纯规则判断
- 按段落级别检测，同一文档内可走不同路径

**新增文件**: `cognee/tasks/chunking/language_detector.py`

#### A2: 中文分块器

新建 `chinese_chunker.py`，核心逻辑：
- 使用 jieba 分词（非空格）
- 中文标点断句：`。！？；` + `\n\n`（连续空行为段落分隔符）
- **保留单换行符**（保护表格/列表结构），不做 `.replace("\n", "")`
- chunk 大小以 embedding model token 为单位（非字符数）
- 从 `chunking.yaml` 读取 `chunk_overlap` 并实际应用

**新增文件**: `cognee/tasks/chunking/chinese_chunker.py`
**修改文件**: `DefaultChunkEngine.py`, `TextChunker.py`, `chunk_by_sentence.py`

#### A3: 修复英文分块器

- 段落边界检测：不再依赖 `isupper()`，改为检测连续换行
- 句子分割正则：支持中文标点（`。！？`后不需要空格）
- 段落合并：不强制插入空格，根据语言决定连接符
- 修复 `while chunk_text[-1] != "."` 的 IndexError 风险

**修改文件**: `chunk_by_word.py`, `chunk_by_sentence.py`, `TextChunker.py`

#### A4: chunking.yaml 配置生效

- `chunk_overlap` 参数从 YAML 读取并传递到 chunker
- `chunk_size` 单位明确为 token（非字符）
- 新增 `language_detection: auto | zh | en` 配置项

**修改文件**: `chunking.yaml`, `get_default_tasks()` 中的配置读取

#### A5: 验证

- 用 SOW 文档重新 cognify，对比分块前后的 chunk 质量
- 跑 RAGAS 双场景验证，精度不回归（>=96.5%）
- 单元测试：中文分块、英文分块、混合文档分块

---

### Phase B: 图谱在大数据集下工作

**目标**: 图谱在 50+ 文档的数据集中仍参与检索，为 Agent 推理提供数据基础

#### B1: 图谱边绑定文档来源

`extract_graph` 阶段给每条边打 `source_document_id` 属性：
- Entity 节点：已有 `_metadata` 可扩展
- 边（Relationship）：新增 `source_document_id` 属性
- 跨文档的同名实体共享节点，但边分属不同文档

**修改文件**: `extract_graph_from_data.py`, `integrate_chunk_graphs()`

#### B2: Scoped Graph Search

检索时按文档作用域查询子图：
- 移除 `if large_dataset: triplets = []` 硬编码
- 新增 `_search_scoped_graph(query, doc_ids)` 方法
- Neo4j Cypher: `MATCH (a)-[r]->(b) WHERE r.source_document_id IN $doc_ids`
- 不再使用硬编码中文关系名 `部分属于`，改为英文或可配置

**修改文件**: `graph_completion_retriever.py`

#### B3: 跨文档实体链接

当查询涉及多文档时（no_scope 场景），利用共享实体节点做跨文档发现：
- 先在目标文档子图中找到相关实体
- 再沿共享实体的跨文档边扩展一跳
- 这是图谱相对于 KD/DC 的独特价值

**修改文件**: `graph_completion_retriever.py`

#### B4: 验证

- 52 文档数据集下验证图谱搜索返回相关三元组
- RAGAS 双场景验证精度不回归
- 对比 Graph 参与 vs 不参与的精度差异

---

### Phase C: 蒸馏健壮化 + 检索器重构

**目标**: KD 从主力降级为增强层，检索器在代码层面保证文档隔离

#### C1: 蒸馏状态管理

- 关系数据库新增 `distillation_status` 表：`(document_id, status, kd_count, created_at, updated_at)`
- status: `pending | in_progress | complete | failed`
- 前端展示每个文档的蒸馏状态，支持手动重跑失败文档
- 废弃"只看第一条 KD"的跳过逻辑

**新增文件**: 蒸馏状态模型、API 端点
**修改文件**: `distill_knowledge.py`, 前端蒸馏状态组件

#### C2: 蒸馏数据清理

- 重新蒸馏时，先按 `source_document_id` 删除旧 KD 条目，再写入新条目
- Qdrant 支持按 payload filter 删除：`delete(filter={"source_document_id": doc_id})`
- 避免新旧矛盾 KD 共存

**修改文件**: `distill_knowledge.py`

#### C3: 走 LLMGateway

- 蒸馏和画像不再直接建 `AsyncOpenAI` 客户端
- 统一通过 `get_llm_client(task_type="extraction")` 获取客户端
- 缓存(B2)、用户模型配置(Phase 22)、并发控制全部生效

**修改文件**: `distill_knowledge.py`

#### C4: QA 数量动态调整

- 根据文档 chunk 数量决定 QA 数量：
  - <=5 chunks: 5-10 个 QA
  - 6-20 chunks: 10-20 个 QA
  - >20 chunks: 20-30 个 QA
- 消除"强制至少30个"导致短文档幻觉的风险

**修改文件**: `distill_knowledge_system.txt`, `distill_knowledge.py`

#### C5: 检索器上下文预算

- 设定总 token 上限（默认 6000 tokens，可配置）
- 三层按比例分配：Graph 20% / KD 30% / DC 50%
- 超出预算时按相关性排序截断，而非字符串硬切

**修改文件**: `graph_completion_retriever.py`, `search.yaml`

#### C6: 代码层面文档隔离

- 文档隔离从 Prompt 指令（规则13）下沉到代码层面
- 在拼接 context 之前，代码过滤只保留目标文档的内容
- KD 使用 Qdrant payload filter（`source_document_id`），不再靠 `[来源: xxx]` 字符串匹配
- DC 使用 Qdrant payload filter 或 Neo4j 关系过滤
- `[来源: xxx]` 前缀保留作为 LLM 的辅助上下文信息，但不作为隔离机制
- 移除 `limit=3000` 暴力搜索

**修改文件**: `graph_completion_retriever.py`

#### C7: 验证

- RAGAS 双场景验证精度 >=97%
- 蒸馏失败/重跑场景测试
- 大数据集（52 文档）下检索延迟测试

---

### Phase D: 管道健壮性

**目标**: 消除生产环境中的崩溃和静默失败风险

#### D1: 错误隔离

- `extract_graph_from_data` 中 `asyncio.gather` 加 `return_exceptions=True`
- `summarize_text` 同上
- 单个 chunk 的 LLM 失败不连累整批，记录错误日志

**修改文件**: `extract_graph_from_data.py`, `summarize_text.py`

#### D2: 文件格式支持

- `EXTENSION_TO_DOCUMENT_CLASS` 添加：`.csv`, `.json`, `.xml`, `.md`, `.html`, `.xlsx`, `.pptx`
- 未知格式返回明确错误信息，不抛 KeyError
- 目录扫描过滤系统文件（`.DS_Store`, `.gitignore` 等）

**修改文件**: `classify_documents.py`, `resolve_data_directories.py`

#### D3: 配置层修复

- YAML 配置加读取缓存（进程级单例，首次读取后缓存）
- `distillation.yaml` 的 `context_char_limit` 从 YAML 读取，不用函数默认值
- `_get_document_name` 扩展名列表补全
- `similarity_threshold` 语义统一文档化（距离 vs 相似度）

**修改文件**: 各 `_get_xxx_config()` 函数, `distill_knowledge.py`, `graph_completion_retriever.py`

#### D4: 蒸馏状态前端展示

- 前端 Dashboard 增加蒸馏状态列：每个文档显示 ✅完成 / ⏳进行中 / ❌失败
- 失败文档支持点击"重新蒸馏"按钮
- cognify 整体进度条细化为：分块 → 图谱提取 → 蒸馏 → 向量索引

**修改文件**: 前端 DatasetsTab, 后端蒸馏 API

#### D5: 验证

- 上传 `.csv`, `.json`, `.xlsx` 等格式验证不崩溃
- 模拟 LLM 超时验证错误隔离
- 模拟蒸馏中断验证状态管理和重跑
- RAGAS 最终验证 >=97%

---

## 执行顺序与依赖关系

```
Phase A (分块) ──→ Phase B (图谱) ──→ Phase C (蒸馏+检索器) ──→ Phase D (健壮性)
   │                   │                     │                        │
   └─ RAGAS >=96.5%    └─ RAGAS >=96.5%      └─ RAGAS >=97%          └─ RAGAS >=97%
```

Phase A 是地基，必须先做。Phase B 和 C 有部分可以并行（图谱修复不依赖蒸馏重构），但建议串行以降低调试复杂度。Phase D 可以穿插在任何阶段。

## 不做的事情

- 不做英文优化（目标客户是中国企业）
- 不做跨文档实体合并（暂缓，待后续规划）
- 不换 embedding 模型（当前模型已验证可用）
- 不重写前端框架（在现有 Next.js 上迭代）

## 风险

1. **分块层重构后需要重新 cognify 所有文档**：分块变化导致 DC 向量全部失效，必须重新摄入
2. **图谱 schema 迁移**：给边加 `source_document_id` 需要迁移现有 Neo4j 数据
3. **KD 降级后精度可能临时下降**：DC 质量提升需要时间追赶，过渡期可能出现回归
4. **jieba 分词质量**：对专业术语（如"AWS PaaS"、"NC6.5"）分词可能不准，需要自定义词典
