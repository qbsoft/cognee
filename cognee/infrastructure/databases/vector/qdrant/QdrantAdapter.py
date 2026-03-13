"""
Qdrant vector database adapter for Cognee.

Implements VectorDBInterface using qdrant-client's AsyncQdrantClient.
Supports three connection modes:
  - In-memory: url is empty or ":memory:" (for testing)
  - Local file persistence: url is a local path (no server needed)
  - Remote server: url starts with "http" (production)

Qdrant natively supports high-concurrency upsert — no write semaphore needed
(unlike LanceDB which crashes at >3 concurrent writers).
"""

import asyncio
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    PointIdsList,
    QueryRequest,
)

from cognee.shared.logging_utils import get_logger
from cognee.modules.storage.utils import get_own_properties
from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.engine.utils import parse_id
from cognee.infrastructure.databases.exceptions import MissingQueryParameterError
from cognee.infrastructure.databases.vector.exceptions import CollectionNotFoundError
from cognee.infrastructure.databases.vector.models.ScoredResult import ScoredResult
from cognee.infrastructure.databases.vector.embeddings.EmbeddingEngine import EmbeddingEngine
from cognee.infrastructure.databases.vector.vector_db_interface import VectorDBInterface
from cognee.infrastructure.databases.vector.utils import normalize_distances

logger = get_logger("QdrantAdapter")


class IndexSchema(DataPoint):
    """Schema for vector index entries (same pattern as LanceDB/ChromaDB)."""
    id: str
    text: str
    metadata: dict = {"index_fields": ["text"]}


def _serialize_payload(data: dict) -> dict:
    """Convert UUID/datetime values to JSON-compatible types for Qdrant payload."""
    result = {}
    for key, value in data.items():
        if isinstance(value, UUID):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = _serialize_payload(value)
        elif isinstance(value, list):
            result[key] = [
                _serialize_payload(item) if isinstance(item, dict)
                else str(item) if isinstance(item, UUID)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result


class QdrantAdapter(VectorDBInterface):
    """Qdrant vector database adapter implementing VectorDBInterface."""

    name = "Qdrant"

    # 类级别的连接缓存：多个 QdrantAdapter 实例共享同一个 AsyncQdrantClient（按 url 隔离）
    # 这样 52 个并发 pipeline 不会各自创建独立的连接，避免 Qdrant TCP accept queue 打满
    _client_cache: dict = {}

    def __init__(
        self,
        url: Optional[str],
        api_key: Optional[str],
        embedding_engine: EmbeddingEngine,
    ):
        self.url = url
        self.api_key = api_key
        self.embedding_engine = embedding_engine

    # ── Connection ──────────────────────────────────────────────────

    async def get_connection(self) -> AsyncQdrantClient:
        """Get or create the async Qdrant client.

        Connection modes:
          - url empty / ":memory:" → in-memory (ephemeral, for tests)
          - url starts with "http"  → remote server
          - otherwise               → local file persistence (path=url)

        使用类级别缓存（_client_cache），让所有 QdrantAdapter 实例共享同一个
        AsyncQdrantClient（按 URL 隔离），避免 52 个并发任务各自建立独立连接。
        """
        cache_key = self.url or ":memory:"
        if cache_key not in QdrantAdapter._client_cache:
            if not self.url or self.url == ":memory:":
                client = AsyncQdrantClient(location=":memory:")
                logger.info("Qdrant: connected in-memory mode")
            elif self.url.startswith("http"):
                # trust_env=False 通过 **kwargs 传给 httpx.AsyncClient，关闭代理读取
                # 避免 Windows 系统代理（Clash/127.0.0.1:7897）拦截本地 Qdrant 请求
                client = AsyncQdrantClient(
                    url=self.url,
                    api_key=self.api_key if self.api_key else None,
                    trust_env=False,
                )
                logger.info(f"Qdrant: connected to remote server {self.url} (proxy disabled, shared client)")
            else:
                client = AsyncQdrantClient(path=self.url)
                logger.info(f"Qdrant: connected with local persistence at {self.url}")
            QdrantAdapter._client_cache[cache_key] = client
        return QdrantAdapter._client_cache[cache_key]

    # ── Embedding ───────────────────────────────────────────────────

    async def embed_data(self, data: List[str]) -> List[List[float]]:
        """Embed text data using the configured embedding engine."""
        return await self.embedding_engine.embed_text(data)

    # ── Collection management ───────────────────────────────────────

    async def has_collection(self, collection_name: str) -> bool:
        client = await self.get_connection()
        return await client.collection_exists(collection_name)

    async def create_collection(self, collection_name: str, payload_schema=None):
        if not await self.has_collection(collection_name):
            client = await self.get_connection()
            vector_size = self.embedding_engine.get_vector_size()
            await client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                f"Qdrant: created collection '{collection_name}' "
                f"(dim={vector_size}, distance=COSINE)"
            )

    async def get_collection(self, collection_name: str):
        """Return collection info (or raise if not found)."""
        if not await self.has_collection(collection_name):
            raise CollectionNotFoundError(
                f"Collection '{collection_name}' not found!"
            )
        client = await self.get_connection()
        return await client.get_collection(collection_name)

    # ── Data point CRUD ─────────────────────────────────────────────

    async def create_data_points(
        self, collection_name: str, data_points: List[DataPoint]
    ):
        """Embed and upsert data points into Qdrant.

        Qdrant handles concurrent upserts natively — no semaphore needed.
        """
        if not await self.has_collection(collection_name):
            await self.create_collection(collection_name)

        client = await self.get_connection()

        # Embed all texts
        texts = [
            DataPoint.get_embeddable_data(dp) for dp in data_points
        ]
        vectors = await self.embed_data(texts)

        # Build PointStruct list
        points = []
        for dp, vector in zip(data_points, vectors):
            properties = get_own_properties(dp)
            # Ensure JSON-serializable payload (UUID → str, datetime → iso)
            properties["id"] = str(properties["id"])
            payload = _serialize_payload(properties)
            points.append(
                PointStruct(
                    id=str(dp.id),
                    vector=vector,
                    payload=payload,
                )
            )

        # Qdrant upsert — high concurrency, no file locks
        await client.upsert(
            collection_name=collection_name,
            points=points,
        )

    async def retrieve(
        self, collection_name: str, data_point_ids: list[str]
    ):
        """Retrieve data points by ID (score=0)."""
        if not await self.has_collection(collection_name):
            raise CollectionNotFoundError(
                f"Collection '{collection_name}' not found!"
            )

        client = await self.get_connection()
        results = await client.retrieve(
            collection_name=collection_name,
            ids=data_point_ids,
            with_payload=True,
        )

        return [
            ScoredResult(
                id=parse_id(point.id),
                payload=point.payload,
                score=0,
            )
            for point in results
        ]

    async def delete_data_points(
        self, collection_name: str, data_point_ids: list[str]
    ):
        """Delete data points by ID."""
        client = await self.get_connection()
        await client.delete(
            collection_name=collection_name,
            points_selector=PointIdsList(points=data_point_ids),
        )

    # ── Search ──────────────────────────────────────────────────────

    async def search(
        self,
        collection_name: str,
        query_text: str = None,
        query_vector: List[float] = None,
        limit: Optional[int] = 15,
        with_vector: bool = False,
        normalized: bool = True,
    ):
        """Vector similarity search.

        Score conversion:
          Qdrant Cosine → score ∈ [0, 1], higher = more similar
          Cognee ScoredResult → score: lower = better
          Conversion: _distance = 1.0 - qdrant_score
        """
        if query_text is None and query_vector is None:
            raise MissingQueryParameterError()

        if query_text and not query_vector:
            query_vector = (
                await self.embedding_engine.embed_text([query_text])
            )[0]

        if not await self.has_collection(collection_name):
            raise CollectionNotFoundError(
                f"Collection '{collection_name}' not found!"
            )

        client = await self.get_connection()

        if limit is None:
            collection_info = await client.get_collection(collection_name)
            limit = collection_info.points_count or 0

        if limit <= 0:
            return []

        # qdrant-client v1.12+ uses query_points instead of search
        response = await client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            with_vectors=with_vector,
        )

        results = response.points if response else []

        if not results:
            return []

        # Convert Qdrant similarity (higher=better) to distance (lower=better)
        result_values = [
            {
                "_distance": 1.0 - point.score,
                "id": point.id,
                "payload": point.payload,
            }
            for point in results
        ]

        normalized_values = normalize_distances(result_values)

        return [
            ScoredResult(
                id=parse_id(result["id"]),
                payload=result["payload"],
                score=normalized_values[i],
            )
            for i, result in enumerate(result_values)
        ]

    async def batch_search(
        self,
        collection_name: str,
        query_texts: List[str],
        limit: Optional[int] = None,
        with_vectors: bool = False,
    ):
        """Batch search using Qdrant's native query_batch_points (more efficient)."""
        query_vectors = await self.embedding_engine.embed_text(query_texts)
        client = await self.get_connection()

        requests = [
            QueryRequest(
                query=qv,
                limit=limit or 5,
                with_payload=True,
                with_vector=with_vectors,
            )
            for qv in query_vectors
        ]

        batch_response = await client.query_batch_points(
            collection_name=collection_name,
            requests=requests,
        )

        all_results = []
        for response in batch_response:
            points = response.points if hasattr(response, 'points') else response
            if not points:
                all_results.append([])
                continue

            result_values = [
                {
                    "_distance": 1.0 - pt.score,
                    "id": pt.id,
                    "payload": pt.payload,
                }
                for pt in points
            ]
            normalized_values = normalize_distances(result_values)
            query_results = [
                ScoredResult(
                    id=parse_id(rv["id"]),
                    payload=rv["payload"],
                    score=normalized_values[j],
                )
                for j, rv in enumerate(result_values)
            ]
            all_results.append(query_results)

        return all_results

    # ── Index operations ────────────────────────────────────────────

    async def create_vector_index(
        self, index_name: str, index_property_name: str
    ):
        """Create a collection for vector index (same pattern as LanceDB)."""
        await self.create_collection(
            f"{index_name}_{index_property_name}",
            payload_schema=IndexSchema,
        )

    async def index_data_points(
        self,
        index_name: str,
        index_property_name: str,
        data_points: List[DataPoint],
    ):
        """Index data points by creating IndexSchema entries."""
        await self.create_data_points(
            f"{index_name}_{index_property_name}",
            [
                IndexSchema(
                    id=str(data_point.id),
                    text=getattr(
                        data_point,
                        data_point.metadata["index_fields"][0],
                    ),
                )
                for data_point in data_points
            ],
        )

    # ── Cleanup ─────────────────────────────────────────────────────

    async def prune(self):
        """Delete all collections."""
        client = await self.get_connection()
        collections = await client.get_collections()
        for collection in collections.collections:
            await client.delete_collection(collection.name)
            logger.info(f"Qdrant: deleted collection '{collection.name}'")

    # ── Schema (no-op for Qdrant) ───────────────────────────────────

    def get_data_point_schema(self, model_type):
        """Qdrant payloads are plain dicts — no schema transformation needed."""
        return model_type
