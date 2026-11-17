"""Armado del ZIP de exportación completa del tenant (C-18, D5, RN-CU-04).

El ZIP se arma entero ANTES de responder, en un ``SpooledTemporaryFile`` (seekable: ``zipfile``
escribe cabeceras estándar): un error produce un 500 limpio, nunca un ZIP truncado ni un evento
``exportar`` huérfano. Cada consulta filtra por ``clinica_id`` (regla dura 10).

``ENTIDADES_EXPORTABLES`` exporta TODAS las columnas del modelo menos ``COLUMNAS_EXCLUIDAS``:
las columnas nuevas de otros changes se exportan solas y los secretos quedan afuera.
C-12 (caja) y C-13 (facturas) suman su entidad acá y salen de ``EXCLUIDAS``; C-19 ya sumó recetas.
"""

import json
import tempfile
from datetime import UTC, datetime
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.agenda.models import (
    Bloqueo,
    Prestacion,
    Profesional,
    ProfesionalSillon,
    SillonRecurso,
)
from app.domain.agenda.turnos import Turno, TurnoTransicion
from app.domain.auditoria.models import AuditoriaHC
from app.domain.clinica.models import Evolucion, Odontograma
from app.domain.core.models import Usuario, UsuarioRol
from app.domain.cumplimiento.errores import FormatoNoSoportado
from app.domain.cumplimiento.exportacion import escribir_csv
from app.domain.cumplimiento.models import Consentimiento, ConsentimientoFirma
from app.domain.pacientes.models import Adjunto, FichaVersion, Paciente
from app.domain.recetas.models import RecetaExterna
from app.infrastructure.storage.adjuntos import AdjuntoStorage

FORMATOS = ("csv",)
MAX_EN_MEMORIA = 16 * 1024 * 1024
CHUNK = 64 * 1024
FILAS_POR_LOTE = 500

#: nombre del CSV -> modelo (todas las tablas tienen ``clinica_id``).
ENTIDADES_EXPORTABLES: dict[str, Any] = {
    "pacientes": Paciente,
    "fichas": FichaVersion,
    "adjuntos": Adjunto,
    "odontogramas": Odontograma,
    "evoluciones": Evolucion,
    "consentimientos": Consentimiento,
    "consentimiento_firmas": ConsentimientoFirma,
    "turnos": Turno,
    "turno_transiciones": TurnoTransicion,
    "profesionales": Profesional,
    "sillones": SillonRecurso,
    "prestaciones": Prestacion,
    "profesional_sillones": ProfesionalSillon,
    "bloqueos": Bloqueo,
    "usuarios": Usuario,
    "usuario_roles": UsuarioRol,
    "auditoria_hc": AuditoriaHC,
    "recetas": RecetaExterna,
}

#: ``password_hash``: secreto; ``rango``: columna derivada de inicio/fin (tstzrange).
COLUMNAS_EXCLUIDAS = frozenset({"password_hash", "rango"})

EXCLUIDAS = [
    {"entidad": "caja", "motivo": "no existe aún (C-12)"},
    {"entidad": "facturas", "motivo": "no existe aún (C-13)"},
]

_EXTENSIONES = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}


def validar_formato(formato: str) -> None:
    if formato not in FORMATOS:
        raise FormatoNoSoportado(formato)


def _version_esquema(session: Session) -> str:
    try:
        with session.begin_nested():
            return session.scalar(text("SELECT version_num FROM alembic_version")) or "desconocida"
    except Exception:
        return "desconocida"


def _agregar_adjuntos(
    session: Session, zf: ZipFile, clinica_id: int, storage: AdjuntoStorage
) -> list[int]:
    """Copia los archivos por chunks; devuelve los ids de adjuntos cuyo archivo falta."""
    faltantes: list[int] = []
    filas = session.execute(
        select(Adjunto.id, Adjunto.mime, Adjunto.storage_key)
        .where(Adjunto.clinica_id == clinica_id)
        .order_by(Adjunto.id)
    ).all()
    for adjunto_id, mime, clave in filas:
        try:
            origen = storage.abrir(clave)
        except (FileNotFoundError, OSError):
            faltantes.append(adjunto_id)
            continue
        with origen, zf.open(f"adjuntos/{adjunto_id}.{_EXTENSIONES[mime]}", "w") as destino:
            while bloque := origen.read(CHUNK):
                destino.write(bloque)
    return faltantes


def construir_zip(
    session: Session, clinica_id: int, storage: AdjuntoStorage
) -> tuple[Any, dict[str, Any]]:
    """Devuelve ``(archivo temporal posicionado en 0, manifest)``; el llamador lo cierra."""
    tmp = tempfile.SpooledTemporaryFile(max_size=MAX_EN_MEMORIA)  # noqa: SIM115
    conteos: dict[str, int] = {}
    try:
        with ZipFile(tmp, "w", ZIP_DEFLATED) as zf:
            for nombre, modelo in ENTIDADES_EXPORTABLES.items():
                tabla = modelo.__table__
                columnas = [c for c in tabla.columns if c.name not in COLUMNAS_EXCLUIDAS]
                consulta = (
                    select(*columnas)
                    .where(tabla.c.clinica_id == clinica_id)
                    .order_by(*tabla.primary_key.columns)
                )
                filas = session.execute(consulta, execution_options={"yield_per": FILAS_POR_LOTE})
                with zf.open(f"{nombre}.csv", "w") as destino:
                    conteos[nombre] = escribir_csv(destino, [c.name for c in columnas], filas)
            faltantes = _agregar_adjuntos(session, zf, clinica_id, storage)
            manifest = {
                "clinica_id": clinica_id,
                "generado_en": datetime.now(UTC).isoformat(),
                "version_esquema": _version_esquema(session),
                "formato": "csv",
                "conteos": conteos,
                "faltantes": faltantes,
                "excluidas": EXCLUIDAS,
            }
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        tmp.seek(0)
    except BaseException:
        tmp.close()
        raise
    return tmp, manifest
