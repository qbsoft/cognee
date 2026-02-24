"""Unit tests for cognee.modules.chunking.models.DocumentChunk module."""
import pytest
from uuid import uuid4, UUID
from unittest.mock import Mock

from cognee.modules.chunking.models.DocumentChunk import DocumentChunk
from cognee.modules.data.processing.document_types import Document
from cognee.modules.engine.models import Entity


def create_test_document(doc_id=None, name="test_doc.txt"):
    """Create a test Document instance."""
    return Document(
        id=doc_id or uuid4(),
        name=name,
        raw_data_location="/tmp/test",
        external_metadata=None,
        mime_type="text/plain",
    )


class TestDocumentChunk:
    """Tests for the DocumentChunk model."""

    def _create_chunk(self, **kwargs):
        """Helper to create a DocumentChunk with default values."""
        defaults = {
            "id": uuid4(),
            "text": "This is test chunk content.",
            "chunk_size": 27,
            "chunk_index": 0,
            "cut_type": "paragraph",
            "is_part_of": create_test_document(),
        }
        defaults.update(kwargs)
        return DocumentChunk(**defaults)

    def test_document_chunk_creation(self):
        """Test basic DocumentChunk creation."""
        chunk = self._create_chunk()

        assert chunk.text == "This is test chunk content."
        assert chunk.chunk_size == 27
        assert chunk.chunk_index == 0
        assert chunk.cut_type == "paragraph"

    def test_document_chunk_with_source_tracing(self):
        """Test DocumentChunk with source tracing fields."""
        source_id = uuid4()
        chunk = self._create_chunk(
            source_data_id=source_id,
            source_file_path="/path/to/file.txt",
            start_line=10,
            end_line=15,
            start_char=100,
            end_char=200,
        )

        assert chunk.source_data_id == source_id
        assert chunk.source_file_path == "/path/to/file.txt"
        assert chunk.start_line == 10
        assert chunk.end_line == 15
        assert chunk.start_char == 100
        assert chunk.end_char == 200

    def test_document_chunk_with_page_number(self):
        """Test DocumentChunk with page number for PDF files."""
        chunk = self._create_chunk(page_number=5)

        assert chunk.page_number == 5

    def test_document_chunk_default_metadata(self):
        """Test DocumentChunk has default metadata with index_fields."""
        chunk = self._create_chunk()

        assert "index_fields" in chunk.metadata
        assert chunk.metadata["index_fields"] == ["text"]

    def test_document_chunk_custom_metadata(self):
        """Test DocumentChunk with custom metadata."""
        custom_metadata = {
            "index_fields": ["text", "summary"],
            "custom_field": "value",
        }
        chunk = self._create_chunk(metadata=custom_metadata)

        assert chunk.metadata["custom_field"] == "value"
        assert "summary" in chunk.metadata["index_fields"]

    def test_document_chunk_contains_default_none(self):
        """Test DocumentChunk contains field defaults to None."""
        chunk = self._create_chunk()

        assert chunk.contains is None

    def test_document_chunk_contains_with_entities(self):
        """Test DocumentChunk with entities in contains field."""
        entity = Entity(
            id=uuid4(),
            name="TestEntity",
            description="A test entity",
        )
        chunk = self._create_chunk(contains=[entity])

        assert len(chunk.contains) == 1
        assert chunk.contains[0].name == "TestEntity"

    def test_document_chunk_empty_text(self):
        """Test DocumentChunk with empty text."""
        chunk = self._create_chunk(text="", chunk_size=0)

        assert chunk.text == ""
        assert chunk.chunk_size == 0

    def test_document_chunk_large_text(self):
        """Test DocumentChunk with large text content."""
        large_text = "A" * 10000
        chunk = self._create_chunk(text=large_text, chunk_size=10000)

        assert len(chunk.text) == 10000
        assert chunk.chunk_size == 10000

    def test_document_chunk_multiline_text(self):
        """Test DocumentChunk with multiline text."""
        multiline_text = "Line 1\nLine 2\nLine 3"
        chunk = self._create_chunk(text=multiline_text)

        assert "\n" in chunk.text
        assert chunk.text.count("\n") == 2

    def test_document_chunk_different_cut_types(self):
        """Test DocumentChunk with different cut types."""
        cut_types = ["paragraph", "sentence", "word", "character"]

        for cut_type in cut_types:
            chunk = self._create_chunk(cut_type=cut_type)
            assert chunk.cut_type == cut_type

    def test_document_chunk_source_fields_optional(self):
        """Test DocumentChunk source fields are optional."""
        chunk = self._create_chunk()

        assert chunk.source_data_id is None
        assert chunk.source_file_path is None
        assert chunk.start_line is None
        assert chunk.end_line is None
        assert chunk.page_number is None
        assert chunk.start_char is None
        assert chunk.end_char is None

    def test_document_chunk_chunk_index_increments(self):
        """Test DocumentChunk with different chunk indices."""
        doc = create_test_document()
        chunks = [self._create_chunk(chunk_index=i, is_part_of=doc) for i in range(5)]

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_document_chunk_is_part_of_reference(self):
        """Test DocumentChunk maintains reference to parent document."""
        doc = create_test_document(name="parent_doc.txt")
        chunk = self._create_chunk(is_part_of=doc)

        assert chunk.is_part_of.name == "parent_doc.txt"

    def test_document_chunk_id_is_uuid(self):
        """Test DocumentChunk id is a valid UUID."""
        chunk_id = uuid4()
        chunk = self._create_chunk(id=chunk_id)

        assert isinstance(chunk.id, UUID)
        assert chunk.id == chunk_id
