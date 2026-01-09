import asyncio
from sqlalchemy import select, text
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.modules.users.models import User, Role


async def check_user_roles(email: str):
    """检查用户的角色"""
    db_engine = get_relational_engine()
    
    async with db_engine.get_async_session() as session:
        # 查找用户
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalars().first()
        
        if not user:
            print(f"❌ 用户 {email} 不存在")
            return
        
        print(f"✅ 用户信息:")
        print(f"   邮箱: {user.email}")
        print(f"   ID: {user.id}")
        print(f"   租户ID: {user.tenant_id}")
        print(f"   is_superuser: {user.is_superuser}")
        print(f"   is_active: {user.is_active}")
        
        # 查询用户的角色
        result = await session.execute(text("""
            SELECT r.name, r.id
            FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = :user_id
        """), {"user_id": str(user.id)})
        
        roles = result.fetchall()
        
        if roles:
            print(f"\n✅ 用户角色 ({len(roles)} 个):")
            for role_name, role_id in roles:
                print(f"   - {role_name} (ID: {role_id})")
        else:
            print("\n❌ 用户没有分配任何角色")


if __name__ == "__main__":
    import sys
    email = sys.argv[1] if len(sys.argv) > 1 else "beijingtech@tyersoft.com"
    asyncio.run(check_user_roles(email))
