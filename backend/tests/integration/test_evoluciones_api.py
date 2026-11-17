"""Evoluciones clínicas append-only con autor y correcciones (C-09 4.1-4.4). PG16 real."""

import pytest
from sqlalchemy import func, select

from app.api.deps import AuthContext  # noqa: F401  (documenta el contrato del JWT)
from app.domain.auditoria.models import AuditoriaHC
from app.domain.clinica.models import Evolucion
from tests.integration.conftest import bearer, nuevo_paciente_c09


@pytest.fixture()
def pid(session_factory, staff_c09) -> int:  # type: ignore[no-untyped-def]
    return nuevo_paciente_c09(session_factory, staff_c09["a"])


def _h(client, staff_c09, clave="o"):  # type: ignore[no-untyped-def]
    return bearer(client, staff_c09[f"{clave}_email"])


def _post(client, pid, h, **cuerpo):  # type: ignore[no-untyped-def]
    cuerpo.setdefault("texto", "Control sintetico")
    return client.post(f"/api/pacientes/{pid}/evoluciones", json=cuerpo, headers=h)


def _n(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            select(func.count()).select_from(Evolucion).where(Evolucion.paciente_id == pid)
        )


def _eventos(session_factory, pid: int, **filtros):  # type: ignore[no-untyped-def]
    with session_factory() as s:
        stmt = select(AuditoriaHC).where(AuditoriaHC.paciente_id == pid)
        for k, v in filtros.items():
            stmt = stmt.where(getattr(AuditoriaHC, k) == v)
        return list(s.scalars(stmt.order_by(AuditoriaHC.id)).all())


# --- 4.1 Alta ------------------------------------------------------------------------------


def test_alta_201_con_autor_profesional_y_hora_del_servidor(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = _post(client, pid, _h(client, staff_c09), texto="Control sintético", pieza_fdi=16)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["texto"] == "Control sintético" and b["pieza_fdi"] == 16
    assert b["autor_usuario_id"] == staff_c09["o"]
    assert b["profesional_id"] == staff_c09["prof_o"]
    assert b["fecha_hora"] and b["corrige_a_id"] is None and b["corregida_por_id"] is None


def test_autor_distinto_para_otro_odontologo(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = _post(client, pid, _h(client, staff_c09, "p"))
    assert r.status_code == 201
    assert (r.json()["autor_usuario_id"], r.json()["profesional_id"]) == (
        staff_c09["p"], staff_c09["prof_p"],
    )  # fmt: skip


@pytest.mark.parametrize("texto", ["", "   "])
def test_texto_vacio_422(client, session_factory, staff_c09, pid, texto) -> None:  # type: ignore[no-untyped-def]
    assert _post(client, pid, _h(client, staff_c09), texto=texto).status_code == 422
    assert _n(session_factory, pid) == 0


def test_pieza_fdi_19_422(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    assert _post(client, pid, _h(client, staff_c09), pieza_fdi=19).status_code == 422
    assert _n(session_factory, pid) == 0


def test_odontologo_sin_profesional_422_sin_fila(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = _post(client, pid, _h(client, staff_c09, "sin_prof"))
    assert r.status_code == 422
    assert "profesional" in r.json()["detail"].lower()
    assert _n(session_factory, pid) == 0
    assert _eventos(session_factory, pid, entidad="evolucion") == []


@pytest.mark.parametrize("campo", ["autor_usuario_id", "profesional_id", "fecha_hora"])
def test_autor_o_fecha_en_el_cuerpo_422(client, session_factory, staff_c09, pid, campo) -> None:  # type: ignore[no-untyped-def]
    valor = "2020-01-01T00:00:00Z" if campo == "fecha_hora" else 1
    assert _post(client, pid, _h(client, staff_c09), **{campo: valor}).status_code == 422
    assert _n(session_factory, pid) == 0


def test_sin_consentimiento_403_antes_de_validar(client, session_factory, staff_c09) -> None:  # type: ignore[no-untyped-def]
    sin = nuevo_paciente_c09(session_factory, staff_c09["a"], consentimiento=False)
    h = _h(client, staff_c09)
    assert _post(client, sin, h).status_code == 403
    assert _post(client, sin, h, texto="").status_code == 403
    assert _n(session_factory, sin) == 0


def test_lectura_tras_revocacion_200(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    _post(client, pid, h)
    rec = bearer(client, "recepcion@test.test")
    client.patch(f"/api/pacientes/{pid}", json={"consentimiento_datos": False}, headers=rec)
    assert _post(client, pid, h).status_code == 403
    r = client.get(f"/api/pacientes/{pid}/evoluciones", headers=h)
    assert r.status_code == 200 and len(r.json()["items"]) == 1


def test_auditoria_de_alta_sin_texto(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = _post(client, pid, _h(client, staff_c09), texto="Texto clinico sintetico secreto")
    (ev,) = _eventos(session_factory, pid, entidad="evolucion", accion="crear")
    assert ev.entidad_id == r.json()["id"] and ev.actor_usuario_id == staff_c09["o"]
    assert ev.diff == {"evolucion_id": r.json()["id"]}
    assert "secreto" not in str(ev.diff)


def test_sin_evento_de_escritura_tras_403_422(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    _post(client, pid, _h(client, staff_c09, "sin_prof"))
    _post(client, pid, _h(client, staff_c09), texto="")
    _post(client, pid, _h(client, staff_c09, "admin_solo"))
    assert _eventos(session_factory, pid, entidad="evolucion") == []


def test_falla_al_auditar_no_deja_evolucion(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid, monkeypatch
) -> None:
    from app.domain.clinica import servicios

    def roto(*_a, **_k):  # type: ignore[no-untyped-def]
        raise RuntimeError("auditoria caida")

    monkeypatch.setattr(servicios, "registrar_evento", roto)
    with pytest.raises(RuntimeError):
        _post(client, pid, _h(client, staff_c09))
    assert _n(session_factory, pid) == 0


# --- 4.2 Correcciones ----------------------------------------------------------------------


def _corregir(client, pid, h, original, **over):  # type: ignore[no-untyped-def]
    cuerpo = {
        "texto": "Texto corregido sintetico", "corrige_a_id": original,
        "motivo_correccion": "Pieza mal indicada",
    }  # fmt: skip
    cuerpo.update(over)
    return client.post(f"/api/pacientes/{pid}/evoluciones", json=cuerpo, headers=h)


def test_autor_corrige_original_intacta_y_corregida_por(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    e1 = _post(client, pid, h, texto="Texto original", pieza_fdi=16).json()
    r = _corregir(client, pid, h, e1["id"])
    assert r.status_code == 201, r.text
    e2 = r.json()
    assert e2["corrige_a_id"] == e1["id"] and e2["motivo_correccion"] == "Pieza mal indicada"
    original = client.get(f"/api/pacientes/{pid}/evoluciones/{e1['id']}", headers=h).json()
    assert original["texto"] == "Texto original" and original["corregida_por_id"] == e2["id"]


def test_auditoria_de_correccion_sin_texto_ni_motivo(
    client, session_factory, staff_c09, pid
) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    e1 = _post(client, pid, h).json()
    e2 = _corregir(client, pid, h, e1["id"], motivo_correccion="Motivo clinico secreto").json()
    (ev,) = _eventos(session_factory, pid, entidad="evolucion", accion="corregir")
    assert ev.entidad_id == e2["id"]
    assert ev.diff == {"evolucion_id": e2["id"], "corrige_a_id": e1["id"]}
    assert "secreto" not in str(ev.diff)


def test_correccion_sin_motivo_o_motivo_sin_correccion_422(
    client, session_factory, staff_c09, pid
) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    e1 = _post(client, pid, h).json()
    sin_motivo = client.post(
        f"/api/pacientes/{pid}/evoluciones",
        json={"texto": "x", "corrige_a_id": e1["id"]}, headers=h,
    )  # fmt: skip
    assert sin_motivo.status_code == 422
    assert _post(client, pid, h, motivo_correccion="solo motivo").status_code == 422
    assert _n(session_factory, pid) == 1


def test_otro_odontologo_intenta_corregir_403(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    e1 = _post(client, pid, _h(client, staff_c09)).json()
    r = _corregir(client, pid, _h(client, staff_c09, "p"), e1["id"])
    assert r.status_code == 403
    assert _n(session_factory, pid) == 1
    # Puede agregar una evolución nueva propia, sin corrige_a_id.
    assert _post(client, pid, _h(client, staff_c09, "p")).status_code == 201


def test_corregir_evolucion_de_otro_paciente_o_clinica_422(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid
) -> None:
    h = _h(client, staff_c09)
    otro = nuevo_paciente_c09(session_factory, staff_c09["a"])
    e_otro = _post(client, otro, h).json()
    assert _corregir(client, pid, h, e_otro["id"]).status_code == 422
    assert _corregir(client, pid, h, 99_999_999).status_code == 422
    # De otra clínica: se crea una evolución en B por SQL directo (datos sintéticos).
    from sqlalchemy import text

    with session_factory() as s:
        prof_b = s.execute(
            text("SELECT id FROM profesional WHERE clinica_id=:b LIMIT 1"), {"b": staff_c09["b"]}
        ).scalar()
        usr_b = s.execute(
            text("SELECT id FROM usuario WHERE clinica_id=:b LIMIT 1"), {"b": staff_c09["b"]}
        ).scalar()
        if prof_b is None:
            prof_b = s.execute(
                text(
                    "INSERT INTO profesional (clinica_id, nombre, matricula) "
                    "VALUES (:b, 'Prof B C09', 'C09-B') RETURNING id"
                ),
                {"b": staff_c09["b"]},
            ).scalar()
        e_b = s.execute(
            text(
                "INSERT INTO evolucion (clinica_id, paciente_id, autor_usuario_id, "
                "profesional_id, texto) VALUES (:b, :p, :u, :prof, 'x') RETURNING id"
            ),
            {"b": staff_c09["b"], "p": staff_c09["pac_b"], "u": usr_b, "prof": prof_b},
        ).scalar()
        s.commit()
    assert _corregir(client, pid, h, e_b).status_code == 422
    assert _n(session_factory, pid) == 0


def test_corregir_ya_corregida_409_nombra_la_vigente_y_corregir_la_vigente_201(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid
) -> None:
    h = _h(client, staff_c09)
    e1 = _post(client, pid, h).json()
    e2 = _corregir(client, pid, h, e1["id"]).json()
    r = _corregir(client, pid, h, e1["id"])
    assert r.status_code == 409
    assert r.json()["evolucion_vigente_id"] == e2["id"] and str(e2["id"]) in r.json()["detail"]
    assert _n(session_factory, pid) == 2
    r3 = _corregir(client, pid, h, e2["id"])
    assert r3.status_code == 201 and r3.json()["corrige_a_id"] == e2["id"]


# --- 4.3 Sin edición ni borrado ------------------------------------------------------------


@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
def test_metodos_de_escritura_405_sin_cambios(
    client, session_factory, staff_c09, pid, metodo
) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    e1 = _post(client, pid, h, texto="Original").json()
    f = getattr(client, metodo)
    kwargs = {"headers": h} if metodo == "delete" else {"headers": h, "json": {"texto": "x"}}
    assert f(f"/api/pacientes/{pid}/evoluciones/{e1['id']}", **kwargs).status_code == 405
    assert f(f"/api/pacientes/{pid}/evoluciones", **kwargs).status_code == 405
    assert f(f"/api/pacientes/{pid}/odontograma", **kwargs).status_code == 405
    assert _n(session_factory, pid) == 1
    assert (
        client.get(f"/api/pacientes/{pid}/evoluciones/{e1['id']}", headers=h).json()["texto"]
        == "Original"
    )


def test_ninguna_ruta_de_odontograma_o_evoluciones_expone_put_patch_delete(client) -> None:  # type: ignore[no-untyped-def]
    paths = client.app.openapi()["paths"]
    rutas = {r: ops for r, ops in paths.items() if "/odontograma" in r or "/evoluciones" in r}
    assert len(rutas) == 4  # no vacío: odontograma, actual, evoluciones, evoluciones/{id}
    for ruta, ops in rutas.items():
        assert set(ops) <= {"get", "post"}, ruta
        assert not ({"put", "patch", "delete"} & set(ops)), ruta
    # y la lista de las 7 rutas de C-09 está completa
    total = sum(len(ops) for r, ops in paths.items() if r.endswith(("/historia",)) or r in rutas)
    assert total == 7


# --- 4.4 Orden y paginación ----------------------------------------------------------------


def test_orden_descendente_con_corregida_por_id(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    e1 = _post(client, pid, h, texto="E1").json()
    e2 = _post(client, pid, h, texto="E2").json()
    e3 = _corregir(client, pid, h, e1["id"], texto="E3").json()
    items = client.get(f"/api/pacientes/{pid}/evoluciones", headers=h).json()["items"]
    assert [i["id"] for i in items] == [e3["id"], e2["id"], e1["id"]]
    assert items[2]["corregida_por_id"] == e3["id"] and items[0]["corrige_a_id"] == e1["id"]


def test_paginacion_sin_repetidos(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    ids = [_post(client, pid, h, texto=f"E{i}").json()["id"] for i in range(3)]
    p1 = client.get(f"/api/pacientes/{pid}/evoluciones?limit=2", headers=h).json()
    assert [i["id"] for i in p1["items"]] == [ids[2], ids[1]] and p1["next_cursor"]
    p2 = client.get(
        f"/api/pacientes/{pid}/evoluciones?limit=2&after_id={p1['next_cursor']}", headers=h
    ).json()
    assert [i["id"] for i in p2["items"]] == [ids[0]] and p2["next_cursor"] is None


@pytest.mark.parametrize("limit", [0, 201])
def test_limit_fuera_de_rango_422(client, staff_c09, pid, limit) -> None:  # type: ignore[no-untyped-def]
    r = client.get(f"/api/pacientes/{pid}/evoluciones?limit={limit}", headers=_h(client, staff_c09))
    assert r.status_code == 422


def test_evolucion_de_otro_paciente_por_id_404(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    otro = nuevo_paciente_c09(session_factory, staff_c09["a"])
    e_otro = _post(client, otro, h).json()
    assert (
        client.get(f"/api/pacientes/{pid}/evoluciones/{e_otro['id']}", headers=h).status_code == 404
    )
    assert client.get(f"/api/pacientes/{pid}/evoluciones/999999999", headers=h).status_code == 404


def test_auditoria_de_lecturas_listado_y_una(client, session_factory, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    e1 = _post(client, pid, h).json()
    client.get(f"/api/pacientes/{pid}/evoluciones", headers=h)
    client.get(f"/api/pacientes/{pid}/evoluciones/{e1['id']}", headers=h)
    leer = _eventos(session_factory, pid, entidad="evolucion", accion="leer")
    assert sorted(e.entidad_id for e in leer) == sorted([pid, e1["id"]])
    assert all(e.actor_usuario_id == staff_c09["o"] for e in leer)
