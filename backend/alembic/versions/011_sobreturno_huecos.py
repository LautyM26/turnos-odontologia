"""011 sobreturno_huecos: sobreturno como marca en ``turno`` (C-05c, design D2).

Agrega ``es_sobreturno``/``motivo_sobreturno`` con CHECK de coherencia y recrea las dos
exclusion constraints con ``AND NOT es_sobreturno``: un sobreturno puede superponerse y seguir
el ciclo de estados de C-05b sin chocar (23P01). El estado ``sobreturno`` de la 005 queda en
el CHECK pero sin uso; filas que lo tuvieran se migran a ``reservado`` + marca.

Numeración: el 007 quedó reservado para C-05c, pero C-09/C-18/C-19 ya encadenaron
006 → 008 → 009 → 010. Insertar 007 en el medio rompería bases que ya están en 010, por eso
va al final de la cadena como 011.

Recrear las constraints toma un lock exclusivo sobre ``turno`` durante la migración (tabla
chica en MVP).

ROLLBACK: ``alembic downgrade 010_recetas_externas`` convierte los sobreturnos activos
(reservado/confirmado/asistido) a ``estado='sobreturno'`` para no violar el predicado viejo,
recrea las constraints de la 005 y borra las columnas (se pierde el motivo).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011_sobreturno_huecos"
down_revision: str | None = "010_recetas_externas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIVO_005 = "is_active AND estado IN ('reservado','confirmado','asistido')"
_ACTIVO_011 = "is_active AND NOT es_sobreturno AND estado IN ('reservado','confirmado','asistido')"
_RECURSOS = (
    ("ex_turno_profesional_rango", "profesional_id"),
    ("ex_turno_sillon_rango", "sillon_id"),
)


def _recrear_exclusiones(predicado: str) -> None:
    for nombre, col in _RECURSOS:
        op.execute(f"ALTER TABLE turno DROP CONSTRAINT {nombre}")
        op.execute(
            f"ALTER TABLE turno ADD CONSTRAINT {nombre} "
            f"EXCLUDE USING gist (clinica_id WITH =, {col} WITH =, rango WITH &&) "
            f"WHERE ({predicado})"
        )


def upgrade() -> None:
    op.add_column(
        "turno",
        sa.Column("es_sobreturno", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("turno", sa.Column("motivo_sobreturno", sa.Text(), nullable=True))
    op.execute(
        "UPDATE turno SET estado='reservado', es_sobreturno=true, "
        "motivo_sobreturno='(migrado desde estado sobreturno)' WHERE estado='sobreturno'"
    )
    op.create_check_constraint(
        op.f("ck_turno_sobreturno_coherente"),
        "turno",
        "es_sobreturno = (motivo_sobreturno IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_turno_motivo_sobreturno_largo"),
        "turno",
        "motivo_sobreturno IS NULL OR length(motivo_sobreturno) <= 500",
    )
    _recrear_exclusiones(_ACTIVO_011)


def downgrade() -> None:
    op.execute(
        "UPDATE turno SET estado='sobreturno' "
        "WHERE es_sobreturno AND estado IN ('reservado','confirmado','asistido')"
    )
    _recrear_exclusiones(_ACTIVO_005)
    op.drop_constraint(op.f("ck_turno_motivo_sobreturno_largo"), "turno", type_="check")
    op.drop_constraint(op.f("ck_turno_sobreturno_coherente"), "turno", type_="check")
    op.drop_column("turno", "motivo_sobreturno")
    op.drop_column("turno", "es_sobreturno")
