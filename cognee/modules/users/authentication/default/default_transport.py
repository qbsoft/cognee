import os
from fastapi_users.authentication import CookieTransport

default_transport = CookieTransport(
    cookie_name=os.getenv("AUTH_TOKEN_COOKIE_NAME", "auth_token"),
    cookie_secure=False,  # 开发环境不需要 HTTPS
    cookie_httponly=True,  # 防止 JavaScript 访问,提升安全性
    cookie_samesite="lax",  # 允许跨站请求携带 Cookie (开发环境使用lax而非none)
    cookie_max_age=86400,  # Cookie 有效期 24 小时,与 JWT 同步
    cookie_domain=None,  # 不限制 domain,自动适应
    cookie_path="/",  # Cookie 路径设置为根路径,确保所有路径都能访问
)

default_transport.name = "cookie"
