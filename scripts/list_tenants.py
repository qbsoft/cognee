#!/usr/bin/env python3
"""
查询租户信息
"""
import asyncio
from sqlalchemy import text
from cognee.infrastructure.databases.relational import get_relational_engine


async def get_tenants():
    """查询所有租户"""
    db_engine = get_relational_engine()
    
    async with db_engine.get_async_session() as session:
        result = await session.execute(text("""
            SELECT p.id, t.name, t.tenant_code
            FROM tenants t
            JOIN principals p ON t.id = p.id
            ORDER BY p.id DESC;
        """))
        tenants = result.fetchall()
        
        if not tenants:
            print("暂无租户")
        else:
            print(f"\n📋 租户列表（共 {len(tenants)} 个）:\n")
            for tenant_id, name, code in tenants:
                print(f"  • {name}")
                print(f"    ID: {tenant_id}")
                print(f"    编码: {code}")
                print()


if __name__ == "__main__":
    asyncio.run(get_tenants())
