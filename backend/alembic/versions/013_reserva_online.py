"""013 reserva_online: slug de clínica, token público del turno y actor de enlace (C-06).

- ``clinica.slug``: identifica la clínica en el enlace público ``/reservar/{slug}`` (D1). Default
  al azar con formato válido (``c-`` + 12 hex), así toda clínica tiene uno sin cambiar sus altas;
  el seed fija ``clinica-piloto`` y C-14 lo hará editable.
- ``turno.token_publico_hash``: SHA-256 del token que permite ver/cancelar la reserva (D2); el
  token en claro nunca se guarda.
- ``turno_transicion``: ``actor_tipo`` (``usuario`` | ``paciente_enlace``) y
  ``actor_usuario_id`` nullable, coherentes por CHECK (D4). Las filas previas quedan ``usuario``.

ROLLBACK: ``alembic downgrade 012_horario_atencion`` falla si ya hay transiciones
``paciente_enlace`` (``actor_usuario_id`` vuelve a NOT NULL y la tabla es append-only): borrarlas
a mano antes. Se pierden slugs y tokens (las reservas por enlace dejan de poder consultarse).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "013_reserva_online"
down_revision: str | None = "012_horario_atencion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG_DEFAULT = "'c-' || substr(md5(random()::text || clock_timestamp()::text), 1, 12)"


def upgrade() -> None:
    op.add_column(
        "clinica",
        sa.Column("slug", sa.Text(), nullable=False, server_default=sa.text(SLUG_DEFAULT)),
    )
    op.create_check_constraint(
        op.f("ck_clinica_slug_formato"),
        "clinica",
        "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(slug) BETWEEN 3 AND 60",
    )
    op.create_unique_constraint("uq_clinica_slug", "clinica", ["slug"])

    op.add_column("turno", sa.Column("token_publico_hash", sa.Text(), nullable=True))
    op.create_index(
        "uq_turno_token_publico_hash",
        "turno",
        ["token_publico_hash"],
        unique=True,
        postgresql_where=sa.text("token_publico_hash IS NOT NULL"),
    )

    op.alter_column("turno_transicion", "actor_usuario_id", nullable=True)
    op.add_column(
        "turno_transicion",
        sa.Column("actor_tipo", sa.Text(), nullable=False, server_default="usuario"),
    )
    op.create_check_constraint(
        op.f("ck_turno_transicion_actor_tipo_valido"),
        "turno_transicion",
        "actor_tipo IN ('usuario','paciente_enlace')",
    )
    op.create_check_constraint(
        op.f("ck_turno_transicion_actor_coherente"),
        "turno_transicion",
        "(actor_tipo = 'usuario') = (actor_usuario_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_turno_transicion_actor_coherente"), "turno_transicion", type_="check"
    )
    op.drop_constraint(
        op.f("ck_turno_transicion_actor_tipo_valido"), "turno_transicion", type_="check"
    )
    op.drop_column("turno_transicion", "actor_tipo")
    op.alter_column("turno_transicion", "actor_usuario_id", nullable=False)
    op.drop_index("uq_turno_token_publico_hash", table_name="turno")
    op.drop_column("turno", "token_publico_hash")
    op.drop_constraint("uq_clinica_slug", "clinica", type_="unique")
    op.drop_constraint(op.f("ck_clinica_slug_formato"), "clinica", type_="check")
    op.drop_column("clinica", "slug")
