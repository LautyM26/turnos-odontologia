"""Settings de la lista de espera (C-16 1.1, D10). Valores sintéticos."""

import pytest
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("LISTA_ESPERA_OFERTA_MIN", "LISTA_ESPERA_ANTICIPACION_MIN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-sintetico-32-chars-minimo-0000")


def test_defaults() -> None:
    from app.infrastructure.settings import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (s.lista_espera_oferta_min, s.lista_espera_anticipacion_min) == (30, 120)


@pytest.mark.parametrize(
    ("var", "valor"),
    [("LISTA_ESPERA_OFERTA_MIN", "1"), ("LISTA_ESPERA_OFERTA_MIN", "241"),
     ("LISTA_ESPERA_ANTICIPACION_MIN", "-1"), ("LISTA_ESPERA_ANTICIPACION_MIN", "1441")],
)  # fmt: skip
def test_fuera_de_rango(monkeypatch: pytest.MonkeyPatch, var: str, valor: str) -> None:
    monkeypatch.setenv(var, valor)
    from app.infrastructure.settings import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
