"""require_tenant: 422 sin header/inválido, 404 inexistente, id si existe (Task 2.3)."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.deps import require_tenant


def _session_with(existing: int | None) -> MagicMock:
    session = MagicMock()
    session.scalars.return_value.first.return_value = existing
    return session


def test_sin_header_rechaza_422() -> None:
    with pytest.raises(HTTPException) as exc:
        require_tenant(None, _session_with(None))  # type: ignore[arg-type]
    assert exc.value.status_code == 422


def test_header_no_numerico_o_no_positivo_rechaza_422() -> None:
    for raw in ("abc", "0", "-3"):
        with pytest.raises(HTTPException) as exc:
            require_tenant(raw, _session_with(None))  # type: ignore[arg-type]
        assert exc.value.status_code == 422


def test_tenant_inexistente_rechaza_404() -> None:
    with pytest.raises(HTTPException) as exc:
        require_tenant("99", _session_with(None))  # type: ignore[arg-type]
    assert exc.value.status_code == 404


def test_tenant_existente_inyecta_id() -> None:
    assert require_tenant("5", _session_with(5)) == 5  # type: ignore[arg-type]
