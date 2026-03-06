import pytest
from uuid import uuid4

def test_build_index_card_summary():
    """_build_index_card_summary creates a useful summary from profile."""
    from cognee.tasks.distillation.distill_knowledge import (
        DocumentProfile, _build_index_card_summary
    )

    profile = DocumentProfile(
        doc_type="contract",
        language="zh",
        key_categories=["项目范围", "实施阶段", "验收标准"],
        enumeration_targets=["实施阶段(共5个)", "服务范围清单"],
        role_parties=["甲方: XX公司", "乙方: YY公司"],
        example_questions=["项目分几个阶段？", "验收标准是什么？"],
        disambiguation_pairs=["质保期 vs 维保期"],
    )

    summary = _build_index_card_summary(profile, doc_name="SOW文档")

    assert "contract" in summary
    assert "项目范围" in summary
    assert "XX公司" in summary
    assert "SOW文档" in summary
    assert len(summary) < 1000


def test_build_index_card_summary_minimal():
    """Works with minimal profile (all defaults)."""
    from cognee.tasks.distillation.distill_knowledge import (
        DocumentProfile, _build_index_card_summary
    )

    profile = DocumentProfile()
    summary = _build_index_card_summary(profile, doc_name="test.pdf")

    assert "test.pdf" in summary
    assert len(summary) > 0


def test_build_index_card_summary_none_profile():
    """Returns basic summary when profile is None."""
    from cognee.tasks.distillation.distill_knowledge import _build_index_card_summary

    summary = _build_index_card_summary(None, doc_name="test.pdf")
    assert "test.pdf" in summary
