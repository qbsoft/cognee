"""DoclingLoader - high-precision document parser using the Docling library."""

import asyncio
import os
from typing import Any, Dict, List, Optional

from cognee.infrastructure.loaders.LoaderInterface import LoaderInterface
from cognee.infrastructure.files.storage import get_file_storage, get_storage_config
from cognee.infrastructure.files.utils.get_file_metadata import get_file_metadata
from cognee.shared.logging_utils import get_logger

logger = get_logger(__name__)


class DoclingLoader(LoaderInterface):
    """
    Document loader using the Docling library for high-precision parsing.

    Docling provides advanced document understanding capabilities including
    layout analysis, table extraction, and structured content generation.
    It supports PDF, DOCX, PPTX, XLSX, HTML, Markdown, and AsciiDoc formats.

    This loader is optional and falls back gracefully (returns None) if
    Docling is not installed or conversion fails, allowing the LoaderEngine
    to try other loaders (e.g., PyPdfLoader).
    """

    _converter = None

    @property
    def supported_extensions(self) -> List[str]:
        """Supported file extensions (without dots, consistent with other loaders)."""
        return ["pdf", "docx", "pptx", "xlsx", "html", "md", "asciidoc"]

    @property
    def supported_mime_types(self) -> List[str]:
        """Supported MIME types for document formats."""
        return [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # pptx
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
            "text/html",
            "text/markdown",
            "text/asciidoc",
        ]

    @property
    def loader_name(self) -> str:
        """Unique identifier for this loader."""
        return "docling_loader"

    def can_handle(self, extension: str, mime_type: str) -> bool:
        """
        Check if this loader can handle the given file.

        Args:
            extension: File extension (without dot)
            mime_type: MIME type of the file

        Returns:
            True if this loader can process the file, False otherwise
        """
        if extension in self.supported_extensions and mime_type in self.supported_mime_types:
            return True
        return False

    def _get_converter(self):
        """
        Lazily initialize and return the Docling DocumentConverter.

        The docling import is deferred to avoid ImportError when
        docling is not installed (it is an optional dependency).

        Returns:
            DocumentConverter instance

        Raises:
            ImportError: If docling is not installed
        """
        if self._converter is None:
            from docling.document_converter import DocumentConverter

            self._converter = DocumentConverter()
        return self._converter

    def _convert_document(self, file_path: str) -> Dict[str, Any]:
        """
        Synchronous conversion of a document using Docling.

        This method runs the actual Docling conversion. It is separated
        from the async load() method so it can be run in an executor
        and easily mocked in tests.

        Args:
            file_path: Path to the document file

        Returns:
            Dictionary with content (markdown), metadata, and structure

        Raises:
            Exception: If conversion fails
        """
        converter = self._get_converter()
        result = converter.convert(file_path)
        document = result.document

        # Extract markdown content
        markdown_content = document.export_to_markdown()

        # Extract metadata
        metadata = {
            "source": file_path,
            "format": os.path.splitext(file_path)[1].lstrip("."),
            "num_pages": getattr(document, "num_pages", None),
        }

        # Extract structural information
        structure = {
            "headings": [],
            "tables": [],
            "figures": [],
        }

        # Try to extract headings, tables, figures from document
        if hasattr(document, "headings"):
            structure["headings"] = [str(h) for h in document.headings]
        if hasattr(document, "tables"):
            structure["tables"] = [str(t) for t in document.tables]
        if hasattr(document, "pictures"):
            structure["figures"] = [str(f) for f in document.pictures]

        return {
            "content": markdown_content,
            "metadata": metadata,
            "structure": structure,
        }

    async def load(
        self, file_path: str, **kwargs
    ) -> Optional[str]:
        """
        Load and process the document using Docling.

        Runs the synchronous Docling conversion in a thread executor
        to avoid blocking the event loop. The extracted markdown content
        is stored as a text file in cognee's data storage, and the
        storage file path is returned (consistent with other loaders).

        Returns None on failure, allowing the LoaderEngine to fall back
        to another loader (e.g., PyPdfLoader for PDFs).

        Args:
            file_path: Path to the document file
            **kwargs: Additional loader-specific configuration

        Returns:
            File path string pointing to the stored text file in cognee
            data storage, or None if conversion fails.
        """
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return None

        try:
            logger.info(f"Processing document with Docling: {file_path}")
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._convert_document, file_path
            )

            # Store the extracted markdown content to cognee data storage
            # (consistent with TextLoader / PyPdfLoader behavior)
            markdown_content = result["content"]

            with open(file_path, "rb") as f:
                file_metadata = await get_file_metadata(f)

            storage_file_name = "text_" + file_metadata["content_hash"] + ".txt"

            storage_config = get_storage_config()
            data_root_directory = storage_config["data_root_directory"]
            storage = get_file_storage(data_root_directory)

            full_file_path = await storage.store(storage_file_name, markdown_content)

            return full_file_path

        except ImportError:
            logger.warning(
                "docling is not installed. "
                "Install with: pip install docling"
            )
            return None
        except Exception as e:
            logger.warning(
                f"Docling conversion failed for {file_path}: {e}. "
                "Falling back to other loaders."
            )
            return None
