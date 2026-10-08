"""001 core models: clinica, rol, usuario, usuario_rol (C-02, D3/D4/D5).

Shared-schema sin RLS (D1); aislamiento a nivel app + índices por tenant.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001_core_models"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tstz(name: str, nullable: bool = True, default_now: bool = False) -> sa.Column:
    """TIMESTAMPTZ column helper (regla dura 7: tiempo SIEMPRE TIMESTAMPTZ)."""
    kwargs: dict = {"nullable": nullable}
    if default_now:
        kwargs["server_default"] = sa.func.now()
    return sa.Column(name, sa.DateTime(timezone=True), **kwargs)


def _audit_columns() -> list:
    """is_active + created_at/updated_at/deleted_at shared by every table."""
    return [
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        _tstz("created_at", nullable=False, default_now=True),
        _tstz("updated_at", nullable=False, default_now=True),
        _tstz("deleted_at"),
    ]


def _pk_identity() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True)


def upgrade() -> None:
    op.create_table(
        "clinica",
        _pk_identity(),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("cuit", sa.Text(), nullable=False),
        sa.Column("email_contacto", sa.Text(), nullable=True),
        sa.Column("moneda", sa.CHAR(3), server_default="ARS", nullable=False),
        sa.Column("sena_porcentaje", sa.Numeric(5, 2), nullable=True),
        sa.Column("sena_monto_minimo", sa.Numeric(12, 2), nullable=True),
        sa.Column("sena_obligatoria", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("es_seed", sa.Boolean(), server_default=sa.false(), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint("cuit", name="uq_clinica_cuit"),
        sa.CheckConstraint("length(nombre) > 0 AND length(nombre) <= 200", name="nombre_len"),
        sa.CheckConstraint("cuit ~ '^[0-9]{11}$'", name="cuit_formato"),
        sa.CheckConstraint("moneda = 'ARS'", name="moneda_ars"),
    )
    op.create_index(
        "ix_clinica_activa", "clinica", ["id"], postgresql_where=sa.text("is_active")
    )

    op.create_table(
        "rol",
        _pk_identity(),
        sa.Column("clave", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint("clave", name="uq_rol_clave"),
        sa.CheckConstraint("length(clave) > 0 AND length(clave) <= 50", name="clave_len"),
    )

    op.create_table(
        "usuario",
        _pk_identity(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["clinica_id"], ["clinica.id"], name="fk_usuario_clinica_id", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("length(email) > 0 AND length(email) <= 320", name="email_len"),
    )
    op.create_index(
        "uq_usuario_clinica_email",
        "usuario",
        ["clinica_id", sa.text("lower(email)")],
        unique=True,
    )
    op.create_index("ix_usuario_clinica_activo", "usuario", ["clinica_id", "is_active"])
    op.create_index(
        "ix_usuario_activos", "usuario", ["clinica_id"], postgresql_where=sa.text("is_active")
    )

    op.create_table(
        "usuario_rol",
        sa.Column("usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("rol_id", sa.BigInteger(), nullable=False),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        _tstz("asignado_en", nullable=False, default_now=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuario.id"],
            name="fk_usuario_rol_usuario_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rol_id"], ["rol.id"], name="fk_usuario_rol_rol_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["clinica_id"], ["clinica.id"],
            name="fk_usuario_rol_clinica_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("usuario_id", "rol_id", name="pk_usuario_rol"),
    )
    op.create_index("ix_usuario_rol_rol", "usuario_rol", ["rol_id"])
    op.create_index("ix_usuario_rol_clinica", "usuario_rol", ["clinica_id", "usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_usuario_rol_clinica", table_name="usuario_rol")
    op.drop_index("ix_usuario_rol_rol", table_name="usuario_rol")
    op.drop_table("usuario_rol")
    op.drop_index("ix_usuario_activos", table_name="usuario")
    op.drop_index("ix_usuario_clinica_activo", table_name="usuario")
    op.drop_index("uq_usuario_clinica_email", table_name="usuario")
    op.drop_table("usuario")
    op.drop_table("rol")
    op.drop_index("ix_clinica_activa", table_name="clinica")
    op.drop_table("clinica")
