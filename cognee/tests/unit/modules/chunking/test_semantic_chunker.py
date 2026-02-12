import pytest


class TestSemanticChunker:
    """测试语义感知分块器"""

    def test_chunk_strategy_has_semantic(self):
        from cognee.shared.data_models import ChunkStrategy
        assert hasattr(ChunkStrategy, "SEMANTIC")
        assert ChunkStrategy.SEMANTIC.value == "semantic"

    def test_semantic_chunker_preserves_tables(self):
        from cognee.modules.chunking.SemanticChunker import SemanticChunker
        text = (
            "# Introduction\n\n"
            "This is the intro paragraph.\n\n"
            "| Col A | Col B | Col C |\n"
            "|-------|-------|-------|\n"
            "| val1  | val2  | val3  |\n"
            "| val4  | val5  | val6  |\n\n"
            "## Section Two\n\n"
            "Another paragraph here."
        )
        chunker = SemanticChunker(max_chunk_size=100)
        chunks = list(chunker.chunk(text))
        table_chunks = [c for c in chunks if "Col A" in c["text"]]
        assert len(table_chunks) == 1
        assert "val6" in table_chunks[0]["text"]

    def test_semantic_chunker_preserves_code_blocks(self):
        from cognee.modules.chunking.SemanticChunker import SemanticChunker
        text = (
            "# Code Example\n\n"
            "Here is some code:\n\n"
            "```python\n"
            "def hello():\n"
            "    print('hello')\n"
            "    return True\n"
            "```\n\n"
            "And here is more text."
        )
        chunker = SemanticChunker(max_chunk_size=100)
        chunks = list(chunker.chunk(text))
        code_chunks = [c for c in chunks if "def hello" in c["text"]]
        assert len(code_chunks) == 1
        assert "return True" in code_chunks[0]["text"]

    def test_semantic_chunker_splits_by_headings(self):
        from cognee.modules.chunking.SemanticChunker import SemanticChunker
        text = (
            "# Chapter 1\n\n"
            "Content of chapter 1.\n\n"
            "# Chapter 2\n\n"
            "Content of chapter 2.\n\n"
            "## Section 2.1\n\n"
            "Content of section 2.1."
        )
        chunker = SemanticChunker(max_chunk_size=500)
        chunks = list(chunker.chunk(text))
        assert len(chunks) >= 2

    def test_semantic_chunker_respects_max_size(self):
        from cognee.modules.chunking.SemanticChunker import SemanticChunker
        text = "Word " * 1000
        chunker = SemanticChunker(max_chunk_size=200)
        chunks = list(chunker.chunk(text))
        for chunk in chunks:
            assert len(chunk["text"]) <= 200 + 50

    def test_semantic_chunker_returns_cut_type(self):
        from cognee.modules.chunking.SemanticChunker import SemanticChunker
        text = "# Title\n\nParagraph one.\n\n# Title 2\n\nParagraph two."
        chunker = SemanticChunker(max_chunk_size=500)
        chunks = list(chunker.chunk(text))
        for chunk in chunks:
            assert "cut_type" in chunk
            assert chunk["cut_type"] in ["heading", "paragraph", "table", "code", "size_limit"]

    def test_semantic_chunker_empty_text(self):
        from cognee.modules.chunking.SemanticChunker import SemanticChunker
        chunker = SemanticChunker(max_chunk_size=500)
        chunks = list(chunker.chunk(""))
        assert chunks == []

    def test_semantic_chunker_overlap(self):
        from cognee.modules.chunking.SemanticChunker import SemanticChunker
        text = (
            "# Section 1\n\n"
            "A " * 100 + "\n\n"
            "# Section 2\n\n"
            "B " * 100
        )
        chunker = SemanticChunker(max_chunk_size=200, overlap=20)
        chunks = list(chunker.chunk(text))
        assert len(chunks) >= 2
