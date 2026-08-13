from typing import Awaitable, Callable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

TokenVerifier = Callable[[str], Awaitable[bool]]


class AuthHandler:
    def __init__(self, verify: Optional[TokenVerifier] = None):
        self._verify = verify

    def set_verifier(self, verify: TokenVerifier):
        self._verify = verify

    async def verify_token(self, token: str) -> bool:
        if self._verify is None:
            return True
        return await self._verify(token)


auth_handler = AuthHandler()


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_paths: Optional[list[str]] = None):
        super().__init__(app)
        self._exclude = exclude_paths or ["/api/health"]

    async def dispatch(self, request: Request, call_next: Callable):
        for path in self._exclude:
            if request.url.path == path or request.url.path.rstrip("/") == path.rstrip("/"):
                return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Token de autorización requerido (Bearer)."},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        if not token or not await auth_handler.verify_token(token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Token inválido o expirado."},
            )

        return await call_next(request)
