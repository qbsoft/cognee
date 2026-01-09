from cognee.shared.logging_utils import get_logger
from uuid import NAMESPACE_OID, uuid5

from cognee.tasks.chunks import chunk_by_paragraph
from cognee.modules.chunking.Chunker import Chunker
from .models.DocumentChunk import DocumentChunk

logger = get_logger()


class TextChunker(Chunker):
    def __init__(self, document, get_text: callable, max_chunk_size: int):
        super().__init__(document, get_text, max_chunk_size)
        self.current_line = 1  # Track current line number in the document
        self.char_offset = 0   # Track character offset
    
    async def read(self):
        paragraph_chunks = []
        async for content_text in self.get_text():
            # Count lines in current text block
            lines_in_block = content_text.count('\n')
            block_start_line = self.current_line
            block_start_char = self.char_offset
            
            for chunk_data in chunk_by_paragraph(
                content_text,
                self.max_chunk_size,
                batch_paragraphs=True,
            ):
                # Calculate line numbers for this chunk
                chunk_text = chunk_data["text"]
                chunk_start_line = block_start_line
                chunk_end_line = block_start_line + chunk_text.count('\n')
                chunk_start_char = block_start_char
                chunk_end_char = block_start_char + len(chunk_text)
                
                # Store position info in chunk_data
                chunk_data["start_line"] = chunk_start_line
                chunk_data["end_line"] = chunk_end_line
                chunk_data["start_char"] = chunk_start_char
                chunk_data["end_char"] = chunk_end_char
                
                # Update tracking variables
                block_start_line = chunk_end_line
                block_start_char = chunk_end_char
                
                if self.chunk_size + chunk_data["chunk_size"] <= self.max_chunk_size:
                    paragraph_chunks.append(chunk_data)
                    self.chunk_size += chunk_data["chunk_size"]
                else:
                    if len(paragraph_chunks) == 0:
                        yield DocumentChunk(
                            id=chunk_data["chunk_id"],
                            text=chunk_data["text"],
                            chunk_size=chunk_data["chunk_size"],
                            is_part_of=self.document,
                            chunk_index=self.chunk_index,
                            cut_type=chunk_data["cut_type"],
                            contains=[],
                            # Source tracing fields
                            source_data_id=self.document.id,
                            source_file_path=self.document.name,
                            start_line=chunk_data["start_line"],
                            end_line=chunk_data["end_line"],
                            start_char=chunk_data["start_char"],
                            end_char=chunk_data["end_char"],
                            metadata={
                                "index_fields": ["text"],
                            },
                        )
                        paragraph_chunks = []
                        self.chunk_size = 0
                    else:
                        chunk_text = " ".join(chunk["text"] for chunk in paragraph_chunks)
                        # Use first chunk's start and last chunk's end for merged chunks
                        merged_start_line = paragraph_chunks[0]["start_line"]
                        merged_end_line = paragraph_chunks[-1]["end_line"]
                        merged_start_char = paragraph_chunks[0]["start_char"]
                        merged_end_char = paragraph_chunks[-1]["end_char"]
                        
                        try:
                            yield DocumentChunk(
                                id=uuid5(
                                    NAMESPACE_OID, f"{str(self.document.id)}-{self.chunk_index}"
                                ),
                                text=chunk_text,
                                chunk_size=self.chunk_size,
                                is_part_of=self.document,
                                chunk_index=self.chunk_index,
                                cut_type=paragraph_chunks[len(paragraph_chunks) - 1]["cut_type"],
                                contains=[],
                                # Source tracing fields
                                source_data_id=self.document.id,
                                source_file_path=self.document.name,
                                start_line=merged_start_line,
                                end_line=merged_end_line,
                                start_char=merged_start_char,
                                end_char=merged_end_char,
                                metadata={
                                    "index_fields": ["text"],
                                },
                            )
                        except Exception as e:
                            logger.error(e)
                            raise e
                        paragraph_chunks = [chunk_data]
                        self.chunk_size = chunk_data["chunk_size"]

                    self.chunk_index += 1
            
            # Update global tracking after processing this block
            self.current_line += lines_in_block
            self.char_offset += len(content_text)

        if len(paragraph_chunks) > 0:
            chunk_text = " ".join(chunk["text"] for chunk in paragraph_chunks)
            merged_start_line = paragraph_chunks[0]["start_line"]
            merged_end_line = paragraph_chunks[-1]["end_line"]
            merged_start_char = paragraph_chunks[0]["start_char"]
            merged_end_char = paragraph_chunks[-1]["end_char"]
            
            try:
                yield DocumentChunk(
                    id=uuid5(NAMESPACE_OID, f"{str(self.document.id)}-{self.chunk_index}"),
                    text=chunk_text,
                    chunk_size=self.chunk_size,
                    is_part_of=self.document,
                    chunk_index=self.chunk_index,
                    cut_type=paragraph_chunks[len(paragraph_chunks) - 1]["cut_type"],
                    contains=[],
                    # Source tracing fields
                    source_data_id=self.document.id,
                    source_file_path=self.document.name,
                    start_line=merged_start_line,
                    end_line=merged_end_line,
                    start_char=merged_start_char,
                    end_char=merged_end_char,
                    metadata={"index_fields": ["text"]},
                )
            except Exception as e:
                logger.error(e)
                raise e
