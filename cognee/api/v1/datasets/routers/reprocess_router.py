"""Router for reprocessing dataset files"""
from uuid import UUID
from typing import List
from pydantic import Field
from fastapi import APIRouter, Depends, HTTPException, status

from cognee.api.DTO import InDTO, OutDTO
from cognee.modules.users.models import User
from cognee.modules.users.methods import get_authenticated_user
from cognee.modules.data.methods import get_authorized_existing_datasets, get_data
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.shared.logging_utils import get_logger
from cognee.api.v1.exceptions import DatasetNotFoundError, DataNotFoundError
from cognee.shared.utils import send_telemetry
from cognee import __version__ as cognee_version

logger = get_logger()


class ReprocessPayloadDTO(InDTO):
    data_ids: List[UUID] = Field(description="List of data item IDs to reprocess")
    stages: List[str] = Field(
        default=["parsing", "chunking", "graph_indexing", "vector_indexing"],
        description="Stages to reprocess (parsing, chunking, graph_indexing, vector_indexing)"
    )
    run_in_background: bool = Field(
        default=True,
        description="Run processing in background"
    )


class ReprocessResponseDTO(OutDTO):
    pipeline_run_id: str
    dataset_id: str
    affected_data_ids: List[str]
    status: str


def get_reprocess_router() -> APIRouter:
    router = APIRouter()

    @router.post("/{dataset_id}/reprocess", response_model=ReprocessResponseDTO)
    async def reprocess_dataset_files(
        dataset_id: UUID,
        payload: ReprocessPayloadDTO,
        user: User = Depends(get_authenticated_user)
    ):
        """
        Batch reprocess data files in a dataset.

        This endpoint allows you to reprocess selected files through the cognify pipeline.
        Useful for retrying failed processing or reprocessing files with updated configurations.

        ## Path Parameters
        - **dataset_id** (UUID): The unique identifier of the dataset

        ## Request Body
        - **data_ids**: List of data item UUIDs to reprocess
        - **stages**: Pipeline stages to reprocess (default: all stages)
          - "parsing": Document parsing and text extraction
          - "chunking": Text segmentation into chunks
          - "graph_indexing": Knowledge graph construction
          - "vector_indexing": Vector embeddings generation
        - **run_in_background**: Run processing asynchronously (default: true)

        ## Response
        Returns processing information:
        - **pipeline_run_id**: ID to track the processing job
        - **dataset_id**: Dataset ID
        - **affected_data_ids**: List of data IDs being reprocessed
        - **status**: Current status ("initiated")

        ## Error Codes
        - **404 Not Found**: Dataset or data items don't exist
        - **403 Forbidden**: User doesn't have write permission
        - **500 Internal Server Error**: Error starting reprocessing
        """
        send_telemetry(
            "Datasets API Endpoint Invoked",
            user.id,
            additional_properties={
                "endpoint": f"POST /v1/datasets/{str(dataset_id)}/reprocess",
                "dataset_id": str(dataset_id),
                "data_count": len(payload.data_ids),
                "cognee_version": cognee_version,
            },
        )

        try:
            # Verify user has write permission on dataset
            dataset = await get_authorized_existing_datasets([dataset_id], "write", user)
            
            if not dataset or len(dataset) == 0:
                raise DatasetNotFoundError(
                    message=f"Dataset ({str(dataset_id)}) not found or no write permission."
                )

            # Get and validate data items
            data_items = []
            for data_id in payload.data_ids:
                data = await get_data(user.id, data_id)
                if data:
                    data_items.append(data)
                else:
                    logger.warning(f"Data item {data_id} not found, skipping")

            if len(data_items) == 0:
                raise DataNotFoundError(
                    message="None of the specified data items were found"
                )

            # Reset pipeline status for specified stages
            db_engine = get_relational_engine()
            async with db_engine.get_async_session() as session:
                for data in data_items:
                    if not data.pipeline_status:
                        data.pipeline_status = {}
                    
                    # Reset each specified stage to pending for this dataset
                    for stage in payload.stages:
                        if stage in ["parsing", "chunking", "graph_indexing", "vector_indexing"]:
                            stage_map = data.pipeline_status.get(stage) or {}
                            if not isinstance(stage_map, dict):
                                stage_map = {}
                            stage_map[str(dataset_id)] = {
                                "status": "pending",
                                "progress": 0,
                                "started_at": None,
                                "completed_at": None,
                                "error": None,
                            }
                            data.pipeline_status[stage] = stage_map
                    
                    session.add(data)
                
                await session.commit()

            # Trigger cognify processing
            from cognee.api.v1.cognify.cognify import cognify
            
            pipeline_runs = await cognify(
                datasets=[dataset_id],
                user=user,
                run_in_background=payload.run_in_background
            )

            pipeline_run_id = str(pipeline_runs[0].pipeline_run_id) if pipeline_runs else "unknown"

            return ReprocessResponseDTO(
                pipeline_run_id=pipeline_run_id,
                dataset_id=str(dataset_id),
                affected_data_ids=[str(data.id) for data in data_items],
                status="initiated"
            )

        except (DatasetNotFoundError, DataNotFoundError) as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as error:
            logger.error(f"Error reprocessing dataset files: {str(error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error reprocessing dataset files: {str(error)}"
            ) from error

    return router
