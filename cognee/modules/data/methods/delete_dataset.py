from uuid import UUID
from sqlalchemy import select
from sqlalchemy.sql import delete as sql_delete

from cognee.modules.data.models import Dataset, DatasetData
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.shared.logging_utils import get_logger

logger = get_logger()


async def delete_dataset(dataset: Dataset):
    """
    Delete a dataset and cascade delete all associated data.
    
    This ensures complete data cleanup across:
    - Graph database (nodes and edges)
    - Vector database (embeddings)
    - Relational database (data records, associations, metadata)
    
    Args:
        dataset: The Dataset object to delete
        
    Returns:
        Dictionary with deletion statistics
    """
    logger.info(f"Starting cascade deletion for dataset: {dataset.name} ({dataset.id})")
    
    db_engine = get_relational_engine()
    
    # Statistics
    stats = {
        "dataset_id": str(dataset.id),
        "dataset_name": dataset.name,
        "deleted_data_count": 0,
        "failed_deletions": [],
    }
    
    async with db_engine.get_async_session() as session:
        # Step 1: Get all data items associated with this dataset
        dataset_data_links = (
            await session.execute(
                select(DatasetData).filter(DatasetData.dataset_id == dataset.id)
            )
        ).scalars().all()
        
        data_ids = [link.data_id for link in dataset_data_links]
        logger.info(f"Found {len(data_ids)} data items to delete for dataset {dataset.name}")
        
        # Step 2: Delete each data item with full cascade
        if data_ids:
            from cognee.api.v1.delete.delete import delete_single_document
            
            for data_id in data_ids:
                try:
                    # Delete from graph, vector, and relational databases
                    await delete_single_document(str(data_id), dataset.id, mode="soft")
                    stats["deleted_data_count"] += 1
                    logger.debug(f"Deleted data item: {data_id}")
                except Exception as e:
                    logger.error(f"Failed to delete data {data_id}: {str(e)}")
                    stats["failed_deletions"].append({
                        "data_id": str(data_id),
                        "error": str(e)
                    })
        
        # Step 3: Delete dataset-data associations (should be cleaned up already, but ensure)
        delete_associations = sql_delete(DatasetData).where(
            DatasetData.dataset_id == dataset.id
        )
        await session.execute(delete_associations)
        
        # Step 4: Delete pipeline runs for this dataset
        try:
            from cognee.modules.pipelines.models import PipelineRun
            delete_pipeline_runs = sql_delete(PipelineRun).where(
                PipelineRun.dataset_id == dataset.id
            )
            await session.execute(delete_pipeline_runs)
            logger.debug(f"Deleted pipeline runs for dataset {dataset.id}")
        except Exception as e:
            logger.warning(f"Could not delete pipeline runs: {str(e)}")
        
        # Step 5: Delete the dataset record itself
        delete_dataset_stmt = sql_delete(Dataset).where(Dataset.id == dataset.id)
        await session.execute(delete_dataset_stmt)
        
        # Step 6: Delete permissions for this dataset
        try:
            from cognee.modules.users.permissions.methods import remove_permissions_on_dataset
            await remove_permissions_on_dataset(dataset.id)
            logger.debug(f"Deleted permissions for dataset {dataset.id}")
        except Exception as e:
            logger.warning(f"Could not delete permissions: {str(e)}")
        
        await session.commit()
    
    logger.info(
        f"Dataset deletion completed: {dataset.name}. "
        f"Deleted {stats['deleted_data_count']} data items, "
        f"Failed: {len(stats['failed_deletions'])}"
    )
    
    return stats
