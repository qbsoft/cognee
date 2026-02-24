"""
Pytest configuration for cognee tests.

This module provides fixtures for proper cleanup of database connections
between tests to prevent connection pool exhaustion issues.
"""

import asyncio
import pytest
import pytest_asyncio
from cognee.infrastructure.databases.relational.create_relational_engine import (
    create_relational_engine,
)


async def _cleanup_connections():
    """Helper function to cleanup database connections."""
    try:
        # Check if there's a cached engine instance
        if create_relational_engine.cache_info().currsize > 0:
            # Get the cached engine
            from cognee.infrastructure.databases.relational import get_relational_engine

            engine = get_relational_engine()

            # Dispose of the connection pool
            if engine and hasattr(engine, "engine"):
                await engine.engine.dispose()

            # Clear the lru_cache to ensure fresh engine for next test
            create_relational_engine.cache_clear()

            # Small delay to allow connections to fully close
            await asyncio.sleep(0.1)
    except Exception:
        # If cleanup fails, still try to clear the cache
        try:
            create_relational_engine.cache_clear()
        except Exception:
            pass


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database_connections():
    """
    Fixture that runs after each test to properly cleanup database connections.

    This fixture addresses the issue where PostgreSQL connection pools are shared
    between tests via the lru_cache on create_relational_engine. Without proper
    cleanup, connections from previous tests may interfere with subsequent tests.

    The fixture:
    1. Yields control to the test
    2. After the test completes, disposes of the engine's connection pool
    3. Clears the lru_cache to ensure fresh connections for the next test
    """
    # Let the test run first
    yield

    # After the test, cleanup the connection pool
    await _cleanup_connections()
