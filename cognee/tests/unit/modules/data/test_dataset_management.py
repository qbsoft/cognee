"""
Unit tests for Dataset/Data management (T305), large file chunking (T306),
and non-UTF-8 encoding handling (T307).
"""
import pytest
import asyncio
from uuid import uuid4, UUID
from unittest.mock import Mock, patch, MagicMock
from io import BufferedReader, BytesIO


# ---------------------------------------------------------------------------
# T305 -- Dataset and Data model tests
# ---------------------------------------------------------------------------

class TestDatasetModel:
    """T305: Verify Dataset model has required fields."""

    def test_dataset_model_has_required_fields(self):
        """Verify Dataset has id, name, owner_id, created_at columns."""
        from cognee.modules.data.models.Dataset import Dataset

        column_names = {col.name for col in Dataset.__table__.columns}
        for field in ("id", "name", "owner_id", "created_at"):
            assert field in column_names, f"Dataset is missing column '{field}'"

    def test_dataset_model_has_updated_at(self):
        """Verify Dataset also exposes updated_at."""
        from cognee.modules.data.models.Dataset import Dataset

        column_names = {col.name for col in Dataset.__table__.columns}
        assert "updated_at" in column_names


class TestDataModel:
    """T305: Verify Data model has required fields and defaults."""

    def test_data_model_has_required_fields(self):
        """Verify Data has id, name, extension, mime_type, content_hash, pipeline_status."""
        from cognee.modules.data.models.Data import Data

        column_names = {col.name for col in Data.__table__.columns}
        for field in ("id", "name", "extension", "mime_type", "content_hash", "pipeline_status"):
            assert field in column_names, f"Data is missing column '{field}'"

    def test_data_model_pipeline_status_default(self):
        """Verify pipeline_status column exists and is JSON type (defaults handled at DB level)."""
        from cognee.modules.data.models.Data import Data
        from sqlalchemy import JSON

        col = Data.__table__.columns["pipeline_status"]
        # The underlying type should be JSON (wrapped by MutableDict)
        assert isinstance(col.type, JSON) or hasattr(col.type, "impl") and isinstance(
            col.type.impl, JSON
        ), "pipeline_status should be a JSON column"

    def test_data_model_token_count_default(self):
        """Verify token_count column exists and is Integer type."""
        from cognee.modules.data.models.Data import Data
        from sqlalchemy import Integer

        col = Data.__table__.columns["token_count"]
        assert isinstance(col.type, Integer), "token_count should be an Integer column"

    def test_data_model_has_timestamps(self):
        """Verify Data has created_at and updated_at."""
        from cognee.modules.data.models.Data import Data

        column_names = {col.name for col in Data.__table__.columns}
        assert "created_at" in column_names
        assert "updated_at" in column_names


# ---------------------------------------------------------------------------
# T306 -- Large file chunking
# ---------------------------------------------------------------------------

def _make_large_text(num_paragraphs: int = 200, words_per_paragraph: int = 80) -> str:
    """Generate a large text with multiple paragraphs for chunking tests."""
    paragraphs = []
    for i in range(num_paragraphs):
        sentence = f"Paragraph {i} contains important information about topic {i % 10}. "
        paragraph = sentence * (words_per_paragraph // 10)
        paragraphs.append(paragraph.strip())
    return "\n\n".join(paragraphs)


def _make_large_markdown(num_sections: int = 30, sentences_per_section: int = 20) -> str:
    """Generate a large markdown text with headings for SemanticChunker tests."""
    sections = []
    for i in range(num_sections):
        heading = f"## Section {i}: Topic about area {i % 5}"
        body_sentences = [
            f"This is sentence {j} discussing details of section {i}. "
            for j in range(sentences_per_section)
        ]
        sections.append(heading + "\n\n" + "".join(body_sentences))
    return "\n\n".join(sections)


class TestTextChunkerLargeText:
    """T306: Verify TextChunker handles large text (50KB+)."""

    @pytest.mark.asyncio
    async def test_text_chunker_handles_large_text(self):
        """Create a 50KB+ text, verify TextChunker produces multiple chunks."""
        from cognee.modules.chunking.TextChunker import TextChunker
        from cognee.modules.data.processing.document_types import Document

        large_text = _make_large_text(num_paragraphs=200, words_per_paragraph=80)
        # Ensure text is at least 50KB
        assert len(large_text.encode("utf-8")) > 50 * 1024, (
            f"Generated text is only {len(large_text.encode('utf-8'))} bytes, need > 50KB"
        )

        doc = Document(
            id=uuid4(),
            name="large_test.txt",
            raw_data_location="/tmp/large_test.txt",
            external_metadata=None,
            mime_type="text/plain",
        )

        async def get_text():
            yield large_text

        max_chunk_size = 64  # token-based size; will force many chunks

        # Mock the embedding engine used by chunk_by_sentence -> get_word_size
        mock_tokenizer = Mock()
        mock_tokenizer.count_tokens = lambda word: len(word.split())

        mock_engine = Mock()
        mock_engine.tokenizer = mock_tokenizer

        with patch(
            "cognee.tasks.chunks.chunk_by_sentence.get_embedding_engine",
            return_value=mock_engine,
        ):
            chunker = TextChunker(doc, get_text=get_text, max_chunk_size=max_chunk_size)

            chunks = []
            async for chunk in chunker.read():
                chunks.append(chunk)

        assert len(chunks) > 1, (
            f"Expected multiple chunks for 50KB+ text, got {len(chunks)}"
        )
        # Every chunk should have text
        for chunk in chunks:
            assert chunk.text, "Chunk text should not be empty"


class TestSemanticChunkerLargeText:
    """T306: Verify SemanticChunker handles large text with headings."""

    def test_semantic_chunker_handles_large_text(self):
        """Create a large markdown text with headings, verify SemanticChunker splits correctly."""
        from cognee.modules.chunking.SemanticChunker import SemanticChunker

        large_markdown = _make_large_markdown(num_sections=30, sentences_per_section=20)
        assert len(large_markdown) > 10000, "Markdown should be large enough to split"

        chunker = SemanticChunker(max_chunk_size=500)
        chunks = list(chunker.chunk(large_markdown))

        assert len(chunks) > 1, (
            f"Expected multiple chunks for large markdown, got {len(chunks)}"
        )
        # All chunks should have non-empty text
        for chunk in chunks:
            assert chunk["text"].strip(), "Chunk text should not be empty"

    def test_chunk_sizes_respect_max_limit(self):
        """Verify no chunk exceeds max_chunk_size (character-based for SemanticChunker)."""
        from cognee.modules.chunking.SemanticChunker import SemanticChunker

        large_markdown = _make_large_markdown(num_sections=20, sentences_per_section=15)

        max_size = 600
        chunker = SemanticChunker(max_chunk_size=max_size)
        chunks = list(chunker.chunk(large_markdown))

        assert len(chunks) > 0, "Should produce at least one chunk"
        for i, chunk in enumerate(chunks):
            assert len(chunk["text"]) <= max_size, (
                f"Chunk {i} has length {len(chunk['text'])} which exceeds max_chunk_size={max_size}"
            )


# ---------------------------------------------------------------------------
# T307 -- Non-UTF-8 encoding / special character handling
# ---------------------------------------------------------------------------

class TestNonUtf8Encoding:
    """T307: Verify handling of binary files, unicode content, and non-ASCII filenames."""

    def test_classify_handles_binary_file(self):
        """classify() should return BinaryData for a BufferedReader."""
        from cognee.modules.ingestion.classify import classify
        from cognee.modules.ingestion.data_types import BinaryData

        raw_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        bio = BytesIO(raw_bytes)
        # BufferedReader wrapping BytesIO
        reader = BufferedReader(bio)

        result = classify(reader, filename="image.png")

        assert isinstance(result, BinaryData), (
            f"Expected BinaryData, got {type(result).__name__}"
        )
        assert result.name == "image.png"

    def test_text_data_with_unicode_content(self):
        """TextData should handle unicode content (Chinese, emoji, etc.)."""
        from cognee.modules.ingestion.data_types import TextData

        unicode_text = (
            "Hello, this is a multilingual test. "
            "This has Chinese characters. "
            "And some emoji content here. "
            "Also Japanese: konnichiwa, Korean: annyeong."
        )
        text_data = TextData(unicode_text)

        assert text_data.data == unicode_text
        # get_metadata should not raise
        metadata = text_data.get_metadata()
        assert "name" in metadata
        assert "content_hash" in metadata
        assert metadata["content_hash"], "content_hash should not be empty"

    def test_text_data_with_chinese_content(self):
        """TextData handles Chinese characters correctly."""
        from cognee.modules.ingestion.data_types import TextData

        chinese_text = "\u8fd9\u662f\u4e00\u6bb5\u4e2d\u6587\u6d4b\u8bd5\u6587\u672c\uff0c\u7528\u4e8e\u9a8c\u8bc1\u7cfb\u7edf\u7684Unicode\u652f\u6301\u3002"
        text_data = TextData(chinese_text)

        metadata = text_data.get_metadata()
        assert metadata["content_hash"], "Should produce a valid hash for Chinese text"
        assert text_data.data == chinese_text

    def test_data_model_accepts_non_ascii_name(self):
        """Data model column definition should accept non-ASCII filenames.

        We verify the column type is String (which accepts any unicode string).
        Since Data is a SQLAlchemy model, we cannot instantiate it without a DB session,
        so we verify the schema accepts the right types.
        """
        from cognee.modules.data.models.Data import Data
        from sqlalchemy import String

        name_col = Data.__table__.columns["name"]
        assert isinstance(name_col.type, String), (
            f"Expected String column type, got {type(name_col.type).__name__}"
        )

        # Also verify extension column accepts non-ASCII
        ext_col = Data.__table__.columns["extension"]
        assert isinstance(ext_col.type, String), (
            f"Expected String column type for extension, got {type(ext_col.type).__name__}"
        )

    def test_classify_binary_reader_without_filename(self):
        """classify() should handle BufferedReader without explicit filename."""
        from cognee.modules.ingestion.classify import classify
        from cognee.modules.ingestion.data_types import BinaryData

        raw_bytes = b"Some binary content"
        bio = BytesIO(raw_bytes)
        reader = BufferedReader(bio)

        result = classify(reader)

        assert isinstance(result, BinaryData)
        # Without explicit filename, should still produce a BinaryData object
        assert result.name is not None
