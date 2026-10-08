"""FastAPI application factory with structured logging and safe error handlers."""

import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.admin_catalogo import router as admin_catalogo_router
from app.api.auth import router as auth_router
from app.api.bloqueos_propios import router as bloqueos_propios_router
from app.api.catalogo import router as catalogo_router
from app.api.health import router as health_router
from app.api.pacientes import router as pacientes_router
from app.api.permissions import set_resolver_agenda_propia, set_resolver_vinculo_paciente
from app.domain.agenda.servicio import CatalogoError, profesional_de_usuario
from app.domain.auth.ratelimit import RETRY_AFTER_S, LoginEmailMiddleware, limiter
from app.domain.pacientes.servicios import PacienteError

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
    # C-04: vinculo real Usuario->Profesional para require_own_agenda (firma de C-03 intacta).
    set_resolver_agenda_propia(profesional_de_usuario)
    # C-08: regla interina de vinculo odontologo-paciente (C-05 la reemplaza); reset por app.
    set_resolver_vinculo_paciente(None)

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

    @app.exception_handler(CatalogoError)
    async def catalogo_error_handler(request: Request, exc: CatalogoError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(PacienteError)
    async def paciente_error_handler(request: Request, exc: PacienteError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail, **exc.extra}
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        _logger.exception("unhandled exception path=%s", request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

    app.add_middleware(LoginEmailMiddleware)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(admin_catalogo_router)
    app.include_router(bloqueos_propios_router)
    app.include_router(catalogo_router)
    app.include_router(pacientes_router)
    return app


app = create_app()
