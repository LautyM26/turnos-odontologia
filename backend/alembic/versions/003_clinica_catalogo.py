"""003 clinica catalogo: profesional, sillon_recurso, prestacion, habilitacion, bloqueo (C-04).

Integridad tenant por FK compuesta (clinica_id, id). ``bloqueo.rango`` es una
columna generada ``tstzrange(inicio, fin, '[)')`` con indice GiST para que C-05
consulte solapamientos con ``&&``. El downgrade NO elimina ``btree_gist``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSTZRANGE

from alembic import op

revision: str = "003_clinica_catalogo"
down_revision: str | None = "002_token_blacklist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> list:
    return [
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _pk_identity() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True)


def _clinica_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["clinica_id"], ["clinica.id"], name=f"fk_{table}_clinica_id", ondelete="RESTRICT"
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_unique_constraint("uq_usuario_clinica_id", "usuario", ["clinica_id", "id"])

    op.create_table(
        "profesional",
        _pk_identity(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("matricula", sa.Text(), nullable=False),
        sa.Column("especialidad", sa.Text(), nullable=True),
        sa.Column("agenda_activa", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("tercerizado", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("usuario_id", sa.BigInteger(), nullable=True),
        sa.Column("es_seed", sa.Boolean(), server_default=sa.false(), nullable=False),
        *_audit_columns(),
        _clinica_fk("profesional"),
        sa.ForeignKeyConstraint(
            ["clinica_id", "usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_profesional_usuario",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("clinica_id", "id", name="uq_profesional_clinica_id"),
        sa.CheckConstraint("length(nombre) BETWEEN 1 AND 200", name="nombre_len"),
        sa.CheckConstraint("length(matricula) BETWEEN 1 AND 50", name="matricula_len"),
    )
    op.create_index(
        "uq_profesional_matricula_activa",
        "profesional",
        ["clinica_id", sa.text("lower(matricula)")],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "uq_profesional_usuario_activo",
        "profesional",
        ["clinica_id", "usuario_id"],
        unique=True,
        postgresql_where=sa.text("usuario_id IS NOT NULL AND is_active"),
    )
    op.create_index("ix_profesional_clinica_activo", "profesional", ["clinica_id", "is_active"])

    op.create_table(
        "sillon_recurso",
        _pk_identity(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("es_seed", sa.Boolean(), server_default=sa.false(), nullable=False),
        *_audit_columns(),
        _clinica_fk("sillon_recurso"),
        sa.UniqueConstraint("clinica_id", "id", name="uq_sillon_recurso_clinica_id"),
        sa.CheckConstraint("length(nombre) BETWEEN 1 AND 200", name="nombre_len"),
        sa.CheckConstraint("tipo IN ('sillon','box','equipo')", name="tipo_valido"),
    )
    op.create_index(
        "uq_sillon_recurso_nombre_activo",
        "sillon_recurso",
        ["clinica_id", sa.text("lower(nombre)")],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_sillon_recurso_clinica_activo", "sillon_recurso", ["clinica_id", "is_active"]
    )

    op.create_table(
        "prestacion",
        _pk_identity(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("duracion_min", sa.Integer(), nullable=False),
        sa.Column("precio_referencia", sa.Numeric(12, 2), nullable=False),
        sa.Column("es_seed", sa.Boolean(), server_default=sa.false(), nullable=False),
        *_audit_columns(),
        _clinica_fk("prestacion"),
        sa.CheckConstraint("length(nombre) BETWEEN 1 AND 200", name="nombre_len"),
        sa.CheckConstraint("duracion_min BETWEEN 5 AND 480", name="duracion_rango"),
        sa.CheckConstraint("precio_referencia >= 0", name="precio_no_negativo"),
    )
    op.create_index("ix_prestacion_clinica_activo", "prestacion", ["clinica_id", "is_active"])

    op.create_table(
        "profesional_sillon",
        sa.Column("profesional_id", sa.BigInteger(), nullable=False),
        sa.Column("sillon_id", sa.BigInteger(), nullable=False),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        *_audit_columns(),
        _clinica_fk("profesional_sillon"),
        sa.ForeignKeyConstraint(
            ["clinica_id", "profesional_id"],
            ["profesional.clinica_id", "profesional.id"],
            name="fk_profesional_sillon_profesional",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["clinica_id", "sillon_id"],
            ["sillon_recurso.clinica_id", "sillon_recurso.id"],
            name="fk_profesional_sillon_sillon",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("profesional_id", "sillon_id", name="pk_profesional_sillon"),
    )
    op.create_index(
        "ix_profesional_sillon_clinica_sillon", "profesional_sillon", ["clinica_id", "sillon_id"]
    )

    op.create_table(
        "bloqueo",
        _pk_identity(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=True),
        sa.Column("sillon_id", sa.BigInteger(), nullable=True),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column(
            "rango",
            TSTZRANGE(),
            sa.Computed("tstzrange(inicio, fin, '[)')", persisted=True),
            nullable=True,
        ),
        *_audit_columns(),
        _clinica_fk("bloqueo"),
        sa.ForeignKeyConstraint(
            ["clinica_id", "profesional_id"],
            ["profesional.clinica_id", "profesional.id"],
            name="fk_bloqueo_profesional",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["clinica_id", "sillon_id"],
            ["sillon_recurso.clinica_id", "sillon_recurso.id"],
            name="fk_bloqueo_sillon",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("fin > inicio", name="fin_posterior"),
        sa.CheckConstraint("fin - inicio <= interval '31 days'", name="duracion_maxima"),
        sa.CheckConstraint(
            "NOT (profesional_id IS NOT NULL AND sillon_id IS NOT NULL)", name="alcance_unico"
        ),
        sa.CheckConstraint("length(motivo) BETWEEN 1 AND 200", name="motivo_len"),
    )
    op.create_index(
        "ix_bloqueo_rango_activo",
        "bloqueo",
        ["clinica_id", "rango"],
        postgresql_using="gist",
        postgresql_where=sa.text("is_active"),
    )
    op.create_index("ix_bloqueo_clinica_profesional", "bloqueo", ["clinica_id", "profesional_id"])
    op.create_index("ix_bloqueo_clinica_sillon", "bloqueo", ["clinica_id", "sillon_id"])
    op.create_index("ix_bloqueo_clinica_activo", "bloqueo", ["clinica_id", "is_active"])


def downgrade() -> None:
    op.drop_table("bloqueo")
    op.drop_table("profesional_sillon")
    op.drop_table("prestacion")
    op.drop_table("sillon_recurso")
    op.drop_table("profesional")
    op.drop_constraint("uq_usuario_clinica_id", "usuario", type_="unique")
    # btree_gist se conserva a proposito: la necesita C-05 y otros objetos podrian depender.
