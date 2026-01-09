from uuid import UUID
from typing import List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from cognee.infrastructure.databases.relational import with_async_session

from ..models.Notebook import Notebook
from .create_notebook import _create_tutorial_notebook, TUTORIAL_NOTEBOOK_NAME

from cognee.shared.logging_utils import get_logger

logger = get_logger()


@with_async_session
async def get_notebooks(
    user_id: UUID,
    session: AsyncSession,
) -> List[Notebook]:
    # Check if tutorial notebook already exists for this user
    tutorial_query = select(Notebook).where(
        and_(
            Notebook.owner_id == user_id,
            Notebook.name == TUTORIAL_NOTEBOOK_NAME,
            ~Notebook.deletable,
        )
    )
    tutorial_result = await session.execute(tutorial_query)
    # Use first() instead of scalar_one_or_none() to handle duplicate tutorial notebooks
    tutorial_notebook = tutorial_result.scalars().first()

    # If tutorial notebook doesn't exist, create it
    if tutorial_notebook is None:
        logger.info(f"Tutorial notebook not found for user {user_id}, creating it")
        try:
            await _create_tutorial_notebook(user_id, session, force_refresh=False)
            # Refresh the session to get the newly created notebook
            await session.commit()
        except Exception as e:
            # Log the error but continue to return existing notebooks
            logger.error(f"Failed to create tutorial notebook for user {user_id}: {e}")
            # Rollback on error to avoid partial state
            await session.rollback()

    # Get all notebooks for the user
    result = await session.execute(select(Notebook).where(Notebook.owner_id == user_id))

    return list(result.scalars().all())
