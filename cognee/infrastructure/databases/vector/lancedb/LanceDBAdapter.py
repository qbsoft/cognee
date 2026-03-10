import asyncio
from os import path
import lancedb
from pydantic import BaseModel
from lancedb.pydantic import LanceModel, Vector
from typing import Generic, List, Optional, TypeVar, Union, get_args, get_origin, get_type_hints

from cognee.infrastructure.databases.exceptions import MissingQueryParameterError
from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.engine.utils import parse_id
from cognee.infrastructure.files.storage import get_file_storage
from cognee.modules.storage.utils import copy_model, get_own_properties
from cognee.infrastructure.databases.vector.exceptions import CollectionNotFoundError

from ..embeddings.EmbeddingEngine import EmbeddingEngine
from ..models.ScoredResult import ScoredResult
from ..utils import normalize_distances
from ..vector_db_interface import VectorDBInterface

# 全局写入信号量：限制整个 LanceDB 同时执行的 merge_insert 操作数量
# 即使不同集合并发写入，LanceDB 底层的文件锁定机制仍可能冲突
# （20 个管道 × 7 个集合 = 140 个并发写入 → "Too many concurrent writers" 错误）
# 信号量限制为 3，确保同时最多 3 个写入操作，彻底消除并发写入错误
_LANCE_GLOBAL_WRITE_SEM: Optional[asyncio.Semaphore] = None

# 集合级写锁：同一集合的写入串行化（第二层保护）
_LANCE_COLLECTION_LOCKS: dict = {}

# 进程级压缩标志：每个进程只执行一次碎片压缩（在第一次写入前）
_COMPACTION_DONE: bool = False
_COMPACTION_LOCK: Optional[asyncio.Lock] = None


def _get_global_write_sem() -> asyncio.Semaphore:
    """获取全局写入信号量（懒初始化，限制并发 merge_insert 为 3）。"""
    global _LANCE_GLOBAL_WRITE_SEM
    if _LANCE_GLOBAL_WRITE_SEM is None:
        _LANCE_GLOBAL_WRITE_SEM = asyncio.Semaphore(3)
    return _LANCE_GLOBAL_WRITE_SEM


def _get_compaction_lock() -> asyncio.Lock:
    """获取进程级压缩锁（懒初始化）。"""
    global _COMPACTION_LOCK
    if _COMPACTION_LOCK is None:
        _COMPACTION_LOCK = asyncio.Lock()
    return _COMPACTION_LOCK


def _get_lance_write_lock(collection_name: str) -> asyncio.Lock:
    """获取指定集合的写锁（懒初始化）。"""
    if collection_name not in _LANCE_COLLECTION_LOCKS:
        _LANCE_COLLECTION_LOCKS[collection_name] = asyncio.Lock()
    return _LANCE_COLLECTION_LOCKS[collection_name]


class IndexSchema(DataPoint):
    """
    Represents a schema for an index data point containing an ID and text.

    Attributes:

    - id: A string representing the unique identifier for the data point.
    - text: A string representing the content of the data point.
    - metadata: A dictionary with default index fields for the schema, currently configured
    to include 'text'.
    """

    id: str
    text: str

    metadata: dict = {"index_fields": ["text"]}


class LanceDBAdapter(VectorDBInterface):
    name = "LanceDB"
    url: str
    api_key: str
    connection: lancedb.AsyncConnection = None

    def __init__(
        self,
        url: Optional[str],
        api_key: Optional[str],
        embedding_engine: EmbeddingEngine,
    ):
        self.url = url
        self.api_key = api_key
        self.embedding_engine = embedding_engine

    def _get_collection_lock(self, collection_name: str) -> asyncio.Lock:
        """返回指定集合的写锁，不同集合可以并发写入。"""
        return _get_lance_write_lock(collection_name)

    async def get_connection(self):
        """
        Establishes and returns a connection to the LanceDB.

        If a connection already exists, it will return the existing connection.

        Returns:
        --------

            - lancedb.AsyncConnection: An active connection to the LanceDB.
        """
        if self.connection is None:
            # Configure storage options for temporary directory
            import os
            storage_options = {}
            
            # Check if LANCE_TEMP_DIR environment variable is set
            lance_temp_dir = os.getenv('LANCE_TEMP_DIR')
            if lance_temp_dir:
                storage_options['temp_dir'] = lance_temp_dir
            
            self.connection = await lancedb.connect_async(
                self.url, 
                api_key=self.api_key,
                storage_options=storage_options if storage_options else None
            )

        return self.connection

    async def embed_data(self, data: list[str]) -> list[list[float]]:
        """
        Embeds the provided textual data into vector representation.

        Uses the embedding engine to convert the list of strings into a list of float vectors.

        Parameters:
        -----------

            - data (list[str]): A list of strings representing the data to be embedded.

        Returns:
        --------

            - list[list[float]]: A list of embedded vectors corresponding to the input data.
        """
        return await self.embedding_engine.embed_text(data)

    async def has_collection(self, collection_name: str) -> bool:
        """
        Checks if the specified collection exists in the LanceDB.

        Returns True if the collection is present, otherwise False.

        Parameters:
        -----------

            - collection_name (str): The name of the collection to check.

        Returns:
        --------

            - bool: True if the collection exists, otherwise False.
        """
        connection = await self.get_connection()
        collection_names = await connection.table_names()
        return collection_name in collection_names

    async def list_collections(self) -> list[str]:
        """
        Returns a list of all collection names in the LanceDB.

        Returns:
        --------

            - list[str]: A list of collection (table) names.
        """
        connection = await self.get_connection()
        return await connection.table_names()

    async def get_collection_size(self, collection_name: str) -> int:
        """
        Returns the number of vectors in the specified collection.

        Parameters:
        -----------

            - collection_name (str): The name of the collection.

        Returns:
        --------

            - int: The number of vectors in the collection.
        """
        if not await self.has_collection(collection_name):
            return 0
        
        collection = await self.get_collection(collection_name)
        return await collection.count_rows()

    async def create_collection(self, collection_name: str, payload_schema: BaseModel):
        vector_size = self.embedding_engine.get_vector_size()

        payload_schema = self.get_data_point_schema(payload_schema)
        data_point_types = get_type_hints(payload_schema)

        class LanceDataPoint(LanceModel):
            """
            Represents a data point in the Lance model with an ID, vector, and associated payload.

            The class inherits from LanceModel and defines the following public attributes:
            - id: A unique identifier for the data point.
            - vector: A vector representing the data point in a specified dimensional space.
            - payload: Additional data or metadata associated with the data point.
            """

            id: data_point_types["id"]
            vector: Vector(vector_size)
            payload: payload_schema

        if not await self.has_collection(collection_name):
            async with self._get_collection_lock(collection_name):
                if not await self.has_collection(collection_name):
                    connection = await self.get_connection()
                    return await connection.create_table(
                        name=collection_name,
                        schema=LanceDataPoint,
                        exist_ok=True,
                    )

    async def get_collection(self, collection_name: str):
        if not await self.has_collection(collection_name):
            raise CollectionNotFoundError(f"Collection '{collection_name}' not found!")

        connection = await self.get_connection()
        return await connection.open_table(collection_name)

    async def create_data_points(self, collection_name: str, data_points: list[DataPoint]):
        # 进程级一次性压缩：消除碎片化（每次 merge_insert 产生一个碎片文件，
        # 多次 cognify 后碎片 >6000，每次写入需要扫描全部 →  ~6.4s/次）
        # 压缩后碎片 <20，写入降至 ~0.5s/次，总体节省 30+ 分钟
        global _COMPACTION_DONE
        if not _COMPACTION_DONE:
            async with _get_compaction_lock():
                if not _COMPACTION_DONE:
                    await self.compact_all_collections()
                    _COMPACTION_DONE = True  # 压缩完成后再设置，确保并发调用在锁上等待

        payload_schema = type(data_points[0])

        if not await self.has_collection(collection_name):
            async with self._get_collection_lock(collection_name):
                if not await self.has_collection(collection_name):
                    # 注意：不能调用 self.create_collection()，因为该方法内部也会获取
                    # 同一个集合锁，asyncio.Lock 不可重入，会导致死锁。
                    # 因此直接内联建表逻辑。
                    vector_size_for_schema = self.embedding_engine.get_vector_size()
                    schema_for_collection = self.get_data_point_schema(payload_schema)
                    schema_types = get_type_hints(schema_for_collection)

                    class _LanceDataPointSchema(LanceModel):
                        id: schema_types["id"]
                        vector: Vector(vector_size_for_schema)
                        payload: schema_for_collection

                    connection = await self.get_connection()
                    await connection.create_table(
                        name=collection_name,
                        schema=_LanceDataPointSchema,
                        exist_ok=True,
                    )

        collection = await self.get_collection(collection_name)

        data_vectors = await self.embed_data(
            [DataPoint.get_embeddable_data(data_point) for data_point in data_points]
        )

        IdType = TypeVar("IdType")
        PayloadSchema = TypeVar("PayloadSchema")
        vector_size = self.embedding_engine.get_vector_size()

        class LanceDataPoint(LanceModel, Generic[IdType, PayloadSchema]):
            """
            Represents a data point in the Lance model with an ID, vector, and payload.

            This class encapsulates a data point consisting of an identifier, a vector representing
            the data, and an associated payload, allowing for operations and manipulations specific
            to the Lance data structure.
            """

            id: IdType
            vector: Vector(vector_size)
            payload: PayloadSchema

        def create_lance_data_point(data_point: DataPoint, vector: list[float]) -> LanceDataPoint:
            properties = get_own_properties(data_point)
            properties["id"] = str(properties["id"])

            return LanceDataPoint[str, self.get_data_point_schema(type(data_point))](
                id=str(data_point.id),
                vector=vector,
                payload=properties,
            )

        lance_data_points = [
            create_lance_data_point(data_point, data_vectors[data_point_index])
            for (data_point_index, data_point) in enumerate(data_points)
        ]

        async with _get_global_write_sem():
            async with self._get_collection_lock(collection_name):
                await (
                    collection.merge_insert("id")
                    .when_matched_update_all()
                    .when_not_matched_insert_all()
                    .execute(lance_data_points)
                )

    async def compact_collection(self, collection_name: str) -> None:
        """合并 LanceDB 碎片文件，加速后续读写。

        LanceDB 的 merge_insert/add 操作会产生大量小型 .lance 文件，
        碎片化越严重，每次写入的 merge_insert 扫描越慢。
        AsyncTable.optimize() 执行压缩 + 旧版本清理 + 索引优化。
        注意：同步 Table 有 compact_files()，但 AsyncTable 只有 optimize()。
        """
        try:
            if not await self.has_collection(collection_name):
                return
            collection = await self.get_collection(collection_name)
            await collection.optimize()
        except Exception as e:
            from cognee.shared.logging_utils import get_logger
            get_logger().warning(f"optimize failed for '{collection_name}': {e}")

    async def compact_all_collections(self) -> None:
        """Compact all existing LanceDB collections."""
        import time
        from cognee.shared.logging_utils import get_logger
        logger = get_logger()
        try:
            table_names = await self.list_collections()
            if not table_names:
                logger.info("No LanceDB collections to compact")
                return
            logger.info(f"Compacting {len(table_names)} LanceDB collections (defragmentation)...")
            t0 = time.time()
            for name in table_names:
                await self.compact_collection(name)
            elapsed = time.time() - t0
            logger.info(f"LanceDB compaction complete in {elapsed:.1f}s ({len(table_names)} collections)")
        except Exception as e:
            logger.warning(f"compact_all_collections failed: {e}")

    async def retrieve(self, collection_name: str, data_point_ids: list[str]):
        collection = await self.get_collection(collection_name)

        # AsyncQuery.where() returns AsyncQuery (not awaitable).
        # Must call .to_list() to get an awaitable coroutine → List[dict].
        if len(data_point_ids) == 1:
            results_list = await collection.query().where(f"id = '{data_point_ids[0]}'").to_list()
        else:
            results_list = await collection.query().where(f"id IN {tuple(data_point_ids)}").to_list()

        return [
            ScoredResult(
                id=parse_id(result["id"]),
                payload=result["payload"],
                score=0,
            )
            for result in results_list
        ]

    async def search(
        self,
        collection_name: str,
        query_text: str = None,
        query_vector: List[float] = None,
        limit: Optional[int] = 15,
        with_vector: bool = False,
        normalized: bool = True,
    ):
        if query_text is None and query_vector is None:
            raise MissingQueryParameterError()

        if query_text and not query_vector:
            query_vector = (await self.embedding_engine.embed_text([query_text]))[0]

        collection = await self.get_collection(collection_name)

        if limit is None:
            limit = await collection.count_rows()

        # LanceDB search will break if limit is 0 so we must return
        if limit <= 0:
            return []

        result_values = await collection.vector_search(query_vector).limit(limit).to_list()

        if not result_values:
            return []

        normalized_values = normalize_distances(result_values)

        return [
            ScoredResult(
                id=parse_id(result["id"]),
                payload=result["payload"],
                score=normalized_values[value_index],
            )
            for value_index, result in enumerate(result_values)
        ]

    async def batch_search(
        self,
        collection_name: str,
        query_texts: List[str],
        limit: Optional[int] = None,
        with_vectors: bool = False,
    ):
        query_vectors = await self.embedding_engine.embed_text(query_texts)

        return await asyncio.gather(
            *[
                self.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=limit,
                    with_vector=with_vectors,
                )
                for query_vector in query_vectors
            ]
        )

    async def delete_data_points(self, collection_name: str, data_point_ids: list[str]):
        collection = await self.get_collection(collection_name)

        # Delete one at a time to avoid commit conflicts
        for data_point_id in data_point_ids:
            await collection.delete(f"id = '{data_point_id}'")

    async def create_vector_index(self, index_name: str, index_property_name: str):
        await self.create_collection(
            f"{index_name}_{index_property_name}", payload_schema=IndexSchema
        )

    async def index_data_points(
        self, index_name: str, index_property_name: str, data_points: list[DataPoint]
    ):
        await self.create_data_points(
            f"{index_name}_{index_property_name}",
            [
                IndexSchema(
                    id=str(data_point.id),
                    text=getattr(data_point, data_point.metadata["index_fields"][0]),
                )
                for data_point in data_points
            ],
        )

    async def prune(self):
        connection = await self.get_connection()
        collection_names = await connection.table_names()

        for collection_name in collection_names:
            collection = await self.get_collection(collection_name)
            await collection.delete("id IS NOT NULL")
            await connection.drop_table(collection_name)

        if self.url.startswith("/"):
            db_dir_path = path.dirname(self.url)
            db_file_name = path.basename(self.url)
            await get_file_storage(db_dir_path).remove_all(db_file_name)

    def get_data_point_schema(self, model_type: BaseModel):
        related_models_fields = []
        for field_name, field_config in model_type.model_fields.items():
            if hasattr(field_config, "model_fields"):
                related_models_fields.append(field_name)

            elif hasattr(field_config.annotation, "model_fields"):
                related_models_fields.append(field_name)

            elif (
                get_origin(field_config.annotation) == Union
                or get_origin(field_config.annotation) is list
            ):
                models_list = get_args(field_config.annotation)
                if any(hasattr(model, "model_fields") for model in models_list):
                    related_models_fields.append(field_name)
                elif models_list and any(get_args(model) is DataPoint for model in models_list):
                    related_models_fields.append(field_name)
                elif models_list and any(
                    submodel is DataPoint for submodel in get_args(models_list[0])
                ):
                    related_models_fields.append(field_name)

            elif get_origin(field_config.annotation) == Optional:
                model = get_args(field_config.annotation)
                if hasattr(model, "model_fields"):
                    related_models_fields.append(field_name)

        return copy_model(
            model_type,
            include_fields={
                "id": (str, ...),
            },
            exclude_fields=["metadata"] + related_models_fields,
        )
