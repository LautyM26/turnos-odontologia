"""005 turnos: tabla ``turno`` con anti-solapamiento duro en la base (C-05 recorte).

Dos exclusion constraints GiST (por profesional y por sillon, dentro de la clinica) sobre el
rango semiabierto ``[inicio, fin)`` y solo para turnos activos (``reservado``, ``confirmado``,
``asistido`` y no dados de baja). ``sobreturno`` queda fuera del predicado a proposito
(RN-AG-04). Requiere ``btree_gist`` (la 003 ya la crea; ``IF NOT EXISTS`` es idempotente y el
downgrade NO la elimina porque la usa ``bloqueo``). Agrega ``UNIQUE (clinica_id, id)`` en
``prestacion`` para la FK compuesta por tenant (aditivo).

ROLLBACK: ``alembic downgrade 004_pacientes_ficha`` borra ``turno`` (se pierden los turnos
cargados) y ``uq_prestacion_clinica_id``. Con datos reales se hace roll-forward.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSTZRANGE

from alembic import op

revision: str = "005_turnos"
down_revision: str | None = "004_pacientes_ficha"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIVO = "is_active AND estado IN ('reservado','confirmado','asistido')"


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


def _fk(col: str, tabla: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["clinica_id", col],
        [f"{tabla}.clinica_id", f"{tabla}.id"],
        name=f"fk_turno_{col.removesuffix('_id')}",
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_unique_constraint("uq_prestacion_clinica_id", "prestacion", ["clinica_id", "id"])

    op.create_table(
        "turno",
        _pk_identity(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=False),
        sa.Column("sillon_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("prestacion_id", sa.BigInteger(), nullable=False),
        sa.Column("duracion_min", sa.Integer(), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "rango",
            TSTZRANGE(),
            sa.Computed("tstzrange(inicio, fin, '[)')", persisted=True),
            nullable=True,
        ),
        sa.Column("estado", sa.Text(), server_default="reservado", nullable=False),
        sa.Column("origen", sa.Text(), server_default="mostrador", nullable=False),
        *_audit_columns(),
        _clinica_fk("turno"),
        _fk("profesional_id", "profesional"),
        _fk("sillon_id", "sillon_recurso"),
        _fk("paciente_id", "paciente"),
        _fk("prestacion_id", "prestacion"),
        sa.CheckConstraint("fin > inicio", name="fin_posterior"),
        sa.CheckConstraint("duracion_min BETWEEN 5 AND 480", name="duracion_rango"),
        sa.CheckConstraint(
            "estado IN ('reservado','confirmado','asistido','ausente','cancelado','sobreturno')",
            name="estado_valido",
        ),
        sa.CheckConstraint(
            "origen IN ('enlace','mostrador','whatsapp','lista_espera')", name="origen_valido"
        ),
    )
    op.create_index(
        "ix_turno_clinica_profesional_inicio", "turno", ["clinica_id", "profesional_id", "inicio"]
    )
    op.create_index(
        "ix_turno_clinica_sillon_inicio", "turno", ["clinica_id", "sillon_id", "inicio"]
    )
    op.create_index(
        "ix_turno_clinica_paciente_inicio", "turno", ["clinica_id", "paciente_id", "inicio"]
    )
    op.create_index("ix_turno_clinica_estado", "turno", ["clinica_id", "estado"])

    op.execute(
        "ALTER TABLE turno ADD CONSTRAINT ex_turno_profesional_rango "
        f"EXCLUDE USING gist (clinica_id WITH =, profesional_id WITH =, rango WITH &&) "
        f"WHERE ({_ACTIVO})"
    )
    op.execute(
        "ALTER TABLE turno ADD CONSTRAINT ex_turno_sillon_rango "
        f"EXCLUDE USING gist (clinica_id WITH =, sillon_id WITH =, rango WITH &&) "
        f"WHERE ({_ACTIVO})"
    )


def downgrade() -> None:
    op.drop_table("turno")  # arrastra constraints e indices
    op.drop_constraint("uq_prestacion_clinica_id", "prestacion", type_="unique")
    # btree_gist se conserva a proposito: la usa bloqueo.
