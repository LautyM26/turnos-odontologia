"""Exportación completa del tenant en ZIP de CSV (C-18 5.1, 5.2, 5.4). PG16 real, sintéticos."""

import csv
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import select, text

from app.domain.agenda.turnos import Turno, TurnoTransicion
from app.domain.auditoria.models import AuditoriaAdmin
from app.domain.core.models import Clinica
from tests.integration.conftest import (
    BACKEND_DIR,
    bearer,
    crear_usuario,
    nuevo_paciente_c09,
    paciente_sintetico,
    receta_sintetica,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"sintetico" * 20

#: CSV -> tabla (las 17 entidades de D5 + recetas de C-19 + WhatsApp de C-15).
CSVS = {
    "pacientes": "paciente", "fichas": "ficha_version", "adjuntos": "adjunto",
    "odontogramas": "odontograma", "evoluciones": "evolucion",
    "consentimientos": "consentimiento", "consentimiento_firmas": "consentimiento_firma",
    "turnos": "turno", "turno_transiciones": "turno_transicion",
    "profesionales": "profesional", "sillones": "sillon_recurso", "prestaciones": "prestacion",
    "profesional_sillones": "profesional_sillon", "bloqueos": "bloqueo",
    "usuarios": "usuario", "usuario_roles": "usuario_rol", "auditoria_hc": "auditoria_hc",
    "recetas": "receta_externa",
    "mensajes_whatsapp": "mensaje_whatsapp", "whatsapp_sesiones": "whatsapp_sesion",
    "lista_espera": "lista_espera", "ofertas_lista_espera": "oferta_lista_espera",
    "conversaciones_whatsapp": "conversacion_wa",
}  # fmt: skip


def _leer_zip(resp) -> zipfile.ZipFile:  # type: ignore[no-untyped-def]
    return zipfile.ZipFile(io.BytesIO(resp.content))


def _filas(zf: zipfile.ZipFile, nombre: str) -> list[list[str]]:
    texto = zf.read(f"{nombre}.csv").decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto, newline="")))


def _exportar(client, h, formato="csv"):  # type: ignore[no-untyped-def]
    return client.get(f"/api/admin/exportacion?formato={formato}", headers=h)


@pytest.fixture(scope="module")
def seed(session_factory, auth_data, turnos_data, staff_c09):  # type: ignore[no-untyped-def]
    """Clínica A con una historia completa; la B ya trae paciente y catálogo del fixture."""
    a = auth_data["clinica_a"]
    out = {"a": a, "b": auth_data["clinica_b"]}
    with session_factory() as s:
        malo = paciente_sintetico(a, nombre="=CMD()", apellido="Formula, \"Peña\"",
                                  consentimiento_datos=True)  # fmt: skip
        malo.consentimiento_datos_at = datetime.now(UTC)
        s.add(malo)
        s.flush()
        out["pac_formula"] = malo.id
        inicio = datetime(2032, 3, 1, 10, tzinfo=UTC)
        turno = Turno(
            clinica_id=a, profesional_id=turnos_data["p"], sillon_id=turnos_data["s1"],
            paciente_id=turnos_data["pac_a"], prestacion_id=turnos_data["prest_a"],
            duracion_min=30, inicio=inicio, fin=inicio + timedelta(minutes=30),
        )  # fmt: skip
        s.add(turno)
        s.flush()
        s.add(TurnoTransicion(
            clinica_id=a, turno_id=turno.id, desde="reservado", hacia="confirmado",
            actor_usuario_id=staff_c09["o"],
        ))  # fmt: skip
        s.commit()
    return out


@pytest.fixture()
def historia(client, session_factory, staff_c09):  # type: ignore[no-untyped-def]
    """Ficha, adjunto, odontograma, evolución y consentimiento firmado del paciente con datos."""
    cli, pid = client, nuevo_paciente_c09(session_factory, staff_c09["a"])
    h = bearer(cli, staff_c09["o_email"])
    ficha = cli.put(
        f"/api/pacientes/{pid}/ficha",
        json={"version_esperada": 0, "alergias": "Ninguna sintetica"},
        headers=h,
    )
    assert ficha.status_code == 200
    adj = cli.post(
        f"/api/pacientes/{pid}/adjuntos", headers=h, files={"file": ("foto.png", PNG, "image/png")}
    )
    assert adj.status_code == 201, adj.text
    odonto = {"version_esperada": 0, "denticion": "permanente",
              "piezas": {"16": {"estado": {"codigo": "corona"}}}}  # fmt: skip
    assert cli.post(f"/api/pacientes/{pid}/odontograma", json=odonto, headers=h).status_code == 201
    evo = cli.post(
        f"/api/pacientes/{pid}/evoluciones", json={"texto": "Control sintetico"}, headers=h
    )
    assert evo.status_code == 201
    receta_sintetica(session_factory, staff_c09["a"], pid, evo.json()["id"], staff_c09["o"],
                     staff_c09["prof_o"])  # fmt: skip
    base = f"/api/pacientes/{pid}/consentimientos"
    doc = cli.post(base, json={"tipo": "extraccion"}, headers=h).json()
    firma = {"acepta": True, "firmante_nombre": "Firmante Sintetico", "firmante_dni": "90000001",
             "texto_hash": doc["texto_hash"]}  # fmt: skip
    r = cli.post(f"{base}/{doc['id']}/firmar", json=firma, headers=h)
    assert r.status_code == 201
    return {"pid": pid, "adjunto": adj.json()}


def _conteo_db(session_factory, tabla: str, clinica: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            text(f"SELECT count(*) FROM {tabla} WHERE clinica_id=:c"), {"c": clinica}  # noqa: S608
        )


def _n_eventos(session_factory, accion="exportar") -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return len(list(s.scalars(select(AuditoriaAdmin).where(AuditoriaAdmin.accion == accion))))


# --- 5.1 Exportación completa --------------------------------------------------------------


def test_exportacion_200_zip_con_un_csv_por_entidad_y_conteos_de_la_db(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data, seed, historia
) -> None:
    r = _exportar(client, bearer(client, auth_data["admin_email"]))
    assert r.status_code == 200, r.text[:200]
    assert r.headers["content-type"] == "application/zip"
    assert r.headers["content-disposition"].startswith("attachment;")
    assert f"exportacion-clinica-{seed['a']}-" in r.headers["content-disposition"]
    zf = _leer_zip(r)
    assert zf.testzip() is None
    manifest = json.loads(zf.read("manifest.json"))
    for nombre, tabla in CSVS.items():
        filas = _filas(zf, nombre)
        esperado = _conteo_db(session_factory, tabla, seed["a"])
        assert len(filas) - 1 == esperado, nombre
        assert manifest["conteos"][nombre] == esperado, nombre
    # Las entidades sembradas tienen filas reales (no es una exportación vacía).
    for nombre in ("pacientes", "fichas", "adjuntos", "odontogramas", "evoluciones",
                   "consentimientos", "consentimiento_firmas", "turnos", "turno_transiciones",
                   "usuarios", "auditoria_hc", "recetas"):  # fmt: skip
        assert manifest["conteos"][nombre] >= 1, nombre


def test_manifest_con_clinica_fecha_con_zona_esquema_y_excluidas(  # type: ignore[no-untyped-def]
    client, auth_data, seed, historia
) -> None:
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    m = json.loads(zf.read("manifest.json"))
    assert m["clinica_id"] == seed["a"] and m["formato"] == "csv"
    assert datetime.fromisoformat(m["generado_en"]).utcoffset() is not None
    assert m["version_esquema"] == ScriptDirectory(str(BACKEND_DIR / "alembic")).get_current_head()
    assert {e["entidad"] for e in m["excluidas"]} == {"caja", "facturas"}
    assert all(e["motivo"] for e in m["excluidas"])
    assert isinstance(m["faltantes"], list)


def test_archivos_de_adjuntos_dentro_del_zip(client, auth_data, historia) -> None:  # type: ignore[no-untyped-def]
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    nombre = f"adjuntos/{historia['adjunto']['id']}.png"
    assert nombre in zf.namelist()
    assert zf.read(nombre) == PNG


def test_fechas_en_iso_con_desplazamiento_horario(client, auth_data, historia) -> None:  # type: ignore[no-untyped-def]
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    filas = _filas(zf, "consentimiento_firmas")
    valor = filas[1][filas[0].index("firmado_en")]
    assert datetime.fromisoformat(valor).utcoffset() is not None


def test_segunda_exportacion_tambien_es_valida_y_deja_otro_evento(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data, historia
) -> None:
    h = bearer(client, auth_data["admin_email"])
    antes = _n_eventos(session_factory)
    assert _leer_zip(_exportar(client, h)).testzip() is None
    assert _leer_zip(_exportar(client, h)).testzip() is None
    assert _n_eventos(session_factory) == antes + 2


# --- 5.2 Bordes ----------------------------------------------------------------------------


def test_clinica_sin_pacientes_csv_solo_encabezados_y_conteos_cero(  # type: ignore[no-untyped-def]
    client, session_factory, password_hash
) -> None:
    with session_factory() as s:
        c = Clinica(nombre="Clinica Vacia Sintetica", cuit="30712345686", es_seed=True)
        s.add(c)
        s.commit()
        cid = c.id
    crear_usuario(session_factory, password_hash, cid, "vacia-admin@test.test", ["admin"])
    zf = _leer_zip(_exportar(client, bearer(client, "vacia-admin@test.test")))
    m = json.loads(zf.read("manifest.json"))
    for nombre in ("pacientes", "fichas", "adjuntos", "evoluciones", "consentimientos", "turnos"):
        assert len(_filas(zf, nombre)) == 1, nombre  # solo encabezados
        assert m["conteos"][nombre] == 0
    assert m["conteos"]["usuarios"] == 1
    assert not [n for n in zf.namelist() if n.startswith("adjuntos/")]


@pytest.mark.parametrize("formato", ["pdf", "xml", ""])
def test_formato_no_soportado_422_sin_evento(client, session_factory, auth_data, formato) -> None:  # type: ignore[no-untyped-def]
    antes = _n_eventos(session_factory)
    r = _exportar(client, bearer(client, auth_data["admin_email"]), formato)
    assert r.status_code == 422
    assert r.json()["formatos"] == ["csv"]
    assert _n_eventos(session_factory) == antes


def test_sin_parametro_formato_usa_csv(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/admin/exportacion", headers=bearer(client, auth_data["admin_email"]))
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"


def test_adjunto_sin_archivo_exportacion_completa_y_manifest_lo_lista(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data, staff_c09, tmp_path
) -> None:
    from app.infrastructure.settings import get_settings
    from app.infrastructure.storage.adjuntos import LocalDirStorage

    pid = nuevo_paciente_c09(session_factory, staff_c09["a"])
    h = bearer(client, staff_c09["o_email"])
    adj = client.post(f"/api/pacientes/{pid}/adjuntos", headers=h,
                          files={"file": ("x.png", PNG, "image/png")}).json()  # fmt: skip
    with session_factory() as s:
        clave = s.scalar(text("SELECT storage_key FROM adjunto WHERE id=:i"), {"i": adj["id"]})
    LocalDirStorage(get_settings().adjuntos_storage_dir).eliminar(clave)
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    m = json.loads(zf.read("manifest.json"))
    assert adj["id"] in m["faltantes"]
    ids = {fila[0] for fila in _filas(zf, "adjuntos")[1:]}
    assert str(adj["id"]) in ids  # la fila se conserva
    assert f"adjuntos/{adj['id']}.png" not in zf.namelist()


def test_ningun_csv_tiene_columnas_de_secretos(client, auth_data, historia) -> None:  # type: ignore[no-untyped-def]
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    for nombre in CSVS:
        encabezado = _filas(zf, nombre)[0]
        for col in encabezado:
            assert not any(s in col.lower() for s in ("password", "secret", "token")), (nombre, col)
    assert "password_hash" not in _filas(zf, "usuarios")[0]


def test_nombre_con_formula_sale_con_apostrofo_y_conserva_comas_y_comillas(  # type: ignore[no-untyped-def]
    client, auth_data, seed
) -> None:
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    filas = _filas(zf, "pacientes")
    enc = filas[0]
    fila = next(f for f in filas[1:] if f[enc.index("id")] == str(seed["pac_formula"]))
    assert fila[enc.index("nombre")] == "'=CMD()"
    assert fila[enc.index("apellido")] == 'Formula, "Peña"'


def test_columna_rango_derivada_no_se_exporta(client, auth_data, historia) -> None:  # type: ignore[no-untyped-def]
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    assert "rango" not in _filas(zf, "turnos")[0]
    assert {"inicio", "fin", "estado"} <= set(_filas(zf, "turnos")[0])


# --- 5.4 Auditoría -------------------------------------------------------------------------


def test_exportacion_exitosa_deja_evento_con_conteos_sin_datos_de_pacientes(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data, historia
) -> None:
    h = bearer(client, auth_data["admin_email"])
    antes = _n_eventos(session_factory)
    zf = _leer_zip(_exportar(client, h))
    manifest = json.loads(zf.read("manifest.json"))
    with session_factory() as s:
        ev = s.scalars(select(AuditoriaAdmin).where(AuditoriaAdmin.accion == "exportar")
                       .order_by(AuditoriaAdmin.id.desc())).first()  # fmt: skip
    assert _n_eventos(session_factory) == antes + 1
    assert ev.entidad_id is None and ev.clinica_id == auth_data["clinica_a"]
    assert ev.diff["formato"] == "csv" and ev.diff["conteos"] == manifest["conteos"]
    assert "Sintetico" not in str(ev.diff) and "=CMD" not in str(ev.diff)


def test_403_no_registra_exportacion(client, session_factory) -> None:  # type: ignore[no-untyped-def]
    antes = _n_eventos(session_factory)
    r = _exportar(client, bearer(client, "odonto@test.test"))
    assert r.status_code == 403
    assert _n_eventos(session_factory) == antes


def test_recetas_csv_con_filas_de_la_clinica_y_items_json(client, auth_data, historia) -> None:  # type: ignore[no-untyped-def]
    """C-19 4.1: recetas.csv sale con todas las columnas de la tabla (items como JSON)."""
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    filas = _filas(zf, "recetas")
    enc = filas[0]
    assert {"id_externo", "partner", "simulada", "pdf_url", "items", "evolucion_id"} <= set(enc)
    assert len(filas) >= 2
    fila = filas[1]
    assert fila[enc.index("simulada")] == "true"
    assert "ibuprofeno" in fila[enc.index("items")]


def test_mensajes_whatsapp_incluidos_y_aislados(client, session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    """C-15 8.1: mensajes_whatsapp.csv trae solo los de la clínica, con conteo en el manifest."""
    from app.domain.whatsapp.models import MensajeWhatsApp

    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    with session_factory() as s:
        for clinica, n in ((a, 2), (b, 1)):
            for i in range(n):
                s.add(MensajeWhatsApp(
                    clinica_id=clinica, direccion="entrante", estado="recibido",
                    intencion="desconocida", telefono=f"+549110000{clinica:02d}{i:02d}",
                    texto="hola sintetico",
                ))  # fmt: skip
        s.commit()
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    filas = _filas(zf, "mensajes_whatsapp")
    enc = filas[0]
    assert len(filas) - 1 == 2
    assert {fila[enc.index("clinica_id")] for fila in filas[1:]} == {str(a)}
    assert json.loads(zf.read("manifest.json"))["conteos"]["mensajes_whatsapp"] == 2


def test_lista_espera_incluida_y_aislada(client, session_factory, auth_data, turnos_data) -> None:  # type: ignore[no-untyped-def]
    """C-16 7.1: lista_espera.csv trae solo las entradas de la clínica."""
    from app.domain.lista_espera.models import ListaEspera

    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    with session_factory() as s:
        for clinica, prest, n in ((a, turnos_data["prest_a"], 2), (b, turnos_data["prest_b"], 1)):
            for _ in range(n):
                pac = paciente_sintetico(clinica)
                s.add(pac)
                s.flush()
                s.add(ListaEspera(clinica_id=clinica, paciente_id=pac.id, prestacion_id=prest))
        s.commit()
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    filas = _filas(zf, "lista_espera")
    enc = filas[0]
    assert len(filas) - 1 == 2
    assert {fila[enc.index("clinica_id")] for fila in filas[1:]} == {str(a)}
    assert json.loads(zf.read("manifest.json"))["conteos"]["lista_espera"] == 2


def test_conversaciones_incluidas(client, session_factory, auth_data, turnos_data) -> None:  # type: ignore[no-untyped-def]
    """C-17 5.1: conversaciones_whatsapp.csv trae solo las de la clínica."""
    from app.domain.reprogramacion.models import ConversacionWA

    a, b = auth_data["clinica_a"], auth_data["clinica_b"]
    inicio = datetime(2038, 1, 4, 10, tzinfo=UTC)
    with session_factory() as s:
        for clinica, prof, sillon, pac, prest, tel in (
            (a, turnos_data["p"], turnos_data["s1"], turnos_data["pac_a"], turnos_data["prest_a"],
             "+5491100000201"),
            (b, turnos_data["prof_b"], turnos_data["sillon_b"], turnos_data["pac_b"],
             turnos_data["prest_b"], "+5491100000202"),
        ):  # fmt: skip
            t = Turno(clinica_id=clinica, profesional_id=prof, sillon_id=sillon, paciente_id=pac,
                      prestacion_id=prest, duracion_min=30, inicio=inicio,
                      fin=inicio + timedelta(minutes=30))  # fmt: skip
            s.add(t)
            s.flush()
            s.add(ConversacionWA(clinica_id=clinica, paciente_id=pac, telefono=tel, turno_id=t.id,
                                 opciones=[], expira_at=inicio))  # fmt: skip
        s.commit()
    zf = _leer_zip(_exportar(client, bearer(client, auth_data["admin_email"])))
    filas = _filas(zf, "conversaciones_whatsapp")
    enc = filas[0]
    assert len(filas) - 1 == 1 and filas[1][enc.index("clinica_id")] == str(a)
