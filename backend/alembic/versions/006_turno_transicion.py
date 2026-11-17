"""006 turno_transicion: historial append-only de cambios de estado del turno (C-05b).

Una fila por transición aceptada (RN-TU-01, design D4): estado anterior/nuevo, actor, motivo
opcional y fecha del servidor. Inmutable: reutiliza ``fn_rechazar_mutacion()`` de la 004 con
triggers por fila (UPDATE/DELETE) y por sentencia (TRUNCATE). Agrega ``UNIQUE (clinica_id, id)``
en ``turno`` para la FK compuesta por tenant (aditivo, mismo patrón que la 005 en prestacion).

ROLLBACK: ``alembic downgrade 005_turnos`` borra el historial (se pierde la traza de
transiciones) y ``uq_turno_clinica_id``. NO borra ``fn_rechazar_mutacion()`` (es de la 004).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_turno_transicion"
down_revision: str | None = "005_turnos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ESTADOS = "('reservado','confirmado','asistido','ausente','cancelado','sobreturno')"
_TABLA = "turno_transicion"


def upgrade() -> None:
    op.create_unique_constraint("uq_turno_clinica_id", "turno", ["clinica_id", "id"])
    op.create_table(
        _TABLA,
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("turno_id", sa.BigInteger(), nullable=False),
        sa.Column("desde", sa.Text(), nullable=False),
        sa.Column("hacia", sa.Text(), nullable=False),
        sa.Column("actor_usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["clinica_id"], ["clinica.id"], name=f"fk_{_TABLA}_clinica_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["clinica_id", "turno_id"],
            ["turno.clinica_id", "turno.id"],
            name="fk_turno_transicion_turno",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["clinica_id", "actor_usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_turno_transicion_actor_usuario_id",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(f"desde IN {_ESTADOS}", name="desde_valido"),
        sa.CheckConstraint(f"hacia IN {_ESTADOS}", name="hacia_valido"),
        sa.CheckConstraint("motivo IS NULL OR length(motivo) <= 500", name="motivo_largo"),
    )
    op.create_index(
        "ix_turno_transicion_clinica_turno_id", _TABLA, ["clinica_id", "turno_id", "id"]
    )
    op.execute(
        f"CREATE TRIGGER trg_{_TABLA}_append_only_row BEFORE UPDATE OR DELETE ON {_TABLA} "
        "FOR EACH ROW EXECUTE FUNCTION fn_rechazar_mutacion()"
    )
    op.execute(
        f"CREATE TRIGGER trg_{_TABLA}_append_only_truncate BEFORE TRUNCATE ON {_TABLA} "
        "FOR EACH STATEMENT EXECUTE FUNCTION fn_rechazar_mutacion()"
    )


def downgrade() -> None:
    op.drop_table(_TABLA)  # arrastra triggers, índice y FKs
    op.drop_constraint("uq_turno_clinica_id", "turno", type_="unique")
