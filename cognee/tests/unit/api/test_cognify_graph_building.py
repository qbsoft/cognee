"""
Tests for Cognify graph building verification (T401-T404).

T401: Test cognify default pipeline (text -> entities -> relationships)
T402: Test custom DataPoint model cognify
T403: Verify graph database node and edge correctness
T404: Test cognify concurrent execution
"""
import inspect
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pydantic import BaseModel

from cognee.modules.pipelines.tasks.task import Task
from cognee.shared.data_models import KnowledgeGraph
from cognee.modules.chunking.TextChunker import TextChunker
from cognee.tasks.documents import classify_documents, extract_chunks_from_documents
from cognee.tasks.graph import extract_graph_from_data
from cognee.tasks.summarization import summarize_text
from cognee.tasks.storage import add_data_points


def _get_task_executables(tasks):
    """Helper to extract the executable function from each Task."""
    return [t.executable for t in tasks]


# ---------------------------------------------------------------------------
# T401: Test cognify default pipeline (text -> entities -> relationships)
# ---------------------------------------------------------------------------


class TestT401DefaultPipeline:
    """T401: Test that get_default_tasks returns correct task list in order."""

    @pytest.mark.asyncio
    async def test_default_tasks_returns_expected_task_list(self):
        """get_default_tasks() should return the 5 core tasks in correct order."""
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
    async def test_default_tasks_all_are_task_instances(self):
        """Every element returned by get_default_tasks() must be a Task instance."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            for task in tasks:
                assert isinstance(task, Task), f"Expected Task instance, got {type(task)}"

    @pytest.mark.asyncio
    async def test_default_tasks_order_classify_before_extract(self):
        """classify_documents must come before extract_chunks_from_documents."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)

            classify_idx = executables.index(classify_documents)
            extract_idx = executables.index(extract_chunks_from_documents)
            assert classify_idx < extract_idx

    @pytest.mark.asyncio
    async def test_default_tasks_order_extract_graph_after_chunks(self):
        """extract_graph_from_data must come after extract_chunks_from_documents."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)

            chunks_idx = executables.index(extract_chunks_from_documents)
            graph_idx = executables.index(extract_graph_from_data)
            assert chunks_idx < graph_idx

    @pytest.mark.asyncio
    async def test_default_tasks_order_summarize_after_graph(self):
        """summarize_text must come after extract_graph_from_data."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)

            graph_idx = executables.index(extract_graph_from_data)
            summarize_idx = executables.index(summarize_text)
            assert graph_idx < summarize_idx

    @pytest.mark.asyncio
    async def test_default_tasks_order_add_data_points_last(self):
        """add_data_points must be the last core task."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()
            executables = _get_task_executables(tasks)

            assert executables[-1] is add_data_points

    def test_cognify_function_signature_accepts_documented_parameters(self):
        """cognify() must accept all documented parameters in its signature."""
        from cognee.api.v1.cognify.cognify import cognify

        sig = inspect.signature(cognify)
        param_names = list(sig.parameters.keys())

        expected_params = [
            "datasets",
            "user",
            "graph_model",
            "chunker",
            "chunk_size",
            "chunks_per_batch",
            "config",
            "vector_db_config",
            "graph_db_config",
            "run_in_background",
            "incremental_loading",
            "custom_prompt",
            "temporal_cognify",
            "data_per_batch",
        ]

        for param in expected_params:
            assert param in param_names, f"Parameter '{param}' not found in cognify signature"

    def test_cognify_is_async_function(self):
        """cognify must be an async function (coroutine function)."""
        from cognee.api.v1.cognify.cognify import cognify

        assert inspect.iscoroutinefunction(cognify)

    def test_get_default_tasks_is_async_function(self):
        """get_default_tasks must be an async function."""
        from cognee.api.v1.cognify.cognify import get_default_tasks

        assert inspect.iscoroutinefunction(get_default_tasks)


# ---------------------------------------------------------------------------
# T402: Test custom DataPoint model cognify
# ---------------------------------------------------------------------------


class CustomGraphModel(BaseModel):
    """A custom graph model for testing."""
    entity_name: str = ""
    entity_type: str = ""
    relationship: str = ""


class TestT402CustomDataPointModel:
    """T402: Test that custom graph_model is correctly passed through."""

    @pytest.mark.asyncio
    async def test_custom_graph_model_passed_to_extract_graph(self):
        """When a custom graph_model is provided, it must be passed to extract_graph_from_data Task kwargs."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks(graph_model=CustomGraphModel)

            # extract_graph_from_data is at index 2
            extract_graph_task = tasks[2]
            assert extract_graph_task.executable is extract_graph_from_data
            assert extract_graph_task.default_params["kwargs"]["graph_model"] is CustomGraphModel

    @pytest.mark.asyncio
    async def test_custom_pydantic_model_accepted(self):
        """A custom Pydantic BaseModel can be passed as graph_model parameter without error."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            # Should not raise any exception
            tasks = await get_default_tasks(graph_model=CustomGraphModel)
            assert len(tasks) >= 5

    @pytest.mark.asyncio
    async def test_graph_model_defaults_to_knowledge_graph(self):
        """When graph_model is not provided, it should default to KnowledgeGraph."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()

            extract_graph_task = tasks[2]
            assert extract_graph_task.executable is extract_graph_from_data
            assert extract_graph_task.default_params["kwargs"]["graph_model"] is KnowledgeGraph

    @pytest.mark.asyncio
    async def test_default_tasks_signature_graph_model_default(self):
        """get_default_tasks signature default for graph_model should be KnowledgeGraph."""
        from cognee.api.v1.cognify.cognify import get_default_tasks

        sig = inspect.signature(get_default_tasks)
        graph_model_param = sig.parameters["graph_model"]
        assert graph_model_param.default is KnowledgeGraph

    @pytest.mark.asyncio
    async def test_cognify_signature_graph_model_default(self):
        """cognify signature default for graph_model should be KnowledgeGraph."""
        from cognee.api.v1.cognify.cognify import cognify

        sig = inspect.signature(cognify)
        graph_model_param = sig.parameters["graph_model"]
        assert graph_model_param.default is KnowledgeGraph

    @pytest.mark.asyncio
    async def test_custom_graph_model_does_not_affect_other_tasks(self):
        """Passing custom graph_model should not change other tasks in the pipeline."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks(graph_model=CustomGraphModel)
            executables = _get_task_executables(tasks)

            assert executables[0] is classify_documents
            assert executables[1] is extract_chunks_from_documents
            assert executables[3] is summarize_text
            assert executables[4] is add_data_points


# ---------------------------------------------------------------------------
# T403: Verify graph database node and edge correctness
# ---------------------------------------------------------------------------


class TestT403GraphDatabaseConfig:
    """T403: Verify config parameter handling for extract_graph_from_data."""

    @pytest.mark.asyncio
    async def test_extract_graph_receives_config_parameter(self):
        """extract_graph_from_data Task should receive config in its kwargs."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()

            extract_graph_task = tasks[2]
            assert extract_graph_task.executable is extract_graph_from_data
            assert "config" in extract_graph_task.default_params["kwargs"]

    @pytest.mark.asyncio
    async def test_config_dict_has_ontology_config_key(self):
        """The config dict structure must include an 'ontology_config' key."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()

            extract_graph_task = tasks[2]
            config = extract_graph_task.default_params["kwargs"]["config"]
            assert "ontology_config" in config

    @pytest.mark.asyncio
    async def test_config_ontology_config_has_resolver(self):
        """The ontology_config must include an 'ontology_resolver' key."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()

            extract_graph_task = tasks[2]
            config = extract_graph_task.default_params["kwargs"]["config"]
            assert "ontology_resolver" in config["ontology_config"]

    @pytest.mark.asyncio
    async def test_env_ontology_set_uses_get_ontology_resolver_from_env(self):
        """When ontology env config is fully set, get_ontology_resolver_from_env should be called."""
        mock_env_config = MagicMock()
        mock_env_config.ontology_file_path = "/path/to/ontology.owl"
        mock_env_config.ontology_resolver = "rdflib"
        mock_env_config.matching_strategy = "fuzzy"
        mock_env_config.to_dict.return_value = {
            "ontology_file_path": "/path/to/ontology.owl",
            "ontology_resolver": "rdflib",
            "matching_strategy": "fuzzy",
        }

        mock_resolver = MagicMock()

        with patch("cognee.api.v1.cognify.cognify.get_ontology_env_config", return_value=mock_env_config), \
             patch("cognee.api.v1.cognify.cognify.get_ontology_resolver_from_env", return_value=mock_resolver) as mock_from_env, \
             patch("cognee.api.v1.cognify.cognify.get_default_ontology_resolver") as mock_default, \
             patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()

            mock_from_env.assert_called_once_with(
                ontology_file_path="/path/to/ontology.owl",
                ontology_resolver="rdflib",
                matching_strategy="fuzzy",
            )
            mock_default.assert_not_called()

            # Verify the resolver is set in config
            extract_graph_task = tasks[2]
            config = extract_graph_task.default_params["kwargs"]["config"]
            assert config["ontology_config"]["ontology_resolver"] is mock_resolver

    @pytest.mark.asyncio
    async def test_env_ontology_not_set_uses_default_resolver(self):
        """When ontology env config is NOT set (empty file path), get_default_ontology_resolver should be called."""
        mock_env_config = MagicMock()
        mock_env_config.ontology_file_path = ""
        mock_env_config.ontology_resolver = "rdflib"
        mock_env_config.matching_strategy = "fuzzy"

        mock_resolver = MagicMock()

        with patch("cognee.api.v1.cognify.cognify.get_ontology_env_config", return_value=mock_env_config), \
             patch("cognee.api.v1.cognify.cognify.get_ontology_resolver_from_env") as mock_from_env, \
             patch("cognee.api.v1.cognify.cognify.get_default_ontology_resolver", return_value=mock_resolver) as mock_default, \
             patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()

            mock_default.assert_called_once()
            mock_from_env.assert_not_called()

            # Verify the default resolver is set in config
            extract_graph_task = tasks[2]
            config = extract_graph_task.default_params["kwargs"]["config"]
            assert config["ontology_config"]["ontology_resolver"] is mock_resolver

    @pytest.mark.asyncio
    async def test_env_ontology_missing_resolver_uses_default(self):
        """When ontology resolver is empty, should fall back to default resolver."""
        mock_env_config = MagicMock()
        mock_env_config.ontology_file_path = "/some/path"
        mock_env_config.ontology_resolver = ""  # Empty resolver
        mock_env_config.matching_strategy = "fuzzy"

        mock_resolver = MagicMock()

        with patch("cognee.api.v1.cognify.cognify.get_ontology_env_config", return_value=mock_env_config), \
             patch("cognee.api.v1.cognify.cognify.get_ontology_resolver_from_env") as mock_from_env, \
             patch("cognee.api.v1.cognify.cognify.get_default_ontology_resolver", return_value=mock_resolver) as mock_default, \
             patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks()

            # Empty ontology_resolver is falsy, so default should be used
            mock_default.assert_called_once()
            mock_from_env.assert_not_called()

    @pytest.mark.asyncio
    async def test_explicit_config_skips_env_resolution(self):
        """When config is explicitly provided, env config resolution should be skipped."""
        explicit_config = {
            "ontology_config": {"ontology_resolver": MagicMock()}
        }

        with patch("cognee.api.v1.cognify.cognify.get_ontology_env_config") as mock_get_env, \
             patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            tasks = await get_default_tasks(config=explicit_config)

            # When config is explicitly provided, env config should not be consulted
            mock_get_env.assert_not_called()

            extract_graph_task = tasks[2]
            config = extract_graph_task.default_params["kwargs"]["config"]
            assert config is explicit_config

    @pytest.mark.asyncio
    async def test_custom_prompt_passed_to_extract_graph(self):
        """custom_prompt should be passed through to extract_graph_from_data Task."""
        with patch("cognee.api.v1.cognify.cognify.get_module_config", return_value={}):
            from cognee.api.v1.cognify.cognify import get_default_tasks

            custom_prompt = "Extract all scientific entities and their relationships."
            tasks = await get_default_tasks(custom_prompt=custom_prompt)

            extract_graph_task = tasks[2]
            assert extract_graph_task.default_params["kwargs"]["custom_prompt"] == custom_prompt


# ---------------------------------------------------------------------------
# T404: Test cognify concurrent execution
# ---------------------------------------------------------------------------


class TestT404ConcurrentExecution:
    """T404: Test cognify background/blocking execution modes."""

    @pytest.mark.asyncio
    async def test_run_in_background_true_gets_background_executor(self):
        """cognify with run_in_background=True should call get_pipeline_executor with run_in_background=True."""
        from cognee.modules.pipelines.layers.pipeline_execution_mode import (
            run_pipeline_as_background_process,
            run_pipeline_blocking,
        )

        mock_executor = AsyncMock(return_value={})

        with patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock, return_value=[]), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor) as mock_get_executor, \
             patch("cognee.api.v1.cognify.cognify.get_ontology_env_config") as mock_env:
            mock_env_config = MagicMock()
            mock_env_config.ontology_file_path = ""
            mock_env_config.ontology_resolver = ""
            mock_env_config.matching_strategy = ""
            mock_env.return_value = mock_env_config

            from cognee.api.v1.cognify.cognify import cognify

            await cognify(run_in_background=True)

            mock_get_executor.assert_called_once_with(run_in_background=True)

    @pytest.mark.asyncio
    async def test_run_in_background_false_gets_blocking_executor(self):
        """cognify with run_in_background=False should call get_pipeline_executor with run_in_background=False."""
        mock_executor = AsyncMock(return_value={})

        with patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock, return_value=[]), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor) as mock_get_executor, \
             patch("cognee.api.v1.cognify.cognify.get_ontology_env_config") as mock_env:
            mock_env_config = MagicMock()
            mock_env_config.ontology_file_path = ""
            mock_env_config.ontology_resolver = ""
            mock_env_config.matching_strategy = ""
            mock_env.return_value = mock_env_config

            from cognee.api.v1.cognify.cognify import cognify

            await cognify(run_in_background=False)

            mock_get_executor.assert_called_once_with(run_in_background=False)

    @pytest.mark.asyncio
    async def test_default_run_in_background_is_false(self):
        """By default, run_in_background should be False."""
        mock_executor = AsyncMock(return_value={})

        with patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock, return_value=[]), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor) as mock_get_executor, \
             patch("cognee.api.v1.cognify.cognify.get_ontology_env_config") as mock_env:
            mock_env_config = MagicMock()
            mock_env_config.ontology_file_path = ""
            mock_env_config.ontology_resolver = ""
            mock_env_config.matching_strategy = ""
            mock_env.return_value = mock_env_config

            from cognee.api.v1.cognify.cognify import cognify

            await cognify()

            mock_get_executor.assert_called_once_with(run_in_background=False)

    @pytest.mark.asyncio
    async def test_pipeline_executor_receives_expected_kwargs(self):
        """The pipeline_executor_func should receive all expected kwargs."""
        mock_executor = AsyncMock(return_value={})
        mock_tasks = [MagicMock(), MagicMock()]
        mock_user = MagicMock()

        with patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock, return_value=mock_tasks), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor), \
             patch("cognee.api.v1.cognify.cognify.run_pipeline") as mock_run_pipeline, \
             patch("cognee.api.v1.cognify.cognify.get_ontology_env_config") as mock_env:
            mock_env_config = MagicMock()
            mock_env_config.ontology_file_path = ""
            mock_env_config.ontology_resolver = ""
            mock_env_config.matching_strategy = ""
            mock_env.return_value = mock_env_config

            from cognee.api.v1.cognify.cognify import cognify

            await cognify(
                datasets=["test_dataset"],
                user=mock_user,
            )

            mock_executor.assert_called_once()
            call_kwargs = mock_executor.call_args

            # Check that all expected kwargs are present
            assert call_kwargs.kwargs["pipeline"] is mock_run_pipeline
            assert call_kwargs.kwargs["tasks"] is mock_tasks
            assert call_kwargs.kwargs["user"] is mock_user
            assert call_kwargs.kwargs["datasets"] == ["test_dataset"]
            assert "vector_db_config" in call_kwargs.kwargs
            assert "graph_db_config" in call_kwargs.kwargs
            assert "incremental_loading" in call_kwargs.kwargs
            assert call_kwargs.kwargs["pipeline_name"] == "cognify_pipeline"
            assert "data_per_batch" in call_kwargs.kwargs

    @pytest.mark.asyncio
    async def test_pipeline_executor_receives_custom_vector_db_config(self):
        """Custom vector_db_config should be passed through to executor."""
        mock_executor = AsyncMock(return_value={})
        custom_vector_config = {"provider": "qdrant", "host": "localhost"}

        with patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock, return_value=[]), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor), \
             patch("cognee.api.v1.cognify.cognify.get_ontology_env_config") as mock_env:
            mock_env_config = MagicMock()
            mock_env_config.ontology_file_path = ""
            mock_env_config.ontology_resolver = ""
            mock_env_config.matching_strategy = ""
            mock_env.return_value = mock_env_config

            from cognee.api.v1.cognify.cognify import cognify

            await cognify(vector_db_config=custom_vector_config)

            call_kwargs = mock_executor.call_args.kwargs
            assert call_kwargs["vector_db_config"] is custom_vector_config

    @pytest.mark.asyncio
    async def test_pipeline_executor_receives_custom_graph_db_config(self):
        """Custom graph_db_config should be passed through to executor."""
        mock_executor = AsyncMock(return_value={})
        custom_graph_config = {"provider": "neo4j", "url": "bolt://localhost:7687"}

        with patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock, return_value=[]), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor), \
             patch("cognee.api.v1.cognify.cognify.get_ontology_env_config") as mock_env:
            mock_env_config = MagicMock()
            mock_env_config.ontology_file_path = ""
            mock_env_config.ontology_resolver = ""
            mock_env_config.matching_strategy = ""
            mock_env.return_value = mock_env_config

            from cognee.api.v1.cognify.cognify import cognify

            await cognify(graph_db_config=custom_graph_config)

            call_kwargs = mock_executor.call_args.kwargs
            assert call_kwargs["graph_db_config"] is custom_graph_config

    @pytest.mark.asyncio
    async def test_pipeline_executor_receives_incremental_loading(self):
        """incremental_loading parameter should be passed to executor."""
        mock_executor = AsyncMock(return_value={})

        with patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock, return_value=[]), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor), \
             patch("cognee.api.v1.cognify.cognify.get_ontology_env_config") as mock_env:
            mock_env_config = MagicMock()
            mock_env_config.ontology_file_path = ""
            mock_env_config.ontology_resolver = ""
            mock_env_config.matching_strategy = ""
            mock_env.return_value = mock_env_config

            from cognee.api.v1.cognify.cognify import cognify

            await cognify(incremental_loading=False)

            call_kwargs = mock_executor.call_args.kwargs
            assert call_kwargs["incremental_loading"] is False

    @pytest.mark.asyncio
    async def test_pipeline_executor_receives_data_per_batch(self):
        """data_per_batch parameter should be passed to executor."""
        mock_executor = AsyncMock(return_value={})

        with patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock, return_value=[]), \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor), \
             patch("cognee.api.v1.cognify.cognify.get_ontology_env_config") as mock_env:
            mock_env_config = MagicMock()
            mock_env_config.ontology_file_path = ""
            mock_env_config.ontology_resolver = ""
            mock_env_config.matching_strategy = ""
            mock_env.return_value = mock_env_config

            from cognee.api.v1.cognify.cognify import cognify

            await cognify(data_per_batch=50)

            call_kwargs = mock_executor.call_args.kwargs
            assert call_kwargs["data_per_batch"] == 50

    def test_get_pipeline_executor_returns_blocking_for_false(self):
        """get_pipeline_executor(run_in_background=False) should return run_pipeline_blocking."""
        from cognee.modules.pipelines.layers.pipeline_execution_mode import (
            get_pipeline_executor,
            run_pipeline_blocking,
        )

        executor = get_pipeline_executor(run_in_background=False)
        assert executor is run_pipeline_blocking

    def test_get_pipeline_executor_returns_background_for_true(self):
        """get_pipeline_executor(run_in_background=True) should return run_pipeline_as_background_process."""
        from cognee.modules.pipelines.layers.pipeline_execution_mode import (
            get_pipeline_executor,
            run_pipeline_as_background_process,
        )

        executor = get_pipeline_executor(run_in_background=True)
        assert executor is run_pipeline_as_background_process

    def test_get_pipeline_executor_defaults_to_blocking(self):
        """get_pipeline_executor() with no args should default to blocking (run_in_background=False)."""
        from cognee.modules.pipelines.layers.pipeline_execution_mode import (
            get_pipeline_executor,
            run_pipeline_blocking,
        )

        executor = get_pipeline_executor()
        assert executor is run_pipeline_blocking

    @pytest.mark.asyncio
    async def test_temporal_cognify_uses_temporal_tasks(self):
        """When temporal_cognify=True, cognify should call get_temporal_tasks instead of get_default_tasks."""
        mock_executor = AsyncMock(return_value={})
        mock_temporal_tasks = [MagicMock(), MagicMock()]

        with patch("cognee.api.v1.cognify.cognify.get_temporal_tasks", new_callable=AsyncMock, return_value=mock_temporal_tasks) as mock_get_temporal, \
             patch("cognee.api.v1.cognify.cognify.get_default_tasks", new_callable=AsyncMock) as mock_get_default, \
             patch("cognee.api.v1.cognify.cognify.get_pipeline_executor", return_value=mock_executor), \
             patch("cognee.api.v1.cognify.cognify.get_ontology_env_config") as mock_env:
            mock_env_config = MagicMock()
            mock_env_config.ontology_file_path = ""
            mock_env_config.ontology_resolver = ""
            mock_env_config.matching_strategy = ""
            mock_env.return_value = mock_env_config

            from cognee.api.v1.cognify.cognify import cognify

            await cognify(temporal_cognify=True)

            mock_get_temporal.assert_called_once()
            mock_get_default.assert_not_called()

            # Verify temporal tasks were passed to executor
            call_kwargs = mock_executor.call_args.kwargs
            assert call_kwargs["tasks"] is mock_temporal_tasks
