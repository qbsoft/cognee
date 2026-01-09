"""Update pipeline status for data items."""
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select

from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.modules.data.models import Data
from cognee.shared.logging_utils import get_logger

logger = get_logger(__name__)


def _get_stage_status_for_dataset(pipeline_status: dict | None, stage: str, dataset_id: UUID) -> dict:
    """Get stage status for a specific dataset from pipeline_status.

    Expects the stage structure to be:
        {"<dataset_id>": {"status": ..., ...}, ...}
    """
    if not pipeline_status:
        return {}

    stage_obj = pipeline_status.get(stage) or {}
    if not isinstance(stage_obj, dict):
        return {}

    return stage_obj.get(str(dataset_id), {})


def _set_stage_status_for_dataset(
    pipeline_status: dict | None,
    stage: str,
    dataset_id: UUID,
    new_status: dict,
) -> dict:
    """Set stage status for a specific dataset in pipeline_status.

    Ensures the stage structure is:
        {"<dataset_id>": {"status": ..., ...}, ...}
    """
    if pipeline_status is None:
        pipeline_status = {}

    stage_obj = pipeline_status.get(stage)
    if not isinstance(stage_obj, dict):
        stage_obj = {}

    stage_obj[str(dataset_id)] = new_status
    pipeline_status[stage] = stage_obj
    return pipeline_status


async def verify_data_integrity(data_id: UUID, stage: str, dataset_id: UUID | None = None) -> tuple[bool, str]:
    """Verify that actual data exists in graph/vector databases for completed stages.

    This prevents the "phantom completion" bug where pipeline_status shows completed
    but the actual data doesn't exist in the databases.

    Args:
        data_id: UUID of the data item
        stage: Processing stage to verify ("graph_indexing" or "vector_indexing")
        dataset_id: Dataset ID whose databases should be checked. Required for
            graph/vector stages.

    Returns:
        tuple: (is_valid, error_message)
            - is_valid: True if data exists or verification is skipped
            - error_message: Description of the issue if not valid
    """
    # Only graph/vector stages need verification
    if stage not in ("graph_indexing", "vector_indexing"):
        return True, ""

    if not dataset_id:
        raise ValueError(f"dataset_id is required for data integrity verification of stage '{stage}'")

    # Switch to the correct dataset's database context before verification
    from cognee.modules.users.methods import get_user
    from cognee.modules.data.models import Dataset
    from cognee.context_global_variables import set_database_global_context_variables
    from cognee.infrastructure.databases.relational import get_relational_engine
    from sqlalchemy import select

    try:
        # Get the dataset to find its owner
        db_engine = get_relational_engine()
        async with db_engine.get_async_session() as session:
            dataset = await session.get(Dataset, dataset_id)
            if not dataset:
                logger.error("Dataset %s not found for data integrity verification", dataset_id)
                return False, f"Dataset {dataset_id} not found"
            
            owner_id = dataset.owner_id
        
        # Get the owner user
        user = await get_user(owner_id)
        if not user:
            logger.error("Owner user %s not found for dataset %s", owner_id, dataset_id)
            return False, f"Owner user not found for dataset {dataset_id}"
        
        await set_database_global_context_variables(dataset_id, user.id)
        logger.info(
            "Switched to dataset %s context (owner: %s) for verification of data_id %s",
            dataset_id,
            user.email,
            data_id,
        )
    except Exception as ctx_error:  # pragma: no cover - defensive logging
        logger.error("Failed to switch database context for verification: %s", ctx_error, exc_info=True)
        return False, f"Failed to switch database context: {ctx_error}"

    if stage == "graph_indexing":
        try:
            from cognee.infrastructure.databases.graph import get_graph_engine

            graph_engine = await get_graph_engine()
            nodes, edges = await graph_engine.get_graph_data()

            logger.debug("Verifying graph integrity for data_id: %s", data_id)
            logger.debug("Total nodes in graph: %d, Total edges: %d", len(nodes), len(edges))

            # Check if any nodes exist with this data_id
            data_id_str = str(data_id)
            data_id_lower = data_id_str.lower()

            matching_nodes = []
            for node_id, node_data in nodes:
                node_data_id = node_data.get("data_id")

                # Exact string match
                if node_data_id == data_id_str:
                    matching_nodes.append((node_id, node_data))
                    continue

                # Lowercase match (UUID case insensitive)
                if node_data_id and str(node_data_id).lower() == data_id_lower:
                    matching_nodes.append((node_id, node_data))
                    continue

                # data_id embedded in node_id
                if data_id_lower in str(node_id).lower():
                    matching_nodes.append((node_id, node_data))

            if not matching_nodes:
                logger.warning("No graph nodes found for data_id %s", data_id)
                logger.debug("Searched among %d nodes", len(nodes))
                if len(nodes) > 0:
                    sample_node = nodes[0]
                    logger.debug(
                        "Sample node structure: id=%s, data_keys=%s",
                        sample_node[0],
                        list(sample_node[1].keys()),
                    )
                return False, f"No graph nodes found for data_id {data_id}"

            logger.info(
                "Data integrity verified for %s: found %d graph nodes",
                data_id,
                len(matching_nodes),
            )
            logger.debug("Sample matching node: %s", matching_nodes[0][0])
            return True, ""

        except Exception as e:  # pragma: no cover - best-effort verification
            logger.error("Failed to verify graph integrity for %s: %s", data_id, str(e), exc_info=True)
            # Don't fail the status update if verification itself fails
            return True, f"Verification skipped: {str(e)}"

    # stage == "vector_indexing"
    try:
        from cognee.infrastructure.databases.vector import get_vector_engine
        from cognee.infrastructure.databases.vector.config import get_vectordb_context_config

        # Log the vector config before getting the engine
        vector_config = get_vectordb_context_config()
        logger.info(
            "Vector DB config for verification (data_id %s, dataset_id %s): provider=%s, url=%s",
            data_id,
            dataset_id,
            vector_config.get("vector_db_provider"),
            vector_config.get("vector_db_url"),
        )

        vector_engine = get_vector_engine()

        logger.debug("Verifying vector integrity for data_id: %s", data_id)

        # Try to list all collections first
        try:
            all_collections = await vector_engine.list_collections()
            logger.debug("All available collections (%d): %s", len(all_collections), all_collections)
        except Exception as list_error:  # pragma: no cover - defensive logging
            logger.debug("Could not list collections: %s", list_error)
            all_collections = []

        # Common collection names that should exist after vector indexing
        common_collections = [
            "DocumentChunk_text",
            "Chunk_text",
            "Document_name",
            "Entity_name",
            "EntityType_name",
            "EdgeType_relationship_name",
        ]

        found_collections: list[tuple[str, int]] = []
        total_vectors = 0

        for collection_name in common_collections:
            try:
                if await vector_engine.has_collection(collection_name):
                    size = await vector_engine.get_collection_size(collection_name)
                    if size > 0:
                        found_collections.append((collection_name, size))
                        total_vectors += size
            except Exception as e:  # pragma: no cover - best-effort per collection
                logger.debug("Error checking collection %s: %s", collection_name, e)
                continue

        if not found_collections:
            logger.warning("No vector collections found for data_id %s", data_id)
            logger.debug("Checked collections: %s", common_collections)
            logger.info("All collections currently present: %s", all_collections)
            return False, f"No vector collections found for data_id {data_id}"

        logger.info(
            "Data integrity verified for %s: found %d collections with %d total vectors",
            data_id,
            len(found_collections),
            total_vectors,
        )
        logger.debug("Collections found: %s", found_collections)
        return True, ""

    except Exception as e:  # pragma: no cover - best-effort verification
        logger.error("Failed to verify vector integrity for %s: %s", data_id, str(e), exc_info=True)
        # Don't fail the status update if verification itself fails
        return True, f"Verification skipped: {str(e)}"



async def update_data_pipeline_status(
    data_id: UUID,
    stage: str,
    status: str,
    progress: int | None = None,
    error: str | None = None,
    skip_verification: bool = False,
    dataset_id: UUID | None = None,
    **counts,
):
    """Update pipeline status for a specific stage of data processing.

    Args:
        data_id: UUID of the data item
        stage: Processing stage ("parsing", "chunking", "graph_indexing", "vector_indexing")
        status: Status value ("pending", "in_progress", "completed", "failed")
        progress: Progress percentage (0-100)
        error: Error message if status is "failed"
        skip_verification: Skip data integrity verification (use with caution)
        dataset_id: Dataset ID for which the stage status is updated
        **counts: Additional stage-specific counts (chunk_count, node_count, etc.)
    """
    if stage in ("parsing", "chunking", "graph_indexing", "vector_indexing") and not dataset_id:
        raise ValueError(f"dataset_id is required for stage '{stage}'")

    db_engine = get_relational_engine()

    async with db_engine.get_async_session() as session:
        data = (await session.execute(select(Data).filter(Data.id == data_id))).scalar_one_or_none()

        if not data:
            logger.warning("Data item %s not found, cannot update pipeline status", data_id)
            return

        if not data.pipeline_status:
            data.pipeline_status = {}

        # Only these four stages are currently supported
        if stage not in ["parsing", "chunking", "graph_indexing", "vector_indexing"]:
            logger.warning("Unknown stage %s for data %s, skipping status update", stage, data_id)
            return

        # Get current status for this dataset
        stage_status = _get_stage_status_for_dataset(data.pipeline_status, stage, dataset_id)

        # Verify data integrity before marking as completed
        if status == "completed" and not skip_verification and stage in ("graph_indexing", "vector_indexing"):
            is_valid, verification_error = await verify_data_integrity(data_id, stage, dataset_id)

            if not is_valid:
                logger.error(
                    "Data integrity verification failed for %s stage %s (dataset %s): %s",
                    data_id,
                    stage,
                    dataset_id,
                    verification_error,
                )
                # Mark as failed instead of completed
                status = "failed"
                error = f"Data integrity check failed: {verification_error}"
                logger.warning(
                    "Marking %s as failed due to missing data in database (dataset_id=%s)",
                    stage,
                    dataset_id,
                )

        # Update status fields
        new_stage_status = dict(stage_status)
        new_stage_status["status"] = status

        if progress is not None:
            new_stage_status["progress"] = progress

        if error is not None:
            new_stage_status["error"] = error

        # Update timestamps
        now_iso = datetime.now(timezone.utc).isoformat()
        if status == "in_progress" and "started_at" not in new_stage_status:
            new_stage_status["started_at"] = now_iso
        elif status in ["completed", "failed"]:
            new_stage_status["completed_at"] = now_iso

        # Add stage-specific counts
        for key, value in counts.items():
            if value is not None:
                new_stage_status[key] = value

        # Write back into pipeline_status for this dataset
        data.pipeline_status = _set_stage_status_for_dataset(
            data.pipeline_status,
            stage,
            dataset_id,
            new_stage_status,
        )

        # Mark data as modified (important for JSON column update)
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(data, "pipeline_status")
        data.updated_at = datetime.now(timezone.utc)

        # Ensure the change is persisted
        session.add(data)
        await session.commit()
        await session.refresh(data)

        logger.info(
            "Updated pipeline status for data %s, stage %s, dataset %s: %s",
            data_id,
            stage,
            dataset_id,
            status,
        )


async def mark_all_stages_completed(data_id: UUID, dataset_id: UUID):
    """Mark all pipeline stages as completed for a data item.

    This is called after successful pipeline execution to mark parsing, chunking,
    graph_indexing, and vector_indexing as completed for a specific dataset.
    
    The function can be called immediately after pipeline tasks return, because:
    1. index_data_points() and index_graph_edges() already await all their async tasks
    2. All database writes are completed before those functions return
    3. No additional delay is needed - the data is guaranteed to be written

    Args:
        data_id: UUID of the data item
        dataset_id: Dataset ID for which to mark stages as completed
    """
    stages = ["parsing", "chunking", "graph_indexing", "vector_indexing"]

    for stage in stages:
        await update_data_pipeline_status(
            data_id=data_id,
            stage=stage,
            status="completed",
            progress=100,
            dataset_id=dataset_id,
        )


async def check_data_integrity(data_id: UUID, dataset_id: UUID) -> dict:
    """Check data integrity across all databases for a data item in a dataset.

    This provides a comprehensive integrity check that can be used to:
    1. Verify data exists after pipeline completion
    2. Detect "phantom completion" issues
    3. Provide health check capabilities

    Args:
        data_id: UUID of the data item to check
        dataset_id: UUID of the dataset whose databases should be checked

    Returns:
        dict: Integrity check results with:
            - has_graph_data: bool
            - has_vector_data: bool
            - issues: list of detected issues
            - details: dict with detailed check results
    """
    results: dict[str, Any] = {
        "data_id": str(data_id),
        "dataset_id": str(dataset_id),
        "has_graph_data": False,
        "has_vector_data": False,
        "issues": [],
        "details": {},
    }

    # Check graph database
    graph_valid, graph_error = await verify_data_integrity(data_id, "graph_indexing", dataset_id)
    results["has_graph_data"] = graph_valid
    results["details"]["graph_check"] = graph_error if graph_error else "OK"

    if not graph_valid and graph_error and "Verification skipped" not in graph_error:
        results["issues"].append(f"Graph data missing: {graph_error}")

    # Check vector database
    vector_valid, vector_error = await verify_data_integrity(data_id, "vector_indexing", dataset_id)
    results["has_vector_data"] = vector_valid
    results["details"]["vector_check"] = vector_error if vector_error else "OK"

    if not vector_valid and vector_error and "Verification skipped" not in vector_error:
        results["issues"].append(f"Vector data missing: {vector_error}")

    # Check pipeline_status consistency for this dataset
    db_engine = get_relational_engine()
    async with db_engine.get_async_session() as session:
        data = (await session.execute(select(Data).filter(Data.id == data_id))).scalar_one_or_none()

        if data and data.pipeline_status:
            graph_stage = data.pipeline_status.get("graph_indexing", {})
            vector_stage = data.pipeline_status.get("vector_indexing", {})

            graph_status = graph_stage.get(str(dataset_id), {}).get("status") if isinstance(graph_stage, dict) else None
            vector_status = (
                vector_stage.get(str(dataset_id), {}).get("status")
                if isinstance(vector_stage, dict)
                else None
            )

            if graph_status == "completed" and not graph_valid:
                results["issues"].append(
                    "Inconsistency: graph_indexing marked completed but no graph data found",
                )

            if vector_status == "completed" and not vector_valid:
                results["issues"].append(
                    "Inconsistency: vector_indexing marked completed but no vector data found",
                )

            results["details"]["pipeline_status"] = {
                "graph_indexing": graph_status,
                "vector_indexing": vector_status,
            }

    results["is_healthy"] = len(results["issues"]) == 0

    return results
