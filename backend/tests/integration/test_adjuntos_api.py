"""Adjuntos clínicos: subida validada, listado y descarga segura (C-08 8.3/8.4)."""

import hashlib

import pytest
from sqlalchemy import func, select

from app.domain.auditoria.models import AuditoriaHC
from app.domain.pacientes.models import Adjunto
from tests.integration.conftest import alta_paciente, bearer, make_test_client

JPEG = b"\xff\xd8\xff\xe0" + b"sintetico" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"sintetico" * 20
PDF = b"%PDF-1.4\n" + b"sintetico" * 20
EXE = b"MZ\x90\x00" + b"sintetico" * 20
GIF = b"GIF89a" + b"sintetico" * 20


@pytest.fixture()
def paciente(client, auth_data):  # type: ignore[no-untyped-def]
    """Paciente de A CON consentimiento."""
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h).json()["id"]
    client.patch(f"/api/pacientes/{pid}", json={"consentimiento_datos": True}, headers=h)
    return pid


def _subir(client, pid, h, contenido, nombre="foto.jpg", tipo="image/jpeg", **data):  # type: ignore[no-untyped-def]
    return client.post(
        f"/api/pacientes/{pid}/adjuntos",
        files={"file": (nombre, contenido, tipo)},
        data=data or None,
        headers=h,
    )


def _archivos(tmp_path) -> list:  # type: ignore[no-untyped-def]
    raiz = tmp_path / "adjuntos"
    return [p for p in raiz.rglob("*") if p.is_file()] if raiz.exists() else []


def _filas(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return session.scalar(
            select(func.count()).select_from(Adjunto).where(Adjunto.paciente_id == pid)
        )


def test_jpeg_valido_201_con_metadatos_y_evento_sin_nombre(  # type: ignore[no-untyped-def]
    client, session_factory, paciente, tmp_path, auth_data
) -> None:
    h = bearer(client, "odonto@test.test")
    resp = _subir(client, paciente, h, JPEG, nombre="intraoral-secreta.jpg")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["tipo"], body["mime"], body["tamano_bytes"]) == ("foto", "image/jpeg", len(JPEG))
    assert body["sha256"] == hashlib.sha256(JPEG).hexdigest()
    assert body["subido_por"] == auth_data["user_ids"]["odonto@test.test"]
    assert len(_archivos(tmp_path)) == 1
    with session_factory() as session:
        ev = session.scalars(
            select(AuditoriaHC).where(
                AuditoriaHC.paciente_id == paciente, AuditoriaHC.entidad == "adjunto"
            )
        ).one()
    assert (ev.accion, ev.diff) == ("crear", {"adjunto_id": body["id"]})
    assert "secreta" not in str(ev.diff)


@pytest.mark.parametrize(
    ("contenido", "nombre", "tipo"),
    [
        (EXE, "radiografia.pdf", "application/pdf"),  # ejecutable renombrado
        (GIF, "x.gif", "image/gif"),
        (GIF, "x.png", "image/png"),
        (PDF, "x.pdf", "image/png"),  # content-type no coincide
        (b"PK\x03\x04" + b"x" * 50, "x.docx", "application/octet-stream"),
    ],
)
def test_tipos_no_permitidos_415_sin_archivo_ni_fila(  # type: ignore[no-untyped-def]
    client, session_factory, paciente, tmp_path, contenido, nombre, tipo
) -> None:
    h = bearer(client, "odonto@test.test")
    assert _subir(client, paciente, h, contenido, nombre, tipo).status_code == 415
    assert _archivos(tmp_path) == []
    assert _filas(session_factory, paciente) == 0


def test_png_y_pdf_validos(client, paciente) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    assert _subir(client, paciente, h, PNG, "a.png", "image/png").json()["tipo"] == "foto"
    assert _subir(client, paciente, h, PDF, "a.pdf", "application/pdf").json()["tipo"] == "pdf"


def test_tamano_maximo_413_y_limite_exacto_ok(  # type: ignore[no-untyped-def]
    client, session_factory, paciente, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ADJUNTO_MAX_BYTES", "1024")
    h = bearer(client, "odonto@test.test")
    exacto = PDF + b"\x00" * (1024 - len(PDF))
    assert _subir(client, paciente, h, exacto, "a.pdf", "application/pdf").status_code == 201
    exceso = PDF + b"\x00" * (1025 - len(PDF))
    assert _subir(client, paciente, h, exceso, "b.pdf", "application/pdf").status_code == 413
    assert len(_archivos(tmp_path)) == 1
    assert _filas(session_factory, paciente) == 1


def test_archivo_vacio_422(client, paciente, tmp_path) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    assert _subir(client, paciente, h, b"").status_code == 422
    assert _archivos(tmp_path) == []


def test_evolucion_id_o_campo_extra_422(client, paciente, tmp_path) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    assert _subir(client, paciente, h, JPEG, evolucion_id="5").status_code == 422
    assert _subir(client, paciente, h, JPEG, otro="x").status_code == 422
    assert _archivos(tmp_path) == []


def test_sin_consentimiento_403_sin_archivo(client, auth_data, tmp_path) -> None:  # type: ignore[no-untyped-def]
    pid = alta_paciente(client, bearer(client, "recepcion@test.test")).json()["id"]
    h = bearer(client, "odonto@test.test")
    assert _subir(client, pid, h, JPEG).status_code == 403
    assert _archivos(tmp_path) == []


def test_nombre_malicioso_queda_dentro_del_root(client, paciente, tmp_path) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    resp = _subir(client, paciente, h, PNG, "../../etc/passwd.png", "image/png")
    assert resp.status_code == 201
    archivos = _archivos(tmp_path)
    assert len(archivos) == 1
    assert archivos[0].resolve().is_relative_to((tmp_path / "adjuntos").resolve())
    assert "passwd" not in str(archivos[0])
    assert not (tmp_path / "etc").exists()


def test_falla_de_db_deja_el_storage_sin_el_archivo(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, paciente, tmp_path
) -> None:
    from app.domain.pacientes import servicios

    c = make_test_client(session_factory, monkeypatch)
    h = bearer(c, "odonto@test.test")

    def roto(*_a, **_k):  # type: ignore[no-untyped-def]
        raise RuntimeError("db caida")

    monkeypatch.setattr(servicios, "registrar_evento", roto)
    with pytest.raises(RuntimeError):
        _subir(c, paciente, h, JPEG)
    assert _archivos(tmp_path) == []
    assert _filas(session_factory, paciente) == 0


def test_listado_de_metadatos_solo_del_paciente_y_tenant(  # type: ignore[no-untyped-def]
    client, paciente, auth_data
) -> None:
    h = bearer(client, "odonto@test.test")
    a = _subir(client, paciente, h, JPEG).json()["id"]
    otro = alta_paciente(client, bearer(client, "recepcion@test.test")).json()["id"]
    client.patch(
        f"/api/pacientes/{otro}",
        json={"consentimiento_datos": True},
        headers=bearer(client, "recepcion@test.test"),
    )
    _subir(client, otro, h, PNG, "o.png", "image/png")
    lista = client.get(f"/api/pacientes/{paciente}/adjuntos", headers=h)
    assert lista.status_code == 200
    assert [x["id"] for x in lista.json()] == [a]
    hb = bearer(client, "admin-b@test.test")
    assert client.get(f"/api/pacientes/{paciente}/adjuntos", headers=hb).status_code == 404


def test_descarga_con_headers_seguros_y_evento(  # type: ignore[no-untyped-def]
    client, session_factory, paciente
) -> None:
    h = bearer(client, "odonto@test.test")
    adj = _subir(client, paciente, h, PDF, "estudio.pdf", "application/pdf").json()
    resp = client.get(f"/api/pacientes/{paciente}/adjuntos/{adj['id']}/contenido", headers=h)
    assert resp.status_code == 200
    assert resp.content == PDF
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.headers["content-disposition"].startswith("attachment")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"] == "no-store"
    with session_factory() as session:
        acciones = list(
            session.scalars(
                select(AuditoriaHC.accion).where(
                    AuditoriaHC.paciente_id == paciente, AuditoriaHC.entidad == "adjunto"
                )
            )
        )
    assert acciones == ["crear", "descargar"]


def test_descarga_admin_ok_y_recepcion_403(client, paciente, auth_data) -> None:  # type: ignore[no-untyped-def]
    adj = _subir(client, paciente, bearer(client, "odonto@test.test"), JPEG).json()
    url = f"/api/pacientes/{paciente}/adjuntos/{adj['id']}/contenido"
    assert client.get(url, headers=bearer(client, auth_data["admin_email"])).status_code == 200
    assert client.get(url, headers=bearer(client, "recepcion@test.test")).status_code == 403


def test_adjunto_de_otra_clinica_o_paciente_404(  # type: ignore[no-untyped-def]
    client, paciente, auth_data
) -> None:
    h = bearer(client, "odonto@test.test")
    adj = _subir(client, paciente, h, JPEG).json()
    hb = bearer(client, "admin-b@test.test")
    assert (
        client.get(f"/api/pacientes/{paciente}/adjuntos/{adj['id']}/contenido", headers=hb)
    ).status_code == 404
    hr = bearer(client, "recepcion@test.test")
    otro = alta_paciente(client, hr).json()["id"]
    cruzado = client.get(f"/api/pacientes/{otro}/adjuntos/{adj['id']}/contenido", headers=h)
    assert cruzado.status_code == 404
    inexistente = client.get(f"/api/pacientes/{paciente}/adjuntos/999999/contenido", headers=h)
    assert inexistente.status_code == 404
