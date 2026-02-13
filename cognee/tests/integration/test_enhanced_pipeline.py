"""
End-to-end integration tests for the enhanced cognify pipeline (T2B03).

Tests cover:
- Pipeline task injection driven by YAML configuration
- Search type dispatch including HYBRID_SEARCH
- YAML config loading for graph_builder and search modules
- Reciprocal Rank Fusion (RRF) end-to-end correctness
"""
import pytest
import yaml
from unittest.mock import patch, AsyncMock, MagicMock

from cognee.modules.pipelines.tasks.task import Task
from cognee.tasks.documents import classify_documents, extract_chunks_from_documents
from cognee.tasks.graph import extract_graph_from_data
from cognee.tasks.summarization import summarize_text
from cognee.tasks.storage import add_data_points
from cognee.tasks.graph_validation import validate_extracted_graph
from cognee.tasks.entity_resolution import resolve_entities
from cognee.modules.search.types import SearchType
from cognee.modules.search.retrievers.HybridRetriever import (
    HybridRetriever,
    reciprocal_rank_fusion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_task_executables(tasks):
    """Extract the executable function reference from each Task."""
    return [t.executable for t in tasks]


def _make_both_enabled_config():
    """Config with both multi_round_validation and entity_resolution enabled."""
    return {
        "graph_builder": {
            "extraction": {
                "multi_round_validation": True,
                "confidence_threshold": 0.7,
            },
            "entity_resolution": {
                "enabled": True,
                "fuzzy_threshold": 0.85,
                "embedding_threshold": 0.9,
            },
        }
    }


def _make_both_disabled_config():
    """Config with both features explicitly disabled."""
    return {
        "graph_builder": {
            "extraction": {
                "multi_round_validation": False,
            },
            "entity_resolution": {
                "enabled": False,
            },
        }
    }


# ===========================================================================
# Pipeline integration tests
# ===========================================================================


class TestEnhancedPipelineTaskInjection:
    """Verify that get_default_tasks injects the correct tasks based on config."""

    @pytest.mark.asyncio
    async def test_enhanced_pipeline_has_validation_task(self):
        """When graph_builder.yaml has multi_round_validation=true,
        validate_extracted_graph must appear in the task list."""
        mock_config = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": True,
                    "confidence_threshold": 0.7,
                },
                "entity_resolution": {
                    "enabled": False,
                },
            }
        }
        with patch(
            "cognee.api.v1.cognify.cognify.get_module_config",
            return_value=mock_config,
        ):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)

            assert validate_extracted_graph in executables, (
                "validate_extracted_graph should be present when multi_round_validation=true"
            )

    @pytest.mark.asyncio
    async def test_enhanced_pipeline_has_entity_resolution_task(self):
        """When entity_resolution.enabled=true, resolve_entities must appear
        in the task list."""
        mock_config = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": False,
                },
                "entity_resolution": {
                    "enabled": True,
                    "fuzzy_threshold": 0.85,
                    "embedding_threshold": 0.9,
                },
            }
        }
        with patch(
            "cognee.api.v1.cognify.cognify.get_module_config",
            return_value=mock_config,
        ):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)

            assert resolve_entities in executables, (
                "resolve_entities should be present when entity_resolution.enabled=true"
            )

    @pytest.mark.asyncio
    async def test_enhanced_pipeline_task_order(self):
        """When both validation and entity resolution are enabled, the full
        task order must be:
        classify -> extract_chunks -> extract_graph -> validate -> resolve
        -> summarize -> add_data_points
        """
        mock_config = _make_both_enabled_config()
        with patch(
            "cognee.api.v1.cognify.cognify.get_module_config",
            return_value=mock_config,
        ):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)

            expected_order = [
                classify_documents,
                extract_chunks_from_documents,
                extract_graph_from_data,
                validate_extracted_graph,
                resolve_entities,
                summarize_text,
                add_data_points,
            ]
            assert len(executables) == len(expected_order), (
                f"Expected {len(expected_order)} tasks, got {len(executables)}"
            )
            for idx, (actual, expected) in enumerate(zip(executables, expected_order)):
                assert actual is expected, (
                    f"Task at index {idx}: expected {expected.__name__}, "
                    f"got {actual.__name__}"
                )


# ===========================================================================
# Search integration tests
# ===========================================================================


class TestSearchDispatchIntegration:
    """Verify that HYBRID_SEARCH is correctly dispatched."""

    @pytest.mark.asyncio
    async def test_hybrid_search_dispatch_integration(self):
        """Calling get_search_type_tools(SearchType.HYBRID_SEARCH, ...) must
        return a list whose first element is HybridRetriever.get_completion."""
        from cognee.modules.search.methods.get_search_type_tools import (
            get_search_type_tools,
        )

        tools = await get_search_type_tools(SearchType.HYBRID_SEARCH, "test query")

        assert len(tools) >= 1, "HYBRID_SEARCH should return at least one tool"
        # The first tool should be the bound get_completion method of a HybridRetriever
        first_tool = tools[0]
        # Verify it is a bound method from HybridRetriever
        assert hasattr(first_tool, "__self__"), (
            "First tool should be a bound method"
        )
        assert isinstance(first_tool.__self__, HybridRetriever), (
            "First tool should be bound to a HybridRetriever instance"
        )
        assert first_tool.__func__.__name__ == "get_completion", (
            "First tool should be the get_completion method"
        )

    @pytest.mark.asyncio
    async def test_yaml_config_drives_pipeline(self):
        """Modifying YAML config (via mock) should change get_default_tasks behavior.
        Start with both-enabled, switch to both-disabled, verify the difference."""
        from cognee.api.v1.cognify.cognify import get_default_tasks

        # With both enabled
        with patch(
            "cognee.api.v1.cognify.cognify.get_module_config",
            return_value=_make_both_enabled_config(),
        ):
            tasks_enabled = await get_default_tasks()
            exes_enabled = _get_task_executables(tasks_enabled)

        # With both disabled
        with patch(
            "cognee.api.v1.cognify.cognify.get_module_config",
            return_value=_make_both_disabled_config(),
        ):
            tasks_disabled = await get_default_tasks()
            exes_disabled = _get_task_executables(tasks_disabled)

        # Enabled config should produce more tasks
        assert len(exes_enabled) == 7
        assert len(exes_disabled) == 5
        assert validate_extracted_graph in exes_enabled
        assert resolve_entities in exes_enabled
        assert validate_extracted_graph not in exes_disabled
        assert resolve_entities not in exes_disabled


# ===========================================================================
# YAML config integration tests
# ===========================================================================


class TestYamlConfigIntegration:
    """Verify that YAML config loading returns correct structures for each module."""

    def test_yaml_config_loads_graph_builder(self, tmp_path, monkeypatch):
        """get_module_config('graph_builder') should return the full
        graph_builder configuration structure."""
        from cognee.infrastructure.config.yaml_config import (
            get_module_config,
            reload_config,
        )

        reload_config()

        config_content = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": True,
                    "confidence_threshold": 0.7,
                },
                "entity_resolution": {
                    "enabled": True,
                    "fuzzy_threshold": 0.85,
                    "embedding_threshold": 0.9,
                    "llm_assisted": False,
                },
                "ontology": {
                    "enabled": False,
                    "source": "config/ontology.yaml",
                },
            }
        }
        config_file = tmp_path / "graph_builder.yaml"
        config_file.write_text(yaml.dump(config_content))

        monkeypatch.setattr(
            "cognee.infrastructure.config.yaml_config.get_config_dir",
            lambda: tmp_path,
        )

        config = get_module_config("graph_builder")

        assert "graph_builder" in config
        gb = config["graph_builder"]
        assert gb["extraction"]["multi_round_validation"] is True
        assert gb["extraction"]["confidence_threshold"] == 0.7
        assert gb["entity_resolution"]["enabled"] is True
        assert gb["entity_resolution"]["fuzzy_threshold"] == 0.85
        assert gb["entity_resolution"]["embedding_threshold"] == 0.9
        assert gb["ontology"]["enabled"] is False

    def test_yaml_config_loads_search(self, tmp_path, monkeypatch):
        """get_module_config('search') should return the full search
        configuration structure with hybrid strategies and reranking."""
        from cognee.infrastructure.config.yaml_config import (
            get_module_config,
            reload_config,
        )

        reload_config()

        config_content = {
            "search": {
                "default_type": "hybrid",
                "hybrid": {
                    "strategies": {
                        "vector": {"weight": 0.4},
                        "graph": {"weight": 0.3},
                        "lexical": {"weight": 0.3},
                    },
                    "fusion": "reciprocal_rank",
                    "rrf_k": 60,
                    "top_k": 20,
                },
                "reranking": {
                    "enabled": True,
                    "model": "bge-reranker-v2-m3",
                    "top_k": 10,
                    "fallback": "llm",
                },
            }
        }
        config_file = tmp_path / "search.yaml"
        config_file.write_text(yaml.dump(config_content))

        monkeypatch.setattr(
            "cognee.infrastructure.config.yaml_config.get_config_dir",
            lambda: tmp_path,
        )

        config = get_module_config("search")

        assert "search" in config
        search = config["search"]
        assert search["default_type"] == "hybrid"
        hybrid = search["hybrid"]
        assert hybrid["strategies"]["vector"]["weight"] == 0.4
        assert hybrid["strategies"]["graph"]["weight"] == 0.3
        assert hybrid["strategies"]["lexical"]["weight"] == 0.3
        assert hybrid["fusion"] == "reciprocal_rank"
        assert hybrid["rrf_k"] == 60
        assert hybrid["top_k"] == 20
        reranking = search["reranking"]
        assert reranking["enabled"] is True
        assert reranking["model"] == "bge-reranker-v2-m3"
        assert reranking["top_k"] == 10
        assert reranking["fallback"] == "llm"


# ===========================================================================
# RRF fusion end-to-end test
# ===========================================================================


class TestRRFFusionEndToEnd:
    """Verify that reciprocal_rank_fusion correctly fuses and ranks results."""

    def test_rrf_fusion_end_to_end(self):
        """Create multiple mock result lists, fuse them with RRF, and verify
        that the output is correctly ranked by composite score."""
        # Simulate vector retrieval results (best match: doc_a)
        vector_results = [
            {"id": "doc_a", "text": "vector hit A", "score": 0.95},
            {"id": "doc_b", "text": "vector hit B", "score": 0.80},
            {"id": "doc_c", "text": "vector hit C", "score": 0.70},
        ]
        # Simulate graph retrieval results (best match: doc_b)
        graph_results = [
            {"id": "doc_b", "text": "graph hit B", "score": 0.90},
            {"id": "doc_a", "text": "graph hit A", "score": 0.75},
            {"id": "doc_d", "text": "graph hit D", "score": 0.60},
        ]
        # Simulate lexical retrieval results (best match: doc_a)
        lexical_results = [
            {"id": "doc_a", "text": "lexical hit A", "score": 0.88},
            {"id": "doc_d", "text": "lexical hit D", "score": 0.72},
            {"id": "doc_c", "text": "lexical hit C", "score": 0.65},
        ]

        weights = [0.4, 0.3, 0.3]
        fused = reciprocal_rank_fusion(
            [vector_results, graph_results, lexical_results],
            weights=weights,
            k=60,
        )

        # All unique doc IDs should appear
        fused_ids = [item["id"] for item in fused]
        assert set(fused_ids) == {"doc_a", "doc_b", "doc_c", "doc_d"}

        # Each result should have an rrf_score
        for item in fused:
            assert "rrf_score" in item
            assert item["rrf_score"] > 0

        # doc_a appears in rank 0 of vector (weight 0.4), rank 1 of graph (weight 0.3),
        # and rank 0 of lexical (weight 0.3). It should have the highest RRF score.
        assert fused[0]["id"] == "doc_a", (
            f"doc_a should be the top result, but got {fused[0]['id']}"
        )

        # Scores should be in descending order
        scores = [item["rrf_score"] for item in fused]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Scores should be descending: {scores}"
            )

    def test_rrf_fusion_empty_lists(self):
        """RRF with empty input should return empty list."""
        assert reciprocal_rank_fusion([]) == []

    def test_rrf_fusion_single_list(self):
        """RRF with a single result list should preserve order."""
        results = [
            {"id": "a", "text": "first"},
            {"id": "b", "text": "second"},
        ]
        fused = reciprocal_rank_fusion([results])
        assert len(fused) == 2
        assert fused[0]["id"] == "a"
        assert fused[1]["id"] == "b"

    def test_rrf_fusion_with_default_weights(self):
        """RRF with None weights should use equal weights."""
        list_1 = [{"id": "x"}, {"id": "y"}]
        list_2 = [{"id": "y"}, {"id": "x"}]
        fused = reciprocal_rank_fusion([list_1, list_2], weights=None)
        fused_ids = [item["id"] for item in fused]
        # Both x and y appear at rank 0 in one list and rank 1 in the other,
        # so they should have equal RRF scores. Either order is acceptable.
        assert set(fused_ids) == {"x", "y"}
        assert fused[0]["rrf_score"] == fused[1]["rrf_score"]

    def test_rrf_fusion_weighted_preference(self):
        """When one list has a much higher weight, its ordering should dominate."""
        # list_1 with high weight: prefers doc_x
        list_1 = [{"id": "doc_x"}, {"id": "doc_y"}]
        # list_2 with low weight: prefers doc_y
        list_2 = [{"id": "doc_y"}, {"id": "doc_x"}]

        fused = reciprocal_rank_fusion(
            [list_1, list_2],
            weights=[0.9, 0.1],
        )
        # doc_x should be ranked first because list_1 has 90% weight
        assert fused[0]["id"] == "doc_x"

    def test_rrf_fusion_disjoint_results(self):
        """When result lists have no overlap, all items should appear."""
        list_1 = [{"id": "a"}, {"id": "b"}]
        list_2 = [{"id": "c"}, {"id": "d"}]
        fused = reciprocal_rank_fusion([list_1, list_2])
        fused_ids = {item["id"] for item in fused}
        assert fused_ids == {"a", "b", "c", "d"}

    def test_rrf_fusion_score_computation(self):
        """Verify the exact RRF score computation for a known case."""
        # Single list, k=60: score for rank 0 = weight * 1/(60+0+1) = 1.0 * 1/61
        results = [{"id": "only"}]
        fused = reciprocal_rank_fusion([results], weights=[1.0], k=60)
        expected_score = 1.0 / 61
        assert abs(fused[0]["rrf_score"] - expected_score) < 1e-10


# ===========================================================================
# HybridRetriever integration test
# ===========================================================================


class TestHybridRetrieverIntegration:
    """Test that HybridRetriever correctly wires up retrievers and RRF."""

    @pytest.mark.asyncio
    async def test_hybrid_retriever_fuses_results(self):
        """HybridRetriever.get_completion should call all retrievers and
        fuse results via RRF."""

        async def mock_vector(query, **kw):
            return [
                {"id": "v1", "text": "vector result 1"},
                {"id": "v2", "text": "vector result 2"},
            ]

        async def mock_graph(query, **kw):
            return [
                {"id": "g1", "text": "graph result 1"},
                {"id": "v1", "text": "graph also found v1"},
            ]

        async def mock_lexical(query, **kw):
            return [
                {"id": "v1", "text": "lexical also found v1"},
                {"id": "l1", "text": "lexical result 1"},
            ]

        retriever = HybridRetriever(
            vector_retriever=mock_vector,
            graph_retriever=mock_graph,
            lexical_retriever=mock_lexical,
            top_k=10,
        )

        results = await retriever.get_completion("test query")

        result_ids = [r["id"] for r in results]
        # v1 appears in all three lists, so it should be ranked first
        assert results[0]["id"] == "v1", (
            f"v1 should be top-ranked (appeared in all lists), got {results[0]['id']}"
        )
        # All unique IDs should be present
        assert set(result_ids) == {"v1", "v2", "g1", "l1"}

    @pytest.mark.asyncio
    async def test_hybrid_retriever_handles_retriever_failure(self):
        """If one retriever fails, the others should still produce results."""

        async def mock_vector(query, **kw):
            return [{"id": "v1", "text": "from vector"}]

        async def mock_graph(query, **kw):
            raise RuntimeError("Graph DB connection failed")

        async def mock_lexical(query, **kw):
            return [{"id": "l1", "text": "from lexical"}]

        retriever = HybridRetriever(
            vector_retriever=mock_vector,
            graph_retriever=mock_graph,
            lexical_retriever=mock_lexical,
            top_k=10,
        )

        results = await retriever.get_completion("test query")

        result_ids = {r["id"] for r in results}
        assert "v1" in result_ids
        assert "l1" in result_ids

    @pytest.mark.asyncio
    async def test_hybrid_retriever_top_k_limit(self):
        """HybridRetriever should respect the top_k parameter."""

        async def mock_vector(query, **kw):
            return [{"id": f"v{i}"} for i in range(20)]

        async def mock_graph(query, **kw):
            return [{"id": f"g{i}"} for i in range(20)]

        retriever = HybridRetriever(
            vector_retriever=mock_vector,
            graph_retriever=mock_graph,
            top_k=5,
        )

        results = await retriever.get_completion("test query")
        assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_hybrid_retriever_no_retrievers(self):
        """HybridRetriever with no retrievers should return empty list."""
        retriever = HybridRetriever()
        results = await retriever.get_completion("test query")
        assert results == []


# ===========================================================================
# Config-driven pipeline behavior change tests
# ===========================================================================


class TestConfigDrivenBehavior:
    """Verify that changing configuration values alters pipeline behavior."""

    @pytest.mark.asyncio
    async def test_validation_threshold_passed_through(self):
        """The confidence_threshold from config should be passed to the
        validate_extracted_graph task as a keyword argument."""
        mock_config = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": True,
                    "confidence_threshold": 0.92,
                },
                "entity_resolution": {
                    "enabled": False,
                },
            }
        }
        with patch(
            "cognee.api.v1.cognify.cognify.get_module_config",
            return_value=mock_config,
        ):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()

            # Find the validation task
            validation_tasks = [
                t for t in tasks if t.executable is validate_extracted_graph
            ]
            assert len(validation_tasks) == 1
            vt = validation_tasks[0]
            assert vt.default_params["kwargs"]["confidence_threshold"] == 0.92

    @pytest.mark.asyncio
    async def test_entity_resolution_thresholds_passed_through(self):
        """fuzzy_threshold and embedding_threshold from config should be
        passed to the resolve_entities task."""
        mock_config = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": False,
                },
                "entity_resolution": {
                    "enabled": True,
                    "fuzzy_threshold": 0.75,
                    "embedding_threshold": 0.88,
                },
            }
        }
        with patch(
            "cognee.api.v1.cognify.cognify.get_module_config",
            return_value=mock_config,
        ):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()

            resolution_tasks = [
                t for t in tasks if t.executable is resolve_entities
            ]
            assert len(resolution_tasks) == 1
            rt = resolution_tasks[0]
            assert rt.default_params["kwargs"]["fuzzy_threshold"] == 0.75
            assert rt.default_params["kwargs"]["embedding_threshold"] == 0.88

    @pytest.mark.asyncio
    async def test_empty_config_yields_base_pipeline(self):
        """An empty config should yield the base 5-task pipeline with no
        validation or entity resolution."""
        with patch(
            "cognee.api.v1.cognify.cognify.get_module_config",
            return_value={},
        ):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)

            assert len(executables) == 5
            assert validate_extracted_graph not in executables
            assert resolve_entities not in executables

    @pytest.mark.asyncio
    async def test_only_validation_no_resolution(self):
        """With only validation enabled and entity resolution disabled,
        the pipeline should have exactly 6 tasks."""
        mock_config = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": True,
                    "confidence_threshold": 0.7,
                },
                "entity_resolution": {
                    "enabled": False,
                },
            }
        }
        with patch(
            "cognee.api.v1.cognify.cognify.get_module_config",
            return_value=mock_config,
        ):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)

            assert len(executables) == 6
            assert validate_extracted_graph in executables
            assert resolve_entities not in executables

    @pytest.mark.asyncio
    async def test_only_resolution_no_validation(self):
        """With only entity resolution enabled and validation disabled,
        the pipeline should have exactly 6 tasks."""
        mock_config = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": False,
                },
                "entity_resolution": {
                    "enabled": True,
                    "fuzzy_threshold": 0.85,
                    "embedding_threshold": 0.9,
                },
            }
        }
        with patch(
            "cognee.api.v1.cognify.cognify.get_module_config",
            return_value=mock_config,
        ):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)

            assert len(executables) == 6
            assert resolve_entities in executables
            assert validate_extracted_graph not in executables
