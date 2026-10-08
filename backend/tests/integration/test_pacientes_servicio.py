"""Servicio de pacientes (C-08 5.2): alta, dedupe por DNI, auditoría, sin Usuario."""

import pytest
from sqlalchemy import func, select

from app.api.deps import AuthContext
from app.domain.auditoria.models import AuditoriaHC
from app.domain.core.models import Usuario
from app.domain.pacientes.schemas import PacienteCreate
from app.domain.pacientes.servicios import PacienteDuplicado, crear_paciente


def _auth(auth_data, email: str, tenant: str = "clinica_a") -> AuthContext:  # type: ignore[no-untyped-def]
    return AuthContext(
        sub=auth_data["user_ids"][email],
        tenant_id=auth_data[tenant],
        roles=("recepcionista",),
        email=email,
        jti="j",
    )


def _datos(dni: str, **extra) -> PacienteCreate:  # type: ignore[no-untyped-def]
    base = {
        "nombre": "José",
        "apellido": "Pérez",
        "dni": dni,
        "telefono": "011 15 5555-0001",
    }
    return PacienteCreate(**{**base, **extra})


def _usuarios(session, clinica: int) -> int:  # type: ignore[no-untyped-def]
    stmt = select(func.count()).select_from(Usuario).where(Usuario.clinica_id == clinica)
    return session.scalar(stmt)


def test_crear_paciente_persiste_audita_y_no_crea_usuario(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    auth = _auth(auth_data, "recepcion@test.test")
    with session_factory() as session:
        antes = _usuarios(session, auth.tenant_id)
        paciente = crear_paciente(session, auth, _datos("90.100.001"))
        despues = _usuarios(session, auth.tenant_id)
        assert antes == despues
        assert paciente.id is not None
        assert paciente.clinica_id == auth.tenant_id
        assert paciente.dni == "90100001"
        assert paciente.telefono == "+5491155550001"
        assert paciente.nombre_busqueda == "perez jose"
        assert paciente.riesgo_ausencia == 0
        assert paciente.consentimiento_datos is False
        evento = session.scalars(
            select(AuditoriaHC).where(AuditoriaHC.entidad_id == paciente.id)
        ).one()
        assert (evento.accion, evento.entidad) == ("crear", "paciente")
        assert evento.actor_usuario_id == auth.sub
        assert evento.paciente_id == paciente.id
        assert "dni" in evento.diff["campos"]
        assert "90100001" not in str(evento.diff)


def test_dni_duplicado_con_otro_formato_levanta_conflicto(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    auth = _auth(auth_data, "recepcion@test.test")
    with session_factory() as session:
        original = crear_paciente(session, auth, _datos("90100002"))
        with pytest.raises(PacienteDuplicado) as exc:
            crear_paciente(session, auth, _datos("90.100.002"))
        assert exc.value.paciente_id == original.id
        total = session.scalar(
            select(func.count()).select_from(type(original)).where(type(original).dni == "90100002")
        )
        assert total == 1


def test_mismo_dni_en_otra_clinica_es_valido(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    a = _auth(auth_data, "recepcion@test.test")
    b = _auth(auth_data, "admin-b@test.test", tenant="clinica_b")
    with session_factory() as session:
        pa = crear_paciente(session, a, _datos("90100003"))
        pb = crear_paciente(session, b, _datos("90100003"))
        assert pa.id != pb.id
        assert (pa.clinica_id, pb.clinica_id) == (a.tenant_id, b.tenant_id)
