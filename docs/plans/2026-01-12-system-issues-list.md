# Cognee 系统问题清单

> 生成日期：2026-01-12
> 分析版本：v0.4.1
> 源代码文件数：771 个 Python 文件
> 测试文件数：56 个测试文件

---

## 一、Critical（严重）

### 1.1 硬编码密码
| 文件 | 行号 | 问题 | 修复建议 |
|-----|------|------|---------|
| `cognee/api/v1/permissions/routers/get_permissions_router.py` | 335 | 硬编码管理员密码 `admin_password = "12345678"` | 从环境变量或配置文件读取，生产环境必须修改 |

### 1.2 宽泛异常捕获（吞掉错误）
以下位置使用 `except Exception:` 或 `except:` 后直接 `pass`，可能隐藏严重错误：

| 文件 | 行号 | 问题 |
|-----|------|------|
| `cognee/cli/_cognee.py` | 217-243 | 多处 `except Exception: pass`，CLI 错误被完全忽略 |
| `cognee/api/v1/sync/sync.py` | 554 | 同步操作异常被忽略 |
| `cognee/api/v1/ui/ui.py` | 51, 72, 397 | UI 相关异常被忽略 |
| `cognee/tasks/web_scraper/default_url_crawler.py` | 115, 266 | 爬虫错误被忽略 |

**修复建议**：至少记录日志，关键路径应该抛出或返回错误状态。

---

## 二、High（高）

### 2.1 待完成功能（TODO）
共发现 **24 个 TODO** 标记，以下为高优先级：

| 文件 | 行号 | 内容 | 影响 |
|-----|------|------|------|
| `cognee/api/v1/cognify/cognify.py` | 244 | `get_default_tasks` 方法需要重构 | 代码组织不清晰 |
| `cognee/api/v1/sync/sync.py` | 884, 888 | 缺少重试机制 | 同步可能因临时失败而中断 |
| `cognee/modules/pipelines/layers/pipeline_execution_mode.py` | 76 | 需要改为 async gather | 性能瓶颈 |
| `cognee/modules/users/permissions/methods/authorized_give_permission_on_datasets.py` | 33 | 租户间权限分享策略未定 | 潜在安全风险 |

### 2.2 废弃代码未清理
| 文件 | 行号 | 问题 |
|-----|------|------|
| `cognee/infrastructure/llm/tokenizer/Gemini/adapter.py` | 6 | 标记为 DEPRECATED 但仍在代码库中 |
| `cognee/tasks/chunk_naive_llm_classifier/chunk_naive_llm_classifier.py` | 1 | 标记 "PROPOSED TO BE DEPRECATED" |
| `cognee/tasks/storage/index_graph_edges.py` | 53 | 包含废弃警告但未移除旧逻辑 |

**修复建议**：清理废弃代码或完成迁移。

### 2.3 测试覆盖不足
**现有模块**：21 个
**有单元测试的模块**：8 个（38%）

缺少测试的关键模块：
- `cognee/modules/chunking/` - 分块逻辑无测试
- `cognee/modules/cognify/` - 核心认知流程无测试
- `cognee/modules/memify/` - 记忆化流程无测试
- `cognee/modules/ingestion/` - 数据摄入无测试
- `cognee/modules/search/` - 搜索逻辑测试不足
- `cognee/modules/settings/` - 配置管理无测试
- `cognee/modules/storage/` - 存储层无测试
- `cognee/modules/sync/` - 同步功能无测试
- `cognee/modules/engine/` - 引擎核心无测试
- `cognee/modules/cloud/` - 云功能无测试
- `cognee/modules/metrics/` - 指标收集无测试
- `cognee/modules/observability/` - 可观测性无测试

**修复建议**：优先为核心模块（cognify、search、ingestion）添加测试。

### 2.4 调试代码残留
发现 **229 处 print()** 语句分布在 30 个文件中，部分在生产代码中：

| 文件 | print 数量 |
|-----|-----------|
| `cognee/tests/test_delete_by_id.py` | 46 |
| `cognee/tests/test_neptune_analytics_graph.py` | 51 |
| `cognee/api/v1/ui/ui.py` | 13 |
| `cognee/tests/test_permissions.py` | 9 |

**修复建议**：生产代码使用 structlog，测试代码使用 pytest 的 caplog。

---

## 三、Medium（中）

### 3.1 依赖版本问题
| 依赖 | 当前版本 | 问题 |
|-----|---------|------|
| `lancedb` | 0.24.0-0.25.3 | 被固定版本以绕过 lance-namespace 0.2.0 bug |
| `lance-namespace` | <=0.0.21 | 临时修复，需要跟踪上游修复 |
| `kuzu` | ==0.11.3 | 精确版本锁定，可能错过安全更新 |
| `pypika` | ==0.48.9 | chromadb 依赖精确锁定 |
| `pytest-asyncio` | <0.22 | 版本较旧，限制了异步测试特性 |

**修复建议**：定期检查依赖更新，移除临时修复。

### 3.2 代码质量问题
#### 3.2.1 空实现（Abstract methods with pass）
以下接口定义了但未强制实现：

| 文件 | 类/方法 |
|-----|---------|
| `cognee/infrastructure/loaders/LoaderInterface.py` | 5 个抽象方法 |
| `cognee/infrastructure/files/storage/storage.py` | 3 个抽象方法 |
| `cognee/infrastructure/entities/BaseEntityExtractor.py` | 1 个抽象方法 |
| `cognee/eval_framework/benchmark_adapters/base_benchmark_adapter.py` | 1 个抽象方法 |

**说明**：这些是正常的抽象基类定义，但应确保所有子类都正确实现。

#### 3.2.2 可视化模块异常处理不当
| 文件 | 行号 | 问题 |
|-----|------|------|
| `cognee/modules/visualization/cognee_network_visualization.py` | 43, 48 | 异常后直接 `pass`，用户看不到错误 |

### 3.3 注释质量
| 文件 | 行号 | 问题 |
|-----|------|------|
| `cognee/modules/visualization/cognee_network_visualization.py` | 41 | TODO 注释格式不规范 `:TODO:` |
| `cognee/modules/retrieval/utils/completion.py` | 21 | TODO 未指定负责人或时间 |
| `cognee/tests/unit/entity_extraction/regex_entity_extraction_test.py` | 86 | 指名 Lazar 修复但未跟踪 |

### 3.4 配置管理
- 部分配置硬编码在代码中而非配置文件
- 环境变量命名不一致
- 缺少配置验证机制

---

## 四、Low（低）

### 4.1 代码风格
- Ruff 配置忽略了 F401（未使用导入），可能有冗余 import
- 部分文件超过 500 行，建议拆分
- 部分函数超过 50 行，建议重构

### 4.2 文档问题
- `cognee/modules/` 下多数模块缺少模块级 docstring
- API 端点缺少完整的 OpenAPI 文档
- 配置选项缺少说明文档

### 4.3 日志不一致
- 部分模块使用 `structlog`
- 部分模块使用 `print()`
- 部分模块使用 `logging`
- 缺少统一的日志规范

### 4.4 类型标注不完整
- 部分函数参数缺少类型标注
- 部分返回值缺少类型标注
- 建议开启 mypy strict 模式

---

## 五、安全相关

### 5.1 已确认问题
| 严重程度 | 问题 | 位置 |
|---------|------|------|
| Critical | 硬编码密码 | `get_permissions_router.py:335` |
| Medium | 测试代码中的明文密码 | `test_graph_visualization_permissions.py` |

### 5.2 需要审查
- SQL 查询是否全部使用参数化
- 文件上传是否有大小和类型限制
- API 端点是否都有权限检查
- 敏感日志是否被脱敏

---

## 六、性能相关

### 6.1 已识别瓶颈
| 位置 | 问题 | 影响 |
|-----|------|------|
| `pipeline_execution_mode.py:76` | 使用 for 循环而非 async gather | 并行处理受限 |
| `sync.py:884-888` | 缺少重试机制 | 临时失败导致完全失败 |
| 实体提取 | 每个分块独立调用 LLM | 大数据集处理慢 |

### 6.2 建议优化
- 实现 LLM 调用批处理
- 添加结果缓存机制
- 优化数据库查询（添加索引）
- 实现连接池管理

---

## 七、运维相关

### 7.1 监控不足
- 缺少 API 响应时间指标
- 缺少队列长度监控
- 缺少数据库连接池监控
- 缺少 LLM 调用成功率监控

### 7.2 日志不完善
- 关键操作缺少审计日志
- 错误日志缺少上下文信息
- 缺少请求追踪 ID

### 7.3 部署复杂度
- 依赖多个外部服务（数据库、向量库、LLM）
- 缺少健康检查端点的完整实现
- 缺少优雅关闭机制

---

## 八、优先修复建议

### 立即修复（本周）
1. ~~移除硬编码密码~~ → 改用环境变量
2. 修复关键路径的异常处理（至少记录日志）
3. 清理生产代码中的 print 语句

### 短期修复（1-2 周）
1. 为核心模块添加单元测试（cognify、search）
2. 清理废弃代码
3. 统一日志框架
4. 完成 TODO 中的重试机制

### 中期优化（1 个月）
1. 提升测试覆盖率到 60%+
2. 实现 async gather 优化
3. 添加性能监控指标
4. 完善 API 文档

---

## 九、统计摘要

| 指标 | 数值 |
|-----|------|
| Critical 问题 | 2 |
| High 问题 | 8 |
| Medium 问题 | 12 |
| Low 问题 | 10+ |
| TODO 标记 | 24 |
| 废弃代码 | 3 处 |
| 测试覆盖模块 | 38% (8/21) |
| print 语句 | 229 处 |

---

*此清单基于静态代码分析生成，建议结合运行时测试进一步验证。*
