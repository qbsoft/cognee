"""
Unit tests for the knowledge distillation module.

Tests cover:
- KnowledgeDistillation DataPoint model
- Document grouping logic
- Single document distillation
- Hierarchical distillation for large documents
- YAML configuration integration
- Pipeline injection in cognify
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, uuid5, UUID

from cognee.infrastructure.engine.models.KnowledgeDistillation import KnowledgeDistillation
from cognee.tasks.distillation.distill_knowledge import (
    distill_knowledge,
    _get_document_id,
    _distill_single_document,
    _call_llm_distill,
    _hierarchical_distill,
    _parse_distillation_response,
    DistillationItem,
    DistillationResponse,
    DEFAULT_CONTEXT_CHAR_LIMIT,
)


# ============================================================
# Helpers
# ============================================================

def _make_document(doc_id=None):
    """Create a mock Document with an id."""
    doc = MagicMock()
    doc.id = doc_id or uuid4()
    return doc


def _make_chunk(text, chunk_index=0, document=None):
    """Create a mock DocumentChunk."""
    chunk = MagicMock()
    chunk.id = uuid4()
    chunk.text = text
    chunk.chunk_index = chunk_index
    chunk.is_part_of = document or _make_document()
    return chunk


def _make_distillation_response(items=None):
    """Create a mock DistillationResponse."""
    if items is None:
        items = [
            DistillationItem(type="enumeration", text="Test enumeration item"),
            DistillationItem(type="qa", text="Q: Test? A: Yes."),
        ]
    return DistillationResponse(items=items)


def _make_llm_json_response(items=None):
    """Create a JSON string response simulating LLM output (response_model=str)."""
    import json
    if items is None:
        items = [
            {"type": "enumeration", "text": "Test enumeration item"},
            {"type": "qa", "text": "Q: Test? A: Yes."},
        ]
    return json.dumps(items, ensure_ascii=False)


# ============================================================
# KnowledgeDistillation Model Tests
# ============================================================

class TestKnowledgeDistillationModel:
    """Tests for the KnowledgeDistillation DataPoint model."""

    def test_create_basic(self):
        """Test basic model creation."""
        kd = KnowledgeDistillation(
            text="Test knowledge",
            source_document_id=uuid4(),
            distillation_type="enumeration",
        )
        assert kd.text == "Test knowledge"
        assert kd.distillation_type == "enumeration"
        assert kd.metadata == {"index_fields": ["text"]}

    def test_index_fields(self):
        """Test that metadata has correct index_fields for vector search."""
        kd = KnowledgeDistillation(
            text="Indexed text",
            source_document_id=uuid4(),
            distillation_type="qa",
        )
        assert "text" in kd.metadata["index_fields"]

    def test_all_distillation_types(self):
        """Test all valid distillation types."""
        valid_types = ["enumeration", "aggregation", "disambiguation", "negation", "qa"]
        for dtype in valid_types:
            kd = KnowledgeDistillation(
                text=f"Test {dtype}",
                source_document_id=uuid4(),
                distillation_type=dtype,
            )
            assert kd.distillation_type == dtype

    def test_source_document_id(self):
        """Test source_document_id is stored correctly."""
        doc_id = uuid4()
        kd = KnowledgeDistillation(
            text="Test",
            source_document_id=doc_id,
            distillation_type="qa",
        )
        assert kd.source_document_id == doc_id

    def test_custom_id(self):
        """Test custom ID assignment."""
        custom_id = uuid4()
        kd = KnowledgeDistillation(
            id=custom_id,
            text="Test",
            source_document_id=uuid4(),
            distillation_type="qa",
        )
        assert kd.id == custom_id


# ============================================================
# Document Grouping Tests
# ============================================================

class TestDocumentGrouping:
    """Tests for chunk-to-document grouping logic."""

    def test_get_document_id_from_chunk(self):
        """Test extracting document ID from chunk."""
        doc = _make_document()
        chunk = _make_chunk("test", document=doc)
        assert _get_document_id(chunk) == doc.id

    def test_get_document_id_fallback(self):
        """Test fallback to chunk ID when no document."""
        chunk = _make_chunk("test")
        chunk.is_part_of = None
        assert _get_document_id(chunk) == chunk.id


# ============================================================
# Distillation Response Model Tests
# ============================================================

class TestDistillationResponseModel:
    """Tests for the Pydantic response models."""

    def test_distillation_item(self):
        """Test DistillationItem creation."""
        item = DistillationItem(type="qa", text="Q: What? A: That.")
        assert item.type == "qa"
        assert item.text == "Q: What? A: That."

    def test_distillation_response(self):
        """Test DistillationResponse with multiple items."""
        items = [
            DistillationItem(type="enumeration", text="List of 3 items"),
            DistillationItem(type="negation", text="Document does not specify X"),
        ]
        response = DistillationResponse(items=items)
        assert len(response.items) == 2

    def test_empty_response(self):
        """Test empty DistillationResponse."""
        response = DistillationResponse()
        assert len(response.items) == 0


# ============================================================
# Core distill_knowledge Tests
# ============================================================

class TestDistillKnowledge:
    """Tests for the main distill_knowledge function."""

    @pytest.mark.asyncio
    async def test_empty_chunks(self):
        """Test with empty input returns empty list."""
        result = await distill_knowledge([])
        assert result == []

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.add_data_points", new_callable=AsyncMock)
    @patch("cognee.tasks.distillation.distill_knowledge._call_llm_distill", new_callable=AsyncMock)
    async def test_returns_original_chunks(self, mock_llm, mock_add):
        """Test that original chunks are returned unchanged."""
        mock_llm.return_value = [
            DistillationItem(type="qa", text="Test Q&A"),
        ]

        doc = _make_document()
        chunks = [_make_chunk("text1", 0, doc), _make_chunk("text2", 1, doc)]

        result = await distill_knowledge(chunks)

        # Must return the same chunk objects
        assert result is chunks
        assert len(result) == 2

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.add_data_points", new_callable=AsyncMock)
    @patch("cognee.tasks.distillation.distill_knowledge._call_llm_distill", new_callable=AsyncMock)
    async def test_calls_add_data_points(self, mock_llm, mock_add):
        """Test that distillation results are stored via add_data_points."""
        mock_llm.return_value = [
            DistillationItem(type="enumeration", text="List of items"),
            DistillationItem(type="qa", text="Q: What? A: This."),
        ]

        doc = _make_document()
        chunks = [_make_chunk("content", 0, doc)]

        await distill_knowledge(chunks)

        # add_data_points should be called with KnowledgeDistillation objects
        mock_add.assert_called_once()
        stored_points = mock_add.call_args[0][0]
        assert len(stored_points) == 2
        assert all(isinstance(p, KnowledgeDistillation) for p in stored_points)

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.add_data_points", new_callable=AsyncMock)
    @patch("cognee.tasks.distillation.distill_knowledge._call_llm_distill", new_callable=AsyncMock)
    async def test_groups_by_document(self, mock_llm, mock_add):
        """Test that chunks are grouped by document before distillation."""
        mock_llm.return_value = [
            DistillationItem(type="qa", text="Result"),
        ]

        doc1 = _make_document()
        doc2 = _make_document()
        chunks = [
            _make_chunk("doc1 chunk1", 0, doc1),
            _make_chunk("doc2 chunk1", 0, doc2),
            _make_chunk("doc1 chunk2", 1, doc1),
        ]

        await distill_knowledge(chunks)

        # LLM should be called twice (once per document)
        assert mock_llm.call_count == 2

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.add_data_points", new_callable=AsyncMock)
    @patch("cognee.tasks.distillation.distill_knowledge._call_llm_distill", new_callable=AsyncMock)
    async def test_handles_llm_failure(self, mock_llm, mock_add):
        """Test graceful handling when LLM call fails."""
        mock_llm.side_effect = Exception("LLM API error")

        doc = _make_document()
        chunks = [_make_chunk("content", 0, doc)]

        # Should not raise
        result = await distill_knowledge(chunks)
        assert result is chunks

        # add_data_points should NOT be called (no results)
        mock_add.assert_not_called()

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.add_data_points", new_callable=AsyncMock)
    @patch("cognee.tasks.distillation.distill_knowledge._call_llm_distill", new_callable=AsyncMock)
    async def test_deterministic_ids(self, mock_llm, mock_add):
        """Test that distillation point IDs are deterministic."""
        mock_llm.return_value = [
            DistillationItem(type="qa", text="Q: Test? A: Yes."),
        ]

        doc = _make_document()
        chunks = [_make_chunk("content", 0, doc)]

        await distill_knowledge(chunks)

        stored_points = mock_add.call_args[0][0]
        expected_id = uuid5(doc.id, "KnowledgeDistillation_0")
        assert stored_points[0].id == expected_id


# ============================================================
# LLM Call Tests
# ============================================================

class TestCallLlmDistill:
    """Tests for _call_llm_distill (uses response_model=str to avoid instructor overhead)."""

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.LLMGateway")
    @patch("cognee.tasks.distillation.distill_knowledge.read_query_prompt")
    @patch("cognee.tasks.distillation.distill_knowledge.render_prompt")
    async def test_calls_llm_gateway_with_str_model(self, mock_render, mock_read, mock_gateway):
        """Test that LLMGateway is called with response_model=str."""
        mock_read.return_value = "System prompt"
        mock_render.return_value = "Rendered input"
        mock_gateway.acreate_structured_output = AsyncMock(
            return_value=_make_llm_json_response()
        )

        items = await _call_llm_distill("Test document text")

        mock_gateway.acreate_structured_output.assert_called_once()
        call_kwargs = mock_gateway.acreate_structured_output.call_args
        # Must use response_model=str to avoid instructor JSON schema overhead
        assert call_kwargs.kwargs["response_model"] == str
        assert len(items) == 2

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.LLMGateway")
    @patch("cognee.tasks.distillation.distill_knowledge.read_query_prompt")
    @patch("cognee.tasks.distillation.distill_knowledge.render_prompt")
    async def test_filters_invalid_types(self, mock_render, mock_read, mock_gateway):
        """Test that invalid distillation types are filtered out."""
        mock_read.return_value = "System prompt"
        mock_render.return_value = "Rendered input"

        import json
        response_json = json.dumps([
            {"type": "qa", "text": "Valid Q&A"},
            {"type": "invalid_type", "text": "Should be filtered"},
            {"type": "enumeration", "text": "Valid enum"},
        ])
        mock_gateway.acreate_structured_output = AsyncMock(return_value=response_json)

        items = await _call_llm_distill("Test")
        assert len(items) == 2
        assert all(i.type in {"qa", "enumeration"} for i in items)

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.LLMGateway")
    @patch("cognee.tasks.distillation.distill_knowledge.read_query_prompt")
    @patch("cognee.tasks.distillation.distill_knowledge.render_prompt")
    async def test_filters_empty_text(self, mock_render, mock_read, mock_gateway):
        """Test that items with empty text are filtered out."""
        mock_read.return_value = "System prompt"
        mock_render.return_value = "Rendered input"

        import json
        response_json = json.dumps([
            {"type": "qa", "text": "Valid"},
            {"type": "qa", "text": ""},
            {"type": "qa", "text": "   "},
        ])
        mock_gateway.acreate_structured_output = AsyncMock(return_value=response_json)

        items = await _call_llm_distill("Test")
        assert len(items) == 1

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.LLMGateway")
    @patch("cognee.tasks.distillation.distill_knowledge.read_query_prompt")
    @patch("cognee.tasks.distillation.distill_knowledge.render_prompt")
    async def test_handles_llm_exception(self, mock_render, mock_read, mock_gateway):
        """Test graceful handling of LLM exceptions."""
        mock_read.return_value = "System prompt"
        mock_render.return_value = "Rendered input"
        mock_gateway.acreate_structured_output = AsyncMock(
            side_effect=Exception("API Error")
        )

        items = await _call_llm_distill("Test")
        assert items == []

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.LLMGateway")
    @patch("cognee.tasks.distillation.distill_knowledge.read_query_prompt")
    @patch("cognee.tasks.distillation.distill_knowledge.render_prompt")
    async def test_handles_empty_string_response(self, mock_render, mock_read, mock_gateway):
        """Test graceful handling when LLM returns empty string."""
        mock_read.return_value = "System prompt"
        mock_render.return_value = "Rendered input"
        mock_gateway.acreate_structured_output = AsyncMock(return_value="")

        items = await _call_llm_distill("Test")
        assert items == []

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge.LLMGateway")
    @patch("cognee.tasks.distillation.distill_knowledge.read_query_prompt")
    @patch("cognee.tasks.distillation.distill_knowledge.render_prompt")
    async def test_handles_non_string_response(self, mock_render, mock_read, mock_gateway):
        """Test graceful handling when LLM returns non-string."""
        mock_read.return_value = "System prompt"
        mock_render.return_value = "Rendered input"
        mock_gateway.acreate_structured_output = AsyncMock(return_value=None)

        items = await _call_llm_distill("Test")
        assert items == []


# ============================================================
# Response Parsing Tests
# ============================================================

class TestParseDistillationResponse:
    """Tests for _parse_distillation_response (manual JSON parsing from string)."""

    def test_parse_json_array(self):
        """Test parsing a plain JSON array."""
        import json
        text = json.dumps([
            {"type": "enumeration", "text": "List of 3 items"},
            {"type": "qa", "text": "Q: What? A: That."},
        ])
        items = _parse_distillation_response(text)
        assert len(items) == 2
        assert items[0].type == "enumeration"
        assert items[1].type == "qa"

    def test_parse_json_object_with_items(self):
        """Test parsing a JSON object with 'items' key."""
        import json
        text = json.dumps({
            "items": [
                {"type": "aggregation", "text": "Total: 17"},
                {"type": "negation", "text": "Not specified"},
            ]
        })
        items = _parse_distillation_response(text)
        assert len(items) == 2
        assert items[0].type == "aggregation"

    def test_parse_single_json_object(self):
        """Test parsing a single JSON object (not in array)."""
        import json
        text = json.dumps({"type": "disambiguation", "text": "A vs B"})
        items = _parse_distillation_response(text)
        assert len(items) == 1
        assert items[0].type == "disambiguation"

    def test_parse_markdown_code_block(self):
        """Test parsing JSON embedded in markdown code block."""
        text = '```json\n[{"type": "qa", "text": "Q: Test? A: Yes."}]\n```'
        items = _parse_distillation_response(text)
        assert len(items) == 1
        assert items[0].type == "qa"

    def test_parse_markdown_code_block_no_lang(self):
        """Test parsing JSON in markdown code block without language tag."""
        text = '```\n[{"type": "enumeration", "text": "Items: A, B, C"}]\n```'
        items = _parse_distillation_response(text)
        assert len(items) == 1

    def test_parse_json_with_surrounding_text(self):
        """Test extracting JSON from text with surrounding content."""
        text = 'Here are the results:\n[{"type": "qa", "text": "Answer"}]\nDone.'
        items = _parse_distillation_response(text)
        assert len(items) == 1

    def test_parse_filters_unknown_types(self):
        """Test that unknown distillation types are skipped."""
        import json
        text = json.dumps([
            {"type": "qa", "text": "Valid"},
            {"type": "unknown_type", "text": "Invalid"},
        ])
        items = _parse_distillation_response(text)
        assert len(items) == 1
        assert items[0].type == "qa"

    def test_parse_filters_empty_text(self):
        """Test that items with empty text are skipped."""
        import json
        text = json.dumps([
            {"type": "qa", "text": "Valid"},
            {"type": "qa", "text": ""},
            {"type": "qa", "text": "   "},
        ])
        items = _parse_distillation_response(text)
        assert len(items) == 1

    def test_parse_invalid_json(self):
        """Test that unparseable text returns empty list."""
        items = _parse_distillation_response("This is not JSON at all")
        assert items == []

    def test_parse_non_dict_items(self):
        """Test that non-dict items in array are skipped."""
        import json
        text = json.dumps([
            {"type": "qa", "text": "Valid"},
            "just a string",
            42,
            None,
        ])
        items = _parse_distillation_response(text)
        assert len(items) == 1

    def test_parse_chinese_content(self):
        """Test parsing Chinese content correctly."""
        import json
        text = json.dumps([
            {"type": "enumeration", "text": "本项目共实施17个业务流程"},
            {"type": "qa", "text": "Q: 服务范围? A: 共8项"},
        ], ensure_ascii=False)
        items = _parse_distillation_response(text)
        assert len(items) == 2
        assert "17" in items[0].text
        assert "8" in items[1].text


# ============================================================
# Hierarchical Distillation Tests
# ============================================================

class TestHierarchicalDistill:
    """Tests for hierarchical (map-reduce) distillation of large documents."""

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge._call_llm_distill", new_callable=AsyncMock)
    async def test_splits_large_documents(self, mock_llm):
        """Test that large documents are split into batches."""
        mock_llm.return_value = [
            DistillationItem(type="qa", text="Batch result"),
        ]

        # Create chunks that exceed the limit
        chunks = [_make_chunk("x" * 5000, i) for i in range(10)]  # 50000 chars total

        items = await _hierarchical_distill(chunks, context_char_limit=12000)

        # Should be called multiple times (batches + merge)
        assert mock_llm.call_count > 1
        assert len(items) > 0

    @pytest.mark.asyncio
    @patch("cognee.tasks.distillation.distill_knowledge._call_llm_distill", new_callable=AsyncMock)
    async def test_single_batch_no_merge(self, mock_llm):
        """Test that single-batch documents skip merge pass."""
        mock_llm.return_value = [
            DistillationItem(type="qa", text="Result"),
        ]

        # Small enough for one batch
        chunks = [_make_chunk("small text", 0)]

        items = await _hierarchical_distill(chunks, context_char_limit=50000)

        # Only one LLM call needed
        assert mock_llm.call_count == 1


# ============================================================
# Configuration Tests
# ============================================================

class TestDistillationConfig:
    """Tests for YAML configuration loading."""

    def test_config_file_loadable(self):
        """Test that distillation.yaml can be loaded."""
        from cognee.infrastructure.config.yaml_config import get_module_config, reload_config
        reload_config()
        config = get_module_config("distillation")
        distillation = config.get("distillation", {})

        assert distillation.get("enabled") is True
        assert distillation.get("context_char_limit") == 24000
        assert "enumeration" in distillation.get("types", [])
        assert "qa" in distillation.get("types", [])

    def test_config_has_all_types(self):
        """Test that all 5 distillation types are configured."""
        from cognee.infrastructure.config.yaml_config import get_module_config, reload_config
        reload_config()
        config = get_module_config("distillation")
        types = config.get("distillation", {}).get("types", [])

        expected_types = {"enumeration", "aggregation", "disambiguation", "negation", "qa"}
        assert set(types) == expected_types


# ============================================================
# Pipeline Integration Tests
# ============================================================

class TestPipelineIntegration:
    """Tests for cognify pipeline integration."""

    @pytest.mark.asyncio
    @patch("cognee.api.v1.cognify.cognify.get_module_config")
    async def test_distillation_injected_when_enabled(self, mock_config):
        """Test that distill_knowledge task is added when enabled."""
        from cognee.api.v1.cognify.cognify import get_default_tasks

        def config_side_effect(module_name):
            if module_name == "distillation":
                return {"distillation": {"enabled": True, "context_char_limit": 24000}}
            if module_name == "chunking":
                return {"chunking": {"chunk_size": 512, "chunk_overlap": 50}}
            if module_name == "graph_builder":
                return {"graph_builder": {"extraction": {}, "entity_resolution": {}}}
            return {}

        mock_config.side_effect = config_side_effect

        tasks = await get_default_tasks()

        # Find distill_knowledge in tasks
        task_executables = [t.executable.__name__ for t in tasks]
        assert "distill_knowledge" in task_executables

        # Verify it's before summarize_text
        distill_idx = task_executables.index("distill_knowledge")
        summarize_idx = task_executables.index("summarize_text")
        assert distill_idx < summarize_idx

    @pytest.mark.asyncio
    @patch("cognee.api.v1.cognify.cognify.get_module_config")
    async def test_distillation_not_injected_when_disabled(self, mock_config):
        """Test that distill_knowledge task is NOT added when disabled."""
        from cognee.api.v1.cognify.cognify import get_default_tasks

        def config_side_effect(module_name):
            if module_name == "distillation":
                return {"distillation": {"enabled": False}}
            if module_name == "chunking":
                return {"chunking": {"chunk_size": 512, "chunk_overlap": 50}}
            if module_name == "graph_builder":
                return {"graph_builder": {"extraction": {}, "entity_resolution": {}}}
            return {}

        mock_config.side_effect = config_side_effect

        tasks = await get_default_tasks()

        task_executables = [t.executable.__name__ for t in tasks]
        assert "distill_knowledge" not in task_executables

    @pytest.mark.asyncio
    @patch("cognee.api.v1.cognify.cognify.get_module_config")
    async def test_distillation_batch_size(self, mock_config):
        """Test that distillation task has batch_size=10000."""
        from cognee.api.v1.cognify.cognify import get_default_tasks

        def config_side_effect(module_name):
            if module_name == "distillation":
                return {"distillation": {"enabled": True, "context_char_limit": 24000}}
            if module_name == "chunking":
                return {"chunking": {"chunk_size": 512, "chunk_overlap": 50}}
            if module_name == "graph_builder":
                return {"graph_builder": {"extraction": {}, "entity_resolution": {}}}
            return {}

        mock_config.side_effect = config_side_effect

        tasks = await get_default_tasks()

        distill_task = next(t for t in tasks if t.executable.__name__ == "distill_knowledge")
        assert distill_task.task_config["batch_size"] == 10000
