import asyncio
from sqlalchemy import text
from cognee.infrastructure.databases.relational import get_relational_engine

async def add_expires_at_column():
    """添加 expires_at 字段到 tenants 表"""
    db_engine = get_relational_engine()
    
    async with db_engine.get_async_session() as session:
        # 添加字段（如果不存在）
        await session.execute(text("""
            ALTER TABLE tenants 
            ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;
        """))
        
        # 添加索引（如果不存在）
        await session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_tenants_expires_at 
            ON tenants(expires_at);
        """))
        
        await session.commit()
        print("✅ 成功添加 expires_at 字段和索引")

if __name__ == "__main__":
    asyncio.run(add_expires_at_column())
