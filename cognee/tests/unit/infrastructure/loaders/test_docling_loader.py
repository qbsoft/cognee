"""Tests for DoclingLoader - high-precision document parser integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestDoclingLoaderProperties:
    """Test DoclingLoader property definitions."""

    def test_loader_name(self):
        """Verify loader_name is 'docling_loader'."""
        from cognee.infrastructure.loaders.docling_loader import DoclingLoader

        loader = DoclingLoader()
        assert loader.loader_name == "docling_loader"

    def test_supported_extensions(self):
        """Verify pdf, docx, pptx, xlsx are in supported_extensions."""
        from cognee.infrastructure.loaders.docling_loader import DoclingLoader

        loader = DoclingLoader()
        extensions = loader.supported_extensions
        assert "pdf" in extensions
        assert "docx" in extensions
        assert "pptx" in extensions
        assert "xlsx" in extensions
        # Extensions should not have dots (consistent with other loaders)
        for ext in extensions:
            assert not ext.startswith("."), f"Extension '{ext}' should not start with a dot"

    def test_supported_mime_types(self):
        """Verify application/pdf is in supported_mime_types."""
        from cognee.infrastructure.loaders.docling_loader import DoclingLoader

        loader = DoclingLoader()
        mime_types = loader.supported_mime_types
        assert "application/pdf" in mime_types
        assert (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            in mime_types
        )


class TestDoclingLoaderCanHandle:
    """Test DoclingLoader.can_handle method."""

    def test_can_handle_pdf(self):
        """Verify can_handle returns True for PDF and False for unsupported types."""
        from cognee.infrastructure.loaders.docling_loader import DoclingLoader

        loader = DoclingLoader()
        assert loader.can_handle("pdf", "application/pdf") is True
        assert loader.can_handle("txt", "text/plain") is False


class TestDoclingLoaderLoad:
    """Test DoclingLoader.load method."""

    @pytest.mark.asyncio
    async def test_load_returns_file_path(self):
        """Mock _convert_document and verify load returns a file path string."""
        from cognee.infrastructure.loaders.docling_loader.DoclingLoader import DoclingLoader

        _MOD = "cognee.infrastructure.loaders.docling_loader.DoclingLoader"

        loader = DoclingLoader()

        mock_result = {
            "content": "# Heading\n\nSome markdown content",
            "metadata": {
                "source": "/tmp/test.pdf",
                "format": "pdf",
                "num_pages": 1,
            },
            "structure": {
                "headings": ["Heading"],
                "tables": [],
                "figures": [],
            },
        }

        mock_file_metadata = {"content_hash": "abc123hash"}
        mock_storage = AsyncMock()
        mock_storage.store = AsyncMock(return_value="/data/text_abc123hash.txt")

        with patch.object(loader, "_convert_document", return_value=mock_result), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch(f"{_MOD}.get_file_metadata", new_callable=AsyncMock, return_value=mock_file_metadata), \
             patch(f"{_MOD}.get_storage_config", return_value={"data_root_directory": "/data"}), \
             patch(f"{_MOD}.get_file_storage", return_value=mock_storage):
            result = await loader.load("/tmp/test.pdf")

        assert result is not None
        assert isinstance(result, str), f"Expected str file path, got {type(result).__name__}"
        assert "abc123hash" in result

    @pytest.mark.asyncio
    async def test_load_pdf_with_fallback(self):
        """Mock _convert_document to raise exception, verify load returns None."""
        from cognee.infrastructure.loaders.docling_loader import DoclingLoader

        loader = DoclingLoader()

        with patch.object(
            loader,
            "_convert_document",
            side_effect=Exception("Docling conversion failed"),
        ), patch("os.path.exists", return_value=True):
            result = await loader.load("/tmp/test.pdf")

        assert result is None


class TestDoclingLoaderRegistration:
    """Test DoclingLoader registration with LoaderEngine."""

    def test_loader_registration(self):
        """Create LoaderEngine, register DoclingLoader, verify success."""
        from cognee.infrastructure.loaders.LoaderEngine import LoaderEngine
        from cognee.infrastructure.loaders.docling_loader import DoclingLoader

        engine = LoaderEngine()
        loader = DoclingLoader()

        result = engine.register_loader(loader)
        assert result is True
        assert "docling_loader" in engine.get_available_loaders()
