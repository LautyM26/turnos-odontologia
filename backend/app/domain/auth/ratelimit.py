"""Rate limit login 5/60s por par IP+email vía slowapi (C-03 3.3, D4).

La clave combina IP + email normalizado. El email viaja en el body JSON,
que el key_func síncrono no puede leer: ``LoginEmailMiddleware`` lo extrae
antes (Starlette cachea el body, el endpoint lo relee sin costo extra).
Memoria por instancia en MVP (riesgo documentado: F2 mueve el contador a PG).
"""

import json

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.domain.auth.passwords import normalize_email

LOGIN_LIMIT = "5/minute"
LOGIN_PATH = "/api/auth/login"
RETRY_AFTER_S = "60"


def login_key(request: Request) -> str:
    """Clave IP+email; '?' si el email aún no se extrajo (falla cerrado a IP)."""
    email = getattr(request.state, "login_email", "?")
    return f"{get_remote_address(request)}:{email}"


limiter = Limiter(key_func=login_key, default_limits=[])


class LoginEmailMiddleware(BaseHTTPMiddleware):
    """Extrae el email del body de login a ``request.state`` pre-rate-limit."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if request.method == "POST" and request.url.path == LOGIN_PATH:
            try:
                raw = await request.body()
                parsed = json.loads(raw.decode("utf-8") or "{}")
                request.state.login_email = normalize_email(
                    str(parsed.get("email", "?"))
                )
            except (ValueError, UnicodeDecodeError, AttributeError):
                request.state.login_email = "?"
        return await call_next(request)


def reset_login_limits() -> None:
    """Limpia el contador en memoria (solo tests)."""
    storage = getattr(limiter, "_storage", None)
    reset = getattr(storage, "reset", None)
    if callable(reset):
        reset()
