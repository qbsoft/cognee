from typing import List, Union, Optional
from uuid import UUID

from cognee.infrastructure.engine import DataPoint
from cognee.modules.data.processing.document_types import Document
from cognee.modules.engine.models import Entity
from cognee.tasks.temporal_graph.models import Event


class DocumentChunk(DataPoint):
    """
    Represents a chunk of text from a document with associated metadata.

    Public methods include:

    - No public methods defined in the provided code.

    Instance variables include:

    - text: The textual content of the chunk.
    - chunk_size: The size of the chunk.
    - chunk_index: The index of the chunk in the original document.
    - cut_type: The type of cut that defined this chunk.
    - is_part_of: The document to which this chunk belongs.
    - contains: A list of entities or events contained within the chunk (default is None).
    - metadata: A dictionary to hold meta information related to the chunk, including index
    fields.
    
    Source tracing fields (for precise reference and scrolling):
    - source_data_id: UUID of the source Data record (for tracing back to original file).
    - source_file_path: Original file path or name.
    - start_line: Starting line number in the source file (for text files).
    - end_line: Ending line number in the source file (for text files).
    - page_number: Page number (for PDF/document files).
    - start_char: Starting character offset in the source file.
    - end_char: Ending character offset in the source file.
    """

    text: str
    chunk_size: int
    chunk_index: int
    cut_type: str
    is_part_of: Document
    contains: List[Union[Entity, Event]] = None
    
    # Source tracing fields for precise scrolling and reference
    source_data_id: Optional[UUID] = None
    source_file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    page_number: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None

    metadata: dict = {"index_fields": ["text"]}
