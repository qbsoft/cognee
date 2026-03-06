import pytest
from uuid import uuid4

def test_document_index_card_creation():
    """DocumentIndexCard can be created with all fields."""
    from cognee.infrastructure.engine.models.DocumentIndexCard import DocumentIndexCard

    doc_id = uuid4()
    card = DocumentIndexCard(
        summary="XX公司与YY公司的采购管理系统建设合同，涉及17个业务流程...",
        doc_name="采购管理系统SOW",
        doc_type="contract",
        key_entities="甲方:XX公司; 乙方:YY公司; 金额:500万; 用户数:2000",
        source_document_id=doc_id,
    )
    assert card.summary.startswith("XX公司")
    assert card.doc_name == "采购管理系统SOW"
    assert card.doc_type == "contract"
    assert card.source_document_id == doc_id
    assert card.metadata["index_fields"] == ["summary"]


def test_document_index_card_defaults():
    """DocumentIndexCard works with minimal fields."""
    from cognee.infrastructure.engine.models.DocumentIndexCard import DocumentIndexCard

    card = DocumentIndexCard(
        summary="A test document summary",
        doc_name="test.pdf",
        source_document_id=uuid4(),
    )
    assert card.doc_type == "general"
    assert card.key_entities == ""
