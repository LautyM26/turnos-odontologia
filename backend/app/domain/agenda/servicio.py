"""Servicio del catalogo de agenda (C-04): CRUD tenant-scoped + reglas de referencia.

Errores de dominio (``CatalogoError``) se traducen a HTTP en ``create_app()``:
no encontrado/ajeno -> 404, referencia invalida -> 422, unicidad -> 409.
El servicio hace commit; los routers no tocan la transaccion.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.agenda.models import (
    Bloqueo,
    Profesional,
    ProfesionalSillon,
    SillonRecurso,
)
from app.domain.agenda.schemas import validar_rango
from app.domain.core.models import Usuario
from app.infrastructure.persistence.repository import BaseRepository

UNIQUE_VIOLATION = "23505"


class CatalogoError(Exception):
    """Error de dominio con status HTTP asociado."""

    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NoEncontrado(CatalogoError):
    status_code = 404


class Conflicto(CatalogoError):
    status_code = 409


class ReferenciaInvalida(CatalogoError):
    status_code = 422


def _commit(session: Session, mensaje_conflicto: str) -> None:
    """Commit; una violacion de unicidad se traduce a 409, el resto se propaga."""
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == UNIQUE_VIOLATION:
            raise Conflicto(mensaje_conflicto) from exc
        raise


# --- CRUD generico (sillones, prestaciones, profesionales, bloqueos) ----------------------


def listar[M](
    session: Session,
    modelo: type[M],
    clinica_id: int,
    after_id: int | None,
    limit: int,
    incluir_inactivos: bool = False,
    *filtros: Any,
) -> tuple[Sequence[M], int | None]:
    return BaseRepository(session, modelo, clinica_id).page(  # type: ignore[type-var]
        after_id, limit, incluir_inactivos, *filtros
    )


def obtener[M](session: Session, modelo: type[M], clinica_id: int, row_id: int) -> M:
    """Fila activa del tenant; ajena, inexistente o dada de baja -> 404."""
    fila = BaseRepository(session, modelo, clinica_id).get(row_id)  # type: ignore[type-var]
    if fila is None:
        raise NoEncontrado("No encontrado")
    return fila


def crear[M](
    session: Session, modelo: type[M], clinica_id: int, datos: dict[str, Any], conflicto: str
) -> M:
    fila = modelo(**datos)
    BaseRepository(session, modelo, clinica_id).add(fila)  # type: ignore[type-var]
    _commit(session, conflicto)
    session.refresh(fila)
    return fila


def actualizar[M](
    session: Session,
    modelo: type[M],
    clinica_id: int,
    row_id: int,
    datos: dict[str, Any],
    conflicto: str,
) -> M:
    fila = obtener(session, modelo, clinica_id, row_id)
    for campo, valor in datos.items():
        setattr(fila, campo, valor)
    _commit(session, conflicto)
    session.refresh(fila)
    return fila


def dar_de_baja[M](session: Session, modelo: type[M], clinica_id: int, row_id: int) -> None:
    """Baja logica (nunca DELETE fisico)."""
    fila = obtener(session, modelo, clinica_id, row_id)
    BaseRepository(session, modelo, clinica_id).delete(fila)  # type: ignore[type-var]
    session.commit()


# --- Profesionales ------------------------------------------------------------------------

CONFLICTO_MATRICULA = "Ya existe un profesional activo con esa matricula"
CONFLICTO_SILLON = "Ya existe un sillon activo con ese nombre"
CONFLICTO_USUARIO = "El usuario ya esta vinculado a otro profesional activo"


def validar_vinculo_usuario(
    session: Session, clinica_id: int, usuario_id: int, profesional_id: int | None = None
) -> None:
    """Usuario del tenant y activo (422); sin otro profesional activo vinculado (409)."""
    usuario = session.scalars(
        select(Usuario).where(Usuario.id == usuario_id, Usuario.clinica_id == clinica_id)
    ).one_or_none()
    if usuario is None or not usuario.is_active:
        raise ReferenciaInvalida("usuario_id inexistente, inactivo o de otra clinica")
    stmt = select(Profesional.id).where(
        Profesional.clinica_id == clinica_id,
        Profesional.usuario_id == usuario_id,
        Profesional.is_active.is_(True),
    )
    if profesional_id is not None:
        stmt = stmt.where(Profesional.id != profesional_id)
    if session.scalars(stmt).first() is not None:
        raise Conflicto(CONFLICTO_USUARIO)


def crear_profesional(session: Session, clinica_id: int, datos: dict[str, Any]) -> Profesional:
    if datos.get("usuario_id") is not None:
        validar_vinculo_usuario(session, clinica_id, datos["usuario_id"])
    return crear(session, Profesional, clinica_id, datos, CONFLICTO_MATRICULA)


def actualizar_profesional(
    session: Session, clinica_id: int, row_id: int, datos: dict[str, Any]
) -> Profesional:
    if datos.get("usuario_id") is not None:
        validar_vinculo_usuario(session, clinica_id, datos["usuario_id"], row_id)
    return actualizar(session, Profesional, clinica_id, row_id, datos, CONFLICTO_MATRICULA)


def sillon_ids_de(
    session: Session, clinica_id: int, profesional_ids: Sequence[int]
) -> dict[int, list[int]]:
    """Sillones activos habilitados por profesional (ordenados)."""
    if not profesional_ids:
        return {}
    filas = session.execute(
        select(ProfesionalSillon.profesional_id, ProfesionalSillon.sillon_id)
        .join(
            SillonRecurso,
            (SillonRecurso.id == ProfesionalSillon.sillon_id)
            & (SillonRecurso.clinica_id == ProfesionalSillon.clinica_id),
        )
        .where(
            ProfesionalSillon.clinica_id == clinica_id,
            ProfesionalSillon.profesional_id.in_(profesional_ids),
            ProfesionalSillon.is_active.is_(True),
            SillonRecurso.is_active.is_(True),
        )
        .order_by(ProfesionalSillon.sillon_id)
    ).all()
    out: dict[int, list[int]] = {pid: [] for pid in profesional_ids}
    for pid, sid in filas:
        out[pid].append(sid)
    return out


def reemplazar_habilitacion(
    session: Session, clinica_id: int, profesional_id: int, sillon_ids: list[int]
) -> Profesional:
    """Reemplaza el set de sillones habilitados en una sola transaccion (todo o nada)."""
    profesional = obtener(session, Profesional, clinica_id, profesional_id)
    if sillon_ids:
        validos = set(
            session.scalars(
                select(SillonRecurso.id).where(
                    SillonRecurso.clinica_id == clinica_id,
                    SillonRecurso.id.in_(sillon_ids),
                    SillonRecurso.is_active.is_(True),
                )
            ).all()
        )
        if validos != set(sillon_ids):
            raise ReferenciaInvalida("sillon_ids con sillones inexistentes, inactivos o ajenos")
    existentes = {
        fila.sillon_id: fila
        for fila in session.scalars(
            select(ProfesionalSillon).where(
                ProfesionalSillon.clinica_id == clinica_id,
                ProfesionalSillon.profesional_id == profesional_id,
            )
        ).all()
    }
    repo = BaseRepository(session, ProfesionalSillon, clinica_id)
    for sid, fila in existentes.items():
        if sid in sillon_ids and not fila.is_active:
            fila.is_active = True
            fila.deleted_at = None
        elif sid not in sillon_ids and fila.is_active:
            repo.delete(fila)
    for sid in sillon_ids:
        if sid not in existentes:
            repo.add(ProfesionalSillon(profesional_id=profesional_id, sillon_id=sid))
    session.commit()
    return profesional


def profesional_de_usuario(session: Session, usuario_id: int) -> int | None:
    """Profesional activo vinculado al usuario (hook ``set_resolver_agenda_propia``)."""
    return session.scalars(
        select(Profesional.id).where(
            Profesional.usuario_id == usuario_id, Profesional.is_active.is_(True)
        )
    ).first()


# --- Bloqueos -----------------------------------------------------------------------------


def _validar_referencias_bloqueo(
    session: Session, clinica_id: int, profesional_id: int | None, sillon_id: int | None
) -> None:
    if profesional_id is not None:
        profesional = BaseRepository(session, Profesional, clinica_id).get(profesional_id)
        if profesional is None:
            raise ReferenciaInvalida("profesional_id inexistente, inactivo o de otra clinica")
    if sillon_id is not None:
        sillon = BaseRepository(session, SillonRecurso, clinica_id).get(sillon_id)
        if sillon is None:
            raise ReferenciaInvalida("sillon_id inexistente, inactivo o de otra clinica")


def crear_bloqueo(session: Session, clinica_id: int, datos: dict[str, Any]) -> Bloqueo:
    _validar_referencias_bloqueo(
        session, clinica_id, datos.get("profesional_id"), datos.get("sillon_id")
    )
    return crear(session, Bloqueo, clinica_id, datos, "Bloqueo duplicado")


def actualizar_bloqueo(
    session: Session, clinica_id: int, row_id: int, datos: dict[str, Any]
) -> Bloqueo:
    """Aplica cambios parciales y revalida el rango resultante (422)."""
    fila = obtener(session, Bloqueo, clinica_id, row_id)
    try:
        validar_rango(datos.get("inicio", fila.inicio), datos.get("fin", fila.fin))
    except ValueError as exc:
        raise ReferenciaInvalida(str(exc)) from exc
    return actualizar(session, Bloqueo, clinica_id, row_id, datos, "Bloqueo duplicado")


def listar_bloqueos(
    session: Session,
    clinica_id: int,
    after_id: int | None,
    limit: int,
    incluir_inactivos: bool = False,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    profesional_id: int | None = None,
    sillon_id: int | None = None,
) -> tuple[Sequence[Bloqueo], int | None]:
    """Lista paginada; con ventana devuelve solo los que se superponen con ``[desde, hasta)``."""
    filtros = []
    if desde is not None:
        filtros.append(Bloqueo.fin > desde)
    if hasta is not None:
        filtros.append(Bloqueo.inicio < hasta)
    if profesional_id is not None:
        filtros.append(Bloqueo.profesional_id == profesional_id)
    if sillon_id is not None:
        filtros.append(Bloqueo.sillon_id == sillon_id)
    return listar(session, Bloqueo, clinica_id, after_id, limit, incluir_inactivos, *filtros)


def listar_bloqueos_de_profesional(
    session: Session,
    clinica_id: int,
    profesional_id: int,
    after_id: int | None,
    limit: int,
    desde: datetime | None = None,
    hasta: datetime | None = None,
) -> tuple[Sequence[Bloqueo], int | None]:
    obtener(session, Profesional, clinica_id, profesional_id)  # 404 si ajeno/inactivo
    return listar_bloqueos(
        session, clinica_id, after_id, limit, False, desde, hasta, profesional_id=profesional_id
    )


def crear_bloqueo_de_profesional(
    session: Session, clinica_id: int, profesional_id: int, datos: dict[str, Any]
) -> Bloqueo:
    obtener(session, Profesional, clinica_id, profesional_id)
    return crear_bloqueo(session, clinica_id, datos | {"profesional_id": profesional_id})


def dar_de_baja_bloqueo_de_profesional(
    session: Session, clinica_id: int, profesional_id: int, bloqueo_id: int
) -> None:
    """404 si el bloqueo no existe, es de otra clinica o no pertenece a ese profesional."""
    obtener(session, Profesional, clinica_id, profesional_id)
    bloqueo = obtener(session, Bloqueo, clinica_id, bloqueo_id)
    if bloqueo.profesional_id != profesional_id:
        raise NoEncontrado("No encontrado")
    dar_de_baja(session, Bloqueo, clinica_id, bloqueo_id)
