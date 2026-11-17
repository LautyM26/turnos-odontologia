"""Schemas de emisión de recetas y huella de la solicitud (C-19 1.5). Sin DB."""

from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain.recetas.schemas import RecetaIn, huella_solicitud

ADAPTER = TypeAdapter(RecetaIn)
MED = {
    "nombre_generico": "amoxicilina",
    "presentacion": "comprimidos 500 mg",
    "cantidad": 1,
    "posologia": "1 cada 8 horas por 7 dias",
}
EST = {"estudio": "Radiografia panoramica", "indicacion": "Control sintetico"}


def _receta(**over):  # type: ignore[no-untyped-def]
    base = {
        "tipo": "receta",
        "evolucion_id": 1,
        "diagnostico": "Infeccion sintetica",
        "items": [MED],
        "clave_idempotencia": str(uuid4()),
    }
    return {**base, **over}


def _orden(**over):  # type: ignore[no-untyped-def]
    return _receta(**{"tipo": "orden_estudio", "items": [EST], **over})


def test_acepta_receta_y_orden() -> None:
    assert ADAPTER.validate_python(_receta()).tipo == "receta"
    assert ADAPTER.validate_python(_orden()).tipo == "orden_estudio"


@pytest.mark.parametrize("n", [0, 11])
def test_cantidad_de_items_fuera_de_rango(n: int) -> None:
    for mk, item in ((_receta, MED), (_orden, EST)):
        with pytest.raises(ValidationError):
            ADAPTER.validate_python({**mk(), "items": [item] * n})


def test_borde_10_items_ok() -> None:
    assert len(ADAPTER.validate_python(_receta(items=[MED] * 10)).items) == 10


def test_medicamentos_en_orden_y_estudios_en_receta_rechazados() -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(_orden(items=[MED]))
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(_receta(items=[EST]))


@pytest.mark.parametrize("diag", ["", "   ", "x" * 501])
def test_diagnostico_invalido(diag: str) -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(_receta(diagnostico=diag))


def test_diagnostico_500_ok() -> None:
    assert ADAPTER.validate_python(_receta(diagnostico="x" * 500))


def test_clave_no_uuid() -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(_receta(clave_idempotencia="no-es-uuid"))


@pytest.mark.parametrize(
    "extra", ["id_externo", "partner", "pdf_url", "simulada", "autor_usuario_id", "fecha"]
)
def test_extras_de_servidor_rechazados(extra: str) -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(_receta(**{extra: "x"}))


def test_extra_dentro_de_item_rechazado() -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(_receta(items=[{**MED, "precio": 1}]))


def test_huella_estable_ante_orden_de_claves_y_cambia_con_item() -> None:
    a = ADAPTER.validate_python(_receta())
    reordenado = ADAPTER.validate_python(
        {**_receta(), "items": [dict(reversed(list(MED.items())))]}
    )
    assert huella_solicitud(a) == huella_solicitud(reordenado)  # la clave no entra en la huella
    otro = ADAPTER.validate_python(_receta(items=[{**MED, "cantidad": 2}]))
    assert huella_solicitud(a) != huella_solicitud(otro)
    assert len(huella_solicitud(a)) == 64
