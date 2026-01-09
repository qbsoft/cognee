from uuid import UUID
from sqlalchemy.exc import IntegrityError

from cognee.infrastructure.databases.exceptions import EntityAlreadyExistsError
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.modules.users.models import Tenant, Role
from cognee.modules.users.methods import get_user
from .generate_tenant_code import generate_unique_tenant_code


async def create_tenant(
    tenant_name: str, 
    user_id: UUID,
    auto_initialize: bool = True,
) -> UUID:
    """
    创建一个新租户（仅 super-admin 可调用）
    
    创建过程：
    1. 生成唯一的 6 位租户编码
    2. 创建租户记录
    3. 将创建者设置为租户 owner 并加入租户
    4. 如果 auto_initialize=True，自动创建默认角色：
       - "管理员" 角色
       - "普通用户" 角色
    
    Args:
        tenant_name: 租户名称
        user_id: 创建者用户 ID（必须是 super-admin）
        auto_initialize: 是否自动初始化默认角色（默认 True）

    Returns:
        UUID: 新创建的租户 ID
    
    Raises:
        EntityAlreadyExistsError: 用户已有租户或租户名已存在
    """
    db_engine = get_relational_engine()
    async with db_engine.get_async_session() as session:
        try:
            user = await get_user(user_id)
            if user.tenant_id:
                raise EntityAlreadyExistsError(
                    message="User already has a tenant. New tenant cannot be created."
                )

            # 生成唯一租户编码
            tenant_code = await generate_unique_tenant_code()
            
            # 创建租户
            tenant = Tenant(name=tenant_name, tenant_code=tenant_code, owner_id=user_id)
            session.add(tenant)
            await session.flush()

            # 注意：不将super-admin加入租户，也不分配角色
            # 租户管理员将在后续单独创建
            
            # 自动初始化默认角色
            if auto_initialize:
                # 创建 "管理员" 角色
                admin_role = Role(name="管理员", tenant_id=tenant.id)
                session.add(admin_role)
                
                # 创建 "普通用户" 角色
                user_role = Role(name="普通用户", tenant_id=tenant.id)
                session.add(user_role)
                
                await session.flush()
            
            await session.commit()
            return tenant.id
        except IntegrityError as e:
            raise EntityAlreadyExistsError(message="Tenant already exists.") from e
