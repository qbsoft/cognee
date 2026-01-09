"""add_tenant_expires_at_field

Revision ID: e9f90c7bfe8c
Revises: 8d60a996ceac
Create Date: 2025-12-16 16:08:23.541164

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9f90c7bfe8c'
down_revision: Union[str, None] = '8d60a996ceac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 expires_at 字段到 tenants 表
    op.add_column(
        'tenants',
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True)
    )
    # 添加索引以提高查询性能
    op.create_index(
        'ix_tenants_expires_at',
        'tenants',
        ['expires_at'],
        unique=False
    )


def downgrade() -> None:
    # 删除索引
    op.drop_index('ix_tenants_expires_at', table_name='tenants')
    # 删除字段
    op.drop_column('tenants', 'expires_at')
