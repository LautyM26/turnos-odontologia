"""Base + mixins: naming convention FK y columnas obligatorias (Tasks 1.1)."""

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import NAMING_CONVENTION, Base
from app.infrastructure.persistence.mixins import AuditMixin, TenantMixin


def test_naming_convention_fk_estable() -> None:
    assert NAMING_CONVENTION["fk"] == "fk_%(table_name)s_%(column_0_name)s"
    assert Base.metadata.naming_convention["fk"] == NAMING_CONVENTION["fk"]


def test_mixins_exponen_columnas_obligatorias() -> None:
    assert TenantMixin.__abstract_attrs__ == ("clinica_id",)
    assert AuditMixin.__abstract_attrs__ == (
        "is_active",
        "created_at",
        "updated_at",
        "deleted_at",
    )


def test_tenant_mixin_es_not_null_y_audit_timestamps_tz() -> None:
    class Probe(Base, TenantMixin, AuditMixin):
        __tablename__ = "probe_mixin_check"

        id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    cols = Probe.__table__.columns
    assert cols["clinica_id"].nullable is False
    assert cols["is_active"].nullable is False
    assert cols["created_at"].type.timezone is True
    assert cols["deleted_at"].nullable is True
