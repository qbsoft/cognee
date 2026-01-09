"""add_saas_permission_features

Revision ID: 8d60a996ceac
Revises: 211ab850ef3d
Create Date: 2025-12-16 10:33:23.289064

添加 SaaS 权限系统特性：
1. 在 tenants 表添加 tenant_code 字段（6位唯一编码）
2. 创建 invite_tokens 表（邀请链接系统）
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8d60a996ceac'
down_revision: Union[str, None] = '211ab850ef3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库：添加 SaaS 权限功能"""
    
    # 1. 在 tenants 表添加 tenant_code 字段
    op.add_column(
        'tenants',
        sa.Column('tenant_code', sa.String(length=6), nullable=True)  # 先设为 nullable
    )
    
    # 2. 为现有租户生成编码
    # 注：这里使用 SQL 生成简单的随机编码，生产环境应使用更安全的方法
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE tenants 
        SET tenant_code = UPPER(SUBSTRING(MD5(RANDOM()::text || id::text) FROM 1 FOR 6))
        WHERE tenant_code IS NULL
    """))
    
    # 3. 设置 tenant_code 为 NOT NULL 并添加索引和唯一约束
    op.alter_column('tenants', 'tenant_code', nullable=False)
    op.create_index('ix_tenants_tenant_code', 'tenants', ['tenant_code'], unique=False)
    op.create_unique_constraint('uq_tenants_tenant_code', 'tenants', ['tenant_code'])
    
    # 4. 创建 invite_tokens 表
    op.create_table(
        'invite_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('token', sa.String(length=32), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('used_by', sa.UUID(), nullable=True),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['used_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index('ix_invite_tokens_id', 'invite_tokens', ['id'], unique=False)
    op.create_index('ix_invite_tokens_token', 'invite_tokens', ['token'], unique=False)


def downgrade() -> None:
    """降级数据库：移除 SaaS 权限功能"""
    
    # 1. 删除 invite_tokens 表
    op.drop_index('ix_invite_tokens_token', table_name='invite_tokens')
    op.drop_index('ix_invite_tokens_id', table_name='invite_tokens')
    op.drop_table('invite_tokens')
    
    # 2. 删除 tenant_code 相关索引和约束
    op.drop_constraint('uq_tenants_tenant_code', 'tenants', type_='unique')
    op.drop_index('ix_tenants_tenant_code', table_name='tenants')
    
    # 3. 删除 tenant_code 列
    op.drop_column('tenants', 'tenant_code')
