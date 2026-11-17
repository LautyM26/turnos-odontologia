"""Odontograma FDI versionado append-only (C-09 3.1 y 3.3). PG16 real, datos sintéticos."""

import pytest
from sqlalchemy import func, select

from app.domain.auditoria.models import AuditoriaHC
from app.domain.clinica.models import Odontograma
from tests.integration.conftest import bearer, nuevo_paciente_c09


@pytest.fixture()
def pid(session_factory, staff_c09) -> int:  # type: ignore[no-untyped-def]
    """Paciente A con consentimiento, sin odontograma (uno fresco por test)."""
    return nuevo_paciente_c09(session_factory, staff_c09["a"])


def _h(client, staff_c09, clave="o"):  # type: ignore[no-untyped-def]
    return bearer(client, staff_c09[f"{clave}_email"])


def _post(client, pid, h, version=0, denticion="permanente", piezas=None, **extra):  # type: ignore[no-untyped-def]
    cuerpo = {
        "version_esperada": version, "denticion": denticion,
        "piezas": piezas if piezas is not None else {}, **extra,
    }  # fmt: skip
    return client.post(f"/api/pacientes/{pid}/odontograma", json=cuerpo, headers=h)


def _n_versiones(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            select(func.count()).select_from(Odontograma).where(Odontograma.paciente_id == pid)
        )


def _eventos(session_factory, pid: int, **filtros):  # type: ignore[no-untyped-def]
    with session_factory() as s:
        stmt = select(AuditoriaHC).where(AuditoriaHC.paciente_id == pid)
        for k, v in filtros.items():
            stmt = stmt.where(getattr(AuditoriaHC, k) == v)
        return list(s.scalars(stmt.order_by(AuditoriaHC.id)).all())


CARIES_O = {"16": {"caras": {"O": {"codigo": "caries"}}}}


# --- Felices -------------------------------------------------------------------------------


def test_primer_odontograma_201(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = _post(client, pid, _h(client, staff_c09), piezas=CARIES_O)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["version"] == 1 and body["denticion"] == "permanente"
    assert body["autor_usuario_id"] == staff_c09["o"]
    assert body["created_at"]
    assert body["piezas"]["16"]["caras"]["O"] == {"codigo": "caries", "registro": "existente"}


def test_nueva_version_conserva_la_anterior(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    assert _post(client, pid, h, 0, piezas=CARIES_O).status_code == 201
    obt = {"16": {"caras": {"O": {"codigo": "obturacion"}}}}
    r2 = _post(client, pid, h, 1, piezas=obt)
    assert r2.status_code == 201 and r2.json()["version"] == 2
    hist = client.get(f"/api/pacientes/{pid}/odontograma", headers=h).json()
    assert [v["version"] for v in hist] == [2, 1]
    assert hist[1]["piezas"]["16"]["caras"]["O"]["codigo"] == "caries"
    actual = client.get(f"/api/pacientes/{pid}/odontograma/actual", headers=h).json()
    assert actual["version"] == 2


def test_sin_hallazgos_201(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = _post(client, pid, _h(client, staff_c09), piezas={})
    assert r.status_code == 201 and r.json()["version"] == 1 and r.json()["piezas"] == {}


def test_temporal_85_201(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = _post(client, pid, _h(client, staff_c09), denticion="temporal", piezas={"85": {}})
    assert r.status_code == 201, r.text


def test_limites_mixta_201(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    piezas = {p: {} for p in ("11", "48", "51", "85")}
    r = _post(client, pid, _h(client, staff_c09), denticion="mixta", piezas=piezas)
    assert r.status_code == 201, r.text
    assert set(r.json()["piezas"]) == set(piezas)


def test_marcas_validas_por_cara_se_devuelven_tal_cual(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    piezas = {
        "36": {
            "caras": {
                "M": {"codigo": "caries", "registro": "a_realizar"},
                "O": {"codigo": "obturacion", "registro": "existente"},
            }
        }
    }
    r = _post(client, pid, _h(client, staff_c09), piezas=piezas)
    assert r.status_code == 201, r.text
    assert r.json()["piezas"]["36"]["caras"] == piezas["36"]["caras"]


# --- Errores de negocio --------------------------------------------------------------------


def test_version_vieja_409_sin_version_nueva(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    _post(client, pid, h, 0)
    _post(client, pid, h, 1)
    assert _post(client, pid, h, 1).status_code == 409
    assert _post(client, pid, h, 7).status_code == 409
    assert _n_versiones(session_factory, pid) == 2


def test_pieza_temporal_en_permanente_422(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = _post(client, pid, _h(client, staff_c09), piezas={"55": {}})
    assert r.status_code == 422
    assert "55" in r.text
    assert _n_versiones(session_factory, pid) == 0


@pytest.mark.parametrize(
    "piezas",
    [
        {"16": {"caras": {"X": {"codigo": "caries"}}}},
        {"16": {"caras": {"O": {"codigo": "blanqueamiento"}}}},
        {"16": {"estado": {"codigo": "blanqueamiento"}}},
        {"26": {"estado": {"codigo": "ausente"}, "caras": {"O": {"codigo": "caries"}}}},
    ],
)
def test_cara_o_estado_desconocido_o_ausente_con_caras_422(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid, piezas
) -> None:
    assert _post(client, pid, _h(client, staff_c09), piezas=piezas).status_code == 422
    assert _n_versiones(session_factory, pid) == 0


@pytest.mark.parametrize("extra", [{"autor_usuario_id": 1}, {"created_at": "2020-01-01T00:00:00Z"}])
def test_campo_extra_422(client, session_factory, staff_c09, pid, extra) -> None:  # type: ignore[no-untyped-def]
    assert _post(client, pid, _h(client, staff_c09), **extra).status_code == 422
    assert _n_versiones(session_factory, pid) == 0


def test_sin_consentimiento_403_sin_fila_y_antes_de_validar(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09
) -> None:
    sin = nuevo_paciente_c09(session_factory, staff_c09["a"], consentimiento=False)
    h = _h(client, staff_c09)
    assert _post(client, sin, h).status_code == 403
    # 403 antes que 422: el cuerpo inválido tampoco cambia la respuesta.
    assert _post(client, sin, h, piezas={"99": {}}).status_code == 403
    assert _n_versiones(session_factory, sin) == 0


# --- Bordes --------------------------------------------------------------------------------


@pytest.mark.parametrize("pieza", ["10", "19", "49", "56", "86", "90"])
def test_codigos_fuera_de_rango_422(client, staff_c09, pid, pieza) -> None:  # type: ignore[no-untyped-def]
    r = _post(client, pid, _h(client, staff_c09), denticion="mixta", piezas={pieza: {}})
    assert r.status_code == 422


def test_actual_sin_odontograma_version_0(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = client.get(f"/api/pacientes/{pid}/odontograma/actual", headers=_h(client, staff_c09))
    assert r.status_code == 200
    assert r.json()["version"] == 0 and r.json()["piezas"] == {}


def test_historial_vacio_200_lista_vacia(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = client.get(f"/api/pacientes/{pid}/odontograma", headers=_h(client, staff_c09))
    assert r.status_code == 200 and r.json() == []


def test_historial_lo_lee_el_admin(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    ho = _h(client, staff_c09)
    for v in range(3):
        assert _post(client, pid, ho, v).status_code == 201
    r = client.get(f"/api/pacientes/{pid}/odontograma", headers=_h(client, staff_c09, "admin_solo"))
    assert [v["version"] for v in r.json()] == [3, 2, 1]


def test_lectura_tras_revocar_consentimiento(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    _post(client, pid, h, 0, piezas=CARIES_O)
    rec = bearer(client, "recepcion@test.test")
    assert (
        client.patch(
            f"/api/pacientes/{pid}", json={"consentimiento_datos": False}, headers=rec
        ).status_code
        == 200
    )
    assert _post(client, pid, h, 1).status_code == 403
    r = client.get(f"/api/pacientes/{pid}/odontograma/actual", headers=h)
    assert r.status_code == 200 and r.json()["version"] == 1


# --- Auditoría (3.3) -----------------------------------------------------------------------


def test_evento_actualizar_con_codigos_fdi_sin_estados_ni_caras(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid
) -> None:
    h = _h(client, staff_c09)
    _post(client, pid, h, 0, piezas={"16": {"caras": {"O": {"codigo": "caries"}}}})
    r2 = _post(
        client, pid, h, 1,
        piezas={
            "16": {"caras": {"O": {"codigo": "caries"}}},  # sin cambios
            "21": {"estado": {"codigo": "corona"}},  # nueva
        },
    )  # fmt: skip
    eventos = _eventos(session_factory, pid, entidad="odontograma", accion="actualizar")
    assert len(eventos) == 1
    ev = eventos[0]
    assert ev.entidad_id == r2.json()["id"] and ev.actor_usuario_id == staff_c09["o"]
    assert ev.diff == {"odontograma_id": r2.json()["id"], "version": 2, "campos": ["21"]}
    texto = str(ev.diff)
    assert "corona" not in texto and "caries" not in texto and "O" not in ev.diff["campos"]


def test_evento_crear_en_la_primera_version_lista_las_piezas(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid
) -> None:
    h = _h(client, staff_c09)
    _post(client, pid, h, 0, piezas={"21": {}, "16": {}})
    (ev,) = _eventos(session_factory, pid, entidad="odontograma", accion="crear")
    assert ev.diff["version"] == 1 and ev.diff["campos"] == ["16", "21", "denticion"]


def test_evento_leer_en_actual_e_historial(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    client.get(f"/api/pacientes/{pid}/odontograma/actual", headers=h)
    client.get(f"/api/pacientes/{pid}/odontograma", headers=h)
    leer = _eventos(session_factory, pid, entidad="odontograma", accion="leer")
    assert len(leer) == 2 and all(e.actor_usuario_id == staff_c09["o"] for e in leer)


def test_sin_evento_de_escritura_tras_403_409_422(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    _post(client, pid, h, 0)
    antes = len(_eventos(session_factory, pid, entidad="odontograma"))
    assert _post(client, pid, h, 0).status_code == 409
    assert _post(client, pid, h, 1, piezas={"55": {}}).status_code == 422
    assert _post(client, pid, _h(client, staff_c09, "admin_solo"), 1).status_code == 403
    assert len(_eventos(session_factory, pid, entidad="odontograma")) == antes


def test_falla_al_auditar_no_deja_version(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid, monkeypatch
) -> None:
    from app.domain.clinica import servicios

    def _falla(*a, **k):  # type: ignore[no-untyped-def]
        raise RuntimeError("falla de auditoría simulada")

    monkeypatch.setattr(servicios, "registrar_evento", _falla)
    h = _h(client, staff_c09)
    with pytest.raises(RuntimeError):
        _post(client, pid, h, 0, piezas=CARIES_O)
    assert _n_versiones(session_factory, pid) == 0
