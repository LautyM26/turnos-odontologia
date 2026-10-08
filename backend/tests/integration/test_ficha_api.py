"""Ficha de anamnesis versionada append-only (C-08 7.1-7.3)."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select

from app.domain.auditoria.models import AuditoriaHC
from app.domain.pacientes.models import FichaVersion
from tests.integration.conftest import alta_paciente, bearer, make_test_client


@pytest.fixture()
def paciente(client, auth_data):  # type: ignore[no-untyped-def]
    """Paciente de A CON consentimiento."""
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h).json()["id"]
    client.patch(f"/api/pacientes/{pid}", json={"consentimiento_datos": True}, headers=h)
    return pid


def _put(client, pid, h, version, **campos):  # type: ignore[no-untyped-def]
    return client.put(
        f"/api/pacientes/{pid}/ficha", json={"version_esperada": version, **campos}, headers=h
    )


def _versiones_db(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return session.scalar(
            select(func.count()).select_from(FichaVersion).where(FichaVersion.paciente_id == pid)
        )


def test_get_sin_versiones_devuelve_version_0(client, paciente) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    resp = client.get(f"/api/pacientes/{paciente}/ficha", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 0
    assert body["alergias"] is None and body["anamnesis"] is None


def test_put_crea_v1_y_v2_conservando_la_anterior(  # type: ignore[no-untyped-def]
    client, session_factory, paciente, auth_data
) -> None:
    h = bearer(client, "odonto@test.test")
    r1 = _put(client, paciente, h, 0, anamnesis="a1", alergias="sin datos")
    assert r1.status_code == 200, r1.text
    assert r1.json()["version"] == 1
    assert r1.json()["autor_usuario_id"] == auth_data["user_ids"]["odonto@test.test"]
    r2 = _put(client, paciente, h, 1, anamnesis="a1", alergias="polen sintetico")
    assert r2.status_code == 200 and r2.json()["version"] == 2
    vigente = client.get(f"/api/pacientes/{paciente}/ficha", headers=h).json()
    assert vigente["version"] == 2 and vigente["alergias"] == "polen sintetico"
    hist = client.get(f"/api/pacientes/{paciente}/ficha/versiones", headers=h).json()
    v1 = next(v for v in hist if v["version"] == 1)
    assert v1["alergias"] == "sin datos"


def test_put_con_version_vieja_409_sin_nueva_version(  # type: ignore[no-untyped-def]
    client, session_factory, paciente
) -> None:
    h = bearer(client, "odonto@test.test")
    _put(client, paciente, h, 0, alergias="x")
    _put(client, paciente, h, 1, alergias="y")
    assert _put(client, paciente, h, 1, alergias="z").status_code == 409
    assert _put(client, paciente, h, 5, alergias="z").status_code == 409
    assert _versiones_db(session_factory, paciente) == 2


def test_put_sin_consentimiento_403_sin_version(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data
) -> None:
    hr = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, hr).json()["id"]
    h = bearer(client, "odonto@test.test")
    resp = _put(client, pid, h, 0, alergias="x")
    assert resp.status_code == 403
    assert _versiones_db(session_factory, pid) == 0
    # tras revocar también se bloquea, sin borrar lo existente
    client.patch(f"/api/pacientes/{pid}", json={"consentimiento_datos": True}, headers=hr)
    assert _put(client, pid, h, 0, alergias="x").status_code == 200
    client.patch(f"/api/pacientes/{pid}", json={"consentimiento_datos": False}, headers=hr)
    assert _put(client, pid, h, 1, alergias="y").status_code == 403
    assert _versiones_db(session_factory, pid) == 1
    assert client.get(f"/api/pacientes/{pid}/ficha", headers=h).json()["version"] == 1


def test_put_campos_extra_422(client, paciente) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    assert _put(client, paciente, h, 0, autor_usuario_id=1).status_code == 422
    assert _put(client, paciente, h, -1).status_code == 422
    assert client.put(f"/api/pacientes/{paciente}/ficha", json={}, headers=h).status_code == 422


def test_put_concurrente_exactamente_uno_gana(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, paciente, auth_data
) -> None:
    clientes = [make_test_client(session_factory, monkeypatch) for _ in range(2)]
    headers = [bearer(c, "odonto@test.test") for c in clientes]
    _put(clientes[0], paciente, headers[0], 0, alergias="base")
    barrera = Barrier(2)

    def intento(i: int) -> int:
        barrera.wait()
        return _put(clientes[i], paciente, headers[i], 1, alergias=f"carrera {i}").status_code

    with ThreadPoolExecutor(2) as pool:
        codigos = sorted(pool.map(intento, range(2)))
    assert codigos == [200, 409]
    assert _versiones_db(session_factory, paciente) == 2


def test_historial_descendente_con_autor_y_fecha(client, paciente, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    for n in range(3):
        _put(client, paciente, h, n, alergias=f"v{n + 1}")
    resp = client.get(f"/api/pacientes/{paciente}/ficha/versiones", headers=h)
    assert resp.status_code == 200
    items = resp.json()
    assert [v["version"] for v in items] == [3, 2, 1]
    assert all(v["autor_usuario_id"] and v["created_at"] for v in items)


def test_auditoria_de_ficha_sin_texto_clinico(  # type: ignore[no-untyped-def]
    client, session_factory, paciente
) -> None:
    h = bearer(client, "odonto@test.test")
    secreto = "ALERGIA-SINTETICA-CONFIDENCIAL"
    _put(client, paciente, h, 0, alergias=secreto, anamnesis="CONTENIDO-X9")
    _put(client, paciente, h, 1, alergias="otra", anamnesis="CONTENIDO-X9")
    client.get(f"/api/pacientes/{paciente}/ficha", headers=h)
    client.get(f"/api/pacientes/{paciente}/ficha/versiones", headers=h)
    with session_factory() as session:
        eventos = list(
            session.scalars(
                select(AuditoriaHC)
                .where(AuditoriaHC.paciente_id == paciente, AuditoriaHC.entidad == "ficha")
                .order_by(AuditoriaHC.id)
            )
        )
    assert [e.accion for e in eventos] == ["crear", "actualizar", "leer", "leer"]
    assert eventos[0].diff == {"campos": ["alergias", "anamnesis"], "version": 1}
    assert eventos[1].diff == {"campos": ["alergias"], "version": 2}
    volcado = json.dumps([e.diff for e in eventos])
    assert secreto not in volcado and "otra" not in volcado and "X9" not in volcado
    assert all(e.actor_usuario_id for e in eventos)


def test_falla_al_auditar_no_deja_version(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, paciente
) -> None:
    from app.domain.pacientes import servicios

    def roto(*_a, **_k):  # type: ignore[no-untyped-def]
        raise RuntimeError("auditoria caida")

    c = make_test_client(session_factory, monkeypatch)
    h = bearer(c, "odonto@test.test")
    monkeypatch.setattr(servicios, "registrar_evento", roto)
    with pytest.raises(RuntimeError):
        _put(c, paciente, h, 0, alergias="x")
    assert _versiones_db(session_factory, paciente) == 0
