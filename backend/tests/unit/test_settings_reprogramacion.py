"""Settings de la reprogramación (C-17 1.1, D6). Valores sintéticos."""

import pytest
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("CHATBOT_TIMEOUT_MIN", "REPROGRAMACION_ANTICIPACION_MIN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-sintetico-32-chars-minimo-0000")


def test_defaults() -> None:
    from app.infrastructure.settings import Settings

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (s.chatbot_timeout_min, s.reprogramacion_anticipacion_min) == (30, 120)


@pytest.mark.parametrize(
    ("var", "valor"),
    [("CHATBOT_TIMEOUT_MIN", "0"), ("CHATBOT_TIMEOUT_MIN", "241"),
     ("REPROGRAMACION_ANTICIPACION_MIN", "-1"), ("REPROGRAMACION_ANTICIPACION_MIN", "1441")],
)  # fmt: skip
def test_fuera_de_rango(monkeypatch: pytest.MonkeyPatch, var: str, valor: str) -> None:
    monkeypatch.setenv(var, valor)
    from app.infrastructure.settings import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
