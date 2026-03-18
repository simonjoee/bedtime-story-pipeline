import logging
import os
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.auth import COOKIE_NAME, get_session, REQUIRE_LOGIN

logger = logging.getLogger(__name__)

BASE_PATH = os.getenv("BASE_PATH", "")

PUBLIC_PATHS = [
    "/login",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/health",
    f"/api/login",
    f"/api/check-auth",
    "/static",
]

PUBLIC_PREFIXES = [
    "/static",
]


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        
        # 如果不需要登录，直接放行
        if not REQUIRE_LOGIN:
            return await call_next(request)
        
        for public_path in PUBLIC_PATHS:
            if path == public_path or path.startswith(public_path):
                return await call_next(request)
        
        for prefix in PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)
        
        session_id = request.cookies.get(COOKIE_NAME)
        session = get_session(session_id) if session_id else None
        
        if not session:
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    {"error": {"code": "UNAUTHORIZED", "message": "请先登录"}},
                    status_code=401
                )
            else:
                from fastapi.responses import RedirectResponse
                login_url = f"{BASE_PATH}/login" if BASE_PATH else "/login"
                return RedirectResponse(url=login_url)
        
        return await call_next(request)
