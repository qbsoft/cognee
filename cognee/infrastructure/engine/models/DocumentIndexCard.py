"""
Document-level index card for two-stage document routing.

Generated during cognify to enable efficient document selection
in large datasets (100-1000+ documents). The summary field is
vector-indexed for semantic search during Stage 1 routing.
"""
from uuid import UUID
from cognee.infrastructure.engine import DataPoint


class DocumentIndexCard(DataPoint):
    """Per-document summary card for search routing in large datasets."""

    __tablename__ = "document_index_card"

    summary: str                     # Vector-indexed: combined profile + summary
    doc_name: str                    # Document display name
    doc_type: str = "general"        # Document type from profiling
    key_entities: str = ""           # Key entities text for display
    source_document_id: UUID         # Links to the source Document

    metadata: dict = {"index_fields": ["summary"]}
