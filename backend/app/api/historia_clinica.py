"""Router de historia clínica (C-09): odontograma, evoluciones e historia consolidada.

Orden de chequeo (igual que la ficha de C-08): auth (401) -> rol (403) -> paciente en tenant
(404) -> vínculo (403) -> consentimiento (403, solo escrituras) -> validación del cuerpo (422)
-> reglas de negocio (422/403/409).

Append-only (RN-CL-02): no hay PUT, PATCH ni DELETE sobre odontograma ni evoluciones; como la
ruta existe con otros métodos, el servidor responde 405. Corregir una evolución es un POST con
``corrige_a_id`` + ``motivo_correccion``. El autor y la fecha/hora NUNCA vienen del cuerpo: el
autor sale del JWT (y su profesional vinculado) y la hora la pone el servidor.
Lecturas y escrituras quedan auditadas sin texto clínico en el diff.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, get_current_user
from app.api.pacientes import Escritura, Lectura, Sesion
from app.domain.agenda.schemas import Pagina
from app.domain.clinica import servicios
from app.domain.clinica.schemas import (
    EvolucionIn,
    EvolucionOut,
    HistoriaOut,
    OdontogramaIn,
    OdontogramaOut,
    odontograma_out,
)

router = APIRouter(prefix="/api/pacientes", tags=["historia-clinica"])

Auth = Annotated[AuthContext, Depends(get_current_user)]


@router.get("/{paciente_id}/odontograma/actual", response_model=OdontogramaOut)
def odontograma_actual(paciente: Lectura, auth: Auth, session: Sesion):  # type: ignore[no-untyped-def]
    """Versión vigente; ``version = 0`` y sin piezas si el paciente no tiene odontograma."""
    return odontograma_out(servicios.leer_odontograma_actual(session, auth, paciente))


@router.get("/{paciente_id}/odontograma", response_model=list[OdontogramaOut])
def historial_odontograma(paciente: Lectura, auth: Auth, session: Sesion):  # type: ignore[no-untyped-def]
    """Todas las versiones, la más nueva primero."""
    return [odontograma_out(v) for v in servicios.listar_odontogramas(session, auth, paciente)]


@router.post("/{paciente_id}/odontograma", response_model=OdontogramaOut, status_code=201)
def guardar_odontograma(  # type: ignore[no-untyped-def]
    paciente: Escritura, datos: OdontogramaIn, auth: Auth, session: Sesion
):
    """Guarda una versión completa nueva; ``version_esperada`` vieja -> 409."""
    return odontograma_out(servicios.guardar_odontograma(session, auth, paciente, datos))


@router.get("/{paciente_id}/evoluciones", response_model=Pagina[EvolucionOut])
def listar_evoluciones(  # type: ignore[no-untyped-def]
    paciente: Lectura,
    auth: Auth,
    session: Sesion,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    after_id: Annotated[int | None, Query(ge=0)] = None,
):
    """Más recientes primero, paginadas por cursor keyset."""
    items, cursor = servicios.listar_evoluciones(session, auth, paciente, after_id, limit)
    return Pagina[EvolucionOut](items=items, next_cursor=cursor)


@router.post("/{paciente_id}/evoluciones", response_model=EvolucionOut, status_code=201)
def registrar_evolucion(  # type: ignore[no-untyped-def]
    paciente: Escritura, datos: EvolucionIn, auth: Auth, session: Sesion
):
    """Alta o corrección (``corrige_a_id`` + ``motivo_correccion``); autor desde el JWT."""
    return servicios.registrar_evolucion(session, auth, paciente, datos)


@router.get("/{paciente_id}/evoluciones/{evolucion_id}", response_model=EvolucionOut)
def obtener_evolucion(  # type: ignore[no-untyped-def]
    evolucion_id: int, paciente: Lectura, auth: Auth, session: Sesion
):
    """Una evolución del paciente; la de otro paciente -> 404."""
    return servicios.obtener_evolucion(session, auth, paciente, evolucion_id)


@router.get("/{paciente_id}/historia", response_model=HistoriaOut)
def historia(paciente: Lectura, auth: Auth, session: Sesion):  # type: ignore[no-untyped-def]
    """Ficha + odontograma vigentes y las 50 evoluciones más recientes (un solo evento)."""
    return servicios.historia_clinica(session, auth, paciente)
