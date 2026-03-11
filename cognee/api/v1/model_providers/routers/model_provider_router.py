"""API routes for model provider configuration.

GET  /                          list all providers + user status
GET  /{provider_id}             single provider detail
POST /{provider_id}/config      save user credentials
DELETE /{provider_id}/config    remove user credentials
POST /{provider_id}/test        test connection
GET  /user/defaults             get user's default models
PUT  /user/defaults             set user's default models
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException

from cognee.modules.users.methods import get_authenticated_user
from cognee.modules.users.models import User
from cognee.infrastructure.llm.providers.service import ModelProviderService


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

class ProviderConfigInput(BaseModel):
    api_key: str = ""
    base_url: str = ""
    custom_params: dict = Field(default_factory=dict)


class DefaultModelInput(BaseModel):
    provider_id: str
    model_id: str


class DefaultModelsInput(BaseModel):
    chat: Optional[DefaultModelInput] = None
    extraction: Optional[DefaultModelInput] = None
    embedding: Optional[DefaultModelInput] = None


class ConnectionTestInput(BaseModel):
    api_key: str = ""
    base_url: str = ""


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_provider(prov, user_configs: dict | None = None):
    """Convert ProviderDefinition + optional user config to JSON-safe dict."""
    user_cfg = (user_configs or {}).get(prov.id)
    return {
        "id": prov.id,
        "name": prov.name,
        "name_en": prov.name_en,
        "category": prov.category,
        "icon": prov.icon,
        "default_base_url": prov.default_base_url,
        "is_openai_compatible": prov.is_openai_compatible,
        "auth_type": prov.auth_type,
        "capabilities": list(prov.capabilities),
        "notes": prov.notes,
        "notes_en": prov.notes_en,
        "is_configured": user_cfg is not None,
        "is_enabled": user_cfg.enabled if user_cfg else False,
        "api_key_preview": user_cfg.api_key_preview() if user_cfg else "",
        "base_url": (user_cfg.base_url or "") if user_cfg else "",
        "models": [
            {
                "id": m.id,
                "name": m.name,
                "capabilities": list(m.capabilities),
                "max_tokens": m.max_tokens,
                "is_default": m.is_default,
            }
            for m in prov.default_models
        ],
        "config_fields": [
            {
                "key": f.key,
                "label": f.label,
                "label_en": f.label_en,
                "type": f.type,
                "required": f.required,
                "placeholder": f.placeholder,
                "help_text": f.help_text,
                "help_text_en": f.help_text_en,
            }
            for f in prov.config_fields
        ],
    }


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def get_model_provider_router() -> APIRouter:
    router = APIRouter()
    svc = ModelProviderService()

    @router.get("")
    async def list_providers(user: User = Depends(get_authenticated_user)):
        """List all available model providers with user's config status."""
        providers = svc.list_providers()
        user_configs_list = await svc.get_user_configs(user.id)
        user_configs = {c.provider_id: c for c in user_configs_list}

        categories = {
            "local": {"label": "本地模型", "label_en": "Local Models", "providers": []},
            "cloud_cn": {"label": "国内云端", "label_en": "China Cloud", "providers": []},
            "cloud_intl": {"label": "国际云端", "label_en": "International Cloud", "providers": []},
        }

        for prov in providers:
            cat = categories.get(prov.category)
            if cat:
                cat["providers"].append(_serialize_provider(prov, user_configs))

        return {"categories": categories}

    @router.get("/user/defaults")
    async def get_user_defaults(user: User = Depends(get_authenticated_user)):
        """Get user's default model for each task type."""
        defaults = await svc.get_user_defaults(user.id)
        result = {}
        for d in defaults:
            result[d.task_type] = {
                "provider_id": d.provider_id,
                "model_id": d.model_id,
            }
        return {"defaults": result}

    @router.put("/user/defaults")
    async def set_user_defaults(
        body: DefaultModelsInput,
        user: User = Depends(get_authenticated_user),
    ):
        """Set user's default models for each task type."""
        defaults_dict = {}
        for task_type in ("chat", "extraction", "embedding"):
            val = getattr(body, task_type, None)
            if val:
                defaults_dict[task_type] = {
                    "provider_id": val.provider_id,
                    "model_id": val.model_id,
                }

        await svc.set_user_defaults_batch(user.id, defaults_dict)
        return {"status": "ok"}

    @router.get("/{provider_id}")
    async def get_provider(
        provider_id: str,
        user: User = Depends(get_authenticated_user),
    ):
        """Get single provider details + user config."""
        prov = svc.get_provider_definition(provider_id)
        if not prov:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

        user_cfg = await svc.get_user_config(user.id, provider_id)
        user_configs = {provider_id: user_cfg} if user_cfg else {}
        return _serialize_provider(prov, user_configs)

    @router.post("/{provider_id}/config")
    async def save_config(
        provider_id: str,
        body: ProviderConfigInput,
        user: User = Depends(get_authenticated_user),
    ):
        """Save user's provider configuration (API key, endpoint)."""
        prov = svc.get_provider_definition(provider_id)
        if not prov:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

        config = await svc.save_user_config(
            user_id=user.id,
            provider_id=provider_id,
            api_key=body.api_key,
            base_url=body.base_url,
            custom_params=body.custom_params,
        )
        return config.to_dict()

    @router.delete("/{provider_id}/config")
    async def delete_config(
        provider_id: str,
        user: User = Depends(get_authenticated_user),
    ):
        """Remove user's provider configuration."""
        deleted = await svc.delete_user_config(user.id, provider_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Config not found")
        return {"status": "deleted"}

    @router.post("/{provider_id}/test")
    async def test_connection(
        provider_id: str,
        body: ConnectionTestInput,
        user: User = Depends(get_authenticated_user),
    ):
        """Test connection to a provider."""
        prov = svc.get_provider_definition(provider_id)
        if not prov:
            raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

        # Use provided credentials, or fall back to saved ones
        api_key = body.api_key
        base_url = body.base_url

        if (not api_key or "****" in api_key) and not base_url:
            saved = await svc.get_user_config(user.id, provider_id)
            if saved:
                if not api_key or "****" in api_key:
                    api_key = saved.get_api_key()
                if not base_url:
                    base_url = saved.base_url or ""

        result = await svc.test_connection(provider_id, api_key, base_url)
        return {
            "success": result.success,
            "latency_ms": result.latency_ms,
            "error": result.error,
            "models_discovered": result.models_discovered,
        }

    return router
