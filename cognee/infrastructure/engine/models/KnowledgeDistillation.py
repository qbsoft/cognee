"""
KnowledgeDistillation DataPoint model.

Stores auto-generated knowledge distillations (enumerations, aggregations,
disambiguations, negation statements, Q&A pairs) derived from document chunks
during the cognify pipeline. These distillations improve retrieval precision by
providing cross-chunk aggregated knowledge that helps answer complex queries.
"""
from uuid import UUID
from typing import Optional

from cognee.infrastructure.engine.models.DataPoint import DataPoint


class KnowledgeDistillation(DataPoint):
    """
    Represents an auto-generated knowledge distillation from document chunks.

    Each instance contains a piece of distilled knowledge (enumeration, aggregation,
    disambiguation, negation, or Q&A pair) that is automatically vector-indexed
    via the 'text' field for retrieval.

    Instance variables:
    - text: The distilled knowledge content (vector-indexed for search).
    - source_document_id: UUID of the source document this was distilled from.
    - distillation_type: Category of distillation (enumeration/aggregation/
      disambiguation/negation/qa).
    """

    __tablename__ = "knowledge_distillation"

    text: str
    source_document_id: UUID
    distillation_type: str  # enumeration | aggregation | disambiguation | negation | qa

    metadata: dict = {"index_fields": ["text"]}
