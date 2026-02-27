"""
OCR-enhanced image loader.

Dual-layer processing:
- Base layer: OCR text extraction (PaddleOCR or Tesseract)
- Enhancement layer: Vision LLM deep understanding (optional, graceful degradation)

Configuration:
- ocr_engine: "paddleocr" | "tesseract" (default "paddleocr")
- enable_vision_llm: true | false (default true)
"""

import os
import asyncio
import logging
from typing import List

from cognee.infrastructure.loaders.LoaderInterface import LoaderInterface
from cognee.infrastructure.llm.LLMGateway import LLMGateway
from cognee.infrastructure.files.storage import get_file_storage, get_storage_config
from cognee.infrastructure.files.utils.get_file_metadata import get_file_metadata

logger = logging.getLogger(__name__)


class OcrEnhancedImageLoader(LoaderInterface):
    """
    OCR-enhanced image loader with dual-layer processing.

    Base layer uses OCR (PaddleOCR or Tesseract) for text extraction.
    Enhancement layer uses Vision LLM for deep understanding (optional).
    When Vision LLM is unavailable, gracefully degrades to OCR-only results.
    """

    @property
    def supported_extensions(self) -> List[str]:
        """Supported image file extensions (without leading dots)."""
        return [
            "png",
            "jpg",
            "jpeg",
            "jpx",
            "gif",
            "webp",
            "tif",
            "tiff",
            "bmp",
            "heic",
            "avif",
            "apng",
            "cr2",
            "dwg",
            "xcf",
            "jxr",
            "psd",
            "ico",
            "jpe",
        ]

    @property
    def supported_mime_types(self) -> List[str]:
        """Supported MIME types for image content."""
        return [
            "image/png",
            "image/vnd.dwg",
            "image/x-xcf",
            "image/jpeg",
            "image/jpx",
            "image/apng",
            "image/gif",
            "image/webp",
            "image/x-canon-cr2",
            "image/tiff",
            "image/bmp",
            "image/jxr",
            "image/vnd.adobe.photoshop",
            "image/vnd.microsoft.icon",
            "image/heic",
            "image/avif",
        ]

    @property
    def loader_name(self) -> str:
        """Unique identifier for this loader."""
        return "ocr_enhanced_image_loader"

    def can_handle(self, extension: str, mime_type: str) -> bool:
        """
        Check if this loader can handle the given file.

        Args:
            extension: File extension (without leading dot)
            mime_type: MIME type of the file

        Returns:
            True if file can be handled, False otherwise
        """
        if extension in self.supported_extensions and mime_type in self.supported_mime_types:
            return True
        return False

    async def load(self, file_path: str, **kwargs):
        """
        Load and process the image file with OCR and optional Vision LLM.

        Args:
            file_path: Path to the image file
            **kwargs:
                ocr_engine: "paddleocr" or "tesseract" (default "paddleocr")
                enable_vision_llm: Whether to use Vision LLM (default True)

        Returns:
            Path to the stored result file

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ocr_engine = kwargs.get("ocr_engine", "paddleocr")
        # Default to False: use local OCR only, avoid cloud LLM API calls for images
        enable_vision_llm = kwargs.get("enable_vision_llm", False)

        # Step 1: OCR base extraction
        ocr_text = await self._ocr_extract(file_path, engine=ocr_engine)

        # Step 2: Vision LLM deep understanding (optional)
        vision_description = None
        if enable_vision_llm:
            try:
                vision_description = await self._vision_llm_describe(file_path)
            except Exception as e:
                logger.warning(f"Vision LLM unavailable: {e}, using OCR results only")

        # Step 3: Merge results
        content = self._merge_results(ocr_text, vision_description)

        # Step 4: Store results
        with open(file_path, "rb") as f:
            file_metadata = await get_file_metadata(f)

        storage_file_name = "text_" + file_metadata["content_hash"] + ".txt"

        storage_config = get_storage_config()
        data_root_directory = storage_config["data_root_directory"]
        storage = get_file_storage(data_root_directory)

        full_file_path = await storage.store(storage_file_name, content)

        return full_file_path

    async def _ocr_extract(self, file_path: str, engine: str = "paddleocr") -> str:
        """
        Extract text from image using OCR engine.

        Args:
            file_path: Path to the image file
            engine: OCR engine to use ("paddleocr" or "tesseract")

        Returns:
            Extracted text string
        """
        if engine == "paddleocr":
            try:
                from paddleocr import PaddleOCR

                ocr = PaddleOCR(use_angle_cls=True, lang="ch")
                result = await asyncio.get_event_loop().run_in_executor(
                    None, ocr.ocr, file_path
                )
                # Parse results into text lines
                lines = []
                if result and result[0]:
                    for line in result[0]:
                        lines.append(line[1][0])
                return "\n".join(lines)
            except ImportError:
                logger.warning("PaddleOCR not installed, falling back to Tesseract")
                return await self._ocr_extract(file_path, "tesseract")
        elif engine == "tesseract":
            try:
                import pytesseract
                from PIL import Image

                img = Image.open(file_path)
                text = await asyncio.get_event_loop().run_in_executor(
                    None, pytesseract.image_to_string, img
                )
                return text
            except ImportError:
                logger.error("Neither PaddleOCR nor Tesseract is installed")
                return ""
        else:
            logger.error(f"Unknown OCR engine: {engine}")
            return ""

    async def _vision_llm_describe(self, file_path: str) -> str:
        """
        Use Vision LLM to generate a deep description of the image.

        Args:
            file_path: Path to the image file

        Returns:
            Vision LLM description string

        Raises:
            Exception: If Vision LLM is unavailable
        """
        result = await LLMGateway.transcribe_image(file_path)
        return result.choices[0].message.content

    def _merge_results(self, ocr_text: str, vision_description: str = None) -> str:
        """
        Merge OCR text and Vision LLM description into a unified result.

        Args:
            ocr_text: Text extracted by OCR
            vision_description: Description from Vision LLM (may be None)

        Returns:
            Merged content string
        """
        parts = []

        if ocr_text and ocr_text.strip():
            parts.append("[OCR Extracted Text]\n" + ocr_text.strip())

        if vision_description and vision_description.strip():
            parts.append("[Vision LLM Description]\n" + vision_description.strip())

        if not parts:
            return ""

        return "\n\n".join(parts)
