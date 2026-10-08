"""E2E por tenant de pacientes + ficha + adjuntos + auditoría (C-08 10.1). PG16 real."""

from sqlalchemy import func, select

from app.domain.core.models import Usuario
from tests.integration.conftest import bearer, dni_sintetico

PDF = b"%PDF-1.4\n" + b"sintetico" * 30


def test_flujo_completo_y_aislamiento(client, session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        usuarios_antes = s.scalar(select(func.count()).select_from(Usuario))

    # Recepción: alta sin Usuario nuevo + consentimiento.
    hr = bearer(client, "recepcion@test.test")
    alta = client.post(
        "/api/pacientes",
        json={
            "nombre": "Paciente",
            "apellido": "Sintetico",
            "dni": dni_sintetico(),
            "telefono": "011 15 5555-0001",
        },
        headers=hr,
    )
    assert alta.status_code == 201
    pid = alta.json()["id"]
    assert alta.json()["telefono"] == "+5491155550001"
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Usuario)) == usuarios_antes
    assert (
        client.patch(
            f"/api/pacientes/{pid}", json={"consentimiento_datos": True}, headers=hr
        ).status_code
        == 200
    )
    # Recepción no ve lo clínico.
    assert client.get(f"/api/pacientes/{pid}/ficha", headers=hr).status_code == 403

    # Odontólogo: ficha v1/v2, adjunto, descarga.
    ho = bearer(client, "odonto@test.test")
    f1 = client.put(
        f"/api/pacientes/{pid}/ficha", json={"version_esperada": 0, "alergias": "a"}, headers=ho
    )
    f2 = client.put(
        f"/api/pacientes/{pid}/ficha", json={"version_esperada": 1, "alergias": "b"}, headers=ho
    )
    assert (f1.json()["version"], f2.json()["version"]) == (1, 2)
    up = client.post(
        f"/api/pacientes/{pid}/adjuntos",
        files={"file": ("estudio.pdf", PDF, "application/pdf")},
        headers=ho,
    )
    assert up.status_code == 201
    dl = client.get(f"/api/pacientes/{pid}/adjuntos/{up.json()['id']}/contenido", headers=ho)
    assert dl.status_code == 200 and dl.content == PDF

    # Admin: la auditoría muestra la secuencia completa (descendente).
    hadmin = bearer(client, auth_data["admin_email"])
    eventos = client.get(f"/api/pacientes/{pid}/auditoria", headers=hadmin).json()["items"]
    secuencia = [(e["accion"], e["entidad"]) for e in reversed(eventos)]
    assert secuencia == [
        ("crear", "paciente"),
        ("consentimiento_otorgado", "paciente"),
        ("crear", "ficha"),
        ("actualizar", "ficha"),
        ("crear", "adjunto"),
        ("descargar", "adjunto"),
    ]
    assert all(e["actor_usuario_id"] for e in eventos)

    # Clínica B no ve nada de A.
    hb = bearer(client, "admin-b@test.test")
    for url in (
        f"/api/pacientes/{pid}",
        f"/api/pacientes/{pid}/ficha",
        f"/api/pacientes/{pid}/auditoria",
        f"/api/pacientes/{pid}/adjuntos",
    ):
        assert client.get(url, headers=hb).status_code == 404, url
    assert client.get("/api/pacientes", params={"q": "sintetico"}, headers=hb).json()["items"] == []
