from typing import List
from sqlalchemy import select
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.modules.users.models import Tenant


async def get_all_tenants() -> List[Tenant]:
    """
    获取所有租户列表
    
    Returns:
        List[Tenant]: 租户列表，按创建时间倒序排列
    """
    db_engine = get_relational_engine()
    
    async with db_engine.get_async_session() as session:
        result = await session.execute(
            select(Tenant).order_by(Tenant.created_at.desc())
        )
        tenants = result.scalars().all()
        return list(tenants)
