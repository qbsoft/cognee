"""
Tests for OCR-enhanced multimodal image loader.

All tests use mocks - no actual PaddleOCR, Tesseract, or LLM dependencies required.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


class TestOcrEnhancedImageLoaderProperties:
    """Test basic properties of OcrEnhancedImageLoader."""

    def test_ocr_loader_name(self):
        """loader_name should be 'ocr_enhanced_image_loader'."""
        from cognee.infrastructure.loaders.core.ocr_enhanced_image_loader import (
            OcrEnhancedImageLoader,
        )

        loader = OcrEnhancedImageLoader()
        assert loader.loader_name == "ocr_enhanced_image_loader"

    def test_ocr_loader_supported_extensions(self):
        """Should support common image extensions without leading dots."""
        from cognee.infrastructure.loaders.core.ocr_enhanced_image_loader import (
            OcrEnhancedImageLoader,
        )

        loader = OcrEnhancedImageLoader()
        extensions = loader.supported_extensions

        # Must include common image formats
        for ext in ["png", "jpg", "jpeg", "gif", "webp", "tif", "tiff", "bmp", "heic", "avif"]:
            assert ext in extensions, f"Extension '{ext}' should be supported"

        # All extensions should be without leading dots
        for ext in extensions:
            assert not ext.startswith("."), f"Extension '{ext}' should not start with '.'"

    def test_ocr_loader_can_handle(self):
        """can_handle should return True for supported image types."""
        from cognee.infrastructure.loaders.core.ocr_enhanced_image_loader import (
            OcrEnhancedImageLoader,
        )

        loader = OcrEnhancedImageLoader()

        assert loader.can_handle("png", "image/png") is True
        assert loader.can_handle("jpg", "image/jpeg") is True
        assert loader.can_handle("txt", "text/plain") is False


class TestOcrEnhancedImageLoaderOcr:
    """Test OCR extraction functionality."""

    @pytest.mark.asyncio
    async def test_ocr_extract_with_mock_paddleocr(self):
        """Mock PaddleOCR and verify text extraction works."""
        from cognee.infrastructure.loaders.core.ocr_enhanced_image_loader import (
            OcrEnhancedImageLoader,
        )

        loader = OcrEnhancedImageLoader()

        # Mock PaddleOCR module
        mock_paddleocr_module = MagicMock()
        mock_ocr_instance = MagicMock()
        # PaddleOCR().ocr() returns a list of lists: [[line1, line2, ...]]
        # Each line is [bounding_box, (text, confidence)]
        mock_ocr_instance.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 30], [0, 30]], ("Hello World", 0.95)],
                [[[0, 40], [100, 40], [100, 70], [0, 70]], ("OCR Test", 0.90)],
            ]
        ]
        mock_paddleocr_module.PaddleOCR.return_value = mock_ocr_instance

        with patch.dict("sys.modules", {"paddleocr": mock_paddleocr_module}):
            result = await loader._ocr_extract("/fake/image.png", engine="paddleocr")

        assert "Hello World" in result
        assert "OCR Test" in result

    @pytest.mark.asyncio
    async def test_ocr_engine_config_switch(self):
        """When ocr_engine='tesseract', should use Tesseract instead of PaddleOCR."""
        from cognee.infrastructure.loaders.core.ocr_enhanced_image_loader import (
            OcrEnhancedImageLoader,
        )

        loader = OcrEnhancedImageLoader()

        # Mock pytesseract and PIL
        mock_pytesseract = MagicMock()
        mock_pytesseract.image_to_string.return_value = "Tesseract OCR Result"

        mock_pil_image = MagicMock()
        mock_image_instance = MagicMock()
        mock_pil_image.open.return_value = mock_image_instance

        with patch.dict(
            "sys.modules",
            {"pytesseract": mock_pytesseract, "PIL": MagicMock(), "PIL.Image": mock_pil_image},
        ):
            result = await loader._ocr_extract("/fake/image.png", engine="tesseract")

        assert "Tesseract OCR Result" in result


class TestOcrEnhancedImageLoaderFallback:
    """Test graceful degradation when Vision LLM is unavailable."""

    @pytest.mark.asyncio
    async def test_vision_llm_fallback(self):
        """When Vision LLM throws an exception, should return only OCR results."""
        from cognee.infrastructure.loaders.core.ocr_enhanced_image_loader import (
            OcrEnhancedImageLoader,
        )

        loader = OcrEnhancedImageLoader()

        # Mock _ocr_extract to return OCR text
        loader._ocr_extract = AsyncMock(return_value="OCR extracted text")

        # Mock _vision_llm_describe to raise an exception
        loader._vision_llm_describe = AsyncMock(
            side_effect=Exception("Vision LLM unavailable")
        )

        # Mock file existence, file open, and storage
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)

        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", return_value=mock_file
        ), patch(
            "cognee.infrastructure.loaders.core.ocr_enhanced_image_loader.get_file_metadata",
            new_callable=AsyncMock,
            return_value={"content_hash": "abc123"},
        ), patch(
            "cognee.infrastructure.loaders.core.ocr_enhanced_image_loader.get_storage_config",
            return_value={"data_root_directory": "/tmp/storage"},
        ), patch(
            "cognee.infrastructure.loaders.core.ocr_enhanced_image_loader.get_file_storage",
        ) as mock_get_storage:
            mock_storage = MagicMock()
            mock_storage.store = AsyncMock(return_value="/tmp/storage/text_abc123.txt")
            mock_get_storage.return_value = mock_storage

            result = await loader.load(
                "/fake/image.png", enable_vision_llm=True
            )

        # Vision LLM failed, so only OCR text should be in the merged result
        # The stored content should contain OCR text
        stored_content = mock_storage.store.call_args[0][1]
        assert "OCR extracted text" in stored_content
        # Vision description should NOT be present (it failed)
        assert "Vision LLM unavailable" not in stored_content
