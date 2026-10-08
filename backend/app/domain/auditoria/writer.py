"""Writer de auditoría HC (C-08, D8): solo inserta, en la transacción del llamador.

El diff admite únicamente una allowlist de claves (nombres de campos, versiones, ids y
booleanos de consentimiento): nunca texto clínico, contacto ni nombres de archivo.
No existe API de actualización ni de borrado (la DB además lo impide por trigger).
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.domain.auditoria.models import ACCIONES, ENTIDADES, AuditoriaHC

if TYPE_CHECKING:
    from app.api.deps import AuthContext

#: clave de diff -> validador del valor.
_DIFF_PERMITIDO: dict[str, Any] = {
    "campos": lambda v: isinstance(v, list) and all(isinstance(c, str) for c in v),
    "version": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "ficha_version_id": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "adjunto_id": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "consentimiento_datos": lambda v: isinstance(v, bool),
}


def _validar_diff(diff: dict[str, Any]) -> None:
    for clave, valor in diff.items():
        validador = _DIFF_PERMITIDO.get(clave)
        if validador is None:
            raise ValueError(f"Clave de diff no permitida en auditoría: {clave!r}")
        if not validador(valor):
            raise ValueError(f"Valor inválido para la clave de diff {clave!r}")


def registrar_evento(
    session: Session,
    auth: "AuthContext",
    accion: str,
    entidad: str,
    entidad_id: int,
    paciente_id: int,
    diff: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditoriaHC:
    """Agrega el evento a la sesión del llamador (flush, sin commit).

    ``created_at`` lo asigna la DB (``now()``). Si la transacción del llamador se revierte,
    el evento también (atomicidad con la operación auditada).
    """
    if accion not in ACCIONES:
        raise ValueError(f"Acción de auditoría inválida: {accion!r}")
    if entidad not in ENTIDADES:
        raise ValueError(f"Entidad de auditoría inválida: {entidad!r}")
    contenido = dict(diff or {})
    _validar_diff(contenido)
    evento = AuditoriaHC(
        clinica_id=auth.tenant_id,
        paciente_id=paciente_id,
        actor_usuario_id=auth.sub,
        actor_tipo="usuario",
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        diff=contenido,
        ip=ip,
    )
    session.add(evento)
    session.flush()
    session.refresh(evento)
    return evento
