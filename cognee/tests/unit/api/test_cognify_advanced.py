"""
Cognify 图谱构建高级验证测试 (T405-T410)

Tests for:
- T405: LLM failure retry/degradation in validate_extracted_graph and resolve_entities
- T406: Empty dataset handling in cognify
- T407: Pipeline metrics/batch_size configuration
- T408: Multi-round validation quality improvement
- T409: Entity resolution deduplication
- T410: Temporal cognify task sequence and defaults
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from cognee.modules.pipelines.tasks.task import Task
from cognee.tasks.documents import classify_documents, extract_chunks_from_documents
from cognee.tasks.graph import extract_graph_from_data
from cognee.tasks.summarization import summarize_text
from cognee.tasks.storage import add_data_points
from cognee.tasks.graph_validation import validate_extracted_graph
from cognee.tasks.graph_validation.validate_extracted_graph import (
    DEFAULT_CONFIDENCE,
    _apply_default_scores,
    _apply_validation_scores,
    _build_validation_input,
)
from cognee.tasks.entity_resolution import resolve_entities
from cognee.tasks.entity_resolution.resolve_entities import (
    _should_merge,
    _merge_entity_group,
    _name_similarity,
)


def _get_task_executables(tasks):
    """Helper to extract the executable function from each Task."""
    return [t.executable for t in tasks]


# ---------------------------------------------------------------------------
# T405: LLM failure retry/degradation
# ---------------------------------------------------------------------------


class TestT405LLMFailureDegradation:
    """Test that graph validation and entity resolution handle LLM failures gracefully."""

    @pytest.mark.asyncio
    async def test_validate_graph_returns_default_confidence_on_llm_failure(self):
        """When LLM client raises an exception, all items get DEFAULT_CONFIDENCE."""
        data = [
            {"source_entity": "A", "target_entity": "B", "relationship": "knows"},
            {"source_entity": "C", "target_entity": "D", "relationship": "likes"},
        ]

        async def failing_llm(prompt):
            raise RuntimeError("LLM service unavailable")

        result = await validate_extracted_graph(
            extracted_data=data,
            llm_client=failing_llm,
            confidence_threshold=0.7,
        )
        # All items should be returned (no filtering when LLM fails)
        assert len(result) == 2
        for item in result:
            assert item["confidence"] == DEFAULT_CONFIDENCE

    @pytest.mark.asyncio
    async def test_validate_graph_returns_input_unchanged_when_no_llm_client(self):
        """When llm_client is None, graceful degradation: return all with default confidence."""
        data = [
            {"source_entity": "X", "target_entity": "Y", "relationship": "related_to"},
        ]
        result = await validate_extracted_graph(
            extracted_data=data,
            llm_client=None,
            confidence_threshold=0.9,
        )
        assert len(result) == 1
        assert result[0]["confidence"] == DEFAULT_CONFIDENCE
        assert result[0]["source_entity"] == "X"

    @pytest.mark.asyncio
    async def test_validate_graph_empty_input(self):
        """Empty input returns empty list immediately."""
        result = await validate_extracted_graph(
            extracted_data=[],
            llm_client=None,
            confidence_threshold=0.7,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_resolve_entities_works_without_llm(self):
        """resolve_entities uses pure fuzzy matching - no LLM needed."""
        entities = [
            {"name": "Microsoft Corporation", "type": "company"},
            {"name": "Microsoft Corp", "type": "company"},
            {"name": "Apple Inc", "type": "company"},
        ]
        # fuzzy_threshold=0.7 should merge Microsoft Corporation and Microsoft Corp
        result = await resolve_entities(
            entities=entities,
            fuzzy_threshold=0.7,
            embedding_threshold=0.9,
            embedding_func=None,
        )
        # Microsoft variants should be merged, Apple stays separate
        assert len(result) == 2
        names = [e["name"] for e in result]
        assert "Apple Inc" in names

    @pytest.mark.asyncio
    async def test_resolve_entities_single_entity_returns_unchanged(self):
        """Single entity list is returned unchanged."""
        entities = [{"name": "Google", "type": "company"}]
        result = await resolve_entities(entities=entities)
        assert len(result) == 1
        assert result[0]["name"] == "Google"

    @pytest.mark.asyncio
    async def test_resolve_entities_empty_returns_unchanged(self):
        """Empty entity list is returned as-is."""
        result = await resolve_entities(entities=[])
        assert result == []

    def test_apply_default_scores_sets_confidence(self):
        """_apply_default_scores should add DEFAULT_CONFIDENCE to every item."""
        data = [{"source_entity": "A"}, {"source_entity": "B"}]
        result = _apply_default_scores(data)
        assert len(result) == 2
        for item in result:
            assert item["confidence"] == DEFAULT_CONFIDENCE
        # Original data should not be mutated
        assert "confidence" not in data[0]

    def test_apply_validation_scores_uses_llm_results(self):
        """_apply_validation_scores maps LLM scores by index."""
        data = [
            {"source_entity": "A", "target_entity": "B"},
            {"source_entity": "C", "target_entity": "D"},
        ]
        validation_result = [
            {"index": 0, "confidence": 0.95, "reason": "Strong evidence"},
            {"index": 1, "confidence": 0.3, "reason": "Weak evidence"},
        ]
        result = _apply_validation_scores(data, validation_result)
        assert result[0]["confidence"] == 0.95
        assert result[1]["confidence"] == 0.3
        assert result[0]["validation_reason"] == "Strong evidence"

    def test_apply_validation_scores_missing_index_gets_default(self):
        """Items not covered by LLM result get DEFAULT_CONFIDENCE."""
        data = [{"source_entity": "A"}, {"source_entity": "B"}]
        validation_result = [{"index": 0, "confidence": 0.9}]
        result = _apply_validation_scores(data, validation_result)
        assert result[0]["confidence"] == 0.9
        assert result[1]["confidence"] == DEFAULT_CONFIDENCE


# ---------------------------------------------------------------------------
# T406: Empty dataset handling in cognify
# ---------------------------------------------------------------------------


class TestT406EmptyDatasetHandling:
    """Test that cognify handles empty/None datasets properly."""

    @pytest.mark.asyncio
    async def test_get_default_tasks_returns_valid_task_list_with_defaults(self):
        """get_default_tasks with all defaults returns a valid task list."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            assert len(tasks) >= 5
            assert all(isinstance(t, Task) for t in tasks)

    @pytest.mark.asyncio
    async def test_get_default_tasks_with_none_chunks_per_batch(self):
        """chunks_per_batch=None should default to 100."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks(chunks_per_batch=None)
            # extract_graph_from_data task should have batch_size=100
            graph_task = tasks[2]
            assert graph_task.executable is extract_graph_from_data
            assert graph_task.task_config["batch_size"] == 100

    @pytest.mark.asyncio
    async def test_cognify_accepts_datasets_none(self):
        """cognify(datasets=None) should call pipeline executor with datasets=None."""
        mock_executor = AsyncMock(return_value={"result": "ok"})

        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor):
            from cognee.api.v1.cognify.cognify import cognify

            result = await cognify(datasets=None)
            # Verify pipeline executor was called with datasets=None
            mock_executor.assert_called_once()
            call_kwargs = mock_executor.call_args[1]
            assert call_kwargs["datasets"] is None

    @pytest.mark.asyncio
    async def test_cognify_accepts_empty_dataset_list(self):
        """cognify(datasets=[]) should call pipeline executor with datasets=[]."""
        mock_executor = AsyncMock(return_value={"result": "ok"})

        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor):
            from cognee.api.v1.cognify.cognify import cognify

            result = await cognify(datasets=[])
            mock_executor.assert_called_once()
            call_kwargs = mock_executor.call_args[1]
            assert call_kwargs["datasets"] == []

    @pytest.mark.asyncio
    async def test_get_default_tasks_with_none_config(self):
        """get_default_tasks(config=None) should still produce valid task list."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks(config=None)
            executables = _get_task_executables(tasks)
            assert classify_documents in executables
            assert extract_chunks_from_documents in executables
            assert extract_graph_from_data in executables


# ---------------------------------------------------------------------------
# T407: Pipeline metrics / batch_size configuration
# ---------------------------------------------------------------------------


class TestT407PipelineMetrics:
    """Test that Task objects are created with correct task_config batch_size."""

    @pytest.mark.asyncio
    async def test_extract_graph_task_has_correct_batch_size(self):
        """extract_graph_from_data Task has batch_size matching chunks_per_batch."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks(chunks_per_batch=50)
            graph_task = tasks[2]
            assert graph_task.executable is extract_graph_from_data
            assert graph_task.task_config["batch_size"] == 50

    @pytest.mark.asyncio
    async def test_summarize_task_has_correct_batch_size(self):
        """summarize_text Task has batch_size matching chunks_per_batch."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks(chunks_per_batch=75)
            summarize_task = tasks[3]
            assert summarize_task.executable is summarize_text
            assert summarize_task.task_config["batch_size"] == 75

    @pytest.mark.asyncio
    async def test_add_data_points_task_has_correct_batch_size(self):
        """add_data_points Task has batch_size matching chunks_per_batch."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks(chunks_per_batch=200)
            add_task = tasks[4]
            assert add_task.executable is add_data_points
            assert add_task.task_config["batch_size"] == 200

    @pytest.mark.asyncio
    async def test_default_chunks_per_batch_is_100(self):
        """When chunks_per_batch is None, default to 100 for all batch tasks."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks(chunks_per_batch=None)
            # Check all batch-configured tasks
            for task in tasks:
                if hasattr(task, 'task_config') and "batch_size" in task.task_config:
                    assert task.task_config["batch_size"] == 100 or task.task_config["batch_size"] == 1

    @pytest.mark.asyncio
    async def test_classify_documents_no_batch_config(self):
        """classify_documents Task should NOT have a custom task_config (no batch_size override)."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks(chunks_per_batch=50)
            classify_task = tasks[0]
            assert classify_task.executable is classify_documents
            # classify_documents is created without task_config, so it gets default batch_size=1
            assert classify_task.task_config["batch_size"] == 1

    def test_task_creation_stores_batch_size_in_config(self):
        """Task constructed with task_config stores batch_size correctly."""
        dummy_func = lambda x: x
        task = Task(dummy_func, task_config={"batch_size": 42})
        assert task.task_config["batch_size"] == 42

    def test_task_without_config_gets_default_batch_size(self):
        """Task constructed without task_config gets default batch_size=1."""
        dummy_func = lambda x: x
        task = Task(dummy_func)
        assert task.task_config["batch_size"] == 1


# ---------------------------------------------------------------------------
# T408: Multi-round validation quality improvement
# ---------------------------------------------------------------------------


class TestT408MultiRoundValidation:
    """Test multi_round_validation config injection and filtering behavior."""

    @pytest.mark.asyncio
    async def test_validation_injected_when_enabled(self):
        """When multi_round_validation=True, validate_extracted_graph is in task list."""
        mock_config = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": True,
                    "confidence_threshold": 0.7,
                },
                "entity_resolution": {"enabled": False},
            }
        }
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)
            assert validate_extracted_graph in executables

    @pytest.mark.asyncio
    async def test_validation_not_injected_when_disabled(self):
        """When multi_round_validation=False, validate_extracted_graph is NOT in task list."""
        mock_config = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": False,
                },
                "entity_resolution": {"enabled": False},
            }
        }
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)
            assert validate_extracted_graph not in executables

    @pytest.mark.asyncio
    async def test_confidence_threshold_passed_to_validation_task(self):
        """confidence_threshold from config is passed to validate_extracted_graph task kwargs."""
        mock_config = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": True,
                    "confidence_threshold": 0.85,
                },
                "entity_resolution": {"enabled": False},
            }
        }
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            val_task = [t for t in tasks if t.executable is validate_extracted_graph][0]
            assert val_task.default_params["kwargs"]["confidence_threshold"] == 0.85

    @pytest.mark.asyncio
    async def test_validate_filters_low_confidence_relationships(self):
        """validate_extracted_graph filters out items below confidence_threshold when LLM succeeds."""
        data = [
            {"source_entity": "A", "target_entity": "B", "relationship": "knows", "source_text": "A knows B"},
            {"source_entity": "C", "target_entity": "D", "relationship": "likes", "source_text": "C likes D"},
            {"source_entity": "E", "target_entity": "F", "relationship": "hates", "source_text": "E hates F"},
        ]

        async def mock_llm(prompt):
            return [
                {"index": 0, "confidence": 0.95, "reason": "Strong"},
                {"index": 1, "confidence": 0.4, "reason": "Weak"},
                {"index": 2, "confidence": 0.75, "reason": "Medium"},
            ]

        result = await validate_extracted_graph(
            extracted_data=data,
            llm_client=mock_llm,
            confidence_threshold=0.7,
        )
        # Only items with confidence >= 0.7 should pass: index 0 (0.95) and index 2 (0.75)
        assert len(result) == 2
        sources = [r["source_entity"] for r in result]
        assert "A" in sources
        assert "E" in sources
        assert "C" not in sources

    @pytest.mark.asyncio
    async def test_validate_keeps_all_when_threshold_is_zero(self):
        """With confidence_threshold=0.0, all items should pass."""
        data = [
            {"source_entity": "A", "target_entity": "B", "relationship": "r", "source_text": "text"},
        ]

        async def mock_llm(prompt):
            return [{"index": 0, "confidence": 0.01, "reason": "Very weak"}]

        result = await validate_extracted_graph(
            extracted_data=data,
            llm_client=mock_llm,
            confidence_threshold=0.0,
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_default_confidence_threshold_is_0_7(self):
        """When config doesn't specify confidence_threshold, default is 0.7."""
        mock_config = {
            "graph_builder": {
                "extraction": {
                    "multi_round_validation": True,
                    # No confidence_threshold specified
                },
                "entity_resolution": {"enabled": False},
            }
        }
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            val_task = [t for t in tasks if t.executable is validate_extracted_graph][0]
            assert val_task.default_params["kwargs"]["confidence_threshold"] == 0.7


# ---------------------------------------------------------------------------
# T409: Entity resolution deduplication
# ---------------------------------------------------------------------------


class TestT409EntityResolution:
    """Test entity resolution injection and merging behavior."""

    @pytest.mark.asyncio
    async def test_entity_resolution_injected_when_enabled(self):
        """When entity_resolution.enabled=True, resolve_entities is in task list."""
        mock_config = {
            "graph_builder": {
                "extraction": {"multi_round_validation": False},
                "entity_resolution": {
                    "enabled": True,
                    "fuzzy_threshold": 0.85,
                    "embedding_threshold": 0.9,
                },
            }
        }
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)
            assert resolve_entities in executables

    @pytest.mark.asyncio
    async def test_entity_resolution_not_injected_when_disabled(self):
        """When entity_resolution.enabled=False, resolve_entities is NOT in task list."""
        mock_config = {
            "graph_builder": {
                "extraction": {"multi_round_validation": False},
                "entity_resolution": {"enabled": False},
            }
        }
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)
            assert resolve_entities not in executables

    @pytest.mark.asyncio
    async def test_fuzzy_and_embedding_thresholds_passed_correctly(self):
        """fuzzy_threshold and embedding_threshold from config are passed to resolve_entities."""
        mock_config = {
            "graph_builder": {
                "extraction": {"multi_round_validation": False},
                "entity_resolution": {
                    "enabled": True,
                    "fuzzy_threshold": 0.90,
                    "embedding_threshold": 0.95,
                },
            }
        }
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            res_task = [t for t in tasks if t.executable is resolve_entities][0]
            assert res_task.default_params["kwargs"]["fuzzy_threshold"] == 0.90
            assert res_task.default_params["kwargs"]["embedding_threshold"] == 0.95

    @pytest.mark.asyncio
    async def test_same_name_entities_get_merged(self):
        """Entities with identical names and types are merged."""
        entities = [
            {"name": "Google", "type": "company", "id": "1"},
            {"name": "Google", "type": "company", "id": "2"},
        ]
        result = await resolve_entities(entities=entities, fuzzy_threshold=0.85)
        assert len(result) == 1
        assert result[0]["name"] == "Google"
        assert "merged_from" in result[0]

    @pytest.mark.asyncio
    async def test_different_types_dont_merge(self):
        """Entities with different types should NOT be merged even if names match."""
        entities = [
            {"name": "Python", "type": "language"},
            {"name": "Python", "type": "animal"},
        ]
        result = await resolve_entities(entities=entities, fuzzy_threshold=0.85)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_similar_names_merge_above_threshold(self):
        """Similar names with similarity above fuzzy_threshold should merge."""
        entities = [
            {"name": "New York City", "type": "city", "id": "1"},
            {"name": "New York Cty", "type": "city", "id": "2"},  # Typo
        ]
        result = await resolve_entities(entities=entities, fuzzy_threshold=0.8)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_dissimilar_names_dont_merge(self):
        """Names with low similarity should NOT merge."""
        entities = [
            {"name": "Tokyo", "type": "city"},
            {"name": "London", "type": "city"},
        ]
        result = await resolve_entities(entities=entities, fuzzy_threshold=0.85)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_alias_matching_triggers_merge(self):
        """If entity name appears in another entity's aliases, they should merge."""
        entities = [
            {"name": "USA", "type": "country", "aliases": ["United States"]},
            {"name": "United States", "type": "country", "aliases": []},
        ]
        result = await resolve_entities(entities=entities, fuzzy_threshold=0.99)
        # Even with very high threshold, alias match should trigger merge
        assert len(result) == 1

    def test_should_merge_different_types(self):
        """_should_merge returns False for different entity types."""
        a = {"name": "Python", "type": "language"}
        b = {"name": "Python", "type": "animal"}
        assert _should_merge(a, b, 0.85) is False

    def test_should_merge_same_name_same_type(self):
        """_should_merge returns True for same name and type."""
        a = {"name": "Google", "type": "company"}
        b = {"name": "Google", "type": "company"}
        assert _should_merge(a, b, 0.85) is True

    def test_name_similarity_identical(self):
        """Identical names have similarity 1.0."""
        assert _name_similarity("Google", "Google") == 1.0

    def test_name_similarity_case_insensitive(self):
        """Name similarity is case insensitive."""
        assert _name_similarity("Google", "google") == 1.0

    def test_name_similarity_empty(self):
        """Empty name returns 0.0 similarity."""
        assert _name_similarity("", "Google") == 0.0
        assert _name_similarity("Google", "") == 0.0

    def test_merge_entity_group_picks_longest_name(self):
        """_merge_entity_group picks entity with longest name as primary."""
        group = [
            {"name": "MS", "type": "company", "id": "1"},
            {"name": "Microsoft Corporation", "type": "company", "id": "2"},
            {"name": "Microsoft", "type": "company", "id": "3"},
        ]
        merged = _merge_entity_group(group)
        assert merged["name"] == "Microsoft Corporation"
        assert "MS" in merged["aliases"]
        assert "Microsoft" in merged["aliases"]
        assert len(merged["merged_from"]) == 3


# ---------------------------------------------------------------------------
# T410: Temporal cognify task sequence and defaults
# ---------------------------------------------------------------------------


class TestT410TemporalCognify:
    """Test temporal cognify task sequence and configuration."""

    @pytest.mark.asyncio
    async def test_temporal_tasks_correct_sequence(self):
        """Temporal tasks include classify, extract_chunks, extract_events, extract_kg, add_data_points."""
        from cognee.api.v1.cognify.cognify import get_temporal_tasks
        from cognee.tasks.temporal_graph.extract_events_and_entities import (
            extract_events_and_timestamps,
        )
        from cognee.tasks.temporal_graph.extract_knowledge_graph_from_events import (
            extract_knowledge_graph_from_events,
        )

        tasks = await get_temporal_tasks()
        executables = _get_task_executables(tasks)

        assert len(tasks) == 5
        assert executables[0] is classify_documents
        assert executables[1] is extract_chunks_from_documents
        assert executables[2] is extract_events_and_timestamps
        assert executables[3] is extract_knowledge_graph_from_events
        assert executables[4] is add_data_points

    @pytest.mark.asyncio
    async def test_temporal_cognify_flag_activates_temporal_tasks(self):
        """temporal_cognify=True in cognify() should use get_temporal_tasks."""
        mock_executor = AsyncMock(return_value={"result": "ok"})

        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor), \
             patch("cognee.api.v1.cognify.cognify.get_temporal_tasks", new_callable=AsyncMock) as mock_temporal, \
             patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock) as mock_default:
            mock_temporal.return_value = [Task(classify_documents)]
            mock_default.return_value = [Task(classify_documents)]

            from cognee.api.v1.cognify.cognify import cognify

            await cognify(temporal_cognify=True)
            mock_temporal.assert_called_once()
            mock_default.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_temporal_cognify_uses_default_tasks(self):
        """temporal_cognify=False (default) should use get_default_tasks."""
        mock_executor = AsyncMock(return_value={"result": "ok"})

        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor), \
             patch("cognee.api.v1.cognify.cognify.get_temporal_tasks", new_callable=AsyncMock) as mock_temporal, \
             patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock) as mock_default:
            mock_temporal.return_value = [Task(classify_documents)]
            mock_default.return_value = [Task(classify_documents)]

            from cognee.api.v1.cognify.cognify import cognify

            await cognify(temporal_cognify=False)
            mock_default.assert_called_once()
            mock_temporal.assert_not_called()

    @pytest.mark.asyncio
    async def test_temporal_default_chunks_per_batch_is_10(self):
        """When chunks_per_batch is None, temporal tasks default to 10."""
        from cognee.api.v1.cognify.cognify import get_temporal_tasks

        tasks = await get_temporal_tasks(chunks_per_batch=None)
        # extract_events_and_timestamps task should have batch_size=10
        events_task = tasks[2]
        assert events_task.task_config["batch_size"] == 10

    @pytest.mark.asyncio
    async def test_temporal_custom_chunks_per_batch(self):
        """Custom chunks_per_batch is passed through to temporal tasks."""
        from cognee.api.v1.cognify.cognify import get_temporal_tasks

        tasks = await get_temporal_tasks(chunks_per_batch=25)
        events_task = tasks[2]
        assert events_task.task_config["batch_size"] == 25
        add_task = tasks[4]
        assert add_task.task_config["batch_size"] == 25

    @pytest.mark.asyncio
    async def test_temporal_tasks_count(self):
        """Temporal pipeline has exactly 5 tasks."""
        from cognee.api.v1.cognify.cognify import get_temporal_tasks

        tasks = await get_temporal_tasks()
        assert len(tasks) == 5

    @pytest.mark.asyncio
    async def test_temporal_extract_events_has_batch_config(self):
        """extract_events_and_timestamps task has task_config with batch_size."""
        from cognee.api.v1.cognify.cognify import get_temporal_tasks

        tasks = await get_temporal_tasks(chunks_per_batch=15)
        events_task = tasks[2]
        assert "batch_size" in events_task.task_config
        assert events_task.task_config["batch_size"] == 15
