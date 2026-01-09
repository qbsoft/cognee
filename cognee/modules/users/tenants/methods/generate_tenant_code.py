import secrets
import string
from typing import Set
from sqlalchemy import select
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.modules.users.models import Tenant


async def generate_unique_tenant_code() -> str:
    """
    生成一个唯一的 6 位租户编码
    
    编码规则:
    - 6 位大写字母和数字组合
    - 避免容易混淆的字符: 0/O, 1/I/L
    - 确保全局唯一性
    
    Returns:
        str: 6 位唯一租户编码
    """
    # 定义字符集（排除容易混淆的字符）
    # 移除: 0(数字零), O(字母O), 1(数字一), I(字母I), L(字母L)
    allowed_chars = ''.join(
        c for c in string.ascii_uppercase + string.digits 
        if c not in {'0', 'O', '1', 'I', 'L'}
    )  # 结果: ABCDEFGHJKMNPQRSTUVWXYZ23456789 (31个字符)
    
    max_attempts = 10  # 最多尝试 10 次
    db_engine = get_relational_engine()
    
    for attempt in range(max_attempts):
        # 生成 6 位随机编码
        code = ''.join(secrets.choice(allowed_chars) for _ in range(6))
        
        # 检查数据库中是否已存在
        async with db_engine.get_async_session() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.tenant_code == code)
            )
            existing = result.scalars().first()
            
            if not existing:
                return code
    
    # 如果 10 次都冲突（几乎不可能发生，概率为 1/31^6 * 10）
    raise RuntimeError(
        "Failed to generate unique tenant code after multiple attempts. "
        "This is extremely rare and may indicate a database issue."
    )


def validate_tenant_code(code: str) -> bool:
    """
    验证租户编码格式是否正确
    
    Args:
        code: 待验证的租户编码
    
    Returns:
        bool: 是否有效
    """
    if not code or len(code) != 6:
        return False
    
    # 允许的字符集
    allowed_chars = set('ABCDEFGHJKMNPQRSTUVWXYZ23456789')
    
    return all(c in allowed_chars for c in code.upper())


async def check_tenant_code_exists(code: str) -> bool:
    """
    检查租户编码是否已存在
    
    Args:
        code: 租户编码
    
    Returns:
        bool: 是否存在
    """
    db_engine = get_relational_engine()
    
    async with db_engine.get_async_session() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.tenant_code == code.upper())
        )
        return result.scalars().first() is not None
