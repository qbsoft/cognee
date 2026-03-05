# Phase B: 双模型策略 + LLM 缓存 + 任务并行 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 通过双模型策略（快速模型做提取，强模型做回答）、LLM 结果缓存、任务并行三重手段，将 cognify 管道速度提升 3-8x，同时保持检索精度 >=95%。

**Architecture:** 在 LLMGateway 层添加 `task_type` 路由，通过 YAML 配置映射不同任务到不同模型。提取/摘要/蒸馏使用快速模型 (Qwen-turbo)，回答生成保持强模型 (Qwen-plus)。LLM 缓存基于内容哈希去重，避免重复文档重复调用 LLM。

**Tech Stack:** Python 3.11 / litellm / instructor / asyncio / pydantic / YAML config

---

## 架构分析

### 当前 LLM 调用链

```
                    ┌─ extract_content_graph.py ──┐
                    ├─ extract_summary.py ────────┤
全部走同一个模型 ─→  ├─ distill_knowledge.py ──────┤──→ LLMGateway.acreate_structured_output()
                    ├─ completion.py ─────────────┤      │
                    └─ graph_completion_cot_*.py ──┘      ↓
                                                    get_llm_client()
                                                         │
                                                         ↓
                                                  GenericAPIAdapter(model=llm_config.llm_model)
```

**关键发现:**
1. `get_llm_config()` 是 `@lru_cache` 单例，所有任务共享同一个模型
2. `GenericAPIAdapter` 在 `__init__` 时接收 `model` 参数，在 `acreate_structured_output()` 中使用 `self.model`
3. `get_llm_client()` 每次调用创建新的 adapter 实例（无缓存），可以传入不同 model
4. `distill_knowledge.py` **绑过 LLMGateway**，直接调用 `litellm.acompletion()`

### 目标架构

```
extract_content_graph ──→ task_type="extraction" ──→ 快速模型 (qwen-turbo)
extract_summary ────────→ task_type="extraction" ──→ 快速模型 (qwen-turbo)
distill_knowledge ──────→ 读取 YAML config ────────→ 快速模型 (qwen-turbo)
completion.py ──────────→ task_type="answer" ──────→ 强模型 (qwen-plus) [不变]
CoT retriever ──────────→ task_type="answer" ──────→ 强模型 (qwen-plus) [不变]
```

---

## Task 1: YAML 模型选择配置

**Files:**
- Create: `config/model_selection.yaml`

**Step 1: 创建配置文件**

```yaml
# 双模型策略配置
# extraction_model: 用于图谱提取、摘要、知识蒸馏等批处理任务（速度优先）
# answer_model: 用于回答生成（质量优先）
# 留空 "" 表示使用 .env 中的默认 LLM_MODEL

models:
  # 提取模型: 速度快、成本低，适合结构化提取任务
  # 推荐: dashscope/qwen-turbo-latest (DashScope) 或 gpt-4o-mini (OpenAI)
  extraction_model: ""

  # 回答模型: 推理能力强，适合回答生成
  # 留空表示使用 .env 中的 LLM_MODEL (默认行为)
  answer_model: ""
```

**Step 2: 验证 YAML 加载**

Run: `python -c "from cognee.infrastructure.config.yaml_config import get_module_config; print(get_module_config('model_selection'))"`
Expected: 能正确加载配置

**Step 3: Commit**

```bash
git add config/model_selection.yaml
git commit -m "feat(B1): add model selection YAML config for dual-model strategy"
```

---

## Task 2: get_llm_client 支持 model_override

**Files:**
- Modify: `cognee/infrastructure/llm/structured_output_framework/litellm_instructor/llm/get_llm_client.py`

**Step 1: 添加 model_override 参数**

在 `get_llm_client()` 函数签名中添加 `model_override: str = None` 参数。

在创建 adapter 时，如果 `model_override` 不为空，使用 `model_override` 替代 `llm_config.llm_model`。同时 `model_max_completion_tokens` 也需要用实际使用的 model 来查询。

```python
def get_llm_client(raise_api_key_error: bool = True, model_override: str = None):
    """
    Get the LLM client based on the configuration using Enums.

    Args:
        raise_api_key_error: Whether to raise error if API key is missing.
        model_override: Optional model name to override the configured model.
                       Used for dual-model strategy (e.g., fast extraction model).
    """
    llm_config = get_llm_config()

    # Use override model if provided, otherwise use config model
    effective_model = model_override if model_override else llm_config.llm_model

    provider = LLMProvider(llm_config.llm_provider)

    from cognee.infrastructure.llm.utils import get_model_max_completion_tokens
    model_max_completion_tokens = get_model_max_completion_tokens(effective_model)
    max_completion_tokens = (
        model_max_completion_tokens
        if model_max_completion_tokens
        else llm_config.llm_max_completion_tokens
    )

    # ... 在每个 provider 分支中，将 llm_config.llm_model 替换为 effective_model
```

**关键修改点** (每个 provider 分支中):

```python
    if provider == LLMProvider.OPENAI:
        # ...
        return OpenAIAdapter(
            # ...
            model=effective_model,  # 原: llm_config.llm_model
            # ...
        )
    # ... CUSTOM 分支同理
    elif provider == LLMProvider.CUSTOM:
        # ...
        return GenericAPIAdapter(
            llm_config.llm_endpoint,
            llm_config.llm_api_key,
            effective_model,  # 原: llm_config.llm_model
            "Custom",
            max_completion_tokens=max_completion_tokens,
            # ...
        )
    # ... 其他 provider 同理
```

**Step 2: 运行现有测试确认无回归**

Run: `pytest tests/ -x -q --timeout=60 -k "not ragas and not e2e"`
Expected: 全部通过（model_override 默认 None，行为不变）

**Step 3: Commit**

```bash
git add cognee/infrastructure/llm/structured_output_framework/litellm_instructor/llm/get_llm_client.py
git commit -m "feat(B1): add model_override param to get_llm_client for dual-model routing"
```

---

## Task 3: LLMGateway 添加 task_type 路由

**Files:**
- Modify: `cognee/infrastructure/llm/LLMGateway.py`

**Step 1: 添加 task_type 参数和模型路由逻辑**

```python
from typing import Type, Optional, Coroutine
from pydantic import BaseModel
from cognee.infrastructure.llm import get_llm_config


def _get_model_for_task(task_type: str) -> Optional[str]:
    """Get the model override for a given task type from YAML config.

    Returns None if no override is configured (use default model).
    """
    if task_type == "default":
        return None

    try:
        from cognee.infrastructure.config.yaml_config import get_module_config
        model_cfg = get_module_config("model_selection").get("models", {})
    except Exception:
        return None

    if task_type == "extraction":
        model = model_cfg.get("extraction_model", "")
        return model if model else None
    elif task_type == "answer":
        model = model_cfg.get("answer_model", "")
        return model if model else None

    return None


class LLMGateway:
    """
    Class handles selection of structured output frameworks and LLM functions.
    """

    @staticmethod
    def acreate_structured_output(
        text_input: str,
        system_prompt: str,
        response_model: Type[BaseModel],
        task_type: str = "default",
    ) -> Coroutine:
        llm_config = get_llm_config()
        model_override = _get_model_for_task(task_type)

        if llm_config.structured_output_framework.upper() == "BAML":
            from cognee.infrastructure.llm.structured_output_framework.baml.baml_src.extraction import (
                acreate_structured_output,
            )
            return acreate_structured_output(
                text_input=text_input,
                system_prompt=system_prompt,
                response_model=response_model,
            )
        else:
            from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import (
                get_llm_client,
            )
            llm_client = get_llm_client(model_override=model_override)
            return llm_client.acreate_structured_output(
                text_input=text_input,
                system_prompt=system_prompt,
                response_model=response_model,
            )

    # create_structured_output, create_transcript, transcribe_image 保持不变
```

**Step 2: 验证默认行为不变**

Run: `python -c "from cognee.infrastructure.llm.LLMGateway import LLMGateway, _get_model_for_task; print(_get_model_for_task('default'), _get_model_for_task('extraction'), _get_model_for_task('answer'))"`
Expected: `None None None`（extraction_model 配置为空时都返回 None）

**Step 3: Commit**

```bash
git add cognee/infrastructure/llm/LLMGateway.py
git commit -m "feat(B1): add task_type routing to LLMGateway for dual-model strategy"
```

---

## Task 4: 更新提取类调用点 — task_type="extraction"

**Files:**
- Modify: `cognee/infrastructure/llm/extraction/knowledge_graph/extract_content_graph.py` (line 32)
- Modify: `cognee/infrastructure/llm/extraction/extract_summary.py` (line 31)
- Modify: `cognee/infrastructure/llm/extraction/extract_categories.py` (line 11)
- Modify: `cognee/infrastructure/llm/extraction/extract_event_entities.py` (line 41)
- Modify: `cognee/infrastructure/llm/extraction/knowledge_graph/extract_event_graph.py` (line 43)

**Step 1: extract_content_graph.py**

```python
# 修改前 (line 32-34):
    content_graph = await LLMGateway.acreate_structured_output(
        content, system_prompt, response_model
    )

# 修改后:
    content_graph = await LLMGateway.acreate_structured_output(
        content, system_prompt, response_model, task_type="extraction"
    )
```

**Step 2: extract_summary.py**

```python
# 修改前 (line 31):
    llm_output = await LLMGateway.acreate_structured_output(content, system_prompt, response_model)

# 修改后:
    llm_output = await LLMGateway.acreate_structured_output(
        content, system_prompt, response_model, task_type="extraction"
    )
```

**Step 3: extract_categories.py**

```python
# 修改前 (line 11):
    llm_output = await LLMGateway.acreate_structured_output(content, system_prompt, response_model)

# 修改后:
    llm_output = await LLMGateway.acreate_structured_output(
        content, system_prompt, response_model, task_type="extraction"
    )
```

**Step 4: extract_event_entities.py**

```python
# 修改前 (line 41-43):
    content_graph = await LLMGateway.acreate_structured_output(
        content, system_prompt, response_model
    )

# 修改后:
    content_graph = await LLMGateway.acreate_structured_output(
        content, system_prompt, response_model, task_type="extraction"
    )
```

**Step 5: extract_event_graph.py**

```python
# 修改前 (line 43-45):
    content_graph = await LLMGateway.acreate_structured_output(
        content, system_prompt, response_model
    )

# 修改后:
    content_graph = await LLMGateway.acreate_structured_output(
        content, system_prompt, response_model, task_type="extraction"
    )
```

**Step 6: Commit**

```bash
git add cognee/infrastructure/llm/extraction/
git commit -m "feat(B1): route extraction tasks to fast model via task_type='extraction'"
```

---

## Task 5: 更新 distill_knowledge — 使用提取模型

**Files:**
- Modify: `cognee/tasks/distillation/distill_knowledge.py`

`distill_knowledge.py` 绕过了 LLMGateway，直接使用 `litellm.acompletion()`。
需要在 `_call_llm_distill()` 和 `_call_llm_merge()` 中读取 YAML config 获取 extraction_model。

**Step 1: 添加模型选择辅助函数**

在文件顶部（import 之后，函数之前）添加:

```python
def _get_extraction_model() -> str:
    """Get the extraction model from YAML config, fallback to default LLM_MODEL."""
    try:
        from cognee.infrastructure.config.yaml_config import get_module_config
        model_cfg = get_module_config("model_selection").get("models", {})
        extraction_model = model_cfg.get("extraction_model", "")
        if extraction_model:
            return extraction_model
    except Exception:
        pass
    from cognee.infrastructure.llm.config import get_llm_config
    return get_llm_config().llm_model
```

**Step 2: 修改 `_call_llm_distill()`**

```python
# 修改前 (line 329-333):
    llm_config = get_llm_config()
    try:
        response = await litellm.acompletion(
            model=llm_config.llm_model,

# 修改后:
    llm_config = get_llm_config()
    effective_model = _get_extraction_model()
    try:
        response = await litellm.acompletion(
            model=effective_model,
```

**Step 3: 修改 `_call_llm_merge()`**

```python
# 修改前 (line 392-395):
    llm_config = get_llm_config()
    try:
        response = await litellm.acompletion(
            model=llm_config.llm_model,

# 修改后:
    llm_config = get_llm_config()
    effective_model = _get_extraction_model()
    try:
        response = await litellm.acompletion(
            model=effective_model,
```

**Step 4: 添加日志标注实际使用的模型**

在两个函数中各添加:
```python
    logger.info(f"Using model: {effective_model} for distillation")
```

**Step 5: Commit**

```bash
git add cognee/tasks/distillation/distill_knowledge.py
git commit -m "feat(B1): route distillation LLM calls to extraction model"
```

---

## Task 6: 确保回答生成使用强模型

**Files:**
- Verify: `cognee/modules/retrieval/utils/completion.py` (无需修改，task_type 默认 "default")
- Verify: `cognee/modules/retrieval/graph_completion_cot_retriever.py` (无需修改)

**说明:** 回答生成调用 `LLMGateway.acreate_structured_output()` 时不传 task_type，
默认为 `"default"`，`_get_model_for_task("default")` 返回 `None`，
`get_llm_client(model_override=None)` 使用原始 `llm_config.llm_model`。

**零改动 = 零风险。**

如果未来想让回答使用不同于 .env 默认的模型:
- 在 `config/model_selection.yaml` 中设置 `answer_model`
- 在 `completion.py` 的调用中添加 `task_type="answer"`

**Step 1: 验证回答路径不受影响**

Run: `python -c "from cognee.infrastructure.llm.LLMGateway import _get_model_for_task; assert _get_model_for_task('default') is None; print('OK: answer path unchanged')"`

---

## Task 7: 配置 extraction_model 并验证

**Files:**
- Modify: `config/model_selection.yaml`

**Step 1: 设置提取模型**

DashScope 用户:
```yaml
models:
  extraction_model: "dashscope/qwen-turbo-latest"
  answer_model: ""
```

OpenAI 用户:
```yaml
models:
  extraction_model: "openai/gpt-4o-mini"
  answer_model: ""
```

**Step 2: 运行回归测试**

Run: `python eval_framework/test_ragas_direct.py`
Expected: RAGAS 精度 >=93% (如果 <93% 需要回退到空 extraction_model)

**Step 3: 性能对比**

Run cognify with extraction_model configured vs empty, 记录耗时对比。
Expected: 3-5x speedup for cognify pipeline。

---

## Task 8: LLM 结果缓存 (B2)

**Files:**
- Create: `cognee/infrastructure/llm/llm_cache.py`
- Modify: `cognee/infrastructure/llm/LLMGateway.py`
- Modify: `config/model_selection.yaml`

**Step 1: 添加缓存配置到 YAML**

```yaml
# 追加到 config/model_selection.yaml:
cache:
  enabled: true
  # 缓存目录 (相对于项目根目录)
  cache_dir: ".cognee_cache/llm"
  # 缓存过期时间 (秒), 默认 7 天
  ttl_seconds: 604800
```

**Step 2: 创建 llm_cache.py**

```python
"""
LLM response cache based on content hashing.

Caches LLM responses keyed by SHA256(model + system_prompt + text_input + response_model_name).
Uses file-based storage for persistence across restarts.
"""
import hashlib
import json
import os
import time
from typing import Optional, Type
from pydantic import BaseModel

from cognee.shared.logging_utils import get_logger

logger = get_logger("llm_cache")


def _get_cache_config() -> dict:
    """Load cache config from YAML."""
    try:
        from cognee.infrastructure.config.yaml_config import get_module_config
        return get_module_config("model_selection").get("cache", {})
    except Exception:
        return {}


def _get_cache_dir() -> str:
    """Get the cache directory path."""
    config = _get_cache_config()
    cache_dir = config.get("cache_dir", ".cognee_cache/llm")
    if not os.path.isabs(cache_dir):
        # Relative to current working directory
        cache_dir = os.path.join(os.getcwd(), cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _compute_cache_key(
    model: str,
    system_prompt: str,
    text_input: str,
    response_model_name: str,
) -> str:
    """Compute SHA256 hash for cache key."""
    content = f"{model}|{system_prompt}|{text_input}|{response_model_name}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def is_cache_enabled() -> bool:
    """Check if LLM caching is enabled."""
    config = _get_cache_config()
    return config.get("enabled", False)


def get_cached_response(
    model: str,
    system_prompt: str,
    text_input: str,
    response_model: Type[BaseModel],
) -> Optional[BaseModel]:
    """
    Look up a cached LLM response.

    Returns the cached response model instance if found and not expired,
    otherwise returns None.
    """
    if not is_cache_enabled():
        return None

    config = _get_cache_config()
    ttl = config.get("ttl_seconds", 604800)

    response_model_name = response_model.__name__ if isinstance(response_model, type) else str(response_model)
    cache_key = _compute_cache_key(model, system_prompt, text_input, response_model_name)
    cache_file = os.path.join(_get_cache_dir(), f"{cache_key}.json")

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)

        # Check TTL
        if time.time() - cached.get("timestamp", 0) > ttl:
            os.remove(cache_file)
            return None

        # Reconstruct response model
        if response_model is str:
            return cached["response"]
        else:
            return response_model.model_validate(cached["response"])

    except Exception as e:
        logger.debug(f"Cache read failed for {cache_key[:12]}: {e}")
        return None


def set_cached_response(
    model: str,
    system_prompt: str,
    text_input: str,
    response_model: Type[BaseModel],
    response: BaseModel,
) -> None:
    """Store an LLM response in the cache."""
    if not is_cache_enabled():
        return

    response_model_name = response_model.__name__ if isinstance(response_model, type) else str(response_model)
    cache_key = _compute_cache_key(model, system_prompt, text_input, response_model_name)
    cache_file = os.path.join(_get_cache_dir(), f"{cache_key}.json")

    try:
        if response_model is str or isinstance(response, str):
            response_data = response
        else:
            response_data = response.model_dump()

        cached = {
            "timestamp": time.time(),
            "model": model,
            "response_model": response_model_name,
            "response": response_data,
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cached, f, ensure_ascii=False)

        logger.debug(f"Cached LLM response: {cache_key[:12]}")

    except Exception as e:
        logger.debug(f"Cache write failed for {cache_key[:12]}: {e}")
```

**Step 3: 在 LLMGateway 中集成缓存**

修改 `LLMGateway.acreate_structured_output()`:

```python
    @staticmethod
    async def acreate_structured_output(
        text_input: str,
        system_prompt: str,
        response_model: Type[BaseModel],
        task_type: str = "default",
    ):
        # NOTE: 方法签名从 Coroutine 返回改为 async，以支持缓存查找
        from cognee.infrastructure.llm.llm_cache import (
            get_cached_response, set_cached_response, is_cache_enabled
        )

        llm_config = get_llm_config()
        model_override = _get_model_for_task(task_type)
        effective_model = model_override or llm_config.llm_model

        # Check cache (only for extraction tasks, not answer generation)
        if task_type == "extraction" and is_cache_enabled():
            cached = get_cached_response(
                effective_model, system_prompt, text_input, response_model
            )
            if cached is not None:
                return cached

        # Call LLM
        if llm_config.structured_output_framework.upper() == "BAML":
            from cognee.infrastructure.llm.structured_output_framework.baml.baml_src.extraction import (
                acreate_structured_output,
            )
            result = await acreate_structured_output(
                text_input=text_input,
                system_prompt=system_prompt,
                response_model=response_model,
            )
        else:
            from cognee.infrastructure.llm.structured_output_framework.litellm_instructor.llm.get_llm_client import (
                get_llm_client,
            )
            llm_client = get_llm_client(model_override=model_override)
            result = await llm_client.acreate_structured_output(
                text_input=text_input,
                system_prompt=system_prompt,
                response_model=response_model,
            )

        # Store in cache
        if task_type == "extraction" and is_cache_enabled():
            set_cached_response(
                effective_model, system_prompt, text_input, response_model, result
            )

        return result
```

**重要注意:** 将 `acreate_structured_output` 从返回 `Coroutine` 改为 `async` 方法。
需要检查所有调用点是否兼容 — 由于所有调用都已经是 `await LLMGateway.acreate_structured_output(...)` 模式，所以兼容。

**Step 4: Commit**

```bash
git add cognee/infrastructure/llm/llm_cache.py cognee/infrastructure/llm/LLMGateway.py config/model_selection.yaml
git commit -m "feat(B2): add content-hash based LLM response cache for extraction tasks"
```

---

## Task 9: 任务级并行 (B3) — extract_graph || distill || summarize

**Files:**
- Create: `cognee/tasks/parallel_processing.py`
- Modify: `cognee/api/v1/cognify/cognify.py` (或管道定义文件)

**分析:**

当前 cognify 管道中，以下三个任务是**串行**执行的:
1. `extract_graph_from_data` — 读取 chunk.text, 提取图谱
2. `distill_knowledge` — 读取 chunk.text, 生成蒸馏知识
3. `summarize_text` — 读取 chunk.text, 生成摘要

这三个任务的**输入**都是 `data_chunks`，且各自独立工作:
- extract_graph: 写入 graph + add_data_points，返回 data_chunks (with .contains)
- distill_knowledge: add_data_points(KD)，返回 data_chunks (unchanged)
- summarize_text: 返回 TextSummary list

**关键问题:** cognify 管道框架 (run_tasks_base) 将任务输出作为下一个任务的输入，
天然是串行的。要实现并行需要创建一个"并行包装任务"。

**Step 1: 创建并行包装任务**

```python
"""
Parallel processing wrapper for cognify pipeline tasks.

Runs extract_graph, distill_knowledge, and summarize_text concurrently
to reduce total processing time. Each task independently reads chunk.text
and writes to different storage targets.
"""
import asyncio
from typing import List, Type, Optional
from pydantic import BaseModel

from cognee.modules.chunking.models.DocumentChunk import DocumentChunk
from cognee.shared.logging_utils import get_logger

logger = get_logger("parallel_processing")


async def parallel_extract_and_summarize(
    data_chunks: List[DocumentChunk],
    graph_model: Type[BaseModel] = None,
    summarization_model: Type[BaseModel] = None,
    graph_config=None,
    custom_prompt: Optional[str] = None,
) -> List[DocumentChunk]:
    """
    Run graph extraction, knowledge distillation, and summarization in parallel.

    All three tasks read chunk.text independently and write to different stores:
    - extract_graph → graph DB + vector index
    - distill_knowledge → vector index (KnowledgeDistillation)
    - summarize_text → returns TextSummary (stored by downstream task)

    Returns the original data_chunks for compatibility with the pipeline.
    """
    from cognee.tasks.graph.extract_graph_from_data import extract_graph_from_data
    from cognee.tasks.summarization.summarize_text import summarize_text

    tasks = []

    # Task 1: Graph extraction
    if graph_model is not None:
        tasks.append(("extract_graph", extract_graph_from_data(
            data_chunks, graph_model, config=graph_config, custom_prompt=custom_prompt
        )))

    # Task 2: Knowledge distillation (check if enabled)
    try:
        from cognee.infrastructure.config.yaml_config import get_module_config
        distillation_cfg = get_module_config("distillation")
        distillation_enabled = distillation_cfg.get("enabled", False)
    except Exception:
        distillation_enabled = False

    if distillation_enabled:
        from cognee.tasks.distillation.distill_knowledge import distill_knowledge
        tasks.append(("distill_knowledge", distill_knowledge(data_chunks)))

    # Task 3: Summarization
    if summarization_model is not None:
        tasks.append(("summarize_text", summarize_text(
            data_chunks, summarization_model
        )))

    if not tasks:
        return data_chunks

    logger.info(
        "Running %d tasks in parallel: %s",
        len(tasks),
        ", ".join(name for name, _ in tasks),
    )

    # Run all tasks concurrently
    results = await asyncio.gather(
        *[coro for _, coro in tasks],
        return_exceptions=True,
    )

    # Log results
    for (task_name, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.error(f"Parallel task {task_name} failed: {result}")
        else:
            logger.info(f"Parallel task {task_name} completed successfully")

    # Return original data_chunks (graph extraction already updated .contains)
    return data_chunks
```

**Step 2: 集成到 cognify 管道**

这一步需要修改 cognify 管道定义，将三个串行 Task 替换为一个并行 Task。
具体修改取决于管道定义的位置。这是一个较大的改动，建议在 B1+B2 验证通过后再实施。

**Step 3: Commit**

```bash
git add cognee/tasks/parallel_processing.py
git commit -m "feat(B3): add parallel processing wrapper for extract+distill+summarize"
```

---

## Task 10: 回归验证 + 性能基准

**Step 1: RAGAS 回归测试**

Run: `python eval_framework/test_ragas_direct.py`
Expected: 精度 >= 93%

**Step 2: 性能对比**

对比 extraction_model=empty vs extraction_model=qwen-turbo-latest:
- 记录 cognify 总耗时
- 记录各阶段 (extract_graph / distill / summarize) 耗时
- Expected: 总耗时降低 3-5x

**Step 3: 如果精度 <93%**

回退策略:
1. 将 `config/model_selection.yaml` 中 `extraction_model` 设为空
2. 所有任务回退到默认模型
3. 分析是哪个任务（提取/摘要/蒸馏）质量下降
4. 考虑只对 summarize_text 使用快速模型（影响最小）

---

## 关键文件汇总

| 文件 | 操作 | Task |
|------|------|------|
| `config/model_selection.yaml` | 新建 | T1, T7, T8 |
| `cognee/infrastructure/llm/structured_output_framework/litellm_instructor/llm/get_llm_client.py` | 修改 | T2 |
| `cognee/infrastructure/llm/LLMGateway.py` | 修改 | T3, T8 |
| `cognee/infrastructure/llm/extraction/knowledge_graph/extract_content_graph.py` | 修改 | T4 |
| `cognee/infrastructure/llm/extraction/extract_summary.py` | 修改 | T4 |
| `cognee/infrastructure/llm/extraction/extract_categories.py` | 修改 | T4 |
| `cognee/infrastructure/llm/extraction/extract_event_entities.py` | 修改 | T4 |
| `cognee/infrastructure/llm/extraction/knowledge_graph/extract_event_graph.py` | 修改 | T4 |
| `cognee/tasks/distillation/distill_knowledge.py` | 修改 | T5 |
| `cognee/infrastructure/llm/llm_cache.py` | 新建 | T8 |
| `cognee/tasks/parallel_processing.py` | 新建 | T9 |

## 安全保障

1. **extraction_model 为空时行为不变** — `_get_model_for_task()` 返回 None，使用默认模型
2. **回答生成零改动** — completion.py 不传 task_type，使用默认模型
3. **缓存仅用于 extraction 任务** — 回答生成不缓存，保证每次查询都是新鲜回答
4. **YAML 配置加载失败时降级** — 所有 try/except 确保配置错误不影响管道运行
5. **回归测试** — RAGAS 精度 >=93% 是上线门槛

## 预期收益

| 优化项 | 预期提速 | 风险 |
|--------|---------|------|
| B1: 双模型 (qwen-turbo) | 3-5x | 提取质量可能略降，需 RAGAS 验证 |
| B2: LLM 缓存 | 1.5-3x (重复文档) | 首次处理无加速 |
| B3: 任务并行 | 1.3x | 需要修改管道定义，改动较大 |
| **总计** | **~5-8x** | 需逐步验证 |
