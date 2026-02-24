"""Unit tests for cognee.modules.storage.utils module."""
import json
import pytest
from uuid import uuid4, UUID
from decimal import Decimal
from datetime import datetime

from cognee.modules.storage.utils import JSONEncoder, copy_model, get_own_properties
from cognee.infrastructure.engine import DataPoint


class TestJSONEncoder:
    """Tests for the JSONEncoder class."""

    def test_encode_datetime(self):
        """Test JSONEncoder encodes datetime to ISO format."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = json.dumps({"date": dt}, cls=JSONEncoder)
        assert "2024-01-15T10:30:00" in result

    def test_encode_uuid(self):
        """Test JSONEncoder encodes UUID to string."""
        uid = uuid4()
        result = json.dumps({"id": uid}, cls=JSONEncoder)
        assert str(uid) in result

    def test_encode_decimal(self):
        """Test JSONEncoder encodes Decimal to float."""
        dec = Decimal("123.45")
        result = json.dumps({"value": dec}, cls=JSONEncoder)
        data = json.loads(result)
        assert data["value"] == 123.45

    def test_encode_regular_types(self):
        """Test JSONEncoder handles regular types."""
        data = {"string": "test", "int": 42, "float": 3.14, "list": [1, 2]}
        result = json.dumps(data, cls=JSONEncoder)
        decoded = json.loads(result)
        assert decoded == data

    def test_encode_nested_objects(self):
        """Test JSONEncoder handles nested special types."""
        data = {
            "id": uuid4(),
            "created_at": datetime.now(),
            "amount": Decimal("99.99"),
        }
        result = json.dumps(data, cls=JSONEncoder)
        assert isinstance(result, str)


class TestCopyModel:
    """Tests for the copy_model function."""

    def test_copy_model_basic(self):
        """Test copy_model creates new model class."""
        class TestModel(DataPoint):
            name: str
            value: int

        NewModel = copy_model(TestModel)
        assert NewModel is not TestModel
        assert "name" in NewModel.model_fields
        assert "value" in NewModel.model_fields

    def test_copy_model_exclude_fields(self):
        """Test copy_model excludes specified fields."""
        class TestModel(DataPoint):
            name: str
            secret: str

        NewModel = copy_model(TestModel, exclude_fields=["secret"])
        assert "name" in NewModel.model_fields
        assert "secret" not in NewModel.model_fields

    def test_copy_model_include_fields(self):
        """Test copy_model includes additional fields."""
        class TestModel(DataPoint):
            name: str

        NewModel = copy_model(TestModel, include_fields={"extra": (str, "default")})
        assert "name" in NewModel.model_fields
        assert "extra" in NewModel.model_fields


class TestGetOwnProperties:
    """Tests for the get_own_properties function."""

    def test_get_own_properties_simple(self):
        """Test get_own_properties returns simple properties."""
        class SimpleModel(DataPoint):
            name: str
            count: int

        instance = SimpleModel(id=uuid4(), name="test", count=5)
        props = get_own_properties(instance)

        assert "name" in props
        assert props["name"] == "test"
        assert "count" in props
        assert props["count"] == 5

    def test_get_own_properties_excludes_metadata(self):
        """Test get_own_properties excludes metadata field."""
        class ModelWithMeta(DataPoint):
            name: str
            metadata: dict = {}

        instance = ModelWithMeta(id=uuid4(), name="test", metadata={"key": "value"})
        props = get_own_properties(instance)

        assert "name" in props
        assert "metadata" not in props
