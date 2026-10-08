"""Auditoría de .env.example: 12 vars documentadas, placeholders, sin secretos."""

import pathlib

BACKEND_EXAMPLE = pathlib.Path("backend/.env.example")
FRONTEND_EXAMPLE = pathlib.Path("frontend/.env.example")

BACKEND_REQUIRED = [
    "DATABASE_URL",
    "MP_ACCESS_TOKEN",
    "MP_WEBHOOK_SECRET",
    # Bloque WhatsApp QR (decisión usuario 2026-10-08, contradice DD-02/API oficial).
    "WHATSAPP_SESSION_DIR",
    "WHATSAPP_RECONNECT",
    "WHATSAPP_BACKUP_DIR",
    "WHATSAPP_PHONE_NUMBER",
    "ARCA_CUIT",
    "ARCA_CERT",
    "ARCA_KEY",
    "RECETAS_PARTNER_KEY",
    "ARS_PRECIO_MENSAJE",
    "RESERVA_PREBLOQUEO_MIN",
    "APP_BASE_URL",
    # Auth JWT (C-03, D9; solo backend, nunca VITE_).
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "JWT_ACCESS_MIN",
    "JWT_REFRESH_DAYS",
    "COOKIE_SECURE",
    "RATE_LIMIT_LOGIN",
]

SECRET_MARKERS = ("APP_USR-", "EAAB", "whsec_", "-----BEGIN")


def test_backend_env_example_lists_all_vars_with_placeholders() -> None:
    content = BACKEND_EXAMPLE.read_text(encoding="utf-8")
    for var in BACKEND_REQUIRED:
        assert var in content, f"falta {var} en backend/.env.example"
    assert "changeme" in content


def test_backend_env_example_has_no_real_secrets() -> None:
    content = BACKEND_EXAMPLE.read_text(encoding="utf-8")
    for marker in SECRET_MARKERS:
        assert marker not in content, f"posible secreto real: {marker}"


def test_frontend_env_example_only_vite_vars() -> None:
    content = FRONTEND_EXAMPLE.read_text(encoding="utf-8")
    assert "VITE_API_BASE_URL" in content
    assert "VITE_CLINICA_ID" in content
    for marker in SECRET_MARKERS:
        assert marker not in content
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        assert key.startswith("VITE_"), f"var no-VITE_ en frontend: {key}"
