"""Servicio de recetas y órdenes de estudio vía partner ReNaPDiS (C-19, RN-CU-03).

Flujo de ``emitir_receta`` (D4): idempotencia -> profesional -> evolución propia -> llamada al
partner (sin escrituras ni locks pendientes) -> INSERT + auditoría en una transacción. El partner
deduplica por ``clave_idempotencia``, así un fallo posterior a su respuesta se recupera con el
reintento. El servicio hace commit; logs: solo ids, nunca ítems ni diagnóstico.
"""

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.agenda.models import Profesional
from app.domain.agenda.servicio import profesional_de_usuario
from app.domain.auditoria.writer import registrar_evento
from app.domain.clinica.errores import AutorProfesionalRequerido
from app.domain.clinica.models import Evolucion
from app.domain.pacientes.models import Paciente
from app.domain.recetas.errores import (
    ClaveIdempotenciaReutilizada,
    EvolucionNoValidaParaReceta,
    PartnerCaido,
    PartnerRechazoError,
    RecetaNoEncontrada,
    sanear_motivo,
)
from app.domain.recetas.models import RecetaExterna
from app.domain.recetas.schemas import (
    OrdenEstudioIn,
    RecetaMedicamentosIn,
    RecetaOut,
    huella_solicitud,
)
from app.infrastructure.recetas.partner_client import (
    PartnerNoDisponible,
    PartnerRecetas,
    PartnerRechazo,
    SolicitudPartner,
)

if TYPE_CHECKING:
    from app.api.deps import AuthContext

UNIQUE_VIOLATION = "23505"


def _sqlstate(exc: IntegrityError) -> str | None:
    return getattr(exc.orig, "sqlstate", None)


def _por_clave(session: Session, clinica_id: int, clave) -> RecetaExterna | None:  # type: ignore[no-untyped-def]
    return session.scalars(
        select(RecetaExterna).where(
            RecetaExterna.clinica_id == clinica_id, RecetaExterna.clave_idempotencia == clave
        )
    ).one_or_none()


def _repetida(fila: RecetaExterna, huella: str, paciente_id: int) -> RecetaOut:
    """Reintento legítimo (mismo contenido y paciente) o reuso de la clave (409)."""
    if fila.huella_solicitud != huella or fila.paciente_id != paciente_id:
        raise ClaveIdempotenciaReutilizada()
    return RecetaOut.model_validate(fila)


def emitir_receta(
    session: Session,
    auth: "AuthContext",
    paciente: Paciente,
    datos: RecetaMedicamentosIn | OrdenEstudioIn,
    partner: PartnerRecetas,
    secreto: str | None,
    ip: str | None,
) -> tuple[RecetaOut, bool]:
    """Devuelve ``(receta, creada)``; ``creada=False`` = reintento idempotente (200)."""
    huella = huella_solicitud(datos)
    previa = _por_clave(session, auth.tenant_id, datos.clave_idempotencia)
    if previa is not None:
        return _repetida(previa, huella, paciente.id), False

    profesional_id = profesional_de_usuario(session, auth.sub)
    if profesional_id is None:
        raise AutorProfesionalRequerido()
    evolucion = session.scalars(
        select(Evolucion).where(
            Evolucion.clinica_id == auth.tenant_id,
            Evolucion.paciente_id == paciente.id,
            Evolucion.id == datos.evolucion_id,
        )
    ).one_or_none()
    if evolucion is None:
        raise EvolucionNoValidaParaReceta()
    if evolucion.autor_usuario_id != auth.sub:
        raise EvolucionNoValidaParaReceta(ajena=True)
    profesional = session.scalars(
        select(Profesional).where(
            Profesional.clinica_id == auth.tenant_id, Profesional.id == profesional_id
        )
    ).one()

    solicitud = SolicitudPartner(
        tipo=datos.tipo,
        clave_idempotencia=datos.clave_idempotencia,
        paciente_nombre=paciente.nombre,
        paciente_apellido=paciente.apellido,
        paciente_dni=paciente.dni,
        obra_social_nombre=paciente.obra_social_nombre,
        obra_social_plan=paciente.obra_social_plan,
        nro_afiliado=paciente.nro_afiliado,
        profesional_nombre=profesional.nombre,
        profesional_matricula=profesional.matricula,
        diagnostico=datos.diagnostico,
        items=tuple(i.model_dump(mode="json") for i in datos.items),
    )
    session.rollback()  # cierra la transacción de lectura: sin locks durante la llamada externa
    try:
        emision = partner.emitir(solicitud)
    except PartnerNoDisponible as exc:
        raise PartnerCaido() from exc
    except PartnerRechazo as exc:
        raise PartnerRechazoError(sanear_motivo(exc.motivo, secreto)) from exc

    fila = RecetaExterna(
        clinica_id=auth.tenant_id,
        paciente_id=paciente.id,
        evolucion_id=datos.evolucion_id,
        tipo=datos.tipo,
        partner=partner.nombre,
        simulada=partner.simulado,
        id_externo=emision.id_externo,
        pdf_url=emision.pdf_url,
        diagnostico=datos.diagnostico,
        items=list(solicitud.items),
        clave_idempotencia=datos.clave_idempotencia,
        huella_solicitud=huella,
        autor_usuario_id=auth.sub,
        profesional_id=profesional_id,
    )
    try:
        session.add(fila)
        session.flush()
        registrar_evento(
            session, auth, "crear", "receta", fila.id, paciente.id,
            {"receta_id": fila.id, "evolucion_id": fila.evolucion_id, "partner": fila.partner},
            ip,
        )  # fmt: skip
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _sqlstate(exc) == UNIQUE_VIOLATION:
            ganadora = _por_clave(session, auth.tenant_id, datos.clave_idempotencia)
            if ganadora is not None:  # carrera con la misma clave: devolvemos la que ganó
                return _repetida(ganadora, huella, paciente.id), False
        raise
    except Exception:
        session.rollback()
        raise
    session.refresh(fila)
    return RecetaOut.model_validate(fila), True


def listar_recetas(
    session: Session,
    auth: "AuthContext",
    paciente: Paciente,
    after_id: int | None,
    limit: int,
    ip: str | None,
) -> tuple[list[RecetaOut], int | None]:
    """Más recientes primero (keyset por ``id``) y un evento ``leer`` por consulta."""
    stmt = select(RecetaExterna).where(
        RecetaExterna.clinica_id == auth.tenant_id, RecetaExterna.paciente_id == paciente.id
    )
    if after_id is not None:
        stmt = stmt.where(RecetaExterna.id < after_id)
    filas = session.scalars(stmt.order_by(RecetaExterna.id.desc()).limit(limit + 1)).all()
    items = [RecetaOut.model_validate(f) for f in filas[:limit]]
    registrar_evento(session, auth, "leer", "receta", paciente.id, paciente.id, None, ip)
    session.commit()
    return items, (items[-1].id if len(filas) > limit else None)


def obtener_receta(
    session: Session, auth: "AuthContext", paciente: Paciente, rid: int, ip: str | None
) -> RecetaOut:
    """Una receta del paciente (404 si es de otro paciente o clínica) y evento ``leer``."""
    fila = session.scalars(
        select(RecetaExterna).where(
            RecetaExterna.clinica_id == auth.tenant_id,
            RecetaExterna.paciente_id == paciente.id,
            RecetaExterna.id == rid,
        )
    ).one_or_none()
    if fila is None:
        raise RecetaNoEncontrada()
    registrar_evento(
        session, auth, "leer", "receta", fila.id, paciente.id, {"receta_id": fila.id}, ip
    )
    session.commit()
    return RecetaOut.model_validate(fila)
