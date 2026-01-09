from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from typing_extensions import Annotated
from fastapi import status
from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException, Query, Depends, Response, Body
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

from cognee.api.DTO import InDTO, OutDTO
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.modules.data.methods import get_authorized_existing_datasets
from cognee.modules.data.methods import create_dataset, get_datasets_by_name
from cognee.shared.logging_utils import get_logger
from cognee.api.v1.exceptions import DataNotFoundError, DatasetNotFoundError
from cognee.modules.users.models import User
from cognee.modules.users.methods import get_authenticated_user
from cognee.modules.users.permissions.methods import (
    get_all_user_permission_datasets,
    give_permission_on_dataset,
)
from cognee.modules.graph.methods import get_formatted_graph_data
from cognee.modules.pipelines.models import PipelineRunStatus
from cognee.shared.utils import send_telemetry
from cognee import __version__ as cognee_version
from cognee.infrastructure.files.storage import get_file_storage
from cognee.infrastructure.files.utils.get_data_file_path import get_data_file_path
import os
from urllib.parse import quote

logger = get_logger()


class ErrorResponseDTO(BaseModel):
    message: str


class DatasetDTO(OutDTO):
    id: UUID
    name: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    owner_id: UUID


class StageStatusDTO(OutDTO):
    status: str = "pending"  # 'pending' | 'in_progress' | 'completed' | 'failed' - default to pending
    progress: Optional[int] = None  # 0-100
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    # Stage-specific counts
    chunk_count: Optional[int] = None
    node_count: Optional[int] = None
    edge_count: Optional[int] = None
    vector_count: Optional[int] = None


class PipelineStatusDTO(OutDTO):
    parsing: Optional[StageStatusDTO] = None
    chunking: Optional[StageStatusDTO] = None
    graph_indexing: Optional[StageStatusDTO] = None
    vector_indexing: Optional[StageStatusDTO] = None


class DataStatsDTO(OutDTO):
    chunk_count: Optional[int] = None
    node_count: Optional[int] = None
    edge_count: Optional[int] = None
    vector_count: Optional[int] = None


class DataDTO(OutDTO):
    id: UUID
    name: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    extension: str
    mime_type: str
    raw_data_location: str
    dataset_id: UUID
    data_size: Optional[int] = None
    token_count: Optional[int] = None
    pipeline_status: Optional[PipelineStatusDTO] = None
    stats: Optional[DataStatsDTO] = None


class GraphNodeDTO(OutDTO):
    id: UUID
    label: str
    properties: dict


class GraphEdgeDTO(OutDTO):
    source: UUID
    target: UUID
    label: str


class GraphDTO(OutDTO):
    nodes: List[GraphNodeDTO]
    edges: List[GraphEdgeDTO]


class DatasetCreationPayload(InDTO):
    name: str


def get_datasets_router() -> APIRouter:
    router = APIRouter()

    @router.get("", response_model=list[DatasetDTO])
    async def get_datasets(user: User = Depends(get_authenticated_user)):
        """
        Get all datasets accessible to the authenticated user.

        This endpoint retrieves all datasets that the authenticated user has
        read permissions for. The datasets are returned with their metadata
        including ID, name, creation time, and owner information.

        ## Response
        Returns a list of dataset objects containing:
        - **id**: Unique dataset identifier
        - **name**: Dataset name
        - **created_at**: When the dataset was created
        - **updated_at**: When the dataset was last updated
        - **owner_id**: ID of the dataset owner

        ## Error Codes
        - **418 I'm a teapot**: Error retrieving datasets
        """
        send_telemetry(
            "Datasets API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": "GET /v1/datasets",
                "cognee_version": cognee_version,
            },
        )

        try:
            datasets = await get_all_user_permission_datasets(user, "read")

            return datasets
        except Exception as error:
            logger.error(f"Error retrieving datasets: {str(error)}")
            raise HTTPException(
                status_code=status.HTTP_418_IM_A_TEAPOT,
                detail=f"Error retrieving datasets: {str(error)}",
            ) from error

    @router.post("", response_model=DatasetDTO)
    async def create_new_dataset(
        dataset_data: DatasetCreationPayload,
        user: User = Depends(get_authenticated_user),
    ):
        """
        Create a new dataset or return existing dataset with the same name.

        This endpoint creates a new dataset with the specified name. If a dataset
        with the same name already exists for the user, it returns the existing
        dataset instead of creating a duplicate. The user is automatically granted
        all permissions (read, write, share, delete) on the created dataset.

        ## Request Parameters
        - **dataset_data** (DatasetCreationPayload): Dataset creation parameters containing:
          - **name**: The name for the new dataset

        ## Response
        Returns the created or existing dataset object containing:
        - **id**: Unique dataset identifier
        - **name**: Dataset name
        - **created_at**: When the dataset was created
        - **updated_at**: When the dataset was last updated
        - **owner_id**: ID of the dataset owner

        ## Error Codes
        - **418 I'm a teapot**: Error creating dataset
        """
        send_telemetry(
            "Datasets API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": "POST /v1/datasets",
                "cognee_version": cognee_version,
            },
        )

        try:
            datasets = await get_datasets_by_name([dataset_data.name], user.id)

            if datasets:
                return datasets[0]

            db_engine = get_relational_engine()
            async with db_engine.get_async_session() as session:
                dataset = await create_dataset(
                    dataset_name=dataset_data.name, user=user, session=session
                )

                await give_permission_on_dataset(user, dataset.id, "read")
                await give_permission_on_dataset(user, dataset.id, "write")
                await give_permission_on_dataset(user, dataset.id, "share")
                await give_permission_on_dataset(user, dataset.id, "delete")

                return dataset
        except Exception as error:
            logger.error(f"Error creating dataset: {str(error)}")
            raise HTTPException(
                status_code=status.HTTP_418_IM_A_TEAPOT,
                detail=f"Error creating dataset: {str(error)}",
            ) from error

    @router.delete(
        "/{dataset_id}", response_model=None, responses={404: {"model": ErrorResponseDTO}}
    )
    async def delete_dataset(dataset_id: UUID, user: User = Depends(get_authenticated_user)):
        """
        Delete a dataset by its ID.

        This endpoint permanently deletes a dataset and all its associated data.
        The user must have delete permissions on the dataset to perform this operation.

        ## Path Parameters
        - **dataset_id** (UUID): The unique identifier of the dataset to delete

        ## Response
        No content returned on successful deletion.

        ## Error Codes
        - **404 Not Found**: Dataset doesn't exist or user doesn't have access
        - **500 Internal Server Error**: Error during deletion
        """
        send_telemetry(
            "Datasets API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"DELETE /v1/datasets/{str(dataset_id)}",
                "dataset_id": str(dataset_id),
                "cognee_version": cognee_version,
            },
        )

        from cognee.modules.data.methods import get_dataset, delete_dataset

        dataset = await get_dataset(user.id, dataset_id)

        if dataset is None:
            raise DatasetNotFoundError(message=f"Dataset ({str(dataset_id)}) not found.")

        await delete_dataset(dataset)

    @router.delete(
        "/{dataset_id}/data/{data_id}",
        response_model=None,
        responses={404: {"model": ErrorResponseDTO}},
    )
    async def delete_data(
        dataset_id: UUID, 
        data_id: UUID, 
        mode: str = "soft",
        user: User = Depends(get_authenticated_user)
    ):
        """
        Delete a specific data item from a dataset with cascade deletion.

        This endpoint removes a specific data item from a dataset along with all
        its associated data including chunks, graph nodes/edges, and vector embeddings.
        The user must have delete permissions on the dataset to perform this operation.

        ## Path Parameters
        - **dataset_id** (UUID): The unique identifier of the dataset containing the data
        - **data_id** (UUID): The unique identifier of the data item to delete

        ## Query Parameters
        - **mode** (str): Deletion mode - "soft" (default) or "hard"
          - soft: Removes the data but keeps related entities that might be shared
          - hard: Also removes degree-one entity nodes that become orphaned

        ## Response
        Returns deletion details including:
        - Deleted node counts (chunks, entities, etc.)
        - Deleted vector counts

        ## Error Codes
        - **404 Not Found**: Dataset or data item doesn't exist, or user doesn't have access
        - **500 Internal Server Error**: Error during deletion
        """
        send_telemetry(
            "Datasets API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"DELETE /v1/datasets/{str(dataset_id)}/data/{str(data_id)}",
                "dataset_id": str(dataset_id),
                "data_id": str(data_id),
                "deletion_mode": mode,
                "cognee_version": cognee_version,
            },
        )

        try:
            # Use the comprehensive cascade deletion from cognee.api.v1.delete
            from cognee.api.v1.delete.delete import delete as delete_cascade
            
            result = await delete_cascade(
                data_id=data_id,
                dataset_id=dataset_id,
                mode=mode,
                user=user
            )
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "Data deleted successfully with cascade",
                    "dataId": str(data_id),
                    "deletedCounts": result.get("graph_deletions", {}),
                    "deletedNodeIds": result.get("deleted_node_ids", [])
                }
            )
        except (DatasetNotFoundError, DataNotFoundError) as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as error:
            logger.error(f"Error deleting data: {str(error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error deleting data: {str(error)}"
            ) from error

    @router.get("/{dataset_id}/graph", response_model=GraphDTO)
    async def get_dataset_graph(dataset_id: UUID, user: User = Depends(get_authenticated_user)):
        """
        Get the knowledge graph visualization for a dataset.

        This endpoint retrieves the knowledge graph data for a specific dataset,
        including nodes and edges that represent the relationships between entities
        in the dataset. The graph data is formatted for visualization purposes.

        ## Path Parameters
        - **dataset_id** (UUID): The unique identifier of the dataset

        ## Response
        Returns the graph data containing:
        - **nodes**: List of graph nodes with id, label, and properties
        - **edges**: List of graph edges with source, target, and label

        ## Error Codes
        - **404 Not Found**: Dataset doesn't exist or user doesn't have access
        - **500 Internal Server Error**: Error retrieving graph data
        """

        graph_data = await get_formatted_graph_data(dataset_id, user)

        return graph_data

    @router.get(
        "/{dataset_id}/data",
        responses={404: {"model": ErrorResponseDTO}},
    )
    async def get_dataset_data(dataset_id: UUID, user: User = Depends(get_authenticated_user)):
        """
        Get all data items in a dataset with detailed processing status.

        This endpoint retrieves all data items (documents, files, etc.) that belong
        to a specific dataset. Each data item includes metadata, processing status,
        and statistics about chunks, graph nodes, and vectors.

        ## Path Parameters
        - **dataset_id** (UUID): The unique identifier of the dataset

        ## Response
        Returns a list of data objects containing:
        - **id**: Unique data item identifier
        - **name**: Data item name
        - **created_at**: When the data was added
        - **updated_at**: When the data was last updated
        - **extension**: File extension
        - **mime_type**: MIME type of the data
        - **raw_data_location**: Storage location of the raw data
        - **data_size**: File size in bytes
        - **token_count**: Number of tokens
        - **pipeline_status**: Processing status for each stage (parsing, chunking, graph_indexing, vector_indexing)
        - **stats**: Statistics (chunk_count, node_count, edge_count, vector_count)

        ## Error Codes
        - **404 Not Found**: Dataset doesn't exist or user doesn't have access
        - **500 Internal Server Error**: Error retrieving data
        """
        send_telemetry(
            "Datasets API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"GET /v1/datasets/{str(dataset_id)}/data",
                "dataset_id": str(dataset_id),
                "cognee_version": cognee_version,
            },
        )

        from cognee.modules.data.methods import get_dataset_data
        from cognee.modules.data.methods.get_data_stats import get_batch_data_stats

        # Verify user has permission to read dataset
        dataset = await get_authorized_existing_datasets([dataset_id], "read", user)

        if dataset is None:
            return JSONResponse(
                status_code=404,
                content=ErrorResponseDTO(f"Dataset ({str(dataset_id)}) not found."),
            )

        dataset_id = dataset[0].id

        dataset_data = await get_dataset_data(dataset_id=dataset_id)

        if dataset_data is None or len(dataset_data) == 0:
            return []

        # Get stats for all data items in batch
        data_ids = [data.id for data in dataset_data]
        stats_map = await get_batch_data_stats(data_ids)

        # Build response with enhanced data
        result = []
        for data in dataset_data:
            data_dict = jsonable_encoder(data)
            data_dict["dataset_id"] = str(dataset_id)
            
            # Parse and format pipeline_status
            pipeline_status = data.pipeline_status or {}
            formatted_pipeline_status = {}

            # Debug log: print raw pipeline_status from database
            logger.info(f"[DEBUG] Data {data.id} raw pipeline_status: {pipeline_status}")

            current_dataset_id_str = str(dataset_id)

            for stage in ["parsing", "chunking", "graph_indexing", "vector_indexing"]:
                stage_map = pipeline_status.get(stage) or {}

                stage_status = None
                if isinstance(stage_map, dict):
                    stage_status = stage_map.get(current_dataset_id_str)

                if not stage_status:
                    # Default to pending if no status recorded for this dataset
                    stage_status = {
                        "status": "pending",
                        "progress": 0,
                    }

                formatted_pipeline_status[stage] = stage_status

            # Debug log: print formatted pipeline_status
            logger.info(f"[DEBUG] Data {data.id} formatted pipeline_status: {formatted_pipeline_status}")

            data_dict["pipeline_status"] = formatted_pipeline_status
            
            # Add stats
            data_dict["stats"] = stats_map.get(data.id, {})
            
            result.append(data_dict)

        return JSONResponse(
            status_code=200,
            content=result
        )

    @router.post("/{dataset_id}/data/batch-delete")
    async def batch_delete_data(
        dataset_id: UUID,
        data_ids: List[UUID] = Body(..., embed=True),
        mode: str = Body("soft", embed=True),
        user: User = Depends(get_authenticated_user)
    ):
        """
        Batch delete multiple data items from a dataset.

        This endpoint removes multiple data items from a dataset with cascade deletion
        of all associated data (chunks, graph nodes, vectors). This is more efficient
        than deleting files one by one.

        ## Path Parameters
        - **dataset_id** (UUID): The unique identifier of the dataset

        ## Request Body
        - **data_ids** (List[UUID]): List of data item UUIDs to delete
        - **mode** (str): Deletion mode - "soft" (default) or "hard"

        ## Response
        Returns summary of deletion operation:
        - Total deleted count
        - Deleted data IDs
        - Aggregate counts (chunks, nodes, vectors)

        ## Error Codes
        - **404 Not Found**: Dataset doesn't exist or user doesn't have access
        - **500 Internal Server Error**: Error during deletion
        """
        send_telemetry(
            "Datasets API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"POST /v1/datasets/{str(dataset_id)}/data/batch-delete",
                "dataset_id": str(dataset_id),
                "data_count": len(data_ids),
                "deletion_mode": mode,
                "cognee_version": cognee_version,
            },
        )

        try:
            from cognee.api.v1.delete.delete import delete as delete_cascade
            from cognee.modules.data.methods import get_data

            # Verify user has delete permission on dataset
            dataset = await get_authorized_existing_datasets([dataset_id], "delete", user)
            
            if not dataset or len(dataset) == 0:
                raise DatasetNotFoundError(
                    message=f"Dataset ({str(dataset_id)}) not found or no delete permission."
                )

            # Delete each file and collect results
            deleted_data_ids = []
            total_chunks = 0
            total_nodes = 0
            total_vectors = 0
            failed_deletions = []

            for data_id in data_ids:
                try:
                    # Check if data exists
                    data = await get_data(user.id, data_id)
                    if not data:
                        logger.warning(f"Data item {data_id} not found, skipping")
                        failed_deletions.append({
                            "dataId": str(data_id),
                            "error": "Data not found"
                        })
                        continue

                    # Perform cascade deletion
                    result = await delete_cascade(
                        data_id=data_id,
                        dataset_id=dataset_id,
                        mode=mode,
                        user=user
                    )

                    deleted_data_ids.append(str(data_id))
                    
                    # Aggregate deletion counts
                    graph_deletions = result.get("graph_deletions", {})
                    total_chunks += graph_deletions.get("chunks", 0)
                    total_nodes += sum(graph_deletions.values())
                    total_vectors += len(result.get("deleted_node_ids", []))

                except Exception as e:
                    logger.error(f"Error deleting data {data_id}: {str(e)}")
                    failed_deletions.append({
                        "dataId": str(data_id),
                        "error": str(e)
                    })

            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "deletedCount": len(deleted_data_ids),
                    "deletedDataIds": deleted_data_ids,
                    "deletedChunkCount": total_chunks,
                    "deletedNodeCount": total_nodes,
                    "deletedVectorCount": total_vectors,
                    "failedDeletions": failed_deletions
                }
            )

        except DatasetNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as error:
            logger.error(f"Error in batch delete: {str(error)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error in batch delete: {str(error)}"
            ) from error

    @router.get("/status", response_model=dict[str, PipelineRunStatus])
    async def get_dataset_status(
        datasets: Annotated[List[UUID], Query(alias="dataset")] = [],
        user: User = Depends(get_authenticated_user),
    ):
        """
        Get the processing status of datasets.

        This endpoint retrieves the current processing status of one or more datasets,
        indicating whether they are being processed, have completed processing, or
        encountered errors during pipeline execution.

        ## Query Parameters
        - **dataset** (List[UUID]): List of dataset UUIDs to check status for

        ## Response
        Returns a dictionary mapping dataset IDs to their processing status:
        - **pending**: Dataset is queued for processing
        - **running**: Dataset is currently being processed
        - **completed**: Dataset processing completed successfully
        - **failed**: Dataset processing encountered an error

        ## Error Codes
        - **500 Internal Server Error**: Error retrieving status information
        """
        send_telemetry(
            "Datasets API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": "GET /v1/datasets/status",
                "datasets": [str(dataset_id) for dataset_id in datasets],
                "cognee_version": cognee_version,
            },
        )

        from cognee.api.v1.datasets.datasets import datasets as cognee_datasets

        try:
            # Verify user has permission to read dataset
            authorized_datasets = await get_authorized_existing_datasets(datasets, "read", user)

            datasets_statuses = await cognee_datasets.get_status(
                [dataset.id for dataset in authorized_datasets]
            )

            return datasets_statuses
        except Exception as error:
            return JSONResponse(status_code=409, content={"error": str(error)})

    @router.get("/{dataset_id}/data/{data_id}/raw", response_class=StreamingResponse)
    async def get_raw_data(
        dataset_id: UUID, data_id: UUID, user: User = Depends(get_authenticated_user)
    ):
        """
        Download the raw data file for a specific data item.

        This endpoint allows users to download the original, unprocessed data file
        for a specific data item within a dataset. The file is returned as a direct
        download with appropriate headers.

        ## Path Parameters
        - **dataset_id** (UUID): The unique identifier of the dataset containing the data
        - **data_id** (UUID): The unique identifier of the data item to download

        ## Response
        Returns the raw data file as a downloadable response.

        ## Error Codes
        - **404 Not Found**: Dataset or data item doesn't exist, or user doesn't have access
        - **500 Internal Server Error**: Error accessing the raw data file
        """
        send_telemetry(
            "Datasets API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"GET /v1/datasets/{str(dataset_id)}/data/{str(data_id)}/raw",
                "dataset_id": str(dataset_id),
                "data_id": str(data_id),
                "cognee_version": cognee_version,
            },
        )

        from cognee.modules.data.methods import get_data
        from cognee.modules.data.methods import get_dataset_data

        # Verify user has permission to read dataset
        dataset = await get_authorized_existing_datasets([dataset_id], "read", user)

        if dataset is None:
            return JSONResponse(
                status_code=404, content={"detail": f"Dataset ({dataset_id}) not found."}
            )

        dataset_data = await get_dataset_data(dataset[0].id)

        if dataset_data is None:
            raise DataNotFoundError(message=f"No data found in dataset ({dataset_id}).")

        matching_data = [data for data in dataset_data if data.id == data_id]

        # Check if matching_data contains an element
        if len(matching_data) == 0:
            raise DataNotFoundError(
                message=f"Data ({data_id}) not found in dataset ({dataset_id})."
            )

        data = await get_data(user.id, data_id)

        if data is None:
            raise DataNotFoundError(
                message=f"Data ({data_id}) not found in dataset ({dataset_id})."
            )

        # Get file storage and return the actual file
        try:
            raw_data_location = data.raw_data_location
            logger.info(f"Attempting to retrieve file from: {raw_data_location}")
            
            # Use get_data_file_path to handle file:// prefix correctly
            actual_file_path = get_data_file_path(raw_data_location)
            logger.info(f"Actual file path after processing: {actual_file_path}")
            
            # Normalize path for Windows
            normalized_path = os.path.normpath(actual_file_path)
            file_dir = os.path.dirname(normalized_path)
            file_name = os.path.basename(normalized_path)
            
            logger.info(f"File directory: {file_dir}, File name: {file_name}")
            
            file_storage = get_file_storage(file_dir)
            
            # Check if file exists
            file_exists = await file_storage.file_exists(file_name)
            logger.info(f"File exists check: {file_exists}")
            
            if not file_exists:
                logger.error(f"File not found at location: {raw_data_location}")
                raise DataNotFoundError(
                    message=f"File not found at location: {raw_data_location}"
                )
            
            # Return FileResponse with the actual file path
            # For local storage, we need the full path
            full_path = normalized_path
            
            logger.info(f"Returning file: {full_path} with media type: {data.mime_type}")
            
            # Read file content at once for smaller files
            # This ensures file is properly closed and CORS headers work correctly
            file_content = b""
            async with file_storage.open(file_name, mode="rb") as file:
                # Read file in chunks
                chunk_size = 8192
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    file_content += chunk
            
            # Return as StreamingResponse with proper headers
            from io import BytesIO
            
            async def file_iterator():
                yield file_content
            
            # Encode filename for Content-Disposition header
            # Use both filename and filename* for maximum compatibility
            try:
                # Try ASCII encoding first
                data.name.encode('ascii')
                # Pure ASCII filename - use simple format
                filename_header = f'inline; filename="{data.name}"'
            except UnicodeEncodeError:
                # Non-ASCII characters - use dual encoding for compatibility
                # filename with ASCII fallback + filename* with UTF-8 encoding
                ascii_fallback = 'file'  # Simple fallback for old browsers
                encoded_filename = quote(data.name, safe='')
                # Both filename and filename* for maximum browser compatibility
                filename_header = f"inline; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_filename}"
            
            response = StreamingResponse(
                file_iterator(),
                media_type=data.mime_type or "application/octet-stream",
                headers={
                    "Content-Disposition": filename_header,
                    "Content-Length": str(len(file_content)),
                }
            )
            
            return response
        except DataNotFoundError:
            # Re-raise DataNotFoundError to maintain expected error handling
            raise
        except Exception as e:
            logger.error(f"Error retrieving raw data file: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving raw data file: {str(e)}"
            )

    @router.post("/{dataset_id}/reprocess")
    async def reprocess_dataset_files(
        dataset_id: UUID,
        data_ids: List[UUID] = Body(..., embed=True),
        stages: List[str] = Body(["parsing", "chunking", "graph_indexing", "vector_indexing"], embed=True),
        run_in_background: bool = Body(True, embed=True),
        user: User = Depends(get_authenticated_user)
    ):
        """
        Reprocess all data files in a dataset.

        This endpoint resets pipeline status and re-runs the cognify pipeline for all files
        in the specified dataset to ensure consistency after failures or config changes.

        ## Path Parameters
        - **dataset_id** (UUID): The unique identifier of the dataset

        ## Request Parameters
        - **data_ids**: List of data item UUIDs to reprocess
        - **stages**: Pipeline stages to reprocess (default: all stages)
        - **run_in_background**: Run processing asynchronously (default: true)

        ## Response
        Returns processing information with pipeline_run_id and affected data IDs.

        ## Error Codes
        - **404 Not Found**: Dataset or data items don't exist
        - **403 Forbidden**: User doesn't have write permission
        - **500 Internal Server Error**: Error starting reprocessing
        """
        logger.info(f"[REPROCESS] 收到重新处理请求: dataset_id={dataset_id}, data_count={len(data_ids)}, run_in_background={run_in_background}")
        
        send_telemetry(
            "Datasets API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"POST /v1/datasets/{str(dataset_id)}/reprocess",
                "dataset_id": str(dataset_id),
                "data_count": len(data_ids),
                "cognee_version": cognee_version,
            },
        )

        try:
            from cognee.modules.data.methods import get_dataset_data

            # Verify user has write permission on dataset
            dataset = await get_authorized_existing_datasets([dataset_id], "write", user)
            
            if not dataset or len(dataset) == 0:
                raise DatasetNotFoundError(
                    message=f"Dataset ({str(dataset_id)}) not found or no write permission."
                )

            # Get all data items in the dataset for full reprocessing
            dataset_internal_id = dataset[0].id
            data_items = await get_dataset_data(dataset_id=dataset_internal_id)

            if not data_items or len(data_items) == 0:
                raise DataNotFoundError(
                    message="No data items found in dataset to reprocess"
                )

            # Reset pipeline status for specified stages
            db_engine = get_relational_engine()
            async with db_engine.get_async_session() as session:
                for data in data_items:
                    if not data.pipeline_status:
                        data.pipeline_status = {}
                    
                    # Reset each specified stage to pending
                    for stage in stages:
                        if stage in ["parsing", "chunking", "graph_indexing", "vector_indexing"]:
                            data.pipeline_status[stage] = {
                                "status": "pending",
                                "progress": 0,
                                "started_at": None,
                                "completed_at": None,
                                "error": None
                            }
                    
                    # Clear old incremental loading status to force reprocessing
                    if "cognify_pipeline" in data.pipeline_status:
                        dataset_status = data.pipeline_status.get("cognify_pipeline", {})
                        if str(dataset_id) in dataset_status:
                            del dataset_status[str(dataset_id)]
                    
                    session.add(data)
                
                await session.commit()

            logger.info(f"[REPROCESS] 已重置 {len(data_items)} 个文件的pipeline_status为 pending")

            # Trigger cognify processing with incremental_loading=False to force reprocessing
            from cognee.api.v1.cognify.cognify import cognify
            from cognee.modules.pipelines.models import PipelineRun
            from sqlalchemy import delete as sql_delete
            
            # Delete old PipelineRun records to bypass dataset-level incremental check
            async with db_engine.get_async_session() as session:
                await session.execute(
                    sql_delete(PipelineRun).where(
                        PipelineRun.dataset_id == dataset_id,
                        PipelineRun.pipeline_name == "cognify_pipeline"
                    )
                )
                await session.commit()
            
            logger.info(f"[REPROCESS] 已删除旧的 PipelineRun 记录")
            
            pipeline_runs = await cognify(
                datasets=[dataset_id],
                user=user,
                run_in_background=run_in_background,
                incremental_loading=False  # Force reprocessing, ignore existing status
            )

            logger.info(f"[REPROCESS] Cognify 返回结果: {pipeline_runs}, 类型: {type(pipeline_runs)}")

            # Handle different return types based on run_in_background
            if run_in_background:
                # Background mode returns dict: {dataset_id: PipelineRunInfo}
                if isinstance(pipeline_runs, dict):
                    if dataset_id in pipeline_runs:
                        pipeline_run_id = str(pipeline_runs[dataset_id].pipeline_run_id)
                    else:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Pipeline started but dataset {dataset_id} not found in response"
                        )
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="Unexpected pipeline response format"
                    )
            else:
                # Blocking mode returns list
                if not pipeline_runs or len(pipeline_runs) == 0:
                    raise HTTPException(
                        status_code=500,
                        detail="Cognify pipeline failed to start. No pipeline runs were created."
                    )
                pipeline_run_id = str(pipeline_runs[0].pipeline_run_id)

            return {
                "pipelineRunId": pipeline_run_id,
                "datasetId": str(dataset_id),
                "affectedDataIds": [str(data.id) for data in data_items],
                "status": "initiated"
            }

        except (DatasetNotFoundError, DataNotFoundError) as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as error:
            logger.error(f"Error reprocessing dataset files: {str(error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error reprocessing dataset files: {str(error)}"
            ) from error

    return router
