"""FastAPI application factory with structured logging and safe error handlers."""

import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.domain.auth.ratelimit import RETRY_AFTER_S, LoginEmailMiddleware, limiter

_logger = logging.getLogger("turnos")
_auth_log = logging.getLogger("turnos.auth")


def _configure_logging() -> None:
    if not _logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('{"level":"%(levelname)s","msg":"%(message)s"}'))
        _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    _configure_logging()
    app = FastAPI(title="Turnos Odontología API")
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        ip = request.client.host if request.client else "?"
        _auth_log.info(
            json.dumps(
                {"evento": "rate_limit", "ip": ip, "path": request.url.path},
                ensure_ascii=False,
            )
        )
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": RETRY_AFTER_S},
            content={"detail": "Demasiados intentos. Reintentá más tarde."},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        _logger.exception("unhandled exception path=%s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

    app.add_middleware(LoginEmailMiddleware)
    app.include_router(health_router)
    app.include_router(auth_router)
    return app


app = create_app()
