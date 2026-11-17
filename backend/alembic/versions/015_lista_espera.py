"""015 lista_espera: cola de espera y ofertas de huecos liberados (C-16, RN-AG-06).

- ``lista_espera``: una entrada activa por (paciente, prestación); preferencias opcionales de
  profesional/sillón, prioridad 0-10 y turno a adelantar opcional (D2).
- ``oferta_lista_espera``: cada hueco ofrecido a una entrada. UNIQUE parciales: una oferta
  pendiente por hueco y por entrada; el mismo hueco nunca dos veces a la misma entrada.
- ``plantilla_wa``: suma ``oferta_aceptada`` y ``oferta_no_disponible``.

Antes de mergear, ``alembic heads`` debe mostrar un único head.

ROLLBACK: ``alembic downgrade 014_whatsapp`` borra ambas tablas (se pierde la cola) y los dos
textos nuevos; falla con mensaje claro si algún mensaje de WhatsApp ya usó esos textos.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "015_lista_espera"
down_revision: str | None = "014_whatsapp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VARIABLES = ["paciente_nombre", "fecha", "hora", "profesional", "clinica"]
TEXTOS_NUEVOS = {
    "oferta_aceptada": (
        "¡Listo {paciente_nombre}! Te reservamos el turno del {fecha} a las {hora} "
        "con {profesional} en {clinica}."
    ),
    "oferta_no_disponible": (
        "Gracias {paciente_nombre}, el turno del {fecha} a las {hora} ya no está disponible. "
        "Te avisamos si se libera otro horario."
    ),
}
_CLAVES_014 = ("recordatorio_24h", "confirmacion", "cancelacion", "reprogramacion", "oferta_hueco")


def _fk(cols: list[str], ref: str, refcols: list[str], name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        cols, [f"{ref}.{c}" for c in refcols], name=name, ondelete="RESTRICT"
    )


def _check_claves(claves: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_plantilla_wa_clave_valida"), "plantilla_wa", type_="check")
    op.create_check_constraint("clave_valida", "plantilla_wa", f"clave IN {claves}")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    ]  # fmt: skip


def upgrade() -> None:
    _check_claves((*_CLAVES_014, *TEXTOS_NUEVOS))
    plantilla = sa.table(
        "plantilla_wa", sa.column("clave"), sa.column("idioma"), sa.column("texto"),
        sa.column("variables", sa.dialects.postgresql.ARRAY(sa.Text())),
    )  # fmt: skip
    op.bulk_insert(
        plantilla,
        [{"clave": k, "idioma": "es_AR", "texto": v, "variables": _VARIABLES}
         for k, v in TEXTOS_NUEVOS.items()],
    )  # fmt: skip

    op.create_table(
        "lista_espera",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("prestacion_id", sa.BigInteger(), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=True),
        sa.Column("sillon_id", sa.BigInteger(), nullable=True),
        sa.Column("turno_a_adelantar_id", sa.BigInteger(), nullable=True),
        sa.Column("prioridad", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estado", sa.Text(), nullable=False, server_default="en_cola"),
        *_timestamps(),
        _fk(["clinica_id"], "clinica", ["id"], "fk_lista_espera_clinica_id"),
        _fk(["clinica_id", "paciente_id"], "paciente", ["clinica_id", "id"],
            "fk_lista_espera_paciente"),
        _fk(["clinica_id", "prestacion_id"], "prestacion", ["clinica_id", "id"],
            "fk_lista_espera_prestacion"),
        _fk(["clinica_id", "profesional_id"], "profesional", ["clinica_id", "id"],
            "fk_lista_espera_profesional"),
        _fk(["clinica_id", "sillon_id"], "sillon_recurso", ["clinica_id", "id"],
            "fk_lista_espera_sillon"),
        _fk(["clinica_id", "turno_a_adelantar_id"], "turno", ["clinica_id", "id"],
            "fk_lista_espera_turno_a_adelantar"),
        sa.UniqueConstraint("clinica_id", "id", name="uq_lista_espera_clinica_id"),
        sa.CheckConstraint("estado IN ('en_cola','ofertado','aceptado','salido')",
                           name="estado_valido"),
        sa.CheckConstraint("prioridad BETWEEN 0 AND 10", name="prioridad_rango"),
    )  # fmt: skip
    op.create_index(
        "ix_lista_espera_cola",
        "lista_espera",
        ["clinica_id", "prestacion_id", "estado", sa.text("prioridad DESC"), "id"],
    )
    op.create_index(
        "uq_lista_espera_activa",
        "lista_espera",
        ["clinica_id", "paciente_id", "prestacion_id"],
        unique=True,
        postgresql_where=sa.text("estado IN ('en_cola','ofertado')"),
    )

    op.create_table(
        "oferta_lista_espera",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("lista_espera_id", sa.BigInteger(), nullable=False),
        sa.Column("turno_liberado_id", sa.BigInteger(), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=False),
        sa.Column("sillon_id", sa.BigInteger(), nullable=False),
        sa.Column("prestacion_id", sa.BigInteger(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False, server_default="pendiente"),
        sa.Column("expira_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("respondida_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mensaje_id", sa.BigInteger(), nullable=True),
        sa.Column("turno_creado_id", sa.BigInteger(), nullable=True),
        *_timestamps(),
        _fk(["clinica_id"], "clinica", ["id"], "fk_oferta_lista_espera_clinica_id"),
        _fk(["clinica_id", "lista_espera_id"], "lista_espera", ["clinica_id", "id"],
            "fk_oferta_lista_espera_entrada"),
        _fk(["clinica_id", "turno_liberado_id"], "turno", ["clinica_id", "id"],
            "fk_oferta_lista_espera_turno_liberado"),
        _fk(["clinica_id", "turno_creado_id"], "turno", ["clinica_id", "id"],
            "fk_oferta_lista_espera_turno_creado"),
        _fk(["mensaje_id"], "mensaje_whatsapp", ["id"], "fk_oferta_lista_espera_mensaje"),
        sa.CheckConstraint(
            "estado IN ('pendiente','aceptada','rechazada','expirada','anulada')",
            name="estado_valido",
        ),
        sa.CheckConstraint("fin > inicio", name="fin_posterior"),
        sa.CheckConstraint("turno_creado_id IS NULL OR estado = 'aceptada'",
                           name="turno_creado_solo_aceptada"),
        sa.UniqueConstraint("clinica_id", "lista_espera_id", "turno_liberado_id",
                            name="uq_oferta_hueco_por_entrada"),
    )  # fmt: skip
    op.create_index(
        "uq_oferta_pendiente_por_hueco",
        "oferta_lista_espera",
        ["clinica_id", "turno_liberado_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'pendiente'"),
    )
    op.create_index(
        "uq_oferta_pendiente_por_entrada",
        "oferta_lista_espera",
        ["clinica_id", "lista_espera_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'pendiente'"),
    )
    op.create_index(
        "ix_oferta_lista_espera_clinica_created",
        "oferta_lista_espera",
        ["clinica_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_oferta_lista_espera_mensaje", "oferta_lista_espera", ["mensaje_id"])


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM mensaje_whatsapp
                     WHERE plantilla IN ('oferta_aceptada','oferta_no_disponible')) THEN
            RAISE EXCEPTION 'downgrade 015 imposible: hay mensajes con los textos de la lista '
              'de espera. Roll-forward.';
          END IF;
        END $$;
        """
    )
    op.drop_table("oferta_lista_espera")
    op.drop_table("lista_espera")
    op.execute("DELETE FROM plantilla_wa WHERE clave IN ('oferta_aceptada','oferta_no_disponible')")
    _check_claves(_CLAVES_014)
