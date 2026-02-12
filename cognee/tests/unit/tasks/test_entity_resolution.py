import pytest
from unittest.mock import AsyncMock


class TestEntityResolution:
    @pytest.mark.asyncio
    async def test_merge_same_entities_by_name_similarity(self):
        from cognee.tasks.entity_resolution.resolve_entities import resolve_entities
        entities = [
            {"id": "1", "name": "阿里巴巴", "type": "Company", "aliases": []},
            {"id": "2", "name": "阿里巴巴集团", "type": "Company", "aliases": []},
            {"id": "3", "name": "腾讯", "type": "Company", "aliases": []},
        ]
        result = await resolve_entities(entities, fuzzy_threshold=0.7)
        company_names = [e["name"] for e in result]
        assert "腾讯" in company_names
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_merge_entities_with_aliases(self):
        from cognee.tasks.entity_resolution.resolve_entities import resolve_entities
        entities = [
            {"id": "1", "name": "Alibaba", "type": "Company", "aliases": ["阿里巴巴"]},
            {"id": "2", "name": "阿里巴巴", "type": "Company", "aliases": []},
        ]
        result = await resolve_entities(entities, fuzzy_threshold=0.7)
        assert len(result) == 1
        assert "Alibaba" in result[0]["aliases"] or result[0]["name"] == "Alibaba"

    @pytest.mark.asyncio
    async def test_no_merge_different_types(self):
        from cognee.tasks.entity_resolution.resolve_entities import resolve_entities
        entities = [
            {"id": "1", "name": "Apple", "type": "Company", "aliases": []},
            {"id": "2", "name": "Apple", "type": "Fruit", "aliases": []},
        ]
        result = await resolve_entities(entities, fuzzy_threshold=0.9)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_entities(self):
        from cognee.tasks.entity_resolution.resolve_entities import resolve_entities
        result = await resolve_entities([])
        assert result == []

    @pytest.mark.asyncio
    async def test_single_entity(self):
        from cognee.tasks.entity_resolution.resolve_entities import resolve_entities
        entities = [{"id": "1", "name": "Test", "type": "Thing", "aliases": []}]
        result = await resolve_entities(entities)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_merge_preserves_all_aliases(self):
        from cognee.tasks.entity_resolution.resolve_entities import resolve_entities
        entities = [
            {"id": "1", "name": "北京大学", "type": "University", "aliases": ["北大"]},
            {"id": "2", "name": "北大", "type": "University", "aliases": ["PKU"]},
        ]
        result = await resolve_entities(entities, fuzzy_threshold=0.6)
        assert len(result) == 1
        all_names = [result[0]["name"]] + result[0].get("aliases", [])
        assert "北大" in all_names or "北京大学" in all_names
