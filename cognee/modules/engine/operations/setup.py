from cognee.infrastructure.databases.relational import (
    create_db_and_tables as create_relational_db_and_tables,
)


async def setup():
    """
    Set up the necessary databases and tables.

    This function asynchronously creates a relational database and its corresponding tables.
    Vector database initialization is handled by the vector engine factory based on configured provider.
    """
    await create_relational_db_and_tables()
