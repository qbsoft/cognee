"""ModelProviderService — business logic for provider configuration.

Handles CRUD for user model configs, connection testing, and model resolution.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from cognee.shared.logging_utils import get_logger
from cognee.infrastructure.databases.relational import get_async_session

from .registry import (
    ProviderDefinition,
    get_all_providers,
    get_provider,
)
from cognee.modules.settings.models.UserModelConfig import UserModelConfig
from cognee.modules.settings.models.UserDefaultModel import UserDefaultModel

logger = get_logger("ModelProviderService")


@dataclass
class ConnectionTestResult:
    success: bool
    latency_ms: int = 0
    error: str = ""
    models_discovered: list[str] | None = None


@dataclass
class ResolvedModelConfig:
    """Everything needed to call an LLM — resolved from the priority chain."""
    provider_id: str
    model_id: str
    api_key: str
    base_url: str
    source: str  # "user" | "yaml" | "env" | "default"


class ModelProviderService:
    """Stateless service — each method receives or creates its own session."""

    # ------------------------------------------------------------------
    # Provider registry (read-only, in-memory)
    # ------------------------------------------------------------------

    @staticmethod
    def list_providers() -> list[ProviderDefinition]:
        return get_all_providers()

    @staticmethod
    def get_provider_definition(provider_id: str) -> Optional[ProviderDefinition]:
        return get_provider(provider_id)

    # ------------------------------------------------------------------
    # User config CRUD
    # ------------------------------------------------------------------

    @staticmethod
    async def get_user_configs(user_id: UUID) -> list[UserModelConfig]:
        async with get_async_session() as session:
            result = await session.execute(
                select(UserModelConfig).where(UserModelConfig.user_id == user_id)
            )
            return list(result.scalars().all())

    @staticmethod
    async def get_user_config(user_id: UUID, provider_id: str) -> Optional[UserModelConfig]:
        async with get_async_session() as session:
            result = await session.execute(
                select(UserModelConfig).where(
                    UserModelConfig.user_id == user_id,
                    UserModelConfig.provider_id == provider_id,
                )
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def save_user_config(
        user_id: UUID,
        provider_id: str,
        api_key: str = "",
        base_url: str = "",
        custom_params: dict | None = None,
    ) -> UserModelConfig:
        async with get_async_session() as session:
            result = await session.execute(
                select(UserModelConfig).where(
                    UserModelConfig.user_id == user_id,
                    UserModelConfig.provider_id == provider_id,
                )
            )
            config = result.scalar_one_or_none()

            if config is None:
                config = UserModelConfig(
                    user_id=user_id,
                    provider_id=provider_id,
                    enabled=True,
                )
                session.add(config)

            # Only update API key if a real value is provided (not masked)
            if api_key and "****" not in api_key:
                config.set_api_key(api_key)

            if base_url is not None:
                config.base_url = base_url or None
            if custom_params is not None:
                config.custom_params = custom_params

            await session.commit()
            await session.refresh(config)
            return config

    @staticmethod
    async def delete_user_config(user_id: UUID, provider_id: str) -> bool:
        async with get_async_session() as session:
            result = await session.execute(
                delete(UserModelConfig).where(
                    UserModelConfig.user_id == user_id,
                    UserModelConfig.provider_id == provider_id,
                )
            )
            await session.commit()
            return result.rowcount > 0

    # ------------------------------------------------------------------
    # Default model CRUD
    # ------------------------------------------------------------------

    @staticmethod
    async def get_user_defaults(user_id: UUID) -> list[UserDefaultModel]:
        async with get_async_session() as session:
            result = await session.execute(
                select(UserDefaultModel).where(UserDefaultModel.user_id == user_id)
            )
            return list(result.scalars().all())

    @staticmethod
    async def set_user_default(
        user_id: UUID, task_type: str, provider_id: str, model_id: str,
    ) -> UserDefaultModel:
        async with get_async_session() as session:
            result = await session.execute(
                select(UserDefaultModel).where(
                    UserDefaultModel.user_id == user_id,
                    UserDefaultModel.task_type == task_type,
                )
            )
            default = result.scalar_one_or_none()

            if default is None:
                default = UserDefaultModel(
                    user_id=user_id,
                    task_type=task_type,
                )
                session.add(default)

            default.provider_id = provider_id
            default.model_id = model_id

            await session.commit()
            await session.refresh(default)
            return default

    @staticmethod
    async def set_user_defaults_batch(
        user_id: UUID,
        defaults: dict[str, dict],
    ) -> list[UserDefaultModel]:
        """Set multiple defaults at once.  defaults = {"chat": {"provider_id": ..., "model_id": ...}}"""
        results = []
        for task_type, info in defaults.items():
            if info.get("provider_id") and info.get("model_id"):
                r = await ModelProviderService.set_user_default(
                    user_id, task_type, info["provider_id"], info["model_id"],
                )
                results.append(r)
        return results

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    @staticmethod
    async def test_connection(
        provider_id: str,
        api_key: str = "",
        base_url: str = "",
    ) -> ConnectionTestResult:
        """Send a lightweight request to verify credentials work."""
        provider_def = get_provider(provider_id)
        if provider_def is None:
            return ConnectionTestResult(success=False, error=f"Unknown provider: {provider_id}")

        effective_url = base_url or provider_def.default_base_url
        if not effective_url:
            return ConnectionTestResult(success=False, error="No API endpoint configured")

        try:
            import httpx

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            t0 = time.monotonic()

            # Try listing models first (lightweight)
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Normalize URL
                url = effective_url.rstrip("/")

                # Try /models endpoint
                resp = await client.get(f"{url}/models", headers=headers)

                latency = int((time.monotonic() - t0) * 1000)

                if resp.status_code == 200:
                    data = resp.json()
                    model_ids = []
                    if isinstance(data, dict) and "data" in data:
                        model_ids = [m.get("id", "") for m in data["data"][:20]]
                    return ConnectionTestResult(
                        success=True, latency_ms=latency, models_discovered=model_ids,
                    )
                elif resp.status_code == 401:
                    return ConnectionTestResult(
                        success=False, latency_ms=latency, error="认证失败: API Key 无效",
                    )
                elif resp.status_code == 404:
                    # /models not supported — try a minimal chat completion
                    return await ModelProviderService._test_via_chat(
                        client, url, headers, provider_def, t0,
                    )
                else:
                    return ConnectionTestResult(
                        success=False, latency_ms=latency,
                        error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    )

        except httpx.ConnectError:
            return ConnectionTestResult(success=False, error=f"无法连接到 {effective_url}")
        except httpx.TimeoutException:
            return ConnectionTestResult(success=False, error="连接超时 (15s)")
        except Exception as e:
            return ConnectionTestResult(success=False, error=str(e)[:200])

    @staticmethod
    async def _test_via_chat(client, url, headers, provider_def, t0):
        """Fallback: test via a tiny chat completion request."""
        import httpx

        model = ""
        if provider_def.default_models:
            model = provider_def.default_models[0].id

        body = {
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }
        try:
            resp = await client.post(f"{url}/chat/completions", headers=headers, json=body)
            latency = int((time.monotonic() - t0) * 1000)

            if resp.status_code in (200, 201):
                return ConnectionTestResult(success=True, latency_ms=latency)
            elif resp.status_code == 401:
                return ConnectionTestResult(
                    success=False, latency_ms=latency, error="认证失败: API Key 无效",
                )
            else:
                return ConnectionTestResult(
                    success=False, latency_ms=latency,
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
        except Exception as e:
            latency = int((time.monotonic() - t0) * 1000)
            return ConnectionTestResult(success=False, latency_ms=latency, error=str(e)[:200])

    # ------------------------------------------------------------------
    # Model resolution (priority chain)
    # ------------------------------------------------------------------

    @staticmethod
    async def resolve_model_config(
        user_id: UUID | None,
        task_type: str = "chat",
    ) -> ResolvedModelConfig:
        """Resolve which provider + model to use for a given user and task.

        Priority: user DB config > YAML model_selection > .env > hardcoded default
        """
        # 1. Try user-level default from DB
        if user_id:
            try:
                async with get_async_session() as session:
                    result = await session.execute(
                        select(UserDefaultModel).where(
                            UserDefaultModel.user_id == user_id,
                            UserDefaultModel.task_type == task_type,
                        )
                    )
                    user_default = result.scalar_one_or_none()

                    if user_default:
                        # Get credentials from user config
                        cred_result = await session.execute(
                            select(UserModelConfig).where(
                                UserModelConfig.user_id == user_id,
                                UserModelConfig.provider_id == user_default.provider_id,
                            )
                        )
                        user_config = cred_result.scalar_one_or_none()

                        provider_def = get_provider(user_default.provider_id)
                        base_url = ""
                        api_key = ""

                        if user_config:
                            api_key = user_config.get_api_key()
                            base_url = user_config.base_url or ""

                        if not base_url and provider_def:
                            base_url = provider_def.default_base_url

                        return ResolvedModelConfig(
                            provider_id=user_default.provider_id,
                            model_id=user_default.model_id,
                            api_key=api_key,
                            base_url=base_url,
                            source="user",
                        )
            except Exception as e:
                logger.debug(f"User model resolution failed: {e}")

        # 2. Fall back to .env / existing config
        from cognee.infrastructure.llm import get_llm_config
        llm_config = get_llm_config()

        return ResolvedModelConfig(
            provider_id=llm_config.llm_provider,
            model_id=llm_config.llm_model,
            api_key=llm_config.llm_api_key or "",
            base_url=llm_config.llm_endpoint or "",
            source="env",
        )
