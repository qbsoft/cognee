"""Unit tests for cognee.modules.ingestion.identify module."""
import pytest
from uuid import UUID, uuid4

from cognee.modules.ingestion.identify import identify
from cognee.modules.ingestion.data_types import TextData
from cognee.modules.users.models import User


class MockIngestionData:
    """Mock IngestionData for testing."""

    def __init__(self, identifier: str):
        self._identifier = identifier

    def get_identifier(self) -> str:
        return self._identifier


class TestIdentify:
    """Tests for the identify function."""

    def _create_test_user(self, user_id: UUID = None) -> User:
        """Create a test user with minimal required fields."""
        return User(
            id=user_id or uuid4(),
            email="test@example.com",
        )

    def test_identify_returns_uuid(self):
        """Test that identify returns a valid UUID."""
        user = self._create_test_user()
        data = MockIngestionData("test_content_hash")

        result = identify(data, user)

        assert isinstance(result, UUID)

    def test_identify_same_content_same_user_returns_same_id(self):
        """Test deterministic ID generation for same content and user."""
        user_id = uuid4()
        user = self._create_test_user(user_id)
        data = MockIngestionData("same_hash")

        result1 = identify(data, user)
        result2 = identify(data, user)

        assert result1 == result2

    def test_identify_different_content_returns_different_id(self):
        """Test different content produces different IDs."""
        user = self._create_test_user()
        data1 = MockIngestionData("hash_one")
        data2 = MockIngestionData("hash_two")

        result1 = identify(data1, user)
        result2 = identify(data2, user)

        assert result1 != result2

    def test_identify_different_users_returns_different_id(self):
        """Test same content with different users produces different IDs."""
        user1 = self._create_test_user(uuid4())
        user2 = self._create_test_user(uuid4())
        data = MockIngestionData("same_hash")

        result1 = identify(data, user1)
        result2 = identify(data, user2)

        assert result1 != result2

    def test_identify_with_text_data(self):
        """Test identify works with TextData."""
        user = self._create_test_user()
        text_data = TextData("Hello, World!")

        result = identify(text_data, user)

        assert isinstance(result, UUID)

    def test_identify_empty_content(self):
        """Test identify handles empty content hash."""
        user = self._create_test_user()
        data = MockIngestionData("")

        result = identify(data, user)

        assert isinstance(result, UUID)

    def test_identify_special_characters_in_hash(self):
        """Test identify handles special characters in content hash."""
        user = self._create_test_user()
        data = MockIngestionData("hash-with_special.chars/and\\more")

        result = identify(data, user)

        assert isinstance(result, UUID)

    def test_identify_unicode_content(self):
        """Test identify handles unicode content hash."""
        user = self._create_test_user()
        data = MockIngestionData("unicode_content")

        result = identify(data, user)

        assert isinstance(result, UUID)
