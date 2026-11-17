"""Consentimientos: generación, firma con constancia y lectura (C-18 3.1, 3.2, 3.4). PG16 real."""

import pytest
from sqlalchemy import select, text

from app.domain.auditoria.models import AuditoriaHC
from app.domain.cumplimiento.hashing import sha256_hex
from app.domain.cumplimiento.textos import CATALOGO
from tests.integration.conftest import bearer, nuevo_paciente_c09

DNI = "90000001"


@pytest.fixture()
def pid(session_factory, staff_c09) -> int:  # type: ignore[no-untyped-def]
    return nuevo_paciente_c09(session_factory, staff_c09["a"])


def _h(client, staff_c09, clave="o"):  # type: ignore[no-untyped-def]
    return bearer(client, staff_c09[f"{clave}_email"])


def _generar(client, pid, h, tipo="extraccion", **extra):  # type: ignore[no-untyped-def]
    return client.post(
        f"/api/pacientes/{pid}/consentimientos", json={"tipo": tipo, **extra}, headers=h
    )


def _firma_ok(texto_hash: str, **over):  # type: ignore[no-untyped-def]
    cuerpo = {"acepta": True, "firmante_nombre": "Firmante Sintetico", "firmante_dni": DNI,
              "texto_hash": texto_hash}  # fmt: skip
    cuerpo.update(over)
    return cuerpo


def _firmar(client, pid, cid, h, cuerpo, headers=None):  # type: ignore[no-untyped-def]
    return client.post(
        f"/api/pacientes/{pid}/consentimientos/{cid}/firmar", json=cuerpo, headers=headers or h
    )


def _eventos(session_factory, pid, **filtros):  # type: ignore[no-untyped-def]
    with session_factory() as s:
        stmt = select(AuditoriaHC).where(
            AuditoriaHC.paciente_id == pid, AuditoriaHC.entidad == "consentimiento"
        )
        for k, v in filtros.items():
            stmt = stmt.where(getattr(AuditoriaHC, k) == v)
        return list(s.scalars(stmt.order_by(AuditoriaHC.id)).all())


def _n_firmas(session_factory, cid) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            text("SELECT count(*) FROM consentimiento_firma WHERE consentimiento_id=:c"),
            {"c": cid},
        )


# --- 3.1 Generación ------------------------------------------------------------------------


def test_generar_201_pendiente_con_texto_hash_y_version_vigente(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = _generar(client, pid, _h(client, staff_c09))
    assert r.status_code == 201, r.text
    b = r.json()
    version, texto = CATALOGO["extraccion"]
    assert b["estado"] == "pendiente" and b["documento_bloqueado"] is False
    assert b["tipo"] == "extraccion" and b["texto"] == texto and b["texto_version"] == version
    assert b["texto_hash"] == sha256_hex(texto)  # recalculable por cualquiera
    assert b["autor_usuario_id"] == staff_c09["o"] and b["created_at"]
    assert b["constancia"] is None


def test_textos_distintos_dan_hashes_distintos(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    a = _generar(client, pid, h, "extraccion").json()
    b = _generar(client, pid, h, "implante").json()
    assert a["texto_hash"] != b["texto_hash"]


@pytest.mark.parametrize("tipo", ["inexistente", "", "EXTRACCION"])
def test_tipo_invalido_422_sin_crear(client, session_factory, staff_c09, pid, tipo) -> None:  # type: ignore[no-untyped-def]
    assert _generar(client, pid, _h(client, staff_c09), tipo).status_code == 422
    h = _h(client, staff_c09)
    assert client.get(f"/api/pacientes/{pid}/consentimientos", headers=h).json() == []


@pytest.mark.parametrize("extra", ["texto", "texto_hash", "fecha", "autor_usuario_id"])
def test_campos_de_servidor_en_el_cuerpo_422(client, staff_c09, pid, extra) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    assert _generar(client, pid, h, **{extra: "x"}).status_code == 422
    assert client.get(f"/api/pacientes/{pid}/consentimientos", headers=h).json() == []


def test_generar_audita_crear_sin_tipo_ni_texto(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    cid = _generar(client, pid, _h(client, staff_c09)).json()["id"]
    (ev,) = _eventos(session_factory, pid, accion="crear")
    assert ev.entidad_id == cid and ev.actor_usuario_id == staff_c09["o"]
    assert ev.diff == {"consentimiento_id": cid, "texto_version": "1.0"}
    assert "extraccion" not in str(ev.diff) and "Autorizo" not in str(ev.diff)


# --- 3.2 Firma -----------------------------------------------------------------------------


def test_firma_completa_201_con_constancia_y_documento_bloqueado(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid
) -> None:
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    r = _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"]),
                headers={**h, "User-Agent": "NavegadorSintetico/1.0"})  # fmt: skip
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["estado"] == "firmado" and b["documento_bloqueado"] is True
    c = b["constancia"]
    assert c["ip"] == "testclient" and c["dispositivo"] == "NavegadorSintetico/1.0"
    assert c["texto_hash"] == doc["texto_hash"] == sha256_hex(b["texto"])
    assert (c["firmante_nombre"], c["firmante_dni"]) == ("Firmante Sintetico", DNI)
    assert c["asistido_por_usuario_id"] == staff_c09["o"] and c["firmado_en"]
    assert c["firmado_en"] >= doc["created_at"]


def test_firma_sin_user_agent_guarda_no_informado(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    r = _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"]),
                headers={**h, "User-Agent": ""})  # fmt: skip
    assert r.status_code == 201
    assert r.json()["constancia"]["dispositivo"] == "no-informado"


def test_user_agent_largo_se_trunca_a_512(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    r = _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"]),
                headers={**h, "User-Agent": "U" * 900})  # fmt: skip
    assert r.status_code == 201
    assert r.json()["constancia"]["dispositivo"] == "U" * 512


@pytest.mark.parametrize(
    ("cambio", "faltantes"),
    [
        ({"acepta": False}, ["acepta"]),
        ({"acepta": None}, ["acepta"]),
        ({"firmante_nombre": ""}, ["firmante_nombre"]),
        ({"firmante_dni": "123456"}, ["firmante_dni"]),
        ({"firmante_dni": "123456789"}, ["firmante_dni"]),
        ({"acepta": False, "firmante_nombre": "  ", "firmante_dni": "1"},
         ["acepta", "firmante_nombre", "firmante_dni"]),
    ],
)  # fmt: skip
def test_firma_incompleta_422_reintentable_sin_constancia_ni_evento(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid, cambio, faltantes
) -> None:
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    r = _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"], **cambio))
    assert r.status_code == 422
    assert r.json()["reintentable"] is True and r.json()["faltantes"] == faltantes
    assert _n_firmas(session_factory, doc["id"]) == 0
    assert _eventos(session_factory, pid, accion="firmar") == []
    detalle = client.get(f"/api/pacientes/{pid}/consentimientos/{doc['id']}", headers=h).json()
    assert detalle["estado"] == "pendiente" and detalle["documento_bloqueado"] is False


def test_sin_acepta_en_el_cuerpo_tambien_es_reintentable(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    r = _firmar(client, pid, doc["id"], h, {"texto_hash": doc["texto_hash"]})
    assert r.status_code == 422 and r.json()["reintentable"] is True
    assert set(r.json()["faltantes"]) == {"acepta", "firmante_nombre", "firmante_dni"}


def test_reintento_exitoso_deja_una_sola_constancia(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid
) -> None:
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    assert _firmar(client, pid, doc["id"], h,
                   _firma_ok(doc["texto_hash"], acepta=False)).status_code == 422  # fmt: skip
    assert _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"])).status_code == 201
    assert _n_firmas(session_factory, doc["id"]) == 1


def test_hash_distinto_409_y_sigue_pendiente(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    r = _firmar(client, pid, doc["id"], h, _firma_ok(sha256_hex(doc["texto"] + " ")))
    assert r.status_code == 409
    assert _n_firmas(session_factory, doc["id"]) == 0
    assert client.get(f"/api/pacientes/{pid}/consentimientos/{doc['id']}",
                      headers=h).json()["estado"] == "pendiente"  # fmt: skip


def test_segunda_firma_409_y_constancia_intacta(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    primera = _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"])).json()
    r = _firmar(client, pid, doc["id"], h,
                _firma_ok(doc["texto_hash"], firmante_nombre="Otro Firmante"))  # fmt: skip
    assert r.status_code == 409
    assert _n_firmas(session_factory, doc["id"]) == 1
    detalle = client.get(f"/api/pacientes/{pid}/consentimientos/{doc['id']}", headers=h).json()
    assert detalle["constancia"] == primera["constancia"]


@pytest.mark.parametrize("extra", ["ip", "fecha", "dispositivo"])
def test_firma_con_ip_fecha_o_dispositivo_en_el_cuerpo_422(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid, extra
) -> None:
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    r = _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"], **{extra: "x"}))
    assert r.status_code == 422 and "reintentable" not in r.json()
    assert _n_firmas(session_factory, doc["id"]) == 0


def test_firmar_audita_sin_datos_del_firmante(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"]))
    (ev,) = _eventos(session_factory, pid, accion="firmar")
    assert ev.entidad_id == doc["id"] and ev.actor_usuario_id == staff_c09["o"]
    assert ev.diff == {"consentimiento_id": doc["id"], "texto_version": "1.0"}
    assert ev.ip == "testclient"
    assert "Firmante" not in str(ev.diff) and DNI not in str(ev.diff)


def test_falla_al_auditar_la_firma_revierte_la_constancia(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid, monkeypatch
) -> None:
    from app.domain.cumplimiento import servicios

    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    original = servicios.registrar_evento

    def roto(*a, **k):  # type: ignore[no-untyped-def]
        if a[2] == "firmar":
            raise RuntimeError("auditoria caida")
        return original(*a, **k)

    monkeypatch.setattr(servicios, "registrar_evento", roto)
    with pytest.raises(RuntimeError):
        _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"]))
    assert _n_firmas(session_factory, doc["id"]) == 0


# --- 3.4 Lectura ---------------------------------------------------------------------------


def test_listado_mas_reciente_primero_con_estados(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    firmado = _generar(client, pid, h, "extraccion").json()
    _firmar(client, pid, firmado["id"], h, _firma_ok(firmado["texto_hash"]))
    pendiente = _generar(client, pid, h, "implante").json()
    ha = bearer(client, staff_c09["admin_solo_email"])
    r = client.get(f"/api/pacientes/{pid}/consentimientos", headers=ha)
    assert r.status_code == 200
    lista = r.json()
    assert [c["id"] for c in lista] == [pendiente["id"], firmado["id"]]
    assert [(c["estado"], c["documento_bloqueado"]) for c in lista] == [
        ("pendiente", False), ("firmado", True),
    ]  # fmt: skip
    assert lista[1]["constancia"]["firmante_dni"] == DNI and lista[0]["constancia"] is None


def test_detalle_con_constancia_y_hash_recalculable(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"]))
    d = client.get(f"/api/pacientes/{pid}/consentimientos/{doc['id']}", headers=h).json()
    assert sha256_hex(d["texto"]) == d["texto_hash"] == d["constancia"]["texto_hash"]


def test_paciente_sin_consentimientos_lista_vacia(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = client.get(f"/api/pacientes/{pid}/consentimientos", headers=_h(client, staff_c09))
    assert r.status_code == 200 and r.json() == []


def test_cid_de_otro_paciente_404(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    otro = nuevo_paciente_c09(session_factory, staff_c09["a"])
    doc = _generar(client, otro, h).json()
    assert client.get(f"/api/pacientes/{pid}/consentimientos/{doc['id']}",
                      headers=h).status_code == 404  # fmt: skip
    assert _firmar(client, pid, doc["id"], h, _firma_ok(doc["texto_hash"])).status_code == 404
    assert _n_firmas(session_factory, doc["id"]) == 0


def test_cid_inexistente_404(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    assert client.get(f"/api/pacientes/{pid}/consentimientos/999999",
                      headers=_h(client, staff_c09)).status_code == 404  # fmt: skip


def test_cada_lectura_deja_un_evento_leer(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    assert _eventos(session_factory, pid, accion="leer") == []
    client.get(f"/api/pacientes/{pid}/consentimientos", headers=h)
    client.get(f"/api/pacientes/{pid}/consentimientos/{doc['id']}", headers=h)
    leer = _eventos(session_factory, pid, accion="leer")
    assert len(leer) == 2
    assert leer[1].entidad_id == doc["id"] and leer[1].diff == {"consentimiento_id": doc["id"]}


@pytest.mark.parametrize("metodo", ["PUT", "PATCH", "DELETE"])
def test_metodos_de_edicion_405_y_documento_intacto(client, staff_c09, pid, metodo) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    doc = _generar(client, pid, h).json()
    r = client.request(metodo, f"/api/pacientes/{pid}/consentimientos/{doc['id']}",
                       json={"texto": "x"}, headers=h)  # fmt: skip
    assert r.status_code == 405
    d = client.get(f"/api/pacientes/{pid}/consentimientos/{doc['id']}", headers=h).json()
    assert d["texto"] == doc["texto"]


def test_ninguna_ruta_de_consentimientos_expone_put_patch_delete(client) -> None:  # type: ignore[no-untyped-def]
    # app.routes no lista las rutas de routers incluidos en esta versión de Starlette:
    # se usa el esquema OpenAPI (gotcha de C-09).
    rutas = {p: m for p, m in client.app.openapi()["paths"].items() if "consentimientos" in p}
    assert len(rutas) == 3  # lista/alta, detalle y firmar
    for ruta, metodos in rutas.items():
        assert not ({"put", "patch", "delete"} & set(metodos)), ruta


def test_el_esquema_de_firma_no_expone_campos_de_servidor(client) -> None:  # type: ignore[no-untyped-def]
    props = client.app.openapi()["components"]["schemas"]["FirmaIn"]["properties"]
    assert set(props) == {"acepta", "firmante_nombre", "firmante_dni", "texto_hash"}
