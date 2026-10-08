"""Dominio auth (C-03). Blacklist persistente de jti + servicio de tokens."""

from app.domain.auth.models import TokenBlacklist

__all__ = ["TokenBlacklist"]
