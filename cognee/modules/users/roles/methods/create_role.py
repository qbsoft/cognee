from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, text

from cognee.infrastructure.databases.exceptions import EntityAlreadyExistsError
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.modules.users.methods import get_user
from cognee.modules.users.permissions.methods import get_tenant
from cognee.modules.users.exceptions import PermissionDeniedError
from cognee.modules.users.models import (
    Role,
)


async def create_role(
    role_name: str,
    owner_id: UUID,
) -> UUID:
    """
        Create a new role with the given name, if the request owner with the given id
        has the necessary permission.
    Args:
        role_name: Name of the new role.
        owner_id: Id of the request owner.

    Returns:
        None
    """
    db_engine = get_relational_engine()
    async with db_engine.get_async_session() as session:
        user = await get_user(owner_id)
        tenant = await get_tenant(user.tenant_id)

        # 检查权限：用户必须是租户 owner 或拥有"管理员"角色
        is_owner = (owner_id == tenant.owner_id)
        
        # 检查用户是否拥有"管理员"角色
        result = await session.execute(text("""
            SELECT COUNT(*) as count
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = :user_id 
            AND r.name = '管理员'
            AND r.tenant_id = :tenant_id
        """), {"user_id": owner_id, "tenant_id": tenant.id})
        
        row = result.fetchone()
        has_admin_role = row.count > 0 if row else False
        
        if not is_owner and not has_admin_role:
            raise PermissionDeniedError(
                "User submitting request does not have permission to create role for tenant. "
                "User must be tenant owner or have '管理员' role."
            )

        try:
            # Add association directly to the association table
            role = Role(name=role_name, tenant_id=tenant.id)
            session.add(role)
        except IntegrityError as e:
            raise EntityAlreadyExistsError(message="Role already exists for tenant.") from e

        await session.commit()
        await session.refresh(role)
        return role.id
