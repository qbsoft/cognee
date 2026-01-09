#!/usr/bin/env python3
"""
检查用户的 superuser 状态
"""
import asyncio
from sqlalchemy import text
from cognee.infrastructure.databases.relational import get_relational_engine


async def check_superuser(user_email: str):
    """检查用户是否为 superuser"""
    db_engine = get_relational_engine()
    
    async with db_engine.get_async_session() as session:
        result = await session.execute(text("""
            SELECT 
                email,
                is_superuser,
                is_active,
                is_verified
            FROM users
            WHERE email = :email;
        """), {"email": user_email})
        
        row = result.fetchone()
        
        if not row:
            print(f"❌ 用户 {user_email} 不存在")
        else:
            print(f"\n✅ 用户: {row.email}")
            print(f"   is_superuser: {row.is_superuser}")
            print(f"   is_active: {row.is_active}")
            print(f"   is_verified: {row.is_verified}")


if __name__ == "__main__":
    import sys
    email = sys.argv[1] if len(sys.argv) > 1 else "superadmin@cognee.ai"
    asyncio.run(check_superuser(email))
