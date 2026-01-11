# Data Quality Engine 设计文档

> 创建日期：2026-01-11
> 状态：待实施

## 一、项目背景

### 1.1 愿景
打造企业级 SaaS 数据平台，为大模型提供超精确的数据。

### 1.2 核心价值
- **知识准确性**：提取的实体、关系、事实要准确无误，减少幻觉
- **数据溯源**：每条数据都能追溯到原始来源，支持验证

### 1.3 目标用户
对外 SaaS 产品，服务通用型企业客户，不限定特定行业。

### 1.4 设计原则
- **全自动化**：系统自动完成质量检测、去重、验证，尽量减少人工干预
- **模块化**：独立质量引擎，与现有流程松耦合
- **可扩展**：检测器可插拔，支持自定义扩展

---

## 二、整体架构

### 2.1 模块定位
Data Quality Engine（DQE）作为独立模块，位于 `cognee/modules/quality/`，与现有的 `cognify`、`memify` 等模块平级。通过钩子（hooks）方式接入现有流程。

### 2.2 三阶段检测架构

```
┌─────────────────────────────────────────────────────────┐
│                 Data Quality Engine                      │
├─────────────┬─────────────────┬─────────────────────────┤
│  Stage 1    │    Stage 2      │      Stage 3            │
│  摄入检测    │    处理检测      │      存储检测            │
├─────────────┼─────────────────┼─────────────────────────┤
│ • 格式验证   │ • 实体去重       │ • 图谱一致性检查         │
│ • 编码检测   │ • 关系验证       │ • 溯源完整性验证         │
│ • 重复检测   │ • 置信度评分     │ • 跨文档冲突检测         │
│ • 元数据校验 │ • 事实核查       │ • 质量报告生成           │
└─────────────┴─────────────────┴─────────────────────────┘
```

### 2.3 核心原则
- **松耦合**：通过事件/钩子接入，不侵入现有代码
- **可配置**：每个检测项可独立开关
- **全自动**：检测 → 评分 → 过滤/修复，无需人工

---

## 三、模块结构

```
cognee/modules/quality/
├── engine.py              # 质量引擎主入口
├── config.py              # 质量配置管理
├── models/
│   ├── QualityScore.py    # 质量评分模型
│   ├── QualityIssue.py    # 质量问题记录
│   └── QualityReport.py   # 质量报告模型
├── detectors/             # 检测器（可插拔）
│   ├── base.py            # 检测器基类
│   ├── duplicate.py       # 重复检测
│   ├── entity_linker.py   # 实体链接与去重
│   ├── relation_validator.py  # 关系验证
│   ├── fact_checker.py    # 事实核查
│   └── consistency.py     # 一致性检查
├── scorers/               # 评分器
│   ├── confidence.py      # 置信度评分
│   └── provenance.py      # 溯源完整性评分
├── fixers/                # 自动修复器
│   ├── deduplicator.py    # 去重修复
│   └── normalizer.py      # 标准化修复
└── api/                   # 对外 API
    └── quality_router.py  # REST 接口
```

### 3.1 关键设计点
- **检测器可插拔**：基于基类实现，支持自定义扩展
- **评分标准化**：所有评分归一化到 0-1 范围
- **问题可追溯**：每个 QualityIssue 记录问题类型、位置、建议

---

## 四、数据流与集成

### 4.1 与现有流程的集成

```
用户调用 add() ──→ 摄入检测 ──→ 数据存储
                      │
                      ▼
                 QualityIssue (如有问题)

用户调用 cognify() ──→ 分块 ──→ 实体提取 ──→ 处理检测 ──→ 图谱构建
                                              │
                                              ▼
                                    置信度评分 + 实体去重
                                              │
                                              ▼
                                    低质量数据自动过滤

后台任务 ──→ 存储检测 ──→ 图谱一致性检查 ──→ 质量报告
```

### 4.2 集成机制 - 事件钩子

```python
# 在 cognify 流程中注册钩子
@quality_hook("after_entity_extraction")
async def check_entity_quality(entities: list[Entity]) -> list[Entity]:
    scored = await quality_engine.score_entities(entities)
    return [e for e in scored if e.confidence >= threshold]
```

### 4.3 数据存储扩展
- `quality_scores` 表：存储每个数据项的质量评分
- `quality_issues` 表：记录检测到的问题
- `provenance` 表：存储完整溯源链（原文位置 → 分块 → 实体 → 关系）

---

## 五、置信度评分系统

### 5.1 多维度评分模型

```
总置信度 = w1×提取置信度 + w2×验证置信度 + w3×一致性置信度 + w4×溯源置信度
```

| 维度 | 评分来源 | 权重(默认) |
|------|---------|-----------|
| 提取置信度 | LLM 返回的 logprobs / 自评分 | 0.3 |
| 验证置信度 | 实体链接成功率、关系合理性 | 0.3 |
| 一致性置信度 | 跨文档事实是否冲突 | 0.2 |
| 溯源置信度 | 原文支撑强度、引用完整性 | 0.2 |

### 5.2 实体置信度计算

```python
class EntityConfidenceScorer:
    async def score(self, entity: Entity, context: ChunkContext) -> float:
        scores = {
            "extraction": await self._llm_confidence(entity),      # LLM 提取时的确定性
            "validation": await self._entity_link_score(entity),   # 能否链接到已知实体
            "consistency": await self._cross_doc_check(entity),    # 跨文档是否一致
            "provenance": self._source_support_score(entity, context)  # 原文支撑度
        }
        return weighted_average(scores, self.weights)
```

### 5.3 自动过滤策略
- 置信度 < 0.3：丢弃，记录到 quality_issues
- 置信度 0.3-0.6：标记为"待确认"，可选人工复核
- 置信度 > 0.6：正常入库

---

## 六、数据溯源系统

### 6.1 溯源链模型

```
原始文件 → 文档块 → 实体/关系 → 知识图谱节点
   │          │          │              │
   ▼          ▼          ▼              ▼
DataSource  Chunk    Extraction    GraphNode
   │          │          │              │
   └──────────┴──────────┴──────────────┘
                    │
                    ▼
              ProvenanceChain (溯源链)
```

### 6.2 溯源数据模型

```python
class ProvenanceRecord(BaseModel):
    id: UUID
    target_id: UUID              # 被溯源对象（实体/关系/节点）
    target_type: str             # "entity" | "relation" | "node"

    # 原始来源
    source_file: str             # 原始文件路径
    source_hash: str             # 文件内容哈希

    # 精确位置
    chunk_id: UUID               # 所属文档块
    start_line: int              # 起始行号
    end_line: int                # 结束行号
    start_char: int              # 起始字符
    end_char: int                # 结束字符
    original_text: str           # 原文片段（证据）

    # 提取上下文
    extraction_model: str        # 使用的 LLM 模型
    extraction_prompt: str       # 使用的提示词版本
    extracted_at: datetime       # 提取时间
```

### 6.3 溯源查询
支持通过 API 查询任意实体的完整溯源链，包含原文证据。

---

## 七、实体去重与链接

### 7.1 问题场景
- 同一实体多种表述："OpenAI" vs "Open AI" vs "openai"
- 别名和简称："张三" vs "张总" vs "老张"
- 跨文档重复：不同文件提取出相同实体

### 7.2 三层去重策略

```
┌─────────────────────────────────────────────┐
│ Layer 1: 规范化匹配                          │
│ • 大小写统一、空格处理、标点清理              │
│ • 快速精确匹配，O(1) 复杂度                  │
├─────────────────────────────────────────────┤
│ Layer 2: 相似度匹配                          │
│ • 编辑距离、Jaccard 相似度                   │
│ • 阈值可配置（默认 0.85）                    │
├─────────────────────────────────────────────┤
│ Layer 3: 语义匹配                            │
│ • 向量嵌入相似度                             │
│ • LLM 辅助判断（高置信度场景）               │
└─────────────────────────────────────────────┘
```

### 7.3 实体合并逻辑

```python
class EntityLinker:
    async def link(self, new_entity: Entity) -> Entity:
        # 1. 查找候选匹配
        candidates = await self._find_candidates(new_entity)

        # 2. 评分排序
        scored = [(c, await self._similarity(new_entity, c)) for c in candidates]
        best_match, score = max(scored, key=lambda x: x[1])

        # 3. 决策
        if score > 0.9:
            return await self._merge(new_entity, best_match)  # 合并
        elif score > 0.7:
            return await self._link_as_alias(new_entity, best_match)  # 建立别名关系
        else:
            return new_entity  # 作为新实体
```

### 7.4 溯源保留
合并后的实体保留所有原始来源，支持追溯到每个提及。

---

## 八、质量 API 与报告

### 8.1 REST API 设计

```
# 质量检测
POST /api/v1/quality/check/{dataset_id}    # 对数据集执行质量检测
GET  /api/v1/quality/score/{dataset_id}    # 获取数据集质量评分

# 溯源查询
GET  /api/v1/quality/provenance/{entity_id}  # 获取实体溯源链
GET  /api/v1/quality/evidence/{node_id}      # 获取图谱节点的原文证据

# 问题管理
GET  /api/v1/quality/issues/{dataset_id}     # 获取质量问题列表
POST /api/v1/quality/issues/{issue_id}/resolve  # 标记问题已解决

# 报告
GET  /api/v1/quality/report/{dataset_id}     # 获取质量报告
```

### 8.2 质量报告模型

```python
class QualityReport(BaseModel):
    dataset_id: UUID
    generated_at: datetime

    # 总体评分
    overall_score: float          # 0-1 综合质量分

    # 分项统计
    total_entities: int
    deduplicated_count: int       # 去重数量
    low_confidence_count: int     # 低置信度数量

    # 问题分布
    issues_by_type: dict[str, int]  # {"duplicate": 23, "low_confidence": 45, ...}

    # 溯源完整性
    provenance_coverage: float    # 有完整溯源的数据占比

    # 建议
    recommendations: list[str]    # 改进建议
```

### 8.3 自动报告触发
每次 `cognify()` 完成后自动生成报告，存储并可通过 API 查询。

---

## 九、错误处理

### 9.1 异常定义

```python
class QualityEngineError(Exception):
    """质量引擎基础异常"""
    pass

class DetectionError(QualityEngineError):
    """检测过程异常 - 不阻塞主流程，记录日志继续"""
    pass

class CriticalQualityError(QualityEngineError):
    """严重质量问题 - 阻塞入库，要求处理"""
    pass
```

### 9.2 容错原则
- 质量检测失败 → 记录警告，数据正常流转，标记为"未检测"
- 评分计算失败 → 使用默认评分（0.5），记录异常
- 去重服务不可用 → 跳过去重，后台任务补偿

---

## 十、测试策略

| 测试类型 | 覆盖范围 | 位置 |
|---------|---------|------|
| 单元测试 | 各检测器、评分器独立逻辑 | `tests/unit/quality/` |
| 集成测试 | 质量引擎与 cognify 流程集成 | `tests/integration/quality/` |
| 质量基准测试 | 使用标注数据集验证准确率 | `tests/benchmarks/quality/` |
| 性能测试 | 大数据量下的处理性能 | `tests/performance/quality/` |

### 10.1 质量基准数据集
- 准备人工标注的实体去重测试集
- 准备事实核查的正确/错误样本
- 定期回归测试，确保质量能力不退化

---

## 十一、实施路线图

### Phase 1: 基础框架
- 质量引擎核心架构
- 置信度评分系统
- 基础 API 接口
- 数据库模型扩展

### Phase 2: 检测能力
- 实体去重（三层策略）
- 关系验证器
- 一致性检查器
- 质量报告生成

### Phase 3: 溯源系统
- 溯源链模型
- 原文证据存储
- 溯源查询 API
- 与现有流程集成

### Phase 4: 优化完善
- 性能优化
- 基准测试
- 文档完善
- 监控集成

---

## 十二、总结

| 项目 | 内容 |
|-----|------|
| 目标 | 企业级 SaaS 数据平台，提供超精确数据 |
| 核心能力 | 知识准确性 + 数据溯源 |
| 方案 | 独立质量引擎（模块化） |
| 模块位置 | `cognee/modules/quality/` |
| 关键功能 | 置信度评分、实体去重、溯源链、质量报告 |
| 集成方式 | 事件钩子，松耦合 |
