"""Credenciales: bcrypt tiempo-constante + email normalizado (C-03 3.2, D3).

Sin enumeración: usuario-inexistente y password-mala responden idéntico
(``authenticate`` retorna None en ambos; el endpoint usa un único 401).
"""

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.core.models import Usuario

LOGIN_FALLO_MSG = "Credenciales inválidas"

# Hash sintético para igualar tiempos ante usuario inexistente (descartado).
_DUMMY_HASH = bcrypt.hashpw(b"dummy-sintetico-no-valido", bcrypt.gensalt()).decode(
    "utf-8"
)


def normalize_email(email: str) -> str:
    """Minúsculas + trim (consistente con UsuarioCreate y uq por lower)."""
    return email.strip().lower()


def verify_password(plain: str, password_hash: str) -> bool:
    """Comparación bcrypt (tiempo constante por diseño). Nunca propaga."""
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"), password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def authenticate(
    session: Session,
    email: str,
    password: str,
    clinica_id: int | None = None,
) -> Usuario | None:
    """Retorna el Usuario activo si las credenciales son válidas, else None.

    Cero o múltiples candidatos (mismo email en varios tenants sin filtro)
    responden igual que password-mala: None + chequeo dummy anti-timing.
    """
    normalized = normalize_email(email)
    query = select(Usuario).where(
        func.lower(Usuario.email) == normalized,
        Usuario.is_active.is_(True),
    )
    if clinica_id is not None:
        query = query.where(Usuario.clinica_id == clinica_id)
    candidates = session.scalars(query).all()
    if len(candidates) != 1:
        verify_password(password, _DUMMY_HASH)
        return None
    user = candidates[0]
    if not verify_password(password, user.password_hash):
        return None
    return user
