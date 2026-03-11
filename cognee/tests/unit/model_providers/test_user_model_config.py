"""Unit tests for UserModelConfig model."""

import pytest
from uuid import uuid4


class TestUserModelConfig:
    """Tests for the UserModelConfig SQLAlchemy model."""

    def test_import(self):
        from cognee.modules.settings.models.UserModelConfig import UserModelConfig
        assert UserModelConfig is not None

    def test_tablename(self):
        from cognee.modules.settings.models.UserModelConfig import UserModelConfig
        assert UserModelConfig.__tablename__ == "user_model_configs"

    def test_set_and_get_api_key(self):
        from cognee.modules.settings.models.UserModelConfig import UserModelConfig
        config = UserModelConfig(
            user_id=uuid4(),
            provider_id="dashscope",
            enabled=True,
        )
        config.set_api_key("sk-test-key-12345")
        assert config.get_api_key() == "sk-test-key-12345"

    def test_api_key_is_base64_encoded(self):
        from cognee.modules.settings.models.UserModelConfig import UserModelConfig
        config = UserModelConfig(
            user_id=uuid4(),
            provider_id="openai",
            enabled=True,
        )
        config.set_api_key("sk-hello")
        # The encoded value should not be the plain text
        assert config.api_key_encoded != "sk-hello"
        assert config.api_key_encoded is not None

    def test_get_api_key_none_when_not_set(self):
        from cognee.modules.settings.models.UserModelConfig import UserModelConfig
        config = UserModelConfig(
            user_id=uuid4(),
            provider_id="openai",
            enabled=True,
        )
        assert config.get_api_key() == ""

    def test_api_key_preview_masked(self):
        from cognee.modules.settings.models.UserModelConfig import UserModelConfig
        config = UserModelConfig(
            user_id=uuid4(),
            provider_id="dashscope",
            enabled=True,
        )
        config.set_api_key("sk-abcdefghijklmnop")
        preview = config.api_key_preview()
        assert "****" in preview
        # Should show first few and last few chars
        assert preview.startswith("sk")

    def test_api_key_preview_empty_when_not_set(self):
        from cognee.modules.settings.models.UserModelConfig import UserModelConfig
        config = UserModelConfig(
            user_id=uuid4(),
            provider_id="openai",
            enabled=True,
        )
        assert config.api_key_preview() == ""

    def test_to_dict(self):
        from cognee.modules.settings.models.UserModelConfig import UserModelConfig
        uid = uuid4()
        config = UserModelConfig(
            id=uuid4(),
            user_id=uid,
            provider_id="deepseek",
            enabled=True,
        )
        config.set_api_key("sk-test")
        d = config.to_dict()
        assert d["provider_id"] == "deepseek"
        assert d["enabled"] is True
        assert "api_key_encoded" not in d  # Should not leak encoded key
        assert "api_key_preview" in d

    def test_set_api_key_roundtrip_unicode(self):
        from cognee.modules.settings.models.UserModelConfig import UserModelConfig
        config = UserModelConfig(
            user_id=uuid4(),
            provider_id="test",
            enabled=True,
        )
        key = "sk-unicode-test-key-with-special-chars"
        config.set_api_key(key)
        assert config.get_api_key() == key


class TestUserDefaultModel:
    """Tests for the UserDefaultModel SQLAlchemy model."""

    def test_import(self):
        from cognee.modules.settings.models.UserDefaultModel import UserDefaultModel
        assert UserDefaultModel is not None

    def test_tablename(self):
        from cognee.modules.settings.models.UserDefaultModel import UserDefaultModel
        assert UserDefaultModel.__tablename__ == "user_default_models"

    def test_to_dict(self):
        from cognee.modules.settings.models.UserDefaultModel import UserDefaultModel
        model = UserDefaultModel(
            id=uuid4(),
            user_id=uuid4(),
            task_type="chat",
            provider_id="dashscope",
            model_id="qwen-plus",
        )
        d = model.to_dict()
        assert d["task_type"] == "chat"
        assert d["provider_id"] == "dashscope"
        assert d["model_id"] == "qwen-plus"
