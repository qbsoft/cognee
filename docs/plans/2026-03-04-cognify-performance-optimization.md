# Cognify 管道性能优化设计

**日期**: 2026-03-04
**目标**: 多文件上传场景下的 cognify 处理效率优化，同时保证检索精度 >= 95%
**原则**: 一切优化以检索质量保证在 95% 以上的精准度为唯一原则

## 1. 问题分析

### 当前性能瓶颈

单文件(20 chunks) cognify 耗时约 30-65 秒，主要瓶颈：

| 任务 | LLM调用 | 耗时 | 占比 |
|------|---------|------|------|
| extract_graph_from_data | N次(每chunk 1次) | 20-40s | ~50% |
| distill_knowledge | 1-3次 | 3-10s | ~15% |
| summarize_text | N次(并行) | 5-15s | ~20% |
| add_data_points | 0(数据库) | 2-5s | ~10% |

### 多文件场景问题

- 10个文件(共200 chunks) 预计耗时 5-10 分钟
- LLM 无并发控制: `asyncio.gather` 对所有 chunk 同时发 LLM 请求，可能触发 API 限流
- 任务串行: extract_graph 和 summarize_text 可以并行但现在是串行
- 无中间进度: 用户从 "pending" 等到 "completed"，中间看不到进度

### 行业对标

| 平台 | 策略 | 效果 |
|------|------|------|
| LightRAG | 多层并发控制(LLM=4, embed=16, 文件=2-10) | token 消耗降 6100x |
| GraphRAG | LazyGraphRAG: 延迟 LLM 到查询时 | 成本降 77% |
| E2GraphRAG | SpaCy 替代 LLM 做实体提取 | 提速 10x |
| LlamaIndex | num_workers 并行 + schema-based 提取 | 250篇/7分钟 |
| NanoGraphRAG | 双模型: 小模型提取, 大模型回答 | 成本降 10x |

## 2. 优化方案

### Phase A: 安全优化 (无精度影响, 本次实施)

#### A1. LLM 并发信号量控制

**改动文件**: `extract_graph_from_data.py`, `summarize_text.py`
**策略**: 添加 `asyncio.Semaphore` 限制并发 LLM 调用

```python
# 从 YAML 配置读取
semaphore = asyncio.Semaphore(max_concurrent_llm_calls)  # 默认 8

async def limited_extract(chunk):
    async with semaphore:
        return await extract_content_graph(chunk.text, graph_model)

chunk_graphs = await asyncio.gather(
    *[limited_extract(chunk) for chunk in data_chunks]
)
```

**预期效果**: 避免 API 限流, 更稳定的处理速度
**精度影响**: 无 (相同的 LLM 调用, 只是控制并发)

#### A2. Cognify 中间进度追踪

**改动文件**: `run_tasks_data_item.py`, `update_pipeline_status.py`
**策略**: 在每个 task 完成后更新 pipeline_status

```
extract_graph 开始 → graph_indexing: "in_progress" (30%)
extract_graph 完成 → graph_indexing: "in_progress" (60%)
add_data_points 完成 → graph_indexing: "completed" (100%)
```

**预期效果**: 用户可看到实时进度
**精度影响**: 无 (仅改变状态上报逻辑)

#### A3. YAML 并发配置

**新建文件**: `config/concurrency.yaml`
**策略**: 将并发参数外部化

```yaml
concurrency:
  # LLM 并发: 同时最多几个 LLM 请求
  max_concurrent_llm_calls: 8
  # 文档并发: 同一批次内最多处理几个文档
  data_per_batch: 20
  # 知识蒸馏并发 (已有, 当前=3)
  distillation_concurrency: 3
```

### Phase B: 高收益优化 (需验证精度, 后续迭代)

#### B1. 双模型策略

- 图谱提取/摘要: 用 Qwen-turbo (速度快 3-5x, 成本低 10x)
- 回答生成: 继续用 Qwen-plus/max (保证质量)
- **需要**: RAGAS 评测验证精度不降

#### B2. LLM 结果缓存

- 对相同文本内容的提取结果做缓存 (content_hash -> result)
- 重新 cognify 时跳过已处理 chunk
- **预计**: 重复数据场景提速 3-5x

#### B3. 任务级并行 (extract_graph || summarize_text)

- 图谱提取和文本摘要无依赖, 可以并行
- **需要**: 修改 pipeline 执行框架

### Phase C: 架构级优化 (长期规划)

#### C1. NLP Fast Mode (可选模式)

- 用 SpaCy/jieba 做实体提取, 共现关系替代 LLM 关系提取
- LLM 仅用于 embedding + 回答
- **预计**: 提速 10-50x, 但精度可能降 5-15%
- **定位**: 作为可选模式, 适合大批量低精度场景

#### C2. LazyGraphRAG 模式 (可选模式)

- 索引阶段只做分块 + 向量化 (无 LLM)
- 查询时按需提取知识图谱
- **适合**: 快速入库、探索式查询场景

## 3. 实施计划

| Phase | 内容 | 预计提速 | 精度影响 | 优先级 |
|-------|------|---------|---------|--------|
| A1 | LLM 并发信号量 | 更稳定 | 无 | 本次 |
| A2 | 中间进度追踪 | 体验改善 | 无 | 本次 |
| A3 | YAML 并发配置 | 可调节 | 无 | 本次 |
| B1 | 双模型策略 | 3-5x | 需验证 | 下次 |
| B2 | LLM 缓存 | 1.5-3x | 无 | 下次 |
| B3 | 任务并行 | 1.3-1.5x | 无 | 下次 |
| C1 | NLP Fast Mode | 10-50x | 降5-15% | 长期 |
| C2 | LazyGraphRAG | 100x+ | 按需加载 | 长期 |
