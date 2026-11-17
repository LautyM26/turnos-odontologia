"""La exportación de A no contiene nada de B (C-18 5.3, regla dura 10). PG16 real."""

import csv
import io
import zipfile
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.infrastructure.settings import get_settings
from app.infrastructure.storage.adjuntos import LocalDirStorage
from tests.integration.conftest import (
    bearer,
    evolucion_sintetica,
    paciente_sintetico,
    receta_sintetica,
)
from tests.integration.test_exportacion_api import CSVS

NOMBRE_B = "ZzUnicoDeLaClinicaB"
PNG_B = b"\x89PNG\r\n\x1a\n" + b"contenido-b" * 20


@pytest.fixture()
def datos_b(session_factory, auth_data, turnos_data, catalogo_data):  # type: ignore[no-untyped-def]
    """Datos de B (paciente, adjunto con archivo, consentimiento) y algo de A."""
    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    admin_b = auth_data["user_ids"]["admin-b@test.test"]
    with session_factory() as s:
        pac_b = paciente_sintetico(b, nombre=NOMBRE_B)
        pac_a = paciente_sintetico(a)
        s.add_all([pac_a, pac_b])
        s.flush()
        clave = f"{b}/{pac_b.id}/{uuid4().hex}"
        adj_id = s.execute(
            text(
                "INSERT INTO adjunto (clinica_id, paciente_id, tipo, mime, tamano_bytes, sha256, "
                "storage_key, subido_por) VALUES (:c, :p, 'foto', 'image/png', :t, :h, :k, :u) "
                "RETURNING id"
            ),
            {"c": b, "p": pac_b.id, "t": len(PNG_B), "h": "b" * 64, "k": clave, "u": admin_b},
        ).scalar()
        cons_id = s.execute(
            text(
                "INSERT INTO consentimiento (clinica_id, paciente_id, tipo, texto, texto_version, "
                "texto_hash, autor_usuario_id) VALUES (:c, :p, 'extraccion', 'T', '1.0', :h, :u) "
                "RETURNING id"
            ),
            {"c": b, "p": pac_b.id, "h": "b" * 64, "u": admin_b},
        ).scalar()
        s.commit()
        pac_a_id = pac_a.id
        out = {"a": a, "b": b, "pac_b": pac_b.id, "dni_b": pac_b.dni, "adj_b": adj_id,
               "cons_b": cons_id}  # fmt: skip
    LocalDirStorage(get_settings().adjuntos_storage_dir).guardar(clave, [PNG_B])
    # C-19: una receta en cada clínica (la de B no puede salir en la exportación de A).
    for clinica, pac, autor, prof in (
        (b, out["pac_b"], admin_b, catalogo_data["prof_b"]),
        (a, pac_a_id, auth_data["user_ids"]["odonto@test.test"], catalogo_data["prof_p"]),
    ):
        evo = evolucion_sintetica(session_factory, clinica, pac, autor, prof)
        out[f"receta_{'b' if clinica == b else 'a'}"] = receta_sintetica(
            session_factory, clinica, pac, evo, autor, prof
        )
    return out


def test_la_exportacion_de_a_no_contiene_nada_de_b(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data, datos_b
) -> None:
    r = client.get("/api/admin/exportacion?formato=csv",
                   headers=bearer(client, auth_data["admin_email"]))  # fmt: skip
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    todo = b"".join(zf.read(n) for n in zf.namelist()).decode("utf-8", errors="ignore")
    assert NOMBRE_B not in todo and datos_b["dni_b"] not in todo
    assert PNG_B not in b"".join(zf.read(n) for n in zf.namelist())
    assert not [n for n in zf.namelist() if n == f"adjuntos/{datos_b['adj_b']}.png"]
    recetas = list(csv.reader(io.StringIO(zf.read("recetas.csv").decode("utf-8-sig"), newline="")))
    ids = {f[recetas[0].index("id")] for f in recetas[1:]}
    assert str(datos_b["receta_a"]) in ids and str(datos_b["receta_b"]) not in ids
    for nombre, tabla in CSVS.items():
        filas = list(csv.reader(io.StringIO(zf.read(f"{nombre}.csv").decode("utf-8-sig"),
                                            newline="")))  # fmt: skip
        enc = filas[0]
        if "id" in enc:
            with session_factory() as s:
                filas_b = s.execute(
                    text(f"SELECT id FROM {tabla} WHERE clinica_id=:c"),  # noqa: S608
                    {"c": auth_data["clinica_b"]},
                ).all()
            ids_b = {str(i) for (i,) in filas_b}
        if "id" in enc:
            ids_csv = {f[enc.index("id")] for f in filas[1:]}
            assert ids_csv.isdisjoint(ids_b), nombre
        if "clinica_id" in enc:
            assert {f[enc.index("clinica_id")] for f in filas[1:]} <= {str(auth_data["clinica_a"])}


def test_la_exportacion_de_b_no_contiene_nada_de_a(client, auth_data, datos_b) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/admin/exportacion?formato=csv",
                   headers=bearer(client, "admin-b@test.test"))  # fmt: skip
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    pacientes = zf.read("pacientes.csv").decode("utf-8-sig")
    assert NOMBRE_B in pacientes
    usuarios = zf.read("usuarios.csv").decode("utf-8-sig")
    assert "admin-b@test.test" in usuarios and "recepcion@test.test" not in usuarios
    assert zf.read(f"adjuntos/{datos_b['adj_b']}.png") == PNG_B
