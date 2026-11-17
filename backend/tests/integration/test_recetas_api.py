"""Emisión y lectura de recetas / órdenes vía partner simulado (C-19 3.1-3.4, 3.6). PG16 real."""

import logging
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.domain.auditoria.models import AuditoriaHC
from app.infrastructure.recetas.partner_client import PartnerNoDisponible, PartnerRechazo
from tests.integration.conftest import (
    bearer,
    evolucion_sintetica,
    nuevo_paciente_c09,
)

MED = {
    "nombre_generico": "amoxicilina",
    "presentacion": "comprimidos 500 mg",
    "cantidad": 1,
    "posologia": "1 cada 8 horas por 7 dias",
}
EST = {"estudio": "Radiografia panoramica", "indicacion": "Control sintetico"}


@pytest.fixture()
def pid(session_factory, staff_c09) -> int:  # type: ignore[no-untyped-def]
    return nuevo_paciente_c09(session_factory, staff_c09["a"])


@pytest.fixture()
def evo(session_factory, staff_c09, pid) -> int:  # type: ignore[no-untyped-def]
    return evolucion_sintetica(
        session_factory, staff_c09["a"], pid, staff_c09["o"], staff_c09["prof_o"]
    )


def _h(client, staff_c09, clave="o"):  # type: ignore[no-untyped-def]
    return bearer(client, staff_c09[f"{clave}_email"])


def _cuerpo(evo: int, **over):  # type: ignore[no-untyped-def]
    base = {
        "tipo": "receta", "evolucion_id": evo, "diagnostico": "Infeccion sintetica",
        "items": [MED], "clave_idempotencia": str(uuid4()),
    }  # fmt: skip
    return {**base, **over}


def _emitir(client, pid, h, cuerpo):  # type: ignore[no-untyped-def]
    return client.post(f"/api/pacientes/{pid}/recetas", json=cuerpo, headers=h)


def _n(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    from app.domain.recetas.models import RecetaExterna

    with session_factory() as s:
        return s.scalar(
            select(func.count()).select_from(RecetaExterna).where(RecetaExterna.paciente_id == pid)
        )


def _eventos(session_factory, pid: int, **filtros):  # type: ignore[no-untyped-def]
    with session_factory() as s:
        stmt = select(AuditoriaHC).where(
            AuditoriaHC.paciente_id == pid, AuditoriaHC.entidad == "receta"
        )
        for k, v in filtros.items():
            stmt = stmt.where(getattr(AuditoriaHC, k) == v)
        return list(s.scalars(stmt.order_by(AuditoriaHC.id)).all())


# --- 3.1 Emisión feliz ----------------------------------------------------------------------


def test_receta_201_simulada_con_datos_del_servidor(
    client_recetas, fake_partner, staff_c09, pid, evo
) -> None:  # type: ignore[no-untyped-def]
    r = _emitir(client_recetas, pid, _h(client_recetas, staff_c09), _cuerpo(evo))
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["id_externo"].startswith("FAKE-") and b["simulada"] is True and b["partner"] == "fake"
    assert b["pdf_url"].startswith("https://partner-simulado.invalid/")
    assert b["evolucion_id"] == evo and b["tipo"] == "receta" and b["emitida_en"]
    assert b["autor_usuario_id"] == staff_c09["o"] and b["profesional_id"] == staff_c09["prof_o"]
    assert b["items"] == [MED]


def test_partner_recibe_datos_de_la_base_no_del_cuerpo(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, session_factory, staff_c09, pid, evo
) -> None:
    from app.domain.pacientes.models import Paciente

    with session_factory() as s:
        p = s.get(Paciente, pid)
        p.obra_social_nombre, p.obra_social_plan, p.nro_afiliado = "OS Sintetica", "Plan 1", "A-1"
        s.commit()
        dni = p.dni
    assert (
        _emitir(client_recetas, pid, _h(client_recetas, staff_c09), _cuerpo(evo)).status_code == 201
    )
    (sol,) = fake_partner.solicitudes
    assert sol.paciente_dni == dni and sol.obra_social_nombre == "OS Sintetica"
    assert sol.nro_afiliado == "A-1" and sol.profesional_matricula == "C09-o"
    assert sol.profesional_nombre == "Profesional C09 o" and sol.tipo == "receta"


def test_orden_de_estudio_201(client_recetas, staff_c09, pid, evo) -> None:  # type: ignore[no-untyped-def]
    r = _emitir(client_recetas, pid, _h(client_recetas, staff_c09),
                _cuerpo(evo, tipo="orden_estudio", items=[EST]))  # fmt: skip
    assert r.status_code == 201 and r.json()["tipo"] == "orden_estudio"


def test_paciente_sin_obra_social_201_particular(
    client_recetas, fake_partner, staff_c09, pid, evo
) -> None:  # type: ignore[no-untyped-def]
    assert (
        _emitir(client_recetas, pid, _h(client_recetas, staff_c09), _cuerpo(evo)).status_code == 201
    )
    assert fake_partner.solicitudes[0].obra_social_nombre is None


def test_evento_crear_sin_items_ni_diagnostico(
    client_recetas, session_factory, staff_c09, pid, evo
) -> None:  # type: ignore[no-untyped-def]
    r = _emitir(client_recetas, pid, _h(client_recetas, staff_c09), _cuerpo(evo)).json()
    (ev,) = _eventos(session_factory, pid, accion="crear")
    assert ev.entidad_id == r["id"] and ev.actor_usuario_id == staff_c09["o"]
    assert ev.diff == {"receta_id": r["id"], "evolucion_id": evo, "partner": "fake"}
    assert "amoxicilina" not in str(ev.diff) and r["id_externo"] not in str(ev.diff)


# --- 3.2 Reglas de negocio ------------------------------------------------------------------


def test_odontologo_sin_profesional_422_sin_llamar_al_partner(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, session_factory, staff_c09, pid, evo
) -> None:
    r = _emitir(client_recetas, pid, _h(client_recetas, staff_c09, "sin_prof"), _cuerpo(evo))
    assert r.status_code == 422 and "profesional" in r.json()["detail"].lower()
    assert fake_partner.solicitudes == [] and _n(session_factory, pid) == 0


def test_evolucion_inexistente_o_de_otro_paciente_422(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, session_factory, staff_c09, pid
) -> None:
    otro = nuevo_paciente_c09(session_factory, staff_c09["a"])
    evo_otro = evolucion_sintetica(
        session_factory, staff_c09["a"], otro, staff_c09["o"], staff_c09["prof_o"]
    )
    h = _h(client_recetas, staff_c09)
    for evo_id in (999_999_999, evo_otro):
        assert _emitir(client_recetas, pid, h, _cuerpo(evo_id)).status_code == 422
    assert fake_partner.solicitudes == [] and _n(session_factory, pid) == 0


def test_evolucion_de_otro_odontologo_422_evolucion_propia(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, session_factory, staff_c09, pid
) -> None:
    ajena = evolucion_sintetica(
        session_factory, staff_c09["a"], pid, staff_c09["p"], staff_c09["prof_p"]
    )
    r = _emitir(client_recetas, pid, _h(client_recetas, staff_c09), _cuerpo(ajena))
    assert r.status_code == 422 and "propia" in r.json()["detail"]
    assert fake_partner.solicitudes == [] and _n(session_factory, pid) == 0


def test_evolucion_propia_corregida_201(
    client_recetas, session_factory, staff_c09, pid, evo
) -> None:  # type: ignore[no-untyped-def]
    h = _h(client_recetas, staff_c09)
    corr = client_recetas.post(
        f"/api/pacientes/{pid}/evoluciones",
        json={"texto": "Corregida sintetica", "corrige_a_id": evo, "motivo_correccion": "Error"},
        headers=h,
    )
    assert corr.status_code == 201, corr.text
    assert _emitir(client_recetas, pid, h, _cuerpo(evo)).status_code == 201


@pytest.mark.parametrize(
    "cambio",
    [{"items": []}, {"items": [MED] * 11}, {"diagnostico": ""}, {"tipo": "orden_estudio"},
     {"clave_idempotencia": "no-uuid"}, {"id_externo": "FAKE-1"}, {"partner": "x"},
     {"pdf_url": "https://x"}, {"simulada": False}, {"autor_usuario_id": 1},
     {"fecha": "2020-01-01"}],
)  # fmt: skip
def test_cuerpo_invalido_422_sin_llamar_al_partner(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, session_factory, staff_c09, pid, evo, cambio
) -> None:
    r = _emitir(client_recetas, pid, _h(client_recetas, staff_c09), _cuerpo(evo, **cambio))
    assert r.status_code == 422
    assert fake_partner.solicitudes == [] and _n(session_factory, pid) == 0


# --- 3.3 Partner ----------------------------------------------------------------------------


def _sin_override(client, monkeypatch, partner: str, entorno: str = "desarrollo"):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("RECETAS_PARTNER", partner)
    monkeypatch.setenv("ENTORNO", entorno)
    return client


def test_sin_partner_501_nombra_variable_y_sin_filas(  # type: ignore[no-untyped-def]
    client, monkeypatch, session_factory, staff_c09, pid, evo
) -> None:
    _sin_override(client, monkeypatch, "")
    r = _emitir(client, pid, _h(client, staff_c09), _cuerpo(evo))
    assert r.status_code == 501 and "RECETAS_PARTNER" in r.json()["detail"]
    assert _n(session_factory, pid) == 0 and _eventos(session_factory, pid) == []


def test_fake_en_produccion_501(client, monkeypatch, session_factory, staff_c09, pid, evo) -> None:  # type: ignore[no-untyped-def]
    _sin_override(client, monkeypatch, "fake", "produccion")
    r = _emitir(client, pid, _h(client, staff_c09), _cuerpo(evo))
    assert r.status_code == 501 and "producción" in r.json()["detail"]
    assert _n(session_factory, pid) == 0


def test_501_viene_antes_que_el_422_del_cuerpo(client, monkeypatch, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    _sin_override(client, monkeypatch, "")
    assert _emitir(client, pid, _h(client, staff_c09), {"basura": 1}).status_code == 501


def test_get_sin_partner_200(client, monkeypatch, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    _sin_override(client, monkeypatch, "")
    r = client.get(f"/api/pacientes/{pid}/recetas", headers=_h(client, staff_c09))
    assert r.status_code == 200 and r.json()["items"] == []


def test_partner_caido_502_reintentable_sin_fila_ni_evento(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, session_factory, staff_c09, pid, evo
) -> None:
    fake_partner.fallar_con(PartnerNoDisponible("timeout"))
    r = _emitir(client_recetas, pid, _h(client_recetas, staff_c09), _cuerpo(evo))
    assert r.status_code == 502 and r.json()["reintentable"] is True
    assert _n(session_factory, pid) == 0 and _eventos(session_factory, pid) == []


def test_partner_rechaza_422_con_credencial_enmascarada(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, monkeypatch, caplog, session_factory, staff_c09, pid, evo
) -> None:
    monkeypatch.setenv("RECETAS_PARTNER_KEY", "clave-sintetica-zzz-987")
    fake_partner.fallar_con(PartnerRechazo("rechazo: header clave-sintetica-zzz-987 invalido"))
    with caplog.at_level(logging.DEBUG):
        r = _emitir(client_recetas, pid, _h(client_recetas, staff_c09), _cuerpo(evo))
    assert r.status_code == 422
    assert "clave-sintetica-zzz-987" not in r.text and "***" in r.json()["detail"]
    assert "clave-sintetica-zzz-987" not in caplog.text
    assert _n(session_factory, pid) == 0


# --- 3.4 Idempotencia -----------------------------------------------------------------------


def test_misma_clave_y_contenido_200_misma_receta_una_emision(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, session_factory, staff_c09, pid, evo
) -> None:
    h, cuerpo = _h(client_recetas, staff_c09), _cuerpo(evo)
    a, b = _emitir(client_recetas, pid, h, cuerpo), _emitir(client_recetas, pid, h, cuerpo)
    assert (a.status_code, b.status_code) == (201, 200)
    assert a.json()["id"] == b.json()["id"]
    assert _n(session_factory, pid) == 1 and len(_eventos(session_factory, pid)) == 1
    assert len(fake_partner.solicitudes) == 1


def test_misma_clave_otro_contenido_409_sin_emitir(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, session_factory, staff_c09, pid, evo
) -> None:
    h, cuerpo = _h(client_recetas, staff_c09), _cuerpo(evo)
    _emitir(client_recetas, pid, h, cuerpo)
    r = _emitir(client_recetas, pid, h, {**cuerpo, "items": [{**MED, "cantidad": 3}]})
    assert r.status_code == 409
    assert _n(session_factory, pid) == 1 and len(fake_partner.solicitudes) == 1


def test_claves_distintas_dos_recetas(client_recetas, session_factory, staff_c09, pid, evo) -> None:  # type: ignore[no-untyped-def]
    h = _h(client_recetas, staff_c09)
    a, b = (_emitir(client_recetas, pid, h, _cuerpo(evo)) for _ in range(2))
    assert (a.status_code, b.status_code) == (201, 201) and a.json()["id"] != b.json()["id"]


def test_falla_al_auditar_no_deja_receta(  # type: ignore[no-untyped-def]
    client_recetas, session_factory, staff_c09, pid, evo, monkeypatch
) -> None:
    from app.domain.recetas import servicios

    def roto(*_a, **_k):  # type: ignore[no-untyped-def]
        raise RuntimeError("auditoria caida")

    monkeypatch.setattr(servicios, "registrar_evento", roto)
    with pytest.raises(RuntimeError):
        _emitir(client_recetas, pid, _h(client_recetas, staff_c09), _cuerpo(evo))
    assert _n(session_factory, pid) == 0


# --- 3.6 Lectura ----------------------------------------------------------------------------


def test_listado_mas_reciente_primero_con_enlaces_y_evento_leer(  # type: ignore[no-untyped-def]
    client_recetas, session_factory, staff_c09, pid, evo
) -> None:
    h = _h(client_recetas, staff_c09)
    ids = [_emitir(client_recetas, pid, h, _cuerpo(evo)).json()["id"] for _ in range(3)]
    r = client_recetas.get(f"/api/pacientes/{pid}/recetas", headers=h)
    assert r.status_code == 200
    assert [i["id"] for i in r.json()["items"]] == sorted(ids, reverse=True)
    assert all(i["pdf_url"].startswith("https://") for i in r.json()["items"])
    assert len(_eventos(session_factory, pid, accion="leer")) == 1


def test_listado_paginado_por_cursor(client_recetas, staff_c09, pid, evo) -> None:  # type: ignore[no-untyped-def]
    h = _h(client_recetas, staff_c09)
    for _ in range(3):
        _emitir(client_recetas, pid, h, _cuerpo(evo))
    p1 = client_recetas.get(f"/api/pacientes/{pid}/recetas?limit=2", headers=h).json()
    p2 = client_recetas.get(
        f"/api/pacientes/{pid}/recetas?limit=2&after_id={p1['next_cursor']}", headers=h
    ).json()
    assert len(p1["items"]) == 2 and len(p2["items"]) == 1 and p2["next_cursor"] is None


def test_detalle_y_rid_de_otro_paciente_404(
    client_recetas, session_factory, staff_c09, pid, evo
) -> None:  # type: ignore[no-untyped-def]
    h = _h(client_recetas, staff_c09)
    rid = _emitir(client_recetas, pid, h, _cuerpo(evo)).json()["id"]
    ok = client_recetas.get(f"/api/pacientes/{pid}/recetas/{rid}", headers=h)
    assert ok.status_code == 200 and ok.json()["id"] == rid
    otro = nuevo_paciente_c09(session_factory, staff_c09["a"])
    assert client_recetas.get(f"/api/pacientes/{otro}/recetas/{rid}", headers=h).status_code == 404
    assert (
        client_recetas.get(f"/api/pacientes/{pid}/recetas/999999999", headers=h).status_code == 404
    )


def test_paciente_sin_recetas_lista_vacia(client_recetas, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = client_recetas.get(f"/api/pacientes/{pid}/recetas", headers=_h(client_recetas, staff_c09))
    assert r.status_code == 200 and r.json() == {"items": [], "next_cursor": None}


@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
def test_metodos_de_edicion_405(client_recetas, staff_c09, pid, evo, metodo) -> None:  # type: ignore[no-untyped-def]
    h = _h(client_recetas, staff_c09)
    rid = _emitir(client_recetas, pid, h, _cuerpo(evo)).json()["id"]
    for url in (f"/api/pacientes/{pid}/recetas", f"/api/pacientes/{pid}/recetas/{rid}"):
        assert getattr(client_recetas, metodo)(url, headers=h).status_code == 405


def test_openapi_sin_put_patch_delete_en_recetas(client_recetas) -> None:  # type: ignore[no-untyped-def]
    paths = client_recetas.app.openapi()["paths"]
    rutas = {p: m for p, m in paths.items() if "/recetas" in p}
    assert len(rutas) == 2
    for metodos in rutas.values():
        assert not {"put", "patch", "delete"} & set(metodos)
    cuerpo = str(paths["/api/pacientes/{paciente_id}/recetas"]["post"])
    assert "id_externo" not in cuerpo.split("responses")[0]
