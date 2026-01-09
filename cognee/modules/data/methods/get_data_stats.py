"""Get statistics for data items (chunks, nodes, edges, vectors)"""
from uuid import UUID
from typing import Optional
from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.shared.logging_utils import get_logger

logger = get_logger()


async def get_data_stats(data_id: UUID) -> dict:
    """
    Get statistics for a data item including chunk count, node count, edge count.
    
    Args:
        data_id: UUID of the data item
        
    Returns:
        dict with keys: chunk_count, node_count, edge_count, vector_count
    """
    stats = {
        "chunk_count": None,
        "node_count": None,
        "edge_count": None,
        "vector_count": None
    }
    
    try:
        graph_engine = await get_graph_engine()
        
        # Get document subgraph to count chunks and nodes
        subgraph = await graph_engine.get_document_subgraph(str(data_id))
        
        if subgraph:
            # Count chunks - ensure we handle None values
            chunks = subgraph.get("chunks") or []
            stats["chunk_count"] = len(chunks) if chunks else 0
            
            # Count all nodes (chunks + entities + entity_types + summaries)
            total_nodes = 0
            for key in ["chunks", "orphan_entities", "orphan_types", "summaries", "made_from_nodes", "document"]:
                nodes = subgraph.get(key) or []  # Handle None by using empty list
                if nodes:
                    total_nodes += len(nodes)
            
            stats["node_count"] = total_nodes
            
            # Count edges (approximate - edges connecting the nodes)
            stats["edge_count"] = total_nodes  # Rough estimate
            
            # Vector count usually equals chunk count (one vector per chunk)
            stats["vector_count"] = stats["chunk_count"]
    
    except Exception as e:
        # Log at debug level to avoid flooding logs during batch operations
        logger.debug(f"Failed to get stats for data {data_id}: {str(e)}")
    
    return stats


async def get_batch_data_stats(data_ids: list[UUID]) -> dict[UUID, dict]:
    """
    Get statistics for multiple data items in batch.
    
    Args:
        data_ids: List of data item UUIDs
        
    Returns:
        Dictionary mapping data_id to stats dict
    """
    results = {}
    
    # TODO: Optimize with batch query to graph database
    # For now, query one by one
    for data_id in data_ids:
        results[data_id] = await get_data_stats(data_id)
    
    return results
