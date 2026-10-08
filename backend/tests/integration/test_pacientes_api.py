"""API administrativa de pacientes (C-08 5.3/5.4): alta, lectura, edición, consentimiento."""

from sqlalchemy import select

from app.domain.auditoria.models import AuditoriaHC
from tests.integration.conftest import alta_paciente, bearer, dni_sintetico


def _eventos(session_factory, paciente_id: int):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return list(
            session.scalars(
                select(AuditoriaHC)
                .where(AuditoriaHC.paciente_id == paciente_id)
                .order_by(AuditoriaHC.id)
            )
        )


def test_alta_201_normaliza_y_defaults(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    resp = alta_paciente(
        client, h, dni="90.123.456", telefono="011 15 5555-0001", email="Ana@Example.com"
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["dni"] == "90123456"
    assert body["telefono"] == "+5491155550001"
    assert body["email"] == "ana@example.com"
    assert body["riesgo_ausencia"] == 0
    assert body["consentimiento_datos"] is False


def test_alta_duplicada_409_con_paciente_id(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    dni = dni_sintetico()
    primero = alta_paciente(client, h, dni=dni).json()
    resp = alta_paciente(client, h, dni=f"{dni[:2]}.{dni[2:5]}.{dni[5:]}")
    assert resp.status_code == 409
    assert resp.json()["paciente_id"] == primero["id"]


def test_alta_422_extra_y_sin_contacto(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    for extra in ({"riesgo_ausencia": 5}, {"clinica_id": 1}, {"campo_raro": "x"}):
        assert alta_paciente(client, h, **extra).status_code == 422
    sin_contacto = {"nombre": "A", "apellido": "B", "dni": dni_sintetico()}
    assert client.post("/api/pacientes", json=sin_contacto, headers=h).status_code == 422


def test_get_y_patch_normalizan_y_auditan_solo_campos(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data
) -> None:
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h).json()["id"]
    assert client.get(f"/api/pacientes/{pid}", headers=h).status_code == 200
    resp = client.patch(
        f"/api/pacientes/{pid}", json={"telefono": "011 15 5555-0009", "nro_afiliado": " 77 "},
        headers=h,
    )  # fmt: skip
    assert resp.status_code == 200, resp.text
    assert resp.json()["telefono"] == "+5491155550009"
    assert resp.json()["nro_afiliado"] == "77"
    eventos = [e for e in _eventos(session_factory, pid) if e.accion == "actualizar"]
    assert len(eventos) == 1
    assert eventos[0].diff == {"campos": ["nro_afiliado", "telefono"]}
    assert "5555" not in str(eventos[0].diff)


def test_patch_recalcula_busqueda_y_rechaza_dni_duplicado(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    a = alta_paciente(client, h).json()
    b = alta_paciente(client, h).json()
    resp = client.patch(f"/api/pacientes/{b['id']}", json={"dni": a["dni"]}, headers=h)
    assert resp.status_code == 409
    assert resp.json()["paciente_id"] == a["id"]
    ok = client.patch(f"/api/pacientes/{b['id']}", json={"apellido": "Ñandú"}, headers=h)
    assert ok.status_code == 200 and ok.json()["apellido"] == "Ñandú"


def test_patch_no_puede_quitar_todo_contacto(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h).json()["id"]  # solo teléfono
    resp = client.patch(f"/api/pacientes/{pid}", json={"telefono": None}, headers=h)
    assert resp.status_code == 422


def test_patch_riesgo_ausencia_422(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h).json()["id"]
    resp = client.patch(f"/api/pacientes/{pid}", json={"riesgo_ausencia": 90}, headers=h)
    assert resp.status_code == 422
    assert client.get(f"/api/pacientes/{pid}", headers=h).json()["riesgo_ausencia"] == 0


def test_otra_clinica_404_y_delete_405(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    ha = bearer(client, "recepcion@test.test")
    hb = bearer(client, "admin-b@test.test")
    pid = alta_paciente(client, ha).json()["id"]
    assert client.get(f"/api/pacientes/{pid}", headers=hb).status_code == 404
    ajeno = client.patch(f"/api/pacientes/{pid}", json={"nombre": "X"}, headers=hb)
    assert ajeno.status_code == 404
    assert client.delete(f"/api/pacientes/{pid}", headers=ha).status_code == 405
    assert client.get(f"/api/pacientes/{pid}", headers=ha).status_code == 200


def test_consentimiento_otorgar_setea_fecha_y_usuario_y_audita(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data
) -> None:
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h).json()["id"]
    resp = client.patch(f"/api/pacientes/{pid}", json={"consentimiento_datos": True}, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["consentimiento_datos"] is True
    assert body["consentimiento_datos_at"] is not None
    assert body["consentimiento_datos_por"] == auth_data["user_ids"]["recepcion@test.test"]
    ev = [e for e in _eventos(session_factory, pid) if e.accion == "consentimiento_otorgado"]
    assert len(ev) == 1 and ev[0].diff == {"consentimiento_datos": True}


def test_consentimiento_revocar_audita_y_conserva_datos(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data
) -> None:
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h).json()["id"]
    client.patch(f"/api/pacientes/{pid}", json={"consentimiento_datos": True}, headers=h)
    resp = client.patch(f"/api/pacientes/{pid}", json={"consentimiento_datos": False}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["consentimiento_datos"] is False
    assert resp.json()["telefono"] == "+5491155550001"
    acciones = [e.accion for e in _eventos(session_factory, pid)]
    assert acciones.count("consentimiento_otorgado") == 1
    assert acciones.count("consentimiento_revocado") == 1


def test_consentimiento_sin_cambio_no_duplica_evento(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data
) -> None:
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h).json()["id"]
    for _ in range(2):
        client.patch(f"/api/pacientes/{pid}", json={"consentimiento_datos": True}, headers=h)
    acciones = [e.accion for e in _eventos(session_factory, pid)]
    assert acciones.count("consentimiento_otorgado") == 1
