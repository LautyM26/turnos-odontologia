"""016 reprogramacion: conversación del chatbot por WhatsApp y textos base (C-17).

- ``conversacion_wa``: una conversación abierta por (clínica, teléfono) con las opciones
  ofrecidas, el paso (``eligiendo|confirmando|ejecutando|cerrada``) y el resultado (D1).
- ``plantilla_wa``: suma 5 textos de reprogramación.

Antes de mergear, ``alembic heads`` debe mostrar un único head.

ROLLBACK: ``alembic downgrade 015_lista_espera`` borra la tabla (se pierde el registro de
conversaciones) y los textos nuevos; falla con mensaje claro si algún mensaje ya los usó.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "016_reprogramacion"
down_revision: str | None = "015_lista_espera"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLAVES_015 = (
    "recordatorio_24h", "confirmacion", "cancelacion", "reprogramacion", "oferta_hueco",
    "oferta_aceptada", "oferta_no_disponible",
)  # fmt: skip
TEXTOS_NUEVOS = {
    "reprogramacion_opciones": (
        "{intro}Estos son los horarios disponibles con {profesional}:\n{opciones}\n"
        "Respondé con el número que prefieras o 0 para dejar tu turno como está."
    ),
    "reprogramacion_confirmar": (
        "¿Confirmás el cambio de tu turno al {fecha} a las {hora} con {profesional}? "
        "Respondé SI para confirmar o NO para dejarlo como está."
    ),
    "reprogramacion_hecha": (
        "¡Listo {paciente_nombre}! Tu turno quedó para el {fecha} a las {hora} "
        "con {profesional} en {clinica}."
    ),
    "reprogramacion_sin_cambios": "Perfecto, tu turno del {fecha} a las {hora} sigue igual.",
    "reprogramacion_vencida": (
        "Pasó el tiempo para elegir un horario. Tu turno del {fecha} a las {hora} sigue igual; "
        "respondé 3 si querés ver opciones nuevas."
    ),
}
_VARIABLES_TURNO = ["paciente_nombre", "fecha", "hora", "profesional", "clinica"]
_VARIABLES = {"reprogramacion_opciones": ["intro", "profesional", "opciones"]}
_CLAVES_NUEVAS_SQL = "(" + ",".join(f"'{k}'" for k in TEXTOS_NUEVOS) + ")"


def _fk(cols: list[str], ref: str, refcols: list[str], name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        cols, [f"{ref}.{c}" for c in refcols], name=name, ondelete="RESTRICT"
    )


def _check_claves(claves: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_plantilla_wa_clave_valida"), "plantilla_wa", type_="check")
    op.create_check_constraint("clave_valida", "plantilla_wa", f"clave IN {claves}")


def upgrade() -> None:
    _check_claves((*_CLAVES_015, *TEXTOS_NUEVOS))
    plantilla = sa.table(
        "plantilla_wa", sa.column("clave"), sa.column("idioma"), sa.column("texto"),
        sa.column("variables", postgresql.ARRAY(sa.Text())),
    )  # fmt: skip
    op.bulk_insert(
        plantilla,
        [{"clave": k, "idioma": "es_AR", "texto": v,
          "variables": _VARIABLES.get(k, _VARIABLES_TURNO)} for k, v in TEXTOS_NUEVOS.items()],
    )  # fmt: skip
    op.create_table(
        "conversacion_wa",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("telefono", sa.Text(), nullable=False),
        sa.Column("turno_id", sa.BigInteger(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False, server_default="eligiendo"),
        sa.Column("resultado", sa.Text(), nullable=True),
        sa.Column("opciones", postgresql.JSONB(), nullable=False),
        sa.Column("elegido", sa.Integer(), nullable=True),
        sa.Column("turno_nuevo_id", sa.BigInteger(), nullable=True),
        sa.Column("expira_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        _fk(["clinica_id"], "clinica", ["id"], "fk_conversacion_wa_clinica_id"),
        _fk(["clinica_id", "paciente_id"], "paciente", ["clinica_id", "id"],
            "fk_conversacion_wa_paciente"),
        _fk(["clinica_id", "turno_id"], "turno", ["clinica_id", "id"], "fk_conversacion_wa_turno"),
        _fk(["clinica_id", "turno_nuevo_id"], "turno", ["clinica_id", "id"],
            "fk_conversacion_wa_turno_nuevo"),
        sa.CheckConstraint("estado IN ('eligiendo','confirmando','ejecutando','cerrada')",
                           name="estado_valido"),
        sa.CheckConstraint(
            "resultado IS NULL OR "
            "resultado IN ('reprogramado','sin_cambios','vencida','sin_opciones')",
            name="resultado_valido",
        ),
        sa.CheckConstraint("(estado = 'cerrada') = (resultado IS NOT NULL)",
                           name="cerrada_con_resultado"),
        sa.CheckConstraint("jsonb_typeof(opciones) = 'array'", name="opciones_arreglo"),
    )  # fmt: skip
    op.create_index(
        "uq_conversacion_wa_abierta",
        "conversacion_wa",
        ["clinica_id", "telefono"],
        unique=True,
        postgresql_where=sa.text("estado <> 'cerrada'"),
    )
    op.create_index(
        "ix_conversacion_wa_clinica_created", "conversacion_wa", ["clinica_id", "created_at"]
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM mensaje_whatsapp WHERE plantilla IN {_CLAVES_NUEVAS_SQL}) THEN
            RAISE EXCEPTION 'downgrade 016 imposible: hay mensajes con los textos del chatbot '
              'de reprogramación. Roll-forward.';
          END IF;
        END $$;
        """
    )
    op.drop_table("conversacion_wa")
    op.execute(f"DELETE FROM plantilla_wa WHERE clave IN {_CLAVES_NUEVAS_SQL}")
    _check_claves(_CLAVES_015)
