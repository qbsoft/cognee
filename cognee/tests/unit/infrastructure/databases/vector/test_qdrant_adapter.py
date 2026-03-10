"""
Qdrant 适配器单元测试（in-memory 模式，无需服务器）
覆盖：has_collection / create_collection / create_data_points /
      retrieve / search / batch_search / delete_data_points / prune
"""
import pytest
import asyncio
from uuid import uuid4

from cognee.infrastructure.databases.vector.qdrant.QdrantAdapter import QdrantAdapter
from cognee.tests.unit.infrastructure.mock_embedding_engine import MockEmbeddingEngine
from cognee.infrastructure.engine import DataPoint


class SimpleDP(DataPoint):
    text: str
    metadata: dict = {"index_fields": ["text"]}


@pytest.fixture
def adapter():
    """in-memory Qdrant，每次测试独立实例。"""
    return QdrantAdapter(url=":memory:", api_key=None, embedding_engine=MockEmbeddingEngine())


@pytest.mark.asyncio
async def test_has_collection_false_when_empty(adapter):
    assert await adapter.has_collection("nonexistent") is False


@pytest.mark.asyncio
async def test_create_and_has_collection(adapter):
    await adapter.create_collection("test_col")
    assert await adapter.has_collection("test_col") is True


@pytest.mark.asyncio
async def test_create_collection_idempotent(adapter):
    """重复创建同一集合不应报错。"""
    await adapter.create_collection("dup_col")
    await adapter.create_collection("dup_col")  # 不应抛出
    assert await adapter.has_collection("dup_col") is True


@pytest.mark.asyncio
async def test_create_data_points_and_retrieve(adapter):
    dp_id = uuid4()
    dp = SimpleDP(id=dp_id, text="hello qdrant")

    await adapter.create_data_points("test_col", [dp])

    results = await adapter.retrieve("test_col", [str(dp_id)])
    assert len(results) == 1
    assert results[0].payload["text"] == "hello qdrant"


@pytest.mark.asyncio
async def test_search_returns_results(adapter):
    for i in range(3):
        dp = SimpleDP(id=uuid4(), text=f"document {i}")
        await adapter.create_data_points("search_col", [dp])

    results = await adapter.search("search_col", query_text="document", limit=5)
    assert len(results) > 0
    # score 是归一化距离，0.0 = 最相似
    assert all(isinstance(r.score, float) for r in results)
    assert any("document" in r.payload.get("text", "") for r in results)


@pytest.mark.asyncio
async def test_search_limit_none_returns_all(adapter):
    """limit=None 应返回所有文档（对齐 LanceDB 行为）。"""
    for i in range(20):
        dp = SimpleDP(id=uuid4(), text=f"item {i}")
        await adapter.create_data_points("limit_col", [dp])

    results = await adapter.search("limit_col", query_text="item", limit=None)
    assert len(results) == 20


@pytest.mark.asyncio
async def test_delete_data_points(adapter):
    dp_id = uuid4()
    dp = SimpleDP(id=dp_id, text="to be deleted")
    await adapter.create_data_points("del_col", [dp])

    await adapter.delete_data_points("del_col", [str(dp_id)])
    results = await adapter.retrieve("del_col", [str(dp_id)])
    assert len(results) == 0


@pytest.mark.asyncio
async def test_batch_search(adapter):
    for i in range(5):
        dp = SimpleDP(id=uuid4(), text=f"batch item {i}")
        await adapter.create_data_points("batch_col", [dp])

    results = await adapter.batch_search(
        "batch_col", query_texts=["batch item 0", "batch item 1"], limit=3
    )
    assert len(results) == 2
    assert all(len(r) > 0 for r in results)
    assert all(any("batch item" in r.payload.get("text", "") for r in group) for group in results)


@pytest.mark.asyncio
async def test_prune_deletes_all_collections(adapter):
    await adapter.create_collection("col_a")
    await adapter.create_collection("col_b")
    await adapter.prune()
    assert await adapter.has_collection("col_a") is False
    assert await adapter.has_collection("col_b") is False


@pytest.mark.asyncio
async def test_index_data_points(adapter):
    """index_data_points 创建 {name}_{field} 集合并插入 IndexSchema。"""
    class EntityDP(DataPoint):
        name: str
        metadata: dict = {"index_fields": ["name"]}

    dp = EntityDP(id=uuid4(), name="Alice")
    await adapter.index_data_points("Entity", "name", [dp])

    assert await adapter.has_collection("Entity_name") is True
    results = await adapter.search("Entity_name", query_text="Alice", limit=5)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_concurrent_writes_no_crash(adapter):
    """Qdrant 应能同时处理 20 个并发写入（LanceDB 在此会崩溃）。"""
    tasks = [
        adapter.create_data_points("concurrent_col", [SimpleDP(id=uuid4(), text=f"item {i}")])
        for i in range(20)
    ]
    # 不应抛出 "Too many concurrent writers" 等错误
    await asyncio.gather(*tasks)

    results = await adapter.search("concurrent_col", query_text="item", limit=None)
    assert len(results) == 20


@pytest.mark.asyncio
async def test_search_raises_if_collection_not_found(adapter):
    from cognee.infrastructure.databases.vector.exceptions import CollectionNotFoundError
    with pytest.raises(CollectionNotFoundError):
        await adapter.search("ghost_col", query_text="test", limit=5)


@pytest.mark.asyncio
async def test_score_normalization_range(adapter):
    """归一化后 score 应在 [0, 1] 范围内，最相似的在最前。"""
    # 插入相同向量的多个文档（mock embedding 总是返回相同向量）
    for i in range(5):
        dp = SimpleDP(id=uuid4(), text=f"doc {i}")
        await adapter.create_data_points("norm_col", [dp])

    results = await adapter.search("norm_col", query_text="doc", limit=5)
    scores = [r.score for r in results]
    assert all(0.0 <= s <= 1.0 for s in scores), f"Score out of range: {scores}"
