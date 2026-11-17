"""012 horario_atencion: franjas semanales por profesional y zona horaria de la clínica (C-05d).

``franja_horaria`` guarda día ISO (1 = lunes) y minutos desde la medianoche local
(``0 <= inicio_min < fin_min <= 1440``; 1440 = 24:00, día completo). Sin baja lógica: el
horario se reemplaza entero (design D1). ``clinica.zona_horaria`` (IANA) es la zona en que se
interpretan las franjas (D2).

ROLLBACK: ``alembic downgrade 011_sobreturno_huecos`` borra la tabla (se pierden los horarios
cargados) y la columna ``zona_horaria``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012_horario_atencion"
down_revision: str | None = "011_sobreturno_huecos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ZONA_DEFAULT = "America/Argentina/Buenos_Aires"


def upgrade() -> None:
    op.add_column(
        "clinica",
        sa.Column("zona_horaria", sa.Text(), nullable=False, server_default=ZONA_DEFAULT),
    )
    op.create_table(
        "franja_horaria",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=False),
        sa.Column("dia_semana", sa.SmallInteger(), nullable=False),
        sa.Column("inicio_min", sa.SmallInteger(), nullable=False),
        sa.Column("fin_min", sa.SmallInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_franja_horaria"),
        sa.ForeignKeyConstraint(
            ["clinica_id"],
            ["clinica.id"],
            name="fk_franja_horaria_clinica_id",
            ondelete="RESTRICT",
        ),  # fmt: skip
        sa.ForeignKeyConstraint(
            ["clinica_id", "profesional_id"],
            ["profesional.clinica_id", "profesional.id"],
            name="fk_franja_horaria_profesional",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("dia_semana BETWEEN 1 AND 7", name="dia_valido"),
        sa.CheckConstraint(
            "inicio_min >= 0 AND inicio_min < fin_min AND fin_min <= 1440",
            name="rango_valido",
        ),
    )
    op.create_index(
        "ix_franja_horaria_clinica_profesional_dia",
        "franja_horaria",
        ["clinica_id", "profesional_id", "dia_semana"],
    )


def downgrade() -> None:
    op.drop_index("ix_franja_horaria_clinica_profesional_dia", table_name="franja_horaria")
    op.drop_table("franja_horaria")
    op.drop_column("clinica", "zona_horaria")
