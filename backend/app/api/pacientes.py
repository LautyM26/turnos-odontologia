"""Router de pacientes (C-08): datos administrativos, ficha versionada, adjuntos, auditoría.

Orden de chequeo: auth (401) -> rol (403) -> paciente en tenant (404) -> vínculo (403)
-> consentimiento (403, solo escrituras clínicas) -> validación de payload/archivo.
Sin DELETE de pacientes ni de auditoría (405). Logs: solo ids, nunca PII/PHI.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, get_current_user, require_tenant_checked
from app.api.permissions import (
    require_clinico,
    require_clinico_escritura,
    require_role,
    require_vinculo_paciente,
)
from app.domain.agenda.schemas import Pagina
from app.domain.pacientes import servicios
from app.domain.pacientes.models import Paciente
from app.domain.pacientes.schemas import (
    AdjuntoOut,
    AuditoriaOut,
    FichaOut,
    FichaPut,
    PacienteCreate,
    PacienteOut,
    PacienteUpdate,
)
from app.infrastructure.db import get_session
from app.infrastructure.settings import get_settings
from app.infrastructure.storage.adjuntos import AdjuntoStorage, LocalDirStorage

router = APIRouter(prefix="/api/pacientes", tags=["pacientes"])

Sesion = Annotated[Session, Depends(get_session)]
Tenant = Annotated[int, Depends(require_tenant_checked)]
Staff = Annotated[AuthContext, Depends(require_role("admin", "recepcionista", "odontologo"))]


@router.post("", response_model=PacienteOut, status_code=201)
def crear(datos: PacienteCreate, auth: Staff, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return servicios.crear_paciente(session, auth, datos)


@router.get("", response_model=Pagina[PacienteOut])
def buscar(  # type: ignore[no-untyped-def]
    auth: Staff,
    session: Sesion,
    tenant: Tenant,
    dni: str | None = None,
    telefono: str | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    after_id: Annotated[int | None, Query(ge=0)] = None,
):
    items, cursor = servicios.buscar_pacientes(session, tenant, after_id, limit, dni, telefono, q)
    return Pagina[PacienteOut](
        items=[PacienteOut.model_validate(i) for i in items], next_cursor=cursor
    )


@router.get("/{paciente_id}", response_model=PacienteOut)
def obtener(paciente_id: int, auth: Staff, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return servicios.obtener_paciente(session, tenant, paciente_id)


@router.patch("/{paciente_id}", response_model=PacienteOut)
def actualizar(  # type: ignore[no-untyped-def]
    paciente_id: int, datos: PacienteUpdate, auth: Staff, session: Sesion, tenant: Tenant
):
    return servicios.actualizar_paciente(session, auth, paciente_id, datos)


# --- Clínico: ficha / adjuntos / auditoría -------------------------------------------------

CONSENTIMIENTO_FALTANTE = "Falta el consentimiento de datos del paciente"


def paciente_lectura(
    auth: Annotated[AuthContext, Depends(require_clinico())],
    paciente: Annotated[Paciente, Depends(require_vinculo_paciente)],
) -> Paciente:
    """Lectura clínica: rol admin/odontólogo -> paciente del tenant (404) -> vínculo (403)."""
    return paciente


def paciente_escritura(
    auth: Annotated[AuthContext, Depends(require_clinico_escritura())],
    paciente: Annotated[Paciente, Depends(require_vinculo_paciente)],
) -> Paciente:
    """Escritura clínica: solo odontólogo; sin consentimiento -> 403 antes de validar payload."""
    if not paciente.consentimiento_datos:
        raise HTTPException(status_code=403, detail=CONSENTIMIENTO_FALTANTE)
    return paciente


Auth = Annotated[AuthContext, Depends(get_current_user)]
Lectura = Annotated[Paciente, Depends(paciente_lectura)]
Escritura = Annotated[Paciente, Depends(paciente_escritura)]


def _ficha_out(fila) -> FichaOut:  # type: ignore[no-untyped-def]
    if fila is None:
        return FichaOut(version=0)
    return FichaOut(
        version=fila.version,
        anamnesis=fila.anamnesis,
        alergias=fila.alergias,
        antecedentes=fila.antecedentes,
        autor_usuario_id=fila.autor_usuario_id,
        created_at=fila.created_at,
    )


@router.get("/{paciente_id}/ficha", response_model=FichaOut)
def leer_ficha(paciente: Lectura, auth: Auth, session: Sesion):  # type: ignore[no-untyped-def]
    return _ficha_out(servicios.leer_ficha(session, auth, paciente))


@router.put("/{paciente_id}/ficha", response_model=FichaOut)
def guardar_ficha(paciente: Escritura, datos: FichaPut, auth: Auth, session: Sesion):  # type: ignore[no-untyped-def]
    return _ficha_out(servicios.guardar_ficha(session, auth, paciente, datos))


@router.get("/{paciente_id}/ficha/versiones", response_model=list[FichaOut])
def versiones_ficha(paciente: Lectura, auth: Auth, session: Sesion):  # type: ignore[no-untyped-def]
    return [_ficha_out(f) for f in servicios.listar_versiones_ficha(session, auth, paciente)]


def get_adjunto_storage() -> AdjuntoStorage:
    """Storage configurado (directorio local); sobreescribible en tests."""
    return LocalDirStorage(get_settings().adjuntos_storage_dir)


Storage = Annotated[AdjuntoStorage, Depends(get_adjunto_storage)]
_EXTENSIONES = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}


@router.get("/{paciente_id}/adjuntos", response_model=list[AdjuntoOut])
def listar_adjuntos(paciente: Lectura, auth: Auth, session: Sesion):  # type: ignore[no-untyped-def]
    return servicios.listar_adjuntos(session, auth.tenant_id, paciente.id)


@router.post("/{paciente_id}/adjuntos", status_code=201, response_model=AdjuntoOut)
async def subir_adjunto(  # type: ignore[no-untyped-def]
    request: Request,
    paciente: Escritura,
    file: UploadFile,
    auth: Auth,
    session: Sesion,
    storage: Storage,
):
    """Solo el campo ``file``: cualquier otro (p. ej. ``evolucion_id``) -> 422."""
    form = await request.form()
    if set(form.keys()) != {"file"}:
        raise HTTPException(status_code=422, detail="Solo se acepta el campo 'file'")
    maximo = get_settings().adjunto_max_bytes
    return await run_in_threadpool(
        servicios.subir_adjunto,
        session, auth, paciente, file.file, file.content_type, file.filename, storage, maximo,
    )  # fmt: skip


@router.get("/{paciente_id}/adjuntos/{adjunto_id}/contenido")
def contenido_adjunto(  # type: ignore[no-untyped-def]
    adjunto_id: int, paciente: Lectura, auth: Auth, session: Sesion, storage: Storage
):
    adjunto, fh = servicios.descargar_adjunto(session, auth, paciente, adjunto_id, storage)

    def leer() -> Iterator[bytes]:
        with fh:
            while bloque := fh.read(servicios.CHUNK):
                yield bloque

    nombre = f"adjunto-{adjunto.id}.{_EXTENSIONES[adjunto.mime]}"
    return StreamingResponse(
        leer(),
        media_type=adjunto.mime,
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + nombre,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/{paciente_id}/auditoria", response_model=Pagina[AuditoriaOut])
def auditoria(  # type: ignore[no-untyped-def]
    paciente_id: int,
    auth: Annotated[AuthContext, Depends(require_role("admin"))],
    session: Sesion,
    tenant: Tenant,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    after_id: Annotated[int | None, Query(ge=0)] = None,
):
    """Solo admin; solo lectura (el resto de métodos -> 405)."""
    servicios.obtener_paciente(session, tenant, paciente_id)
    items, cursor = servicios.listar_auditoria(session, tenant, paciente_id, after_id, limit)
    return Pagina[AuditoriaOut](
        items=[AuditoriaOut.model_validate(i) for i in items], next_cursor=cursor
    )
