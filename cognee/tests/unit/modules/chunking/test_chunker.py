"""Unit tests for cognee.modules.chunking.Chunker module."""
import pytest
from unittest.mock import Mock

from cognee.modules.chunking.Chunker import Chunker


class TestChunker:
    """Tests for the Chunker base class."""

    def test_chunker_initialization(self):
        """Test Chunker initializes with correct default values."""
        document = Mock()
        get_text = Mock()
        max_chunk_size = 1000

        chunker = Chunker(document, get_text, max_chunk_size)

        assert chunker.chunk_index == 0
        assert chunker.chunk_size == 0
        assert chunker.token_count == 0
        assert chunker.document == document
        assert chunker.max_chunk_size == max_chunk_size
        assert chunker.get_text == get_text

    def test_chunker_stores_document_reference(self):
        """Test Chunker stores document reference correctly."""
        document = Mock()
        document.id = "test-doc-id"
        document.name = "test_document.txt"

        chunker = Chunker(document, Mock(), 500)

        assert chunker.document.id == "test-doc-id"
        assert chunker.document.name == "test_document.txt"

    def test_chunker_read_raises_not_implemented(self):
        """Test Chunker.read() raises NotImplementedError."""
        chunker = Chunker(Mock(), Mock(), 1000)

        with pytest.raises(NotImplementedError):
            chunker.read()

    def test_chunker_with_different_max_chunk_sizes(self):
        """Test Chunker handles different max chunk sizes."""
        sizes = [100, 500, 1000, 5000, 10000]

        for size in sizes:
            chunker = Chunker(Mock(), Mock(), size)
            assert chunker.max_chunk_size == size

    def test_chunker_with_zero_max_chunk_size(self):
        """Test Chunker handles zero max chunk size."""
        chunker = Chunker(Mock(), Mock(), 0)
        assert chunker.max_chunk_size == 0

    def test_chunker_callable_get_text(self):
        """Test Chunker accepts callable for get_text."""
        async def async_text_generator():
            yield "text content"

        chunker = Chunker(Mock(), async_text_generator, 1000)
        assert callable(chunker.get_text)

    def test_chunker_attributes_are_mutable(self):
        """Test Chunker attributes can be modified."""
        chunker = Chunker(Mock(), Mock(), 1000)

        chunker.chunk_index = 5
        chunker.chunk_size = 250
        chunker.token_count = 100

        assert chunker.chunk_index == 5
        assert chunker.chunk_size == 250
        assert chunker.token_count == 100
