"""
向量数据库 Provider 切换集成测试。
验证：两套 provider (lancedb / qdrant) 对同一套操作序列的行为一致。
"""
import pytest
from uuid import uuid4
from unittest.mock import patch

from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.databases.vector.lancedb.LanceDBAdapter import LanceDBAdapter
from cognee.infrastructure.databases.vector.qdrant.QdrantAdapter import QdrantAdapter
from cognee.tests.unit.infrastructure.mock_embedding_engine import MockEmbeddingEngine


class DocDP(DataPoint):
    text: str
    metadata: dict = {"index_fields": ["text"]}


class EntityDP(DataPoint):
    name: str
    metadata: dict = {"index_fields": ["name"]}


def make_lancedb(tmp_path):
    return LanceDBAdapter(
        url=str(tmp_path / "test.lancedb"),
        api_key=None,
        embedding_engine=MockEmbeddingEngine(),
    )


def make_qdrant():
    return QdrantAdapter(url=":memory:", api_key=None, embedding_engine=MockEmbeddingEngine())


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["lancedb", "qdrant"])
async def test_create_search_delete_cycle(provider, tmp_path):
    """完整的增-查-删周期，两个 provider 行为一致。"""
    adapter = make_lancedb(tmp_path) if provider == "lancedb" else make_qdrant()

    dp_id = uuid4()
    dp = DocDP(id=dp_id, text="switchable vector db test")
    await adapter.create_data_points("docs", [dp])

    results = await adapter.search("docs", query_text="vector db", limit=5)
    assert len(results) > 0, f"[{provider}] search returned empty"
    assert any("switchable" in r.payload.get("text", "") for r in results)

    retrieved = await adapter.retrieve("docs", [str(dp_id)])
    assert len(retrieved) == 1

    await adapter.delete_data_points("docs", [str(dp_id)])
    results_after = await adapter.search("docs", query_text="vector db", limit=5)
    ids_after = [str(r.id) for r in results_after]
    assert str(dp_id) not in ids_after, f"[{provider}] deleted point still found"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["lancedb", "qdrant"])
async def test_index_data_points_creates_index_collection(provider, tmp_path):
    """index_data_points 应在两个 provider 上都创建 Entity_name 集合。"""
    adapter = make_lancedb(tmp_path) if provider == "lancedb" else make_qdrant()

    dp = EntityDP(id=uuid4(), name="Bob")
    await adapter.index_data_points("Entity", "name", [dp])

    assert await adapter.has_collection("Entity_name"), \
        f"[{provider}] Entity_name collection not created"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["lancedb", "qdrant"])
async def test_prune_clears_all(provider, tmp_path):
    """prune() 在两个 provider 上都应清空所有集合。"""
    adapter = make_lancedb(tmp_path) if provider == "lancedb" else make_qdrant()

    await adapter.create_data_points("col_a", [DocDP(id=uuid4(), text="a")])
    await adapter.create_data_points("col_b", [DocDP(id=uuid4(), text="b")])
    await adapter.prune()

    assert not await adapter.has_collection("col_a"), f"[{provider}] col_a not pruned"
    assert not await adapter.has_collection("col_b"), f"[{provider}] col_b not pruned"


def test_create_vector_engine_factory_lancedb(tmp_path):
    """create_vector_engine 工厂函数应能正确创建 LanceDB 实例。"""
    from cognee.infrastructure.databases.vector.create_vector_engine import create_vector_engine

    with patch(
        "cognee.infrastructure.databases.vector.create_vector_engine.get_embedding_engine",
        return_value=MockEmbeddingEngine(),
    ):
        engine = create_vector_engine(
            vector_db_provider="lancedb",
            vector_db_url=str(tmp_path / "factory.lancedb"),
        )
    assert isinstance(engine, LanceDBAdapter)


def test_create_vector_engine_factory_qdrant():
    """create_vector_engine 工厂函数应能正确创建 Qdrant 实例。"""
    from cognee.infrastructure.databases.vector.create_vector_engine import create_vector_engine

    with patch(
        "cognee.infrastructure.databases.vector.create_vector_engine.get_embedding_engine",
        return_value=MockEmbeddingEngine(),
    ):
        engine = create_vector_engine(
            vector_db_provider="qdrant",
            vector_db_url=":memory:",
        )
    assert isinstance(engine, QdrantAdapter)
