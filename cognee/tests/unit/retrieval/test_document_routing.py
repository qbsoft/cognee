import pytest

def test_should_route_threshold():
    """Routing activates only when doc_count > min_doc_count."""
    from cognee.modules.retrieval.graph_completion_retriever import _should_enable_routing

    assert _should_enable_routing(5) == False
    assert _should_enable_routing(20) == False
    assert _should_enable_routing(21) == True
    assert _should_enable_routing(100) == True


def test_filter_kd_by_doc_names():
    """KD results are filtered to only matching document names."""
    from cognee.modules.retrieval.graph_completion_retriever import _filter_results_by_doc_names

    class MockResult:
        def __init__(self, text, score=0.5):
            self.payload = {"text": text}
            self.score = score
            self.id = "test"

    results = [
        MockResult("[来源: 合同A] 金额500万"),
        MockResult("[来源: 合同B] 金额300万"),
        MockResult("[来源: 合同C] 金额100万"),
    ]

    filtered = _filter_results_by_doc_names(results, {"合同A", "合同C"})
    assert len(filtered) == 2
    assert "合同A" in filtered[0].payload["text"]
    assert "合同C" in filtered[1].payload["text"]


def test_filter_kd_no_filter():
    """When doc_names is None, all results pass through."""
    from cognee.modules.retrieval.graph_completion_retriever import _filter_results_by_doc_names

    class MockResult:
        def __init__(self, text):
            self.payload = {"text": text}
            self.score = 0.5
            self.id = "test"

    results = [MockResult("text1"), MockResult("text2")]
    filtered = _filter_results_by_doc_names(results, None)
    assert len(filtered) == 2
