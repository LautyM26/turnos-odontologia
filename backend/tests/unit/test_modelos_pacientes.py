"""Forma de los modelos ORM de pacientes/auditoría (C-08 4.1)."""

from sqlalchemy import DateTime

from app.domain.auditoria.models import AuditoriaHC
from app.domain.pacientes.models import Adjunto, FichaVersion, Paciente
from app.infrastructure.persistence.mixins import AuditMixin, TenantMixin


def test_paciente_y_adjunto_componen_tenant_y_audit() -> None:
    for modelo in (Paciente, Adjunto):
        assert issubclass(modelo, TenantMixin)
        assert issubclass(modelo, AuditMixin)


def test_ficha_y_auditoria_son_tenant_pero_sin_update_ni_soft_delete() -> None:
    for modelo in (FichaVersion, AuditoriaHC):
        assert issubclass(modelo, TenantMixin)
        assert not issubclass(modelo, AuditMixin)
        columnas = set(modelo.__table__.columns.keys())
        assert "clinica_id" in columnas
        assert "created_at" in columnas
        assert not columnas & {"updated_at", "deleted_at", "is_active"}


def test_columnas_temporales_son_timestamptz() -> None:
    for modelo in (Paciente, FichaVersion, Adjunto, AuditoriaHC):
        temporales = [
            c for c in modelo.__table__.columns if isinstance(c.type, DateTime)
        ]
        assert temporales, modelo.__tablename__
        assert all(c.type.timezone for c in temporales), modelo.__tablename__


def test_paciente_tiene_unicos_tenant() -> None:
    nombres = {c.name for c in Paciente.__table__.constraints if c.name}
    assert {"uq_paciente_clinica_id", "uq_paciente_clinica_dni"} <= nombres
