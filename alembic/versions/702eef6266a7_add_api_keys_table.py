"""add_api_keys_table

Revision ID: 702eef6266a7
Revises: e9f90c7bfe8c
Create Date: 2025-12-16 22:50:11.381066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '702eef6266a7'
down_revision: Union[str, None] = 'e9f90c7bfe8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 api_keys 表
    op.create_table(
        'api_keys',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('scopes', sa.Text(), nullable=True, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # 创建索引
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'], unique=True)
    op.create_index('ix_api_keys_tenant_id', 'api_keys', ['tenant_id'], unique=False)


def downgrade() -> None:
    # 删除索引
    op.drop_index('ix_api_keys_tenant_id', table_name='api_keys')
    op.drop_index('ix_api_keys_key_hash', table_name='api_keys')
    
    # 删除表
    op.drop_table('api_keys')
