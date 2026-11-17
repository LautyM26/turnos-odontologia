"""Router de cumplimiento para administradores (C-18): usuarios y exportación del tenant.

Todas las rutas exigen rol ``admin`` (``require_admin()``; 401 sin token, 403 otro rol) y
trabajan solo sobre la clínica del JWT: un usuario de otra clínica es 404. No hay PUT ni DELETE.

Exportación (RN-CU-04): ``GET /api/admin/exportacion?formato=csv`` devuelve un ZIP con un CSV
UTF-8 con BOM por entidad (fechas ISO 8601 con zona, celdas con ``=+-@`` neutralizadas), los
archivos de adjuntos y ``manifest.json``. Quedan afuera ``password_hash`` y las entidades que
aún no existen (caja, facturas: se declaran en ``manifest.excluidas``). PDF no está soportado
(422). El ZIP se arma completo antes de responder y cada exportación exitosa se audita.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_tenant_checked
from app.api.pacientes import get_adjunto_storage
from app.api.permissions import require_admin
from app.domain.agenda.schemas import Pagina
from app.domain.auditoria.writer import registrar_evento_admin
from app.domain.cumplimiento import exportador
from app.domain.usuarios import servicios as usuarios
from app.domain.usuarios.schemas import RolesIn, UsuarioAdminIn, UsuarioAdminOut
from app.infrastructure.db import get_session
from app.infrastructure.storage.adjuntos import AdjuntoStorage

router = APIRouter(prefix="/api/admin", tags=["admin-cumplimiento"])

Admin = Annotated[AuthContext, Depends(require_admin())]
Sesion = Annotated[Session, Depends(get_session)]
Tenant = Annotated[int, Depends(require_tenant_checked)]
Storage = Annotated[AdjuntoStorage, Depends(get_adjunto_storage)]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/usuarios", response_model=Pagina[UsuarioAdminOut])
def listar_usuarios(  # type: ignore[no-untyped-def]
    auth: Admin,
    session: Sesion,
    tenant: Tenant,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    after_id: Annotated[int | None, Query(ge=0)] = None,
):
    """Usuarios de la clínica con sus roles activos (sin hashes), paginados por cursor."""
    items, cursor = usuarios.listar_usuarios(session, tenant, after_id, limit)
    return Pagina[UsuarioAdminOut](items=items, next_cursor=cursor)


@router.post("/usuarios", response_model=UsuarioAdminOut, status_code=201)
def crear_usuario(  # type: ignore[no-untyped-def]
    request: Request, datos: UsuarioAdminIn, auth: Admin, session: Sesion, tenant: Tenant
):
    """Alta en la clínica del admin; email repetido -> 409."""
    return usuarios.crear_usuario(session, auth, datos, _ip(request))


@router.patch("/usuarios/{usuario_id}/roles", response_model=UsuarioAdminOut)
def reemplazar_roles(  # type: ignore[no-untyped-def]
    usuario_id: int,
    request: Request,
    datos: RolesIn,
    auth: Admin,
    session: Sesion,
    tenant: Tenant,
):
    """Reemplaza los roles activos; quitar el último admin -> 409."""
    return usuarios.reemplazar_roles(session, auth, usuario_id, datos, _ip(request))


def _chunks(archivo: Any) -> Iterator[bytes]:
    try:
        while bloque := archivo.read(exportador.CHUNK):
            yield bloque
    finally:
        archivo.close()


@router.get("/exportacion")
def exportar(  # type: ignore[no-untyped-def]
    request: Request,
    auth: Admin,
    session: Sesion,
    tenant: Tenant,
    storage: Storage,
    formato: str = "csv",
):
    """ZIP completo del tenant; sin costo ni límite de cantidad (RN-CU-04)."""
    exportador.validar_formato(formato)
    archivo, manifest = exportador.construir_zip(session, tenant, storage)
    try:
        registrar_evento_admin(
            session, auth, "exportar", None,
            {
                "formato": formato,
                "conteos": manifest["conteos"],
                "faltantes": manifest["faltantes"],
            },
            _ip(request),
        )  # fmt: skip
        session.commit()
    except Exception:
        session.rollback()
        archivo.close()
        raise
    marca = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return StreamingResponse(
        _chunks(archivo),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="exportacion-clinica-{tenant}-{marca}.zip"'
            ),
            "Cache-Control": "no-store",
        },
    )
