"""Unit tests for cognee.modules.ingestion.classify module."""
import io
import pytest
from tempfile import SpooledTemporaryFile

from cognee.modules.ingestion.classify import classify
from cognee.modules.ingestion.data_types import TextData, BinaryData
from cognee.modules.ingestion.exceptions import IngestionError


class TestClassify:
    """Tests for the classify function."""

    def test_classify_text_string(self):
        """Test classifying a plain text string returns TextData."""
        text = "This is a test document content."
        result = classify(text)

        assert isinstance(result, TextData)
        assert result.data == text

    def test_classify_empty_string(self):
        """Test classifying an empty string returns TextData."""
        result = classify("")

        assert isinstance(result, TextData)
        assert result.data == ""

    def test_classify_multiline_string(self):
        """Test classifying multiline text returns TextData."""
        text = """Line 1
        Line 2
        Line 3"""
        result = classify(text)

        assert isinstance(result, TextData)
        assert "Line 1" in result.data

    def test_classify_buffered_reader(self):
        """Test classifying a BufferedReader returns BinaryData."""
        content = b"Binary file content"
        buffer = io.BufferedReader(io.BytesIO(content))

        result = classify(buffer, filename="test_file.txt")

        assert isinstance(result, BinaryData)
        assert result.name == "test_file.txt"

    def test_classify_spooled_temporary_file(self):
        """Test classifying a SpooledTemporaryFile returns BinaryData."""
        temp_file = SpooledTemporaryFile(max_size=1024, mode='w+b')
        temp_file.write(b"Temporary file content")
        temp_file.seek(0)

        result = classify(temp_file, filename="temp_doc.pdf")

        assert isinstance(result, BinaryData)
        assert result.name == "temp_doc.pdf"

        temp_file.close()

    def test_classify_binary_without_filename(self):
        """Test classifying binary data without filename falls back to 'unknown'."""
        content = b"Binary content"
        buffer = io.BufferedReader(io.BytesIO(content))
        # BufferedReader wrapping BytesIO doesn't have a meaningful name,
        # so this tests the fallback behavior to "unknown"

        result = classify(buffer)
        assert isinstance(result, BinaryData)
        assert result.name == "unknown"

    def test_classify_unsupported_type_raises_error(self):
        """Test classifying unsupported types raises IngestionError."""
        with pytest.raises(IngestionError) as exc_info:
            classify(12345)  # int is not supported

        assert "not supported" in str(exc_info.value)

    def test_classify_list_raises_error(self):
        """Test classifying a list raises IngestionError."""
        with pytest.raises(IngestionError):
            classify(["item1", "item2"])

    def test_classify_dict_raises_error(self):
        """Test classifying a dict raises IngestionError."""
        with pytest.raises(IngestionError):
            classify({"key": "value"})

    def test_classify_none_raises_error(self):
        """Test classifying None raises IngestionError."""
        with pytest.raises(IngestionError):
            classify(None)
