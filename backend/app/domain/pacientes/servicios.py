"""Servicio de pacientes, ficha versionada y adjuntos (C-08).

Los errores de dominio (``PacienteError``) se traducen a HTTP en ``create_app()``.
El servicio hace commit; los routers no tocan la transacción. Toda escritura audita en
la misma transacción (``registrar_evento``). Logs: solo ids, nunca PII/PHI.
"""

import hashlib
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, BinaryIO

from sqlalchemy import ColumnElement, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.auditoria.models import AuditoriaHC
from app.domain.auditoria.writer import registrar_evento
from app.domain.pacientes.archivos import (
    LARGO_CABECERA,
    TipoNoPermitido,
    detectar_tipo,
    sanear_nombre,
)
from app.domain.pacientes.models import Adjunto, FichaVersion, Paciente
from app.domain.pacientes.normalizacion import (
    NormalizacionError,
    nombre_busqueda,
    normalizar_dni,
    normalizar_telefono,
    normalizar_texto,
)
from app.domain.pacientes.schemas import FichaPut, PacienteCreate, PacienteUpdate
from app.infrastructure.persistence.repository import BaseRepository
from app.infrastructure.storage.adjuntos import AdjuntoStorage, generar_clave

if TYPE_CHECKING:
    from app.api.deps import AuthContext

UNIQUE_VIOLATION = "23505"


class PacienteError(Exception):
    """Error de dominio con status HTTP asociado."""

    status_code = 400

    def __init__(self, detail: str, **extra: Any) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class PacienteNoEncontrado(PacienteError):
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Paciente no encontrado")


class PacienteDuplicado(PacienteError):
    status_code = 409

    def __init__(self, paciente_id: int) -> None:
        super().__init__("Ya existe un paciente con ese DNI en la clínica", paciente_id=paciente_id)
        self.paciente_id = paciente_id


class ContactoRequerido(PacienteError):
    status_code = 422

    def __init__(self) -> None:
        super().__init__("Se requiere email o teléfono")


class VersionFichaConflicto(PacienteError):
    status_code = 409

    def __init__(self) -> None:
        super().__init__("La ficha cambió: la versión esperada no coincide con la vigente")


class AdjuntoTipoNoPermitido(PacienteError):
    status_code = 415


class AdjuntoTamanoExcedido(PacienteError):
    status_code = 413

    def __init__(self, maximo: int) -> None:
        super().__init__(f"El archivo supera el máximo de {maximo} bytes")


class AdjuntoVacio(PacienteError):
    status_code = 422

    def __init__(self) -> None:
        super().__init__("El archivo está vacío")


class AdjuntoNoEncontrado(PacienteError):
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Adjunto no encontrado")


class ParametroInvalido(PacienteError):
    status_code = 422


def _sqlstate(exc: IntegrityError) -> str | None:
    return getattr(exc.orig, "sqlstate", None)


def paciente_por_dni(session: Session, clinica_id: int, dni: str) -> Paciente | None:
    return session.scalars(
        select(Paciente).where(Paciente.clinica_id == clinica_id, Paciente.dni == dni)
    ).one_or_none()


def obtener_paciente(session: Session, clinica_id: int, paciente_id: int) -> Paciente:
    """Paciente del tenant; ajeno o inexistente -> 404 (sin enumeración)."""
    fila = BaseRepository(session, Paciente, clinica_id).get(paciente_id)
    if fila is None:
        raise PacienteNoEncontrado()
    return fila


def crear_paciente(session: Session, auth: "AuthContext", datos: PacienteCreate) -> Paciente:
    """Alta en el tenant del JWT; DNI duplicado -> ``PacienteDuplicado``. No crea Usuario."""
    clinica_id = auth.tenant_id
    existente = paciente_por_dni(session, clinica_id, datos.dni)
    if existente is not None:
        raise PacienteDuplicado(existente.id)
    valores = datos.model_dump()
    paciente = Paciente(**valores, nombre_busqueda=nombre_busqueda(datos.apellido, datos.nombre))
    BaseRepository(session, Paciente, clinica_id).add(paciente)
    try:
        session.flush()
        campos = sorted(k for k, v in valores.items() if v is not None)
        registrar_evento(
            session, auth, "crear", "paciente", paciente.id, paciente.id, {"campos": campos}
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _sqlstate(exc) == UNIQUE_VIOLATION:
            carrera = paciente_por_dni(session, clinica_id, datos.dni)
            if carrera is not None:
                raise PacienteDuplicado(carrera.id) from exc
        raise
    session.refresh(paciente)
    return paciente


def actualizar_paciente(
    session: Session, auth: "AuthContext", paciente_id: int, datos: PacienteUpdate
) -> Paciente:
    """Edición parcial normalizada; audita nombres de campos (nunca valores)."""
    paciente = obtener_paciente(session, auth.tenant_id, paciente_id)
    cambios = {k: v for k, v in datos.model_dump(exclude_unset=True).items()}
    consentimiento = cambios.pop("consentimiento_datos", None)
    if "dni" in cambios and cambios["dni"] != paciente.dni:
        otro = paciente_por_dni(session, auth.tenant_id, cambios["dni"])
        if otro is not None and otro.id != paciente.id:
            raise PacienteDuplicado(otro.id)
    for campo, valor in cambios.items():
        setattr(paciente, campo, valor)
    if paciente.email is None and paciente.telefono is None:
        session.rollback()
        raise ContactoRequerido()
    if "nombre" in cambios or "apellido" in cambios:
        paciente.nombre_busqueda = nombre_busqueda(paciente.apellido, paciente.nombre)
    try:
        if cambios:
            registrar_evento(
                session, auth, "actualizar", "paciente", paciente.id, paciente.id,
                {"campos": sorted(cambios)},
            )  # fmt: skip
        if consentimiento is not None and consentimiento != paciente.consentimiento_datos:
            _cambiar_consentimiento(session, auth, paciente, consentimiento)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _sqlstate(exc) == UNIQUE_VIOLATION and "dni" in cambios:
            carrera = paciente_por_dni(session, auth.tenant_id, cambios["dni"])
            if carrera is not None:
                raise PacienteDuplicado(carrera.id) from exc
        raise
    session.refresh(paciente)
    return paciente


def _cambiar_consentimiento(
    session: Session, auth: "AuthContext", paciente: Paciente, otorgado: bool
) -> None:
    """Otorga (fecha + usuario) o revoca (sin borrar HC) y audita el cambio."""
    paciente.consentimiento_datos = otorgado
    if otorgado:
        paciente.consentimiento_datos_at = datetime.now(UTC)
        paciente.consentimiento_datos_por = auth.sub
    registrar_evento(
        session, auth,
        "consentimiento_otorgado" if otorgado else "consentimiento_revocado",
        "paciente", paciente.id, paciente.id, {"consentimiento_datos": otorgado},
    )  # fmt: skip


def filtros_busqueda(
    dni: str | None = None, telefono: str | None = None, q: str | None = None
) -> list[ColumnElement[bool]]:
    """Filtros AND: DNI/teléfono exactos normalizados; ``q`` parcial sin acentos (>= 3)."""
    filtros: list[ColumnElement[bool]] = []
    try:
        if dni is not None:
            filtros.append(Paciente.dni == normalizar_dni(dni))
        if telefono is not None:
            filtros.append(Paciente.telefono == normalizar_telefono(telefono))
    except NormalizacionError as exc:
        raise ParametroInvalido(str(exc)) from exc
    if q is not None:
        texto = normalizar_texto(q)
        if len(texto) < 3:
            raise ParametroInvalido("La búsqueda por nombre requiere al menos 3 caracteres")
        filtros.append(Paciente.nombre_busqueda.contains(texto, autoescape=True))
    return filtros


def buscar_pacientes(
    session: Session,
    clinica_id: int,
    after_id: int | None,
    limit: int,
    dni: str | None = None,
    telefono: str | None = None,
    q: str | None = None,
) -> tuple[Sequence[Paciente], int | None]:
    """Búsqueda keyset por id (``BaseRepository.page``), siempre scoped al tenant."""
    filtros = filtros_busqueda(dni, telefono, q)
    return BaseRepository(session, Paciente, clinica_id).page(after_id, limit, False, *filtros)


# --- Ficha versionada ---------------------------------------------------------------------


def ficha_vigente_fila(session: Session, clinica_id: int, paciente_id: int) -> FichaVersion | None:
    return session.scalars(
        select(FichaVersion)
        .where(FichaVersion.clinica_id == clinica_id, FichaVersion.paciente_id == paciente_id)
        .order_by(FichaVersion.version.desc())
        .limit(1)
    ).one_or_none()


def leer_ficha(session: Session, auth: "AuthContext", paciente: Paciente) -> FichaVersion | None:
    """Ficha vigente (``None`` = versión 0) y auditoría de la lectura (commit propio)."""
    fila = ficha_vigente_fila(session, auth.tenant_id, paciente.id)
    registrar_evento(
        session, auth, "leer", "ficha", fila.id if fila else paciente.id, paciente.id,
        {"version": fila.version if fila else 0},
    )  # fmt: skip
    session.commit()
    return fila


_CAMPOS_FICHA = ("anamnesis", "alergias", "antecedentes")


def guardar_ficha(
    session: Session, auth: "AuthContext", paciente: Paciente, datos: FichaPut
) -> FichaVersion:
    """Nueva versión (``version_esperada + 1``) con control optimista y auditoría atómica."""
    vigente = ficha_vigente_fila(session, auth.tenant_id, paciente.id)
    actual = vigente.version if vigente else 0
    if datos.version_esperada != actual:
        raise VersionFichaConflicto()
    nueva = FichaVersion(
        clinica_id=auth.tenant_id,
        paciente_id=paciente.id,
        version=actual + 1,
        autor_usuario_id=auth.sub,
        **{c: getattr(datos, c) for c in _CAMPOS_FICHA},
    )
    cambiados = sorted(
        c for c in _CAMPOS_FICHA if getattr(datos, c) != (getattr(vigente, c) if vigente else None)
    )
    try:
        session.add(nueva)
        session.flush()
        registrar_evento(
            session, auth, "actualizar" if vigente else "crear", "ficha", nueva.id, paciente.id,
            {"campos": cambiados, "version": nueva.version},
        )  # fmt: skip
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _sqlstate(exc) == UNIQUE_VIOLATION:
            raise VersionFichaConflicto() from exc
        raise
    session.refresh(nueva)
    return nueva


def listar_versiones_ficha(
    session: Session, auth: "AuthContext", paciente: Paciente
) -> Sequence[FichaVersion]:
    """Todas las versiones (descendente) y auditoría de la lectura."""
    filas = session.scalars(
        select(FichaVersion)
        .where(FichaVersion.clinica_id == auth.tenant_id, FichaVersion.paciente_id == paciente.id)
        .order_by(FichaVersion.version.desc())
    ).all()
    registrar_evento(
        session, auth, "leer", "ficha", filas[0].id if filas else paciente.id, paciente.id,
        {"version": filas[0].version if filas else 0},
    )  # fmt: skip
    session.commit()
    return filas


# --- Adjuntos -----------------------------------------------------------------------------

CHUNK = 64 * 1024


def subir_adjunto(
    session: Session,
    auth: "AuthContext",
    paciente: Paciente,
    archivo: BinaryIO,
    content_type: str | None,
    nombre: str | None,
    storage: AdjuntoStorage,
    max_bytes: int,
) -> Adjunto:
    """Valida (vacío, firma, tamaño real) -> guarda -> fila + auditoría -> commit.

    Si la DB falla tras escribir el archivo, se compensa borrándolo (best-effort).
    """
    primero = archivo.read(CHUNK)
    if not primero:
        raise AdjuntoVacio()
    try:
        tipo, mime = detectar_tipo(primero[:LARGO_CABECERA], content_type or None)
    except TipoNoPermitido as exc:
        raise AdjuntoTipoNoPermitido(str(exc)) from exc
    clave = generar_clave(auth.tenant_id, paciente.id)
    digest = hashlib.sha256()
    total = 0

    def chunks() -> Iterator[bytes]:
        nonlocal total
        bloque = primero
        while bloque:
            total += len(bloque)
            if total > max_bytes:
                raise AdjuntoTamanoExcedido(max_bytes)
            digest.update(bloque)
            yield bloque
            bloque = archivo.read(CHUNK)

    storage.guardar(clave, chunks())
    try:
        adjunto = Adjunto(
            clinica_id=auth.tenant_id,
            paciente_id=paciente.id,
            tipo=tipo,
            mime=mime,
            tamano_bytes=total,
            sha256=digest.hexdigest(),
            storage_key=clave,
            nombre_original=sanear_nombre(nombre),
            subido_por=auth.sub,
        )
        session.add(adjunto)
        session.flush()
        registrar_evento(
            session, auth, "crear", "adjunto", adjunto.id, paciente.id, {"adjunto_id": adjunto.id}
        )
        session.commit()
    except BaseException:
        session.rollback()
        storage.eliminar(clave)
        raise
    session.refresh(adjunto)
    return adjunto


def listar_adjuntos(session: Session, clinica_id: int, paciente_id: int) -> Sequence[Adjunto]:
    return session.scalars(
        select(Adjunto)
        .where(
            Adjunto.clinica_id == clinica_id,
            Adjunto.paciente_id == paciente_id,
            Adjunto.is_active.is_(True),
        )
        .order_by(Adjunto.id)
    ).all()


def descargar_adjunto(
    session: Session,
    auth: "AuthContext",
    paciente: Paciente,
    adjunto_id: int,
    storage: AdjuntoStorage,
) -> tuple[Adjunto, BinaryIO]:
    """Abre el contenido y audita la descarga (404 si no es del paciente/tenant)."""
    adjunto = session.scalars(
        select(Adjunto).where(
            Adjunto.id == adjunto_id,
            Adjunto.clinica_id == auth.tenant_id,
            Adjunto.paciente_id == paciente.id,
            Adjunto.is_active.is_(True),
        )
    ).one_or_none()
    if adjunto is None:
        raise AdjuntoNoEncontrado()
    try:
        contenido = storage.abrir(adjunto.storage_key)
    except FileNotFoundError as exc:
        raise AdjuntoNoEncontrado() from exc
    try:
        registrar_evento(
            session, auth, "descargar", "adjunto", adjunto.id, paciente.id,
            {"adjunto_id": adjunto.id},
        )  # fmt: skip
        session.commit()
    except BaseException:
        contenido.close()
        raise
    return adjunto, contenido


# --- Consulta de auditoría ----------------------------------------------------------------


def listar_auditoria(
    session: Session, clinica_id: int, paciente_id: int, after_id: int | None, limit: int
) -> tuple[Sequence[AuditoriaHC], int | None]:
    """Eventos del paciente, ``id`` descendente (= cronológico inverso), keyset por cursor."""
    stmt = select(AuditoriaHC).where(
        AuditoriaHC.clinica_id == clinica_id, AuditoriaHC.paciente_id == paciente_id
    )
    if after_id is not None:
        stmt = stmt.where(AuditoriaHC.id < after_id)
    filas = list(session.scalars(stmt.order_by(AuditoriaHC.id.desc()).limit(limit + 1)).all())
    if len(filas) > limit:
        filas = filas[:limit]
        return filas, filas[-1].id
    return filas, None
