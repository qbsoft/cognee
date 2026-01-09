#!/usr/bin/env python3
"""
手动添加 tenant_code 列到数据库
"""
import asyncio
import secrets
import string
from sqlalchemy import text
from cognee.infrastructure.databases.relational import get_relational_engine


async def add_tenant_code_column():
    """添加 tenant_code 列并为现有租户生成编码"""
    db_engine = get_relational_engine()
    
    async with db_engine.get_async_session() as session:
        # 1. 添加列（如果不存在）
        print("📝 添加 tenant_code 列...")
        try:
            await session.execute(text("""
                ALTER TABLE tenants 
                ADD COLUMN IF NOT EXISTS tenant_code VARCHAR(6);
            """))
            await session.commit()
            print("✅ tenant_code 列已添加")
        except Exception as e:
            print(f"⚠️  列可能已存在: {e}")
            await session.rollback()
        
        # 2. 为现有租户生成编码
        print("\n📝 为现有租户生成编码...")
        result = await session.execute(text("""
            SELECT id, name FROM tenants WHERE tenant_code IS NULL;
        """))
        tenants = result.fetchall()
        
        if not tenants:
            print("✅ 所有租户都已有编码")
        else:
            allowed_chars = ''.join(
                c for c in string.ascii_uppercase + string.digits 
                if c not in {'0', 'O', '1', 'I', 'L'}
            )
            
            for tenant_id, tenant_name in tenants:
                # 生成唯一编码
                max_attempts = 10
                for _ in range(max_attempts):
                    code = ''.join(secrets.choice(allowed_chars) for _ in range(6))
                    
                    # 检查是否已存在
                    check = await session.execute(text(
                        "SELECT id FROM tenants WHERE tenant_code = :code"
                    ), {"code": code})
                    
                    if not check.fetchone():
                        # 更新租户
                        await session.execute(text("""
                            UPDATE tenants SET tenant_code = :code WHERE id = :id
                        """), {"code": code, "id": str(tenant_id)})
                        print(f"   ✅ {tenant_name}: {code}")
                        break
            
            await session.commit()
        
        # 3. 添加唯一约束和索引
        print("\n📝 添加约束和索引...")
        try:
            await session.execute(text("""
                ALTER TABLE tenants 
                ALTER COLUMN tenant_code SET NOT NULL;
            """))
            await session.commit()
            print("✅ 设置 NOT NULL 约束")
        except Exception as e:
            print(f"⚠️  NOT NULL 约束可能已存在: {e}")
            await session.rollback()
        
        try:
            await session.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_tenants_tenant_code 
                ON tenants(tenant_code);
            """))
            await session.commit()
            print("✅ 创建唯一索引")
        except Exception as e:
            print(f"⚠️  索引可能已存在: {e}")
            await session.rollback()
    
    print("\n🎉 数据库更新完成！")


if __name__ == "__main__":
    asyncio.run(add_tenant_code_column())
