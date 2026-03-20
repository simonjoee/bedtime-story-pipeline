import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse, Response

from app.auth import COOKIE_NAME, get_session, REQUIRE_LOGIN

logger = logging.getLogger(__name__)


def get_public_paths() -> list[str]:
    from app.main import BASE_PATH
    base = BASE_PATH or ""
    
    common = [
        "/login",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/health",
        "/api/login",
        "/api/check-auth",
        "/static",
    ]
    
    if not base:
        return common
    
    return common + [
        f"{base}/",
        f"{base}/login",
        f"{base}/api/login",
        f"{base}/api/check-auth",
    ]


def get_public_prefixes() -> list[str]:
    from app.main import BASE_PATH
    base = BASE_PATH or ""
    
    common = ["/static"]
    
    if not base:
        return common
    
    return common + [f"{base}/static"]


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not REQUIRE_LOGIN:
            return await call_next(request)
        
        path = request.url.path
        public_paths = get_public_paths()
        public_prefixes = get_public_prefixes()
        
        if any(path == p or path.startswith(p) for p in public_paths):
            return await call_next(request)
        
        if any(path.startswith(prefix) for prefix in public_prefixes):
            return await call_next(request)
        
        session_id = request.cookies.get(COOKIE_NAME)
        session = get_session(session_id) if session_id else None
        
        if not session:
            if path.startswith("/api/"):
                return JSONResponse(
                    {"error": {"code": "UNAUTHORIZED", "message": "请先登录"}},
                    status_code=401
                )
            
            from app.main import BASE_PATH
            login_url = f"{BASE_PATH}/login" if BASE_PATH else "/login"
            return RedirectResponse(url=login_url)
        
        return await call_next(request)
