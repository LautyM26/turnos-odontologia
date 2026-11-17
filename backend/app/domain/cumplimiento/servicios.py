"""Servicio de consentimientos con firma electrónica (C-18, RN-CU-02).

Documento y constancia son filas append-only (D1): firmar = INSERT de la constancia, nunca
UPDATE. ``estado`` y ``documento_bloqueado`` se derivan de que exista la constancia. El
servicio hace commit; toda escritura audita en la misma transacción y una falla al auditar
revierte la escritura. Logs: solo ids, nunca texto ni datos del firmante.
"""

import re
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.auditoria.writer import registrar_evento
from app.domain.cumplimiento.errores import (
    ConsentimientoNoEncontrado,
    ConsentimientoYaFirmado,
    FirmaIncompleta,
    HashNoCoincide,
)
from app.domain.cumplimiento.hashing import sha256_hex
from app.domain.cumplimiento.models import Consentimiento, ConsentimientoFirma
from app.domain.cumplimiento.schemas import (
    ConsentimientoIn,
    ConsentimientoOut,
    ConstanciaOut,
    FirmaIn,
)
from app.domain.cumplimiento.textos import CATALOGO
from app.domain.pacientes.models import Paciente

if TYPE_CHECKING:
    from app.api.deps import AuthContext

UNIQUE_VIOLATION = "23505"
SIN_DISPOSITIVO = "no-informado"
SIN_IP = "desconocida"
MAX_DISPOSITIVO = 512
_DNI = re.compile(r"^[0-9]{7,8}$")


def faltantes_firma(firma: FirmaIn) -> list[str]:
    """Campos que impiden una firma válida (vacío = completa). Pura, sin DB."""
    faltantes: list[str] = []
    if firma.acepta is not True:
        faltantes.append("acepta")
    if not (firma.firmante_nombre or "").strip():
        faltantes.append("firmante_nombre")
    if not _DNI.match(firma.firmante_dni or ""):
        faltantes.append("firmante_dni")
    return faltantes


def _sqlstate(exc: IntegrityError) -> str | None:
    return getattr(exc.orig, "sqlstate", None)


def _out(doc: Consentimiento, firma: ConsentimientoFirma | None) -> ConsentimientoOut:
    return ConsentimientoOut(
        id=doc.id,
        paciente_id=doc.paciente_id,
        tipo=doc.tipo,
        texto=doc.texto,
        texto_version=doc.texto_version,
        texto_hash=doc.texto_hash,
        autor_usuario_id=doc.autor_usuario_id,
        created_at=doc.created_at,
        estado="firmado" if firma else "pendiente",
        documento_bloqueado=firma is not None,
        constancia=ConstanciaOut.model_validate(firma) if firma else None,
    )


def _con_firma(clinica_id: int, paciente_id: int):  # type: ignore[no-untyped-def]
    """Documentos del paciente (siempre filtrados por clínica) con su constancia si existe."""
    return (
        select(Consentimiento, ConsentimientoFirma)
        .outerjoin(
            ConsentimientoFirma,
            (ConsentimientoFirma.clinica_id == Consentimiento.clinica_id)
            & (ConsentimientoFirma.consentimiento_id == Consentimiento.id),
        )
        .where(Consentimiento.clinica_id == clinica_id, Consentimiento.paciente_id == paciente_id)
    )


def _documento(session: Session, clinica_id: int, paciente_id: int, cid: int):  # type: ignore[no-untyped-def]
    consulta = _con_firma(clinica_id, paciente_id).where(Consentimiento.id == cid)
    fila = session.execute(consulta).one_or_none()
    if fila is None:
        raise ConsentimientoNoEncontrado()
    return fila


def generar_consentimiento(
    session: Session,
    auth: "AuthContext",
    paciente: Paciente,
    datos: ConsentimientoIn,
    ip: str | None,
) -> ConsentimientoOut:
    """Copia el texto vigente del tipo con su versión y hash (calculado en el servidor)."""
    version, texto = CATALOGO[datos.tipo]
    doc = Consentimiento(
        clinica_id=auth.tenant_id,
        paciente_id=paciente.id,
        tipo=datos.tipo,
        texto=texto,
        texto_version=version,
        texto_hash=sha256_hex(texto),
        autor_usuario_id=auth.sub,
    )
    try:
        session.add(doc)
        session.flush()
        registrar_evento(
            session, auth, "crear", "consentimiento", doc.id, paciente.id,
            {"consentimiento_id": doc.id, "texto_version": version}, ip,
        )  # fmt: skip
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(doc)
    return _out(doc, None)


def firmar_consentimiento(
    session: Session,
    auth: "AuthContext",
    paciente: Paciente,
    cid: int,
    datos: FirmaIn,
    ip: str | None,
    dispositivo: str | None,
) -> ConsentimientoOut:
    """Registra la constancia. Orden: 404 -> 409 firmado -> 422 incompleta -> 409 hash -> 201.

    Fecha, IP y dispositivo los pone el servidor; la segunda firma (secuencial o concurrente)
    la rechaza el UNIQUE de la constancia (23505 -> 409).
    """
    doc, firma = _documento(session, auth.tenant_id, paciente.id, cid)
    if firma is not None:
        raise ConsentimientoYaFirmado()
    faltantes = faltantes_firma(datos)
    if faltantes:
        raise FirmaIncompleta(faltantes)
    if datos.texto_hash != doc.texto_hash:
        raise HashNoCoincide()
    nueva = ConsentimientoFirma(
        clinica_id=auth.tenant_id,
        paciente_id=paciente.id,
        consentimiento_id=doc.id,
        ip=ip or SIN_IP,
        dispositivo=(dispositivo or "").strip()[:MAX_DISPOSITIVO] or SIN_DISPOSITIVO,
        texto_hash=doc.texto_hash,
        firmante_nombre=(datos.firmante_nombre or "").strip(),
        firmante_dni=datos.firmante_dni or "",
        asistido_por_usuario_id=auth.sub,
    )
    try:
        session.add(nueva)
        session.flush()
        registrar_evento(
            session, auth, "firmar", "consentimiento", doc.id, paciente.id,
            {"consentimiento_id": doc.id, "texto_version": doc.texto_version}, ip,
        )  # fmt: skip
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _sqlstate(exc) == UNIQUE_VIOLATION:
            raise ConsentimientoYaFirmado() from exc
        raise
    except Exception:
        session.rollback()
        raise
    session.refresh(nueva)
    return _out(doc, nueva)


def listar_consentimientos(
    session: Session, auth: "AuthContext", paciente: Paciente, ip: str | None
) -> list[ConsentimientoOut]:
    """Más recientes primero; un evento ``leer`` por consulta (``entidad_id`` = paciente)."""
    filas = session.execute(
        _con_firma(auth.tenant_id, paciente.id).order_by(Consentimiento.id.desc())
    ).all()
    registrar_evento(session, auth, "leer", "consentimiento", paciente.id, paciente.id, None, ip)
    session.commit()
    return [_out(d, f) for d, f in filas]


def obtener_consentimiento(
    session: Session, auth: "AuthContext", paciente: Paciente, cid: int, ip: str | None
) -> ConsentimientoOut:
    """Detalle con constancia (404 si es de otro paciente o clínica) y evento ``leer``."""
    doc, firma = _documento(session, auth.tenant_id, paciente.id, cid)
    registrar_evento(
        session, auth, "leer", "consentimiento", doc.id, paciente.id,
        {"consentimiento_id": doc.id}, ip,
    )  # fmt: skip
    session.commit()
    return _out(doc, firma)
