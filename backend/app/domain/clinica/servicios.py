"""Servicio de odontograma, evoluciones e historia consolidada (C-09).

Reglas: RN-CL-01 (autor profesional + hora del servidor), RN-CL-02 (append-only; corregir =
fila nueva), RN-CL-03 (piezas FDI). El servicio hace commit; los routers no tocan la
transacción. Toda escritura audita en la misma transacción y una falla al auditar revierte
la escritura. Logs: solo ids, nunca texto clínico.

Las funciones sin auditoría propia (``odontograma_vigente``, ``versiones_odontograma``,
``evoluciones_pagina``) filtran siempre por ``clinica_id`` (regla dura 10) y las reutiliza la
historia consolidada para registrar un único evento de lectura.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.domain.agenda.servicio import profesional_de_usuario
from app.domain.auditoria.writer import registrar_evento
from app.domain.clinica.errores import (
    AutorProfesionalRequerido,
    CorreccionInvalida,
    CorreccionNoAutorizada,
    EvolucionNoEncontrada,
    EvolucionYaCorregida,
    VersionOdontogramaConflicto,
)
from app.domain.clinica.models import Evolucion, Odontograma
from app.domain.clinica.schemas import (
    EvolucionIn,
    EvolucionOut,
    HistoriaOut,
    OdontogramaIn,
    odontograma_out,
)
from app.domain.pacientes.models import Paciente
from app.domain.pacientes.schemas import FichaOut
from app.domain.pacientes.servicios import ficha_vigente_fila

if TYPE_CHECKING:
    from app.api.deps import AuthContext

UNIQUE_VIOLATION = "23505"
LIMITE_HISTORIA = 50


def _sqlstate(exc: IntegrityError) -> str | None:
    return getattr(exc.orig, "sqlstate", None)


# --- Odontograma ---------------------------------------------------------------------------


def odontograma_vigente(session: Session, clinica_id: int, paciente_id: int) -> Odontograma | None:
    """Versión de mayor número (sin auditoría propia)."""
    return session.scalars(
        select(Odontograma)
        .where(Odontograma.clinica_id == clinica_id, Odontograma.paciente_id == paciente_id)
        .order_by(Odontograma.version.desc())
        .limit(1)
    ).one_or_none()


def versiones_odontograma(
    session: Session, clinica_id: int, paciente_id: int
) -> Sequence[Odontograma]:
    """Todas las versiones, la más nueva primero (sin auditoría propia)."""
    return session.scalars(
        select(Odontograma)
        .where(Odontograma.clinica_id == clinica_id, Odontograma.paciente_id == paciente_id)
        .order_by(Odontograma.version.desc())
    ).all()


def _campos_cambiados(
    vigente: Odontograma | None, denticion: str, piezas: dict[str, dict]
) -> list[str]:
    """Códigos FDI cuya marca cambió (alta, modificación o baja) + ``denticion`` si cambió."""
    previas = vigente.piezas if vigente else {}
    campos = {c for c in previas.keys() | piezas.keys() if previas.get(c) != piezas.get(c)}
    if vigente is None or vigente.denticion != denticion:
        campos.add("denticion")
    return sorted(campos)


def guardar_odontograma(
    session: Session, auth: "AuthContext", paciente: Paciente, datos: OdontogramaIn
) -> Odontograma:
    """Nueva versión (``version_esperada + 1``) con control optimista y auditoría atómica."""
    vigente = odontograma_vigente(session, auth.tenant_id, paciente.id)
    actual = vigente.version if vigente else 0
    if datos.version_esperada != actual:
        raise VersionOdontogramaConflicto()
    piezas = {c: p.model_dump(mode="json", exclude_none=True) for c, p in datos.piezas.items()}
    nueva = Odontograma(
        clinica_id=auth.tenant_id,
        paciente_id=paciente.id,
        version=actual + 1,
        denticion=datos.denticion,
        piezas=piezas,
        autor_usuario_id=auth.sub,
    )
    try:
        session.add(nueva)
        session.flush()
        registrar_evento(
            session, auth, "actualizar" if vigente else "crear", "odontograma", nueva.id,
            paciente.id,
            {
                "odontograma_id": nueva.id,
                "version": nueva.version,
                "campos": _campos_cambiados(vigente, datos.denticion, piezas),
            },
        )  # fmt: skip
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _sqlstate(exc) == UNIQUE_VIOLATION:
            raise VersionOdontogramaConflicto() from exc
        raise
    except Exception:
        session.rollback()
        raise
    session.refresh(nueva)
    return nueva


def leer_odontograma_actual(
    session: Session, auth: "AuthContext", paciente: Paciente
) -> Odontograma | None:
    """Vigente (``None`` = versión 0) y auditoría de la lectura (commit propio)."""
    fila = odontograma_vigente(session, auth.tenant_id, paciente.id)
    registrar_evento(
        session, auth, "leer", "odontograma", fila.id if fila else paciente.id, paciente.id,
        {"version": fila.version if fila else 0},
    )  # fmt: skip
    session.commit()
    return fila


def listar_odontogramas(
    session: Session, auth: "AuthContext", paciente: Paciente
) -> Sequence[Odontograma]:
    """Historial completo (descendente) y auditoría de la lectura."""
    filas = versiones_odontograma(session, auth.tenant_id, paciente.id)
    registrar_evento(
        session, auth, "leer", "odontograma", filas[0].id if filas else paciente.id, paciente.id,
        {"version": filas[0].version if filas else 0},
    )  # fmt: skip
    session.commit()
    return filas


# --- Evoluciones ---------------------------------------------------------------------------


def _con_corregida_por(session: Session, clinica_id: int, paciente_id: int):  # type: ignore[no-untyped-def]
    """SELECT de evolución + id de la que la corrige (LEFT JOIN: la original no se toca)."""
    corrige = aliased(Evolucion)
    return (
        select(Evolucion, corrige.id)
        .outerjoin(
            corrige,
            (corrige.clinica_id == Evolucion.clinica_id) & (corrige.corrige_a_id == Evolucion.id),
        )
        .where(Evolucion.clinica_id == clinica_id, Evolucion.paciente_id == paciente_id)
    )


def _evolucion_out(fila: Evolucion, corregida_por_id: int | None) -> EvolucionOut:
    return EvolucionOut(
        id=fila.id,
        paciente_id=fila.paciente_id,
        autor_usuario_id=fila.autor_usuario_id,
        profesional_id=fila.profesional_id,
        fecha_hora=fila.fecha_hora,
        texto=fila.texto,
        pieza_fdi=fila.pieza_fdi,
        corrige_a_id=fila.corrige_a_id,
        motivo_correccion=fila.motivo_correccion,
        corregida_por_id=corregida_por_id,
    )


def evoluciones_pagina(
    session: Session, clinica_id: int, paciente_id: int, after_id: int | None, limit: int
) -> tuple[list[EvolucionOut], int | None]:
    """Más recientes primero, keyset por ``id`` (sin auditoría propia)."""
    stmt = _con_corregida_por(session, clinica_id, paciente_id)
    if after_id is not None:
        stmt = stmt.where(Evolucion.id < after_id)
    filas = session.execute(stmt.order_by(Evolucion.id.desc()).limit(limit + 1)).all()
    items = [_evolucion_out(e, c) for e, c in filas[:limit]]
    return items, (items[-1].id if len(filas) > limit else None)


def _vigente_de_la_cadena(session: Session, clinica_id: int, evolucion_id: int) -> int:
    """Sigue la cadena de correcciones (lineal, DC-7) hasta la evolución vigente."""
    actual = evolucion_id
    while True:
        siguiente = session.scalars(
            select(Evolucion.id).where(
                Evolucion.clinica_id == clinica_id, Evolucion.corrige_a_id == actual
            )
        ).first()
        if siguiente is None:
            return actual
        actual = siguiente


def registrar_evolucion(
    session: Session, auth: "AuthContext", paciente: Paciente, datos: EvolucionIn
) -> EvolucionOut:
    """Alta o corrección; autor = usuario + su profesional vinculado, hora del servidor."""
    profesional_id = profesional_de_usuario(session, auth.sub)
    if profesional_id is None:
        raise AutorProfesionalRequerido()
    if datos.corrige_a_id is not None:
        original = session.scalars(
            select(Evolucion).where(
                Evolucion.clinica_id == auth.tenant_id,
                Evolucion.paciente_id == paciente.id,
                Evolucion.id == datos.corrige_a_id,
            )
        ).one_or_none()
        if original is None:
            raise CorreccionInvalida()
        if original.autor_usuario_id != auth.sub:
            raise CorreccionNoAutorizada()
    nueva = Evolucion(
        clinica_id=auth.tenant_id,
        paciente_id=paciente.id,
        autor_usuario_id=auth.sub,
        profesional_id=profesional_id,
        texto=datos.texto,
        pieza_fdi=datos.pieza_fdi,
        corrige_a_id=datos.corrige_a_id,
        motivo_correccion=datos.motivo_correccion,
    )
    try:
        session.add(nueva)
        session.flush()
        diff = {"evolucion_id": nueva.id}
        if datos.corrige_a_id is not None:
            diff["corrige_a_id"] = datos.corrige_a_id
        registrar_evento(
            session, auth, "corregir" if datos.corrige_a_id else "crear", "evolucion", nueva.id,
            paciente.id, diff,
        )  # fmt: skip
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _sqlstate(exc) == UNIQUE_VIOLATION and datos.corrige_a_id is not None:
            raise EvolucionYaCorregida(
                _vigente_de_la_cadena(session, auth.tenant_id, datos.corrige_a_id)
            ) from exc
        raise
    except Exception:
        session.rollback()
        raise
    session.refresh(nueva)
    return _evolucion_out(nueva, None)


def listar_evoluciones(
    session: Session, auth: "AuthContext", paciente: Paciente, after_id: int | None, limit: int
) -> tuple[list[EvolucionOut], int | None]:
    """Página de evoluciones y auditoría de la lectura (``entidad_id`` = paciente)."""
    items, cursor = evoluciones_pagina(session, auth.tenant_id, paciente.id, after_id, limit)
    registrar_evento(session, auth, "leer", "evolucion", paciente.id, paciente.id)
    session.commit()
    return items, cursor


def obtener_evolucion(
    session: Session, auth: "AuthContext", paciente: Paciente, evolucion_id: int
) -> EvolucionOut:
    """Una evolución del paciente (404 si es de otro) y auditoría de la lectura."""
    fila = session.execute(
        _con_corregida_por(session, auth.tenant_id, paciente.id).where(Evolucion.id == evolucion_id)
    ).one_or_none()
    if fila is None:
        raise EvolucionNoEncontrada()
    registrar_evento(
        session,
        auth,
        "leer",
        "evolucion",
        evolucion_id,
        paciente.id,
        {"evolucion_id": evolucion_id},
    )
    session.commit()
    return _evolucion_out(fila[0], fila[1])


# --- Historia consolidada ------------------------------------------------------------------


def historia_clinica(session: Session, auth: "AuthContext", paciente: Paciente) -> HistoriaOut:
    """Ficha + odontograma vigentes y 50 evoluciones, con UN solo evento de lectura (D5)."""
    ficha = ficha_vigente_fila(session, auth.tenant_id, paciente.id)
    odonto = odontograma_vigente(session, auth.tenant_id, paciente.id)
    evoluciones, cursor = evoluciones_pagina(
        session, auth.tenant_id, paciente.id, None, LIMITE_HISTORIA
    )
    registrar_evento(
        session, auth, "leer", "paciente", paciente.id, paciente.id,
        {"campos": ["ficha", "odontograma", "evoluciones"]},
    )  # fmt: skip
    session.commit()
    return HistoriaOut(
        ficha=FichaOut.model_validate(ficha, from_attributes=True)
        if ficha
        else FichaOut(version=0),
        odontograma=odontograma_out(odonto),
        evoluciones=evoluciones,
        next_cursor=cursor,
    )
