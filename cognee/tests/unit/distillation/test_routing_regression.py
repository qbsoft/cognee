"""
Regression tests for document routing.

Ensures that:
1. Small datasets (≤20 docs) never trigger routing (identical to pre-routing behavior)
2. Large datasets trigger routing correctly
3. Filtering preserves all results when no document names are specified
4. Filtering correctly matches the [来源: docname] prefix format
"""
import pytest


def test_routing_skipped_for_small_datasets():
    """Routing must be skipped when doc_count <= 20."""
    from cognee.modules.retrieval.graph_completion_retriever import _should_enable_routing

    for count in [0, 1, 2, 5, 10, 15, 20]:
        assert _should_enable_routing(count) == False, f"Routing wrongly enabled for {count} docs"


def test_routing_enabled_for_large_datasets():
    """Routing activates for datasets with >20 documents."""
    from cognee.modules.retrieval.graph_completion_retriever import _should_enable_routing

    for count in [21, 50, 100, 500, 1000]:
        assert _should_enable_routing(count) == True, f"Routing not enabled for {count} docs"


def test_filter_preserves_all_when_no_names():
    """No filtering when doc_names is None (small dataset behavior)."""
    from cognee.modules.retrieval.graph_completion_retriever import _filter_results_by_doc_names

    class MockResult:
        def __init__(self, text):
            self.payload = {"text": text}

    results = [MockResult(f"text_{i}") for i in range(10)]
    filtered = _filter_results_by_doc_names(results, None)
    assert len(filtered) == 10  # All preserved


def test_filter_works_with_source_prefix():
    """Filtering correctly matches [来源: docname] prefix."""
    from cognee.modules.retrieval.graph_completion_retriever import _filter_results_by_doc_names

    class MockResult:
        def __init__(self, text):
            self.payload = {"text": text}

    results = [
        MockResult("[来源: 采购合同] 共有17个流程"),
        MockResult("[来源: 技术方案] 系统架构包括3层"),
        MockResult("[来源: 会议纪要] 讨论了项目进度"),
        MockResult("[来源: 采购合同] 甲方为XX公司"),
    ]

    # Only keep 采购合同 results
    filtered = _filter_results_by_doc_names(results, {"采购合同"})
    assert len(filtered) == 2
    assert all("采购合同" in r.payload["text"] for r in filtered)

    # Keep multiple document types
    filtered = _filter_results_by_doc_names(results, {"采购合同", "会议纪要"})
    assert len(filtered) == 3
