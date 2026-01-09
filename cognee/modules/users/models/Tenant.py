from sqlalchemy.orm import relationship
from sqlalchemy import Column, String, ForeignKey, UUID, DateTime
from datetime import datetime, timezone
from .Principal import Principal
from .User import User
from .Role import Role


class Tenant(Principal):
    __tablename__ = "tenants"

    id = Column(UUID, ForeignKey("principals.id"), primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    
    # 6位唯一租户编码，用于用户注册
    tenant_code = Column(String(6), unique=True, nullable=False, index=True)
    
    # 租户有效期，超过有效期的租户用户无法登录
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    owner_id = Column(UUID, index=True)

    # One-to-Many relationship with User; specify the join via User.tenant_id
    users = relationship(
        "User",
        back_populates="tenant",
        foreign_keys=lambda: [User.tenant_id],
    )

    # One-to-Many relationship with Role (if needed; similar fix)
    roles = relationship(
        "Role",
        back_populates="tenant",
        foreign_keys=lambda: [Role.tenant_id],
    )

    __mapper_args__ = {
        "polymorphic_identity": "tenant",
    }
