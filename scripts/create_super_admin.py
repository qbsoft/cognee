#!/usr/bin/env python3
"""
超级管理员初始化脚本

用途：创建第一个 super-admin 用户，用于管理整个 SaaS 平台

使用方法：
    python scripts/create_super_admin.py --email admin@example.com --password your_password
"""
import asyncio
import argparse
from cognee.modules.users.methods import create_user


async def create_super_admin(email: str, password: str):
    """
    创建超级管理员用户
    
    Args:
        email: 管理员邮箱
        password: 管理员密码
    """
    try:
        user = await create_user(
            email=email,
            password=password,
            is_superuser=True,  # 设置为超级管理员
            is_active=True,
            is_verified=True,
            auto_login=False
        )
        
        print(f"✅ 超级管理员创建成功！")
        print(f"   邮箱: {user.email}")
        print(f"   用户ID: {user.id}")
        print(f"   权限: super-admin")
        print(f"\n现在您可以使用此账号登录并创建租户。")
        
    except Exception as e:
        print(f"❌ 创建超级管理员失败: {str(e)}")
        if "already exists" in str(e).lower():
            print(f"   该邮箱已被注册，请使用其他邮箱。")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="创建 Cognee 超级管理员用户"
    )
    parser.add_argument(
        "--email",
        required=True,
        help="超级管理员邮箱"
    )
    parser.add_argument(
        "--password",
        required=True,
        help="超级管理员密码（至少8位）"
    )
    
    args = parser.parse_args()
    
    # 验证密码长度
    if len(args.password) < 8:
        print("❌ 密码至少需要8位字符")
        return
    
    print(f"正在创建超级管理员: {args.email}")
    
    try:
        asyncio.run(create_super_admin(args.email, args.password))
    except KeyboardInterrupt:
        print("\n❌ 操作已取消")
    except Exception:
        exit(1)


if __name__ == "__main__":
    main()
