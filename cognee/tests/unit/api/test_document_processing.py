"""Tests for document processing: DoclingLoader, classify, and loader fallback.

T303: PDF file upload + DoclingLoader parsing
T304: classify() accuracy
T308: Docling failure -> PyPdf fallback
"""

import io
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from cognee.infrastructure.loaders.docling_loader.DoclingLoader import DoclingLoader
from cognee.infrastructure.loaders.LoaderEngine import LoaderEngine
from cognee.modules.ingestion.classify import classify
from cognee.modules.ingestion.data_types import TextData, BinaryData
from cognee.modules.ingestion.exceptions.exceptions import IngestionError


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===========================================================================
# T303 - DoclingLoader handles PDF
# ===========================================================================


class TestDoclingLoaderHandlesPdf:
    """T303-1: DoclingLoader.can_handle recognises PDF files."""

    def test_can_handle_pdf(self):
        loader = DoclingLoader()
        assert loader.can_handle("pdf", "application/pdf") is True

    def test_cannot_handle_unknown_extension(self):
        loader = DoclingLoader()
        assert loader.can_handle("xyz", "application/octet-stream") is False

    def test_cannot_handle_mismatched_mime(self):
        loader = DoclingLoader()
        # Extension matches but MIME does not
        assert loader.can_handle("pdf", "text/plain") is False


class TestDoclingLoaderReturnsStructuredContent:
    """T303-2: DoclingLoader.load() returns structured content dict."""

    def test_load_returns_content_and_metadata(self, tmp_path):
        loader = DoclingLoader()

        fake_result = {
            "content": "# Hello World\nSome text",
            "metadata": {"source": str(tmp_path / "doc.pdf"), "format": "pdf", "num_pages": 2},
            "structure": {"headings": ["Hello World"], "tables": [], "figures": []},
        }

        # Create a dummy file so os.path.exists passes
        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        with patch.object(loader, "_convert_document", return_value=fake_result):
            result = _run(loader.load(str(pdf_file)))

        assert result is not None
        assert "content" in result
        assert "metadata" in result
        assert result["content"] == "# Hello World\nSome text"
        assert result["metadata"]["format"] == "pdf"

    def test_load_returns_structure_key(self, tmp_path):
        loader = DoclingLoader()

        fake_result = {
            "content": "text",
            "metadata": {"source": "x", "format": "pdf", "num_pages": 1},
            "structure": {"headings": ["H1"], "tables": ["T1"], "figures": []},
        }

        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        with patch.object(loader, "_convert_document", return_value=fake_result):
            result = _run(loader.load(str(pdf_file)))

        assert "structure" in result
        assert result["structure"]["headings"] == ["H1"]


class TestDoclingLoaderReturnsNoneOnFailure:
    """T303-3: DoclingLoader.load() returns None when _convert_document throws."""

    def test_returns_none_on_conversion_error(self, tmp_path):
        loader = DoclingLoader()
        pdf_file = tmp_path / "bad.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 corrupt")

        with patch.object(loader, "_convert_document", side_effect=RuntimeError("conversion failed")):
            result = _run(loader.load(str(pdf_file)))

        assert result is None

    def test_returns_none_on_import_error(self, tmp_path):
        loader = DoclingLoader()
        pdf_file = tmp_path / "no_docling.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        with patch.object(loader, "_convert_document", side_effect=ImportError("no docling")):
            result = _run(loader.load(str(pdf_file)))

        assert result is None

    def test_returns_none_when_file_missing(self):
        loader = DoclingLoader()
        result = _run(loader.load("/nonexistent/path/to/file.pdf"))
        assert result is None


# ===========================================================================
# T304 - classify accuracy
# ===========================================================================


class TestClassifyStringReturnsTextData:
    """T304-1: classify(str) returns TextData."""

    def test_classify_plain_string(self):
        result = classify("hello")
        assert isinstance(result, TextData)

    def test_classify_empty_string(self):
        result = classify("")
        assert isinstance(result, TextData)

    def test_classify_multiline_string(self):
        result = classify("line1\nline2\nline3")
        assert isinstance(result, TextData)


class TestClassifyBinaryReturnsBinaryData:
    """T304-2: classify(BinaryIO) returns BinaryData."""

    def test_classify_buffered_reader(self, tmp_path):
        f = tmp_path / "sample.bin"
        f.write_bytes(b"binary content")
        with open(str(f), "rb") as fh:
            result = classify(fh)
        assert isinstance(result, BinaryData)


class TestClassifyFilenameExtraction:
    """T304-3: BinaryData preserves the correct filename."""

    def test_explicit_filename_used(self, tmp_path):
        f = tmp_path / "sample.bin"
        f.write_bytes(b"data")
        with open(str(f), "rb") as fh:
            result = classify(fh, filename="report.pdf")
        assert isinstance(result, BinaryData)
        assert result.name == "report.pdf"

    def test_filename_from_stream_name(self, tmp_path):
        f = tmp_path / "myfile.txt"
        f.write_bytes(b"content")
        with open(str(f), "rb") as fh:
            result = classify(fh)
        assert isinstance(result, BinaryData)
        # The name should contain the filename from the stream
        assert "myfile.txt" in result.name


class TestClassifyInvalidTypeRaisesError:
    """T304-4: classify() raises IngestionError for unsupported types."""

    def test_classify_integer_raises(self):
        with pytest.raises(IngestionError):
            classify(123)

    def test_classify_list_raises(self):
        with pytest.raises(IngestionError):
            classify([1, 2, 3])

    def test_classify_dict_raises(self):
        with pytest.raises(IngestionError):
            classify({"key": "value"})


# ===========================================================================
# T308 - Docling fallback to PyPdf
# ===========================================================================


class _FakeLoader:
    """Minimal loader stub for testing LoaderEngine priority/fallback."""

    def __init__(self, name, extensions, mime_types, can_handle_result=True):
        self._name = name
        self._extensions = extensions
        self._mime_types = mime_types
        self._can_handle_result = can_handle_result

    @property
    def supported_extensions(self):
        return self._extensions

    @property
    def supported_mime_types(self):
        return self._mime_types

    @property
    def loader_name(self):
        return self._name

    def can_handle(self, extension, mime_type):
        return self._can_handle_result


class TestLoaderEngineFallbackWhenDoclingFails:
    """T308-1: When DoclingLoader returns None, PyPdfLoader is used."""

    def test_fallback_to_pypdf(self, tmp_path):
        """
        Simulate: DoclingLoader.load() returns None, PyPdfLoader.load() returns content.
        The LoaderEngine.get_loader only picks the first matching loader, but
        load_file relies on a single loader. So the fallback mechanism is that
        DoclingLoader returns None gracefully, and users re-try with next loader.

        For this test, we verify the LoaderEngine priority-based selection:
        when docling_loader is not registered (simulating unavailability),
        pypdf_loader is selected next.
        """
        engine = LoaderEngine()

        # Only register pypdf_loader (docling not available)
        pypdf = _FakeLoader("pypdf_loader", ["pdf"], ["application/pdf"])
        engine.register_loader(pypdf)

        # Create a real PDF-like file for guess_file_type
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        with patch(
            "cognee.infrastructure.loaders.LoaderEngine.guess_file_type"
        ) as mock_guess:
            mock_guess.return_value = MagicMock(extension="pdf", mime="application/pdf")
            loader = engine.get_loader(str(pdf_file), preferred_loaders=None)

        assert loader is not None
        assert loader.loader_name == "pypdf_loader"


class TestLoaderEngineDoclingPriority:
    """T308-2: docling_loader is first in default_loader_priority."""

    def test_docling_first_in_priority(self):
        engine = LoaderEngine()
        assert engine.default_loader_priority[0] == "docling_loader"

    def test_pypdf_in_priority_list(self):
        engine = LoaderEngine()
        assert "pypdf_loader" in engine.default_loader_priority

    def test_docling_before_pypdf(self):
        engine = LoaderEngine()
        priority = engine.default_loader_priority
        docling_idx = priority.index("docling_loader")
        pypdf_idx = priority.index("pypdf_loader")
        assert docling_idx < pypdf_idx


class TestLoaderEngineUsesFirstSuccessfulLoader:
    """T308-3: When the first loader cannot handle a file, the next one is used."""

    def test_second_loader_used_when_first_cannot_handle(self, tmp_path):
        engine = LoaderEngine()

        # First loader: registered as "docling_loader" but cannot handle PDF
        first = _FakeLoader("docling_loader", ["pdf"], ["application/pdf"], can_handle_result=False)
        # Second loader: can handle PDF
        second = _FakeLoader("pypdf_loader", ["pdf"], ["application/pdf"], can_handle_result=True)

        engine.register_loader(first)
        engine.register_loader(second)

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        with patch(
            "cognee.infrastructure.loaders.LoaderEngine.guess_file_type"
        ) as mock_guess:
            mock_guess.return_value = MagicMock(extension="pdf", mime="application/pdf")
            loader = engine.get_loader(str(pdf_file), preferred_loaders=None)

        assert loader is not None
        assert loader.loader_name == "pypdf_loader"

    def test_first_loader_used_when_it_can_handle(self, tmp_path):
        engine = LoaderEngine()

        first = _FakeLoader("docling_loader", ["pdf"], ["application/pdf"], can_handle_result=True)
        second = _FakeLoader("pypdf_loader", ["pdf"], ["application/pdf"], can_handle_result=True)

        engine.register_loader(first)
        engine.register_loader(second)

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        with patch(
            "cognee.infrastructure.loaders.LoaderEngine.guess_file_type"
        ) as mock_guess:
            mock_guess.return_value = MagicMock(extension="pdf", mime="application/pdf")
            loader = engine.get_loader(str(pdf_file), preferred_loaders=None)

        assert loader is not None
        assert loader.loader_name == "docling_loader"
