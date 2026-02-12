"""
Tests for conditional injection of graph validation and entity resolution
into the cognify pipeline based on YAML configuration (T2B01).
"""
import pytest
from unittest.mock import patch, MagicMock

from cognee.modules.pipelines.tasks.task import Task
from cognee.tasks.documents import classify_documents, extract_chunks_from_documents
from cognee.tasks.graph import extract_graph_from_data
from cognee.tasks.summarization import summarize_text
from cognee.tasks.storage import add_data_points
from cognee.tasks.graph_validation import validate_extracted_graph
from cognee.tasks.entity_resolution import resolve_entities


def _get_task_executables(tasks):
    """Helper to extract the executable function from each Task."""
    return [t.executable for t in tasks]


@pytest.mark.asyncio
async def test_default_tasks_without_config():
    """When YAML config is not loaded (empty dict), task list should be the original 5 tasks."""
    with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
        from cognee.api.v1.cognify.cognify import get_default_tasks

        tasks = await get_default_tasks()
        executables = _get_task_executables(tasks)

        assert len(tasks) == 5
        assert executables[0] is classify_documents
        assert executables[1] is extract_chunks_from_documents
        assert executables[2] is extract_graph_from_data
        assert executables[3] is summarize_text
        assert executables[4] is add_data_points


@pytest.mark.asyncio
async def test_tasks_with_validation_enabled():
    """When multi_round_validation is true, validate_extracted_graph should appear after extract_graph_from_data."""
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
    with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
        from cognee.api.v1.cognify.cognify import get_default_tasks

        tasks = await get_default_tasks()
        executables = _get_task_executables(tasks)

        assert len(tasks) == 6
        assert executables[0] is classify_documents
        assert executables[1] is extract_chunks_from_documents
        assert executables[2] is extract_graph_from_data
        assert executables[3] is validate_extracted_graph
        assert executables[4] is summarize_text
        assert executables[5] is add_data_points


@pytest.mark.asyncio
async def test_tasks_with_entity_resolution_enabled():
    """When entity_resolution.enabled is true (but validation disabled), resolve_entities should be in the task list."""
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
    with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
        from cognee.api.v1.cognify.cognify import get_default_tasks

        tasks = await get_default_tasks()
        executables = _get_task_executables(tasks)

        assert len(tasks) == 6
        assert executables[0] is classify_documents
        assert executables[1] is extract_chunks_from_documents
        assert executables[2] is extract_graph_from_data
        assert executables[3] is resolve_entities
        assert executables[4] is summarize_text
        assert executables[5] is add_data_points


@pytest.mark.asyncio
async def test_tasks_with_both_enabled():
    """When both features are enabled, the order should be:
    classify -> extract_chunks -> extract_graph -> validate -> resolve -> summarize -> add_data_points (7 tasks)."""
    mock_config = {
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
    with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
        from cognee.api.v1.cognify.cognify import get_default_tasks

        tasks = await get_default_tasks()
        executables = _get_task_executables(tasks)

        assert len(tasks) == 7
        assert executables[0] is classify_documents
        assert executables[1] is extract_chunks_from_documents
        assert executables[2] is extract_graph_from_data
        assert executables[3] is validate_extracted_graph
        assert executables[4] is resolve_entities
        assert executables[5] is summarize_text
        assert executables[6] is add_data_points


@pytest.mark.asyncio
async def test_tasks_with_both_disabled():
    """When both features are explicitly disabled, original 5 tasks unchanged."""
    mock_config = {
        "graph_builder": {
            "extraction": {
                "multi_round_validation": False,
                "confidence_threshold": 0.7,
            },
            "entity_resolution": {
                "enabled": False,
                "fuzzy_threshold": 0.85,
                "embedding_threshold": 0.9,
            },
        }
    }
    with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
        from cognee.api.v1.cognify.cognify import get_default_tasks

        tasks = await get_default_tasks()
        executables = _get_task_executables(tasks)

        assert len(tasks) == 5
        assert executables[0] is classify_documents
        assert executables[1] is extract_chunks_from_documents
        assert executables[2] is extract_graph_from_data
        assert executables[3] is summarize_text
        assert executables[4] is add_data_points


@pytest.mark.asyncio
async def test_confidence_threshold_from_config():
    """Verify that confidence_threshold from YAML is passed to validate_extracted_graph Task kwargs."""
    mock_config = {
        "graph_builder": {
            "extraction": {
                "multi_round_validation": True,
                "confidence_threshold": 0.85,
            },
            "entity_resolution": {
                "enabled": False,
            },
        }
    }
    with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value=mock_config):
        from cognee.api.v1.cognify.cognify import get_default_tasks

        tasks = await get_default_tasks()
        # The validate_extracted_graph task should be at index 3
        validation_task = tasks[3]
        assert validation_task.executable is validate_extracted_graph
        # Check that the confidence_threshold was passed via kwargs
        assert validation_task.default_params["kwargs"]["confidence_threshold"] == 0.85


@pytest.mark.asyncio
async def test_fuzzy_threshold_from_config():
    """Verify that fuzzy_threshold from YAML is passed to resolve_entities Task kwargs."""
    mock_config = {
        "graph_builder": {
            "extraction": {
                "multi_round_validation": False,
            },
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
        # The resolve_entities task should be at index 3
        resolution_task = tasks[3]
        assert resolution_task.executable is resolve_entities
        assert resolution_task.default_params["kwargs"]["fuzzy_threshold"] == 0.90
        assert resolution_task.default_params["kwargs"]["embedding_threshold"] == 0.95
