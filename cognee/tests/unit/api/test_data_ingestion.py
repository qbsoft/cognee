"""
Tests for data ingestion pipeline (T301 + T302).

T301: Text data adding via add() pipeline
T302: URL data crawling and storage

These are mock-based unit tests that verify the pipeline wiring and data flow
without requiring real database or LLM connections.
"""
import hashlib
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, ANY
from uuid import uuid4, UUID

from cognee.modules.ingestion.classify import classify
from cognee.modules.ingestion.data_types import TextData, BinaryData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_user():
    """Create a minimal mock User object for testing."""
    user = MagicMock()
    user.id = uuid4()
    user.tenant_id = None
    return user


def _make_mock_dataset(dataset_id=None):
    """Create a minimal mock Dataset object for testing."""
    ds = MagicMock()
    ds.id = dataset_id or uuid4()
    ds.data = []
    return ds


def _make_mock_loader_engine():
    """Create a minimal mock loader engine."""
    loader = MagicMock()
    loader.loader_name = "text_loader"
    return loader


# ---------------------------------------------------------------------------
# T301 - Text data adding tests
# ---------------------------------------------------------------------------


class TestClassifyText:
    """Test that classify() correctly handles text strings."""

    def test_classify_plain_text_returns_text_data(self):
        """classify('hello world') should return a TextData instance."""
        result = classify("hello world")
        assert isinstance(result, TextData)

    def test_classify_preserves_text_content(self):
        """The TextData should contain the original text."""
        text = "Natural language processing is a field of AI."
        result = classify(text)
        assert result.data == text

    def test_classify_text_metadata_has_content_hash(self):
        """TextData metadata should include a content_hash derived from text."""
        text = "some test content"
        result = classify(text)
        metadata = result.get_metadata()
        expected_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        assert metadata["content_hash"] == expected_hash

    def test_classify_text_metadata_name_is_txt(self):
        """TextData metadata name should end with .txt."""
        result = classify("test")
        metadata = result.get_metadata()
        assert metadata["name"].endswith(".txt")
        assert metadata["name"].startswith("text_")

    def test_classify_url_string_still_returns_text_data(self):
        """classify() treats all strings as TextData, including URLs.
        The URL detection happens upstream in save_data_item_to_storage, not classify."""
        result = classify("https://example.com")
        assert isinstance(result, TextData)

    def test_classify_empty_string(self):
        """An empty string should still produce a TextData instance."""
        result = classify("")
        assert isinstance(result, TextData)
        assert result.data == ""


class TestAddTextCreatesDataObjects:
    """T301-1: Verify that add('some text') triggers the pipeline and ingestion creates Data objects."""

    @pytest.mark.asyncio
    async def test_add_text_calls_run_pipeline(self):
        """Calling add('some text') should invoke run_pipeline with correct tasks."""
        mock_user = _make_mock_user()
        mock_dataset = _make_mock_dataset()

        # Create an async generator that yields a mock run_info
        async def mock_run_pipeline_gen(**kwargs):
            yield MagicMock(status="completed")

        with patch("cognee.api.v1.add.add.setup", new_callable=AsyncMock) as mock_setup, \
             patch("cognee.api.v1.add.add.resolve_authorized_user_dataset",
                   new_callable=AsyncMock,
                   return_value=(mock_user, mock_dataset)) as mock_resolve, \
             patch("cognee.api.v1.add.add.reset_dataset_pipeline_run_status",
                   new_callable=AsyncMock) as mock_reset, \
             patch("cognee.api.v1.add.add.run_pipeline",
                   side_effect=mock_run_pipeline_gen) as mock_run:

            from cognee.api.v1.add.add import add
            result = await add("some text", dataset_name="test_ds", user=mock_user)

            # Verify setup was called
            mock_setup.assert_called_once()

            # Verify run_pipeline was called
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args
            # Tasks should be a list of 2 Task objects (resolve_data_directories, ingest_data)
            tasks = call_kwargs.kwargs.get("tasks") or call_kwargs[1].get("tasks")
            assert len(tasks) == 2

            # Verify the data passed to pipeline
            data_arg = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
            assert data_arg == "some text"

    @pytest.mark.asyncio
    async def test_add_text_pipeline_tasks_are_correct(self):
        """The pipeline tasks should be resolve_data_directories and ingest_data."""
        mock_user = _make_mock_user()
        mock_dataset = _make_mock_dataset()

        async def mock_run_pipeline_gen(**kwargs):
            yield MagicMock(status="completed")

        with patch("cognee.api.v1.add.add.setup", new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.resolve_authorized_user_dataset",
                   new_callable=AsyncMock,
                   return_value=(mock_user, mock_dataset)), \
             patch("cognee.api.v1.add.add.reset_dataset_pipeline_run_status",
                   new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.run_pipeline",
                   side_effect=mock_run_pipeline_gen) as mock_run:

            from cognee.api.v1.add.add import add
            from cognee.tasks.ingestion import ingest_data, resolve_data_directories

            await add("hello world", dataset_name="test_ds", user=mock_user)

            call_kwargs = mock_run.call_args
            tasks = call_kwargs.kwargs.get("tasks") or call_kwargs[1].get("tasks")
            executables = [t.executable for t in tasks]
            assert executables[0] is resolve_data_directories
            assert executables[1] is ingest_data

    @pytest.mark.asyncio
    async def test_add_text_returns_pipeline_run_info(self):
        """add() should return the pipeline run info from the last iteration."""
        mock_user = _make_mock_user()
        mock_dataset = _make_mock_dataset()
        expected_info = MagicMock(status="completed", pipeline_id="test_123")

        async def mock_run_pipeline_gen(**kwargs):
            yield expected_info

        with patch("cognee.api.v1.add.add.setup", new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.resolve_authorized_user_dataset",
                   new_callable=AsyncMock,
                   return_value=(mock_user, mock_dataset)), \
             patch("cognee.api.v1.add.add.reset_dataset_pipeline_run_status",
                   new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.run_pipeline",
                   side_effect=mock_run_pipeline_gen):

            from cognee.api.v1.add.add import add
            result = await add("some text", user=mock_user)

            assert result is expected_info


class TestAddMultipleTexts:
    """T301-4: Test adding multiple strings."""

    @pytest.mark.asyncio
    async def test_add_multiple_texts_passes_list_to_pipeline(self):
        """When a list of strings is passed, they should all reach the pipeline as data."""
        mock_user = _make_mock_user()
        mock_dataset = _make_mock_dataset()

        async def mock_run_pipeline_gen(**kwargs):
            yield MagicMock(status="completed")

        with patch("cognee.api.v1.add.add.setup", new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.resolve_authorized_user_dataset",
                   new_callable=AsyncMock,
                   return_value=(mock_user, mock_dataset)), \
             patch("cognee.api.v1.add.add.reset_dataset_pipeline_run_status",
                   new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.run_pipeline",
                   side_effect=mock_run_pipeline_gen) as mock_run:

            from cognee.api.v1.add.add import add
            texts = ["first text", "second text", "third text"]
            await add(texts, user=mock_user)

            call_kwargs = mock_run.call_args
            data_arg = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
            assert data_arg == texts
            assert len(data_arg) == 3


class TestResolveDataDirectories:
    """Test the resolve_data_directories step handles text strings correctly."""

    @pytest.mark.asyncio
    async def test_resolve_text_string_passes_through(self):
        """A plain text string (not a directory) should pass through resolve_data_directories unchanged."""
        with patch("cognee.tasks.ingestion.resolve_data_directories.get_s3_config") as mock_s3:
            mock_s3.return_value = MagicMock(
                aws_access_key_id=None, aws_secret_access_key=None
            )
            from cognee.tasks.ingestion.resolve_data_directories import resolve_data_directories

            result = await resolve_data_directories("hello world")
            assert result == ["hello world"]

    @pytest.mark.asyncio
    async def test_resolve_multiple_text_strings(self):
        """Multiple text strings should all pass through."""
        with patch("cognee.tasks.ingestion.resolve_data_directories.get_s3_config") as mock_s3:
            mock_s3.return_value = MagicMock(
                aws_access_key_id=None, aws_secret_access_key=None
            )
            from cognee.tasks.ingestion.resolve_data_directories import resolve_data_directories

            texts = ["text one", "text two", "text three"]
            result = await resolve_data_directories(texts)
            assert result == texts

    @pytest.mark.asyncio
    async def test_resolve_url_string_passes_through(self):
        """A URL string should pass through resolve_data_directories unchanged (not a directory)."""
        with patch("cognee.tasks.ingestion.resolve_data_directories.get_s3_config") as mock_s3:
            mock_s3.return_value = MagicMock(
                aws_access_key_id=None, aws_secret_access_key=None
            )
            from cognee.tasks.ingestion.resolve_data_directories import resolve_data_directories

            result = await resolve_data_directories("https://example.com")
            assert result == ["https://example.com"]


# ---------------------------------------------------------------------------
# T302 - URL data crawling and storage tests
# ---------------------------------------------------------------------------


class TestUrlDetection:
    """T302-5: Verify that strings starting with http:// or https:// are treated as URLs."""

    @pytest.mark.asyncio
    async def test_http_url_triggers_fetch(self):
        """save_data_item_to_storage should call fetch_page_content for http:// URLs."""
        mock_content = {"http://example.com": "<html><body>Hello</body></html>"}

        with patch("cognee.tasks.ingestion.save_data_item_to_storage.fetch_page_content",
                   new_callable=AsyncMock,
                   return_value=mock_content) as mock_fetch, \
             patch("cognee.tasks.ingestion.save_data_item_to_storage.save_data_to_file",
                   new_callable=AsyncMock,
                   return_value="file://data/test.html") as mock_save:

            from cognee.tasks.ingestion.save_data_item_to_storage import save_data_item_to_storage

            result = await save_data_item_to_storage("http://example.com")

            mock_fetch.assert_called_once_with("http://example.com")
            mock_save.assert_called_once_with(
                "<html><body>Hello</body></html>", file_extension="html"
            )

    @pytest.mark.asyncio
    async def test_https_url_triggers_fetch(self):
        """save_data_item_to_storage should call fetch_page_content for https:// URLs."""
        mock_content = {"https://example.com": "<html>Content</html>"}

        with patch("cognee.tasks.ingestion.save_data_item_to_storage.fetch_page_content",
                   new_callable=AsyncMock,
                   return_value=mock_content) as mock_fetch, \
             patch("cognee.tasks.ingestion.save_data_item_to_storage.save_data_to_file",
                   new_callable=AsyncMock,
                   return_value="file://data/page.html") as mock_save:

            from cognee.tasks.ingestion.save_data_item_to_storage import save_data_item_to_storage

            result = await save_data_item_to_storage("https://example.com")

            mock_fetch.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_plain_text_does_not_trigger_fetch(self):
        """Plain text should NOT call fetch_page_content; it should call save_data_to_file directly."""
        with patch("cognee.tasks.ingestion.save_data_item_to_storage.fetch_page_content",
                   new_callable=AsyncMock) as mock_fetch, \
             patch("cognee.tasks.ingestion.save_data_item_to_storage.save_data_to_file",
                   new_callable=AsyncMock,
                   return_value="file://data/text_abc.txt") as mock_save:

            from cognee.tasks.ingestion.save_data_item_to_storage import save_data_item_to_storage

            result = await save_data_item_to_storage("Just some plain text content")

            # fetch_page_content should NOT be called for plain text
            mock_fetch.assert_not_called()
            # save_data_to_file should be called with the text itself
            mock_save.assert_called_once_with("Just some plain text content")


class TestUrlContentSavedToStorage:
    """T302-6: Mock URL fetching, verify content is saved to file storage."""

    @pytest.mark.asyncio
    async def test_url_html_content_saved_with_html_extension(self):
        """Fetched URL content should be saved with file_extension='html'."""
        url = "https://example.com/article"
        html_content = "<html><head><title>Test</title></head><body><p>Article body</p></body></html>"
        mock_content = {url: html_content}
        saved_path = "file://data/text_abc123.html"

        with patch("cognee.tasks.ingestion.save_data_item_to_storage.fetch_page_content",
                   new_callable=AsyncMock,
                   return_value=mock_content) as mock_fetch, \
             patch("cognee.tasks.ingestion.save_data_item_to_storage.save_data_to_file",
                   new_callable=AsyncMock,
                   return_value=saved_path) as mock_save:

            from cognee.tasks.ingestion.save_data_item_to_storage import save_data_item_to_storage

            result = await save_data_item_to_storage(url)

            # Verify saved with html extension
            mock_save.assert_called_once_with(html_content, file_extension="html")
            # Verify the returned path is what save_data_to_file returned
            assert result == saved_path

    @pytest.mark.asyncio
    async def test_url_fetched_content_is_passed_to_save(self):
        """The actual HTML content fetched from the URL should be passed to save_data_to_file."""
        url = "https://news.example.com/story"
        fetched_html = "<html><body><h1>Breaking News</h1><p>Story content here</p></body></html>"

        with patch("cognee.tasks.ingestion.save_data_item_to_storage.fetch_page_content",
                   new_callable=AsyncMock,
                   return_value={url: fetched_html}), \
             patch("cognee.tasks.ingestion.save_data_item_to_storage.save_data_to_file",
                   new_callable=AsyncMock,
                   return_value="file://data/saved.html") as mock_save:

            from cognee.tasks.ingestion.save_data_item_to_storage import save_data_item_to_storage

            await save_data_item_to_storage(url)

            # The first positional arg to save_data_to_file should be the fetched HTML
            call_args = mock_save.call_args
            saved_content = call_args[0][0]
            assert saved_content == fetched_html


class TestAddUrlCreatesDataEntry:
    """T302-7: Verify that the add() pipeline processes URL data end-to-end."""

    @pytest.mark.asyncio
    async def test_add_url_passes_url_to_pipeline(self):
        """Calling add('https://...') should pass the URL string to the pipeline as data."""
        mock_user = _make_mock_user()
        mock_dataset = _make_mock_dataset()

        async def mock_run_pipeline_gen(**kwargs):
            yield MagicMock(status="completed")

        with patch("cognee.api.v1.add.add.setup", new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.resolve_authorized_user_dataset",
                   new_callable=AsyncMock,
                   return_value=(mock_user, mock_dataset)), \
             patch("cognee.api.v1.add.add.reset_dataset_pipeline_run_status",
                   new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.run_pipeline",
                   side_effect=mock_run_pipeline_gen) as mock_run:

            from cognee.api.v1.add.add import add

            url = "https://example.com/article"
            await add(url, user=mock_user)

            call_kwargs = mock_run.call_args
            data_arg = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
            assert data_arg == url

    @pytest.mark.asyncio
    async def test_add_url_sets_pipeline_name(self):
        """The pipeline should be run with pipeline_name='add_pipeline'."""
        mock_user = _make_mock_user()
        mock_dataset = _make_mock_dataset()

        async def mock_run_pipeline_gen(**kwargs):
            yield MagicMock(status="completed")

        with patch("cognee.api.v1.add.add.setup", new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.resolve_authorized_user_dataset",
                   new_callable=AsyncMock,
                   return_value=(mock_user, mock_dataset)), \
             patch("cognee.api.v1.add.add.reset_dataset_pipeline_run_status",
                   new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.run_pipeline",
                   side_effect=mock_run_pipeline_gen) as mock_run:

            from cognee.api.v1.add.add import add

            await add("https://example.com", user=mock_user)

            call_kwargs = mock_run.call_args
            pipeline_name = call_kwargs.kwargs.get("pipeline_name") or call_kwargs[1].get("pipeline_name")
            assert pipeline_name == "add_pipeline"

    @pytest.mark.asyncio
    async def test_add_mixed_url_and_text(self):
        """When a list with both URLs and text is passed, all items reach the pipeline."""
        mock_user = _make_mock_user()
        mock_dataset = _make_mock_dataset()

        async def mock_run_pipeline_gen(**kwargs):
            yield MagicMock(status="completed")

        with patch("cognee.api.v1.add.add.setup", new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.resolve_authorized_user_dataset",
                   new_callable=AsyncMock,
                   return_value=(mock_user, mock_dataset)), \
             patch("cognee.api.v1.add.add.reset_dataset_pipeline_run_status",
                   new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.run_pipeline",
                   side_effect=mock_run_pipeline_gen) as mock_run:

            from cognee.api.v1.add.add import add

            mixed_data = ["https://example.com", "plain text data", "http://another.com/page"]
            await add(mixed_data, user=mock_user)

            call_kwargs = mock_run.call_args
            data_arg = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
            assert data_arg == mixed_data
            assert len(data_arg) == 3


class TestAddPipelineDatasetHandling:
    """Test that add() correctly handles dataset authorization and reset."""

    @pytest.mark.asyncio
    async def test_add_resolves_authorized_dataset(self):
        """add() should call resolve_authorized_user_dataset with correct params."""
        mock_user = _make_mock_user()
        mock_dataset = _make_mock_dataset()

        async def mock_run_pipeline_gen(**kwargs):
            yield MagicMock(status="completed")

        with patch("cognee.api.v1.add.add.setup", new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.resolve_authorized_user_dataset",
                   new_callable=AsyncMock,
                   return_value=(mock_user, mock_dataset)) as mock_resolve, \
             patch("cognee.api.v1.add.add.reset_dataset_pipeline_run_status",
                   new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.run_pipeline",
                   side_effect=mock_run_pipeline_gen):

            from cognee.api.v1.add.add import add

            await add("test data", dataset_name="my_dataset", user=mock_user)

            mock_resolve.assert_called_once_with(
                dataset_name="my_dataset", dataset_id=None, user=mock_user
            )

    @pytest.mark.asyncio
    async def test_add_resets_pipeline_run_status(self):
        """add() should reset both add_pipeline and cognify_pipeline statuses."""
        mock_user = _make_mock_user()
        mock_dataset = _make_mock_dataset()

        async def mock_run_pipeline_gen(**kwargs):
            yield MagicMock(status="completed")

        with patch("cognee.api.v1.add.add.setup", new_callable=AsyncMock), \
             patch("cognee.api.v1.add.add.resolve_authorized_user_dataset",
                   new_callable=AsyncMock,
                   return_value=(mock_user, mock_dataset)), \
             patch("cognee.api.v1.add.add.reset_dataset_pipeline_run_status",
                   new_callable=AsyncMock) as mock_reset, \
             patch("cognee.api.v1.add.add.run_pipeline",
                   side_effect=mock_run_pipeline_gen):

            from cognee.api.v1.add.add import add

            await add("test", user=mock_user)

            mock_reset.assert_called_once_with(
                mock_dataset.id, mock_user,
                pipeline_names=["add_pipeline", "cognify_pipeline"]
            )
