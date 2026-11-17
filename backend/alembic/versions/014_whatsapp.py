"""014 whatsapp: sesión QR por clínica, mensajes con costo ARS y textos base (C-15, DD-10).

- ``plantilla_wa``: 5 textos base globales de la plataforma (como ``rol``, sin ``clinica_id``),
  sin aprobación de Meta (DD-10). Se siembran acá (D4).
- ``whatsapp_sesion``: una sesión (número dedicado) por clínica; ``nombre = 'clinica-<id>'`` (D2).
- ``mensaje_whatsapp``: cada mensaje saliente/entrante con estado, intentos, motivo de error,
  costo ``NUMERIC(12,2)`` en ARS (RN-WA-02/03) y marca de bandeja (D3). Idempotencia de eventos
  por ``UNIQUE (clinica_id, id_externo)``; un recordatorio por turno por UNIQUE parcial (D5).
- ``turno_transicion.actor_tipo`` admite ``paciente_whatsapp`` sin usuario (D8).

Antes de mergear, ``alembic heads`` debe mostrar un único head.

ROLLBACK: ``alembic downgrade 013_reserva_online`` borra las tres tablas (se pierde el registro
de mensajes y costos) y restaura el CHECK de ``actor_tipo``. Falla con un mensaje claro si ya hay
transiciones ``paciente_whatsapp``: el historial es append-only y no se borra para poder bajar.
En producción: roll-forward, o ``WHATSAPP_GATEWAY=`` vacío para apagar el canal.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "014_whatsapp"
down_revision: str | None = "013_reserva_online"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTORES_NUEVOS = "('usuario','paciente_enlace','paciente_whatsapp')"
_ACTORES_VIEJOS = "('usuario','paciente_enlace')"
_VARIABLES = ["paciente_nombre", "fecha", "hora", "profesional", "clinica"]

TEXTOS_BASE = {
    "recordatorio_24h": (
        "Hola {paciente_nombre}, te recordamos tu turno en {clinica} el {fecha} a las {hora} "
        "con {profesional}. Respondé 1 para confirmar, 2 para cancelar o 3 para reprogramar."
    ),
    "confirmacion": (
        "¡Gracias {paciente_nombre}! Tu turno del {fecha} a las {hora} con {profesional} "
        "quedó confirmado."
    ),
    "cancelacion": (
        "Listo {paciente_nombre}, cancelamos tu turno del {fecha} a las {hora}. "
        "Si fue un error, comunicate con {clinica}."
    ),
    "reprogramacion": (
        "Recibimos tu pedido para reprogramar el turno del {fecha} a las {hora}. "
        "Desde {clinica} te vamos a contactar para elegir otro horario."
    ),
    "oferta_hueco": (
        "Hola {paciente_nombre}, se liberó un turno en {clinica} el {fecha} a las {hora} "
        "con {profesional}. ¿Lo tomás? Respondé 1 para aceptar o 2 para rechazar."
    ),
}


def _fk(cols: list[str], ref: str, refcols: list[str], name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        cols, [f"{ref}.{c}" for c in refcols], name=name, ondelete="RESTRICT"
    )


def _check_actores(actores: str) -> None:
    op.drop_constraint(
        op.f("ck_turno_transicion_actor_tipo_valido"), "turno_transicion", type_="check"
    )
    op.create_check_constraint("actor_tipo_valido", "turno_transicion", f"actor_tipo IN {actores}")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    ]  # fmt: skip


def upgrade() -> None:
    plantilla = op.create_table(
        "plantilla_wa",
        sa.Column("clave", sa.Text(), primary_key=True),
        sa.Column("idioma", sa.Text(), nullable=False, server_default="es_AR"),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("variables", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.CheckConstraint(f"clave IN {tuple(TEXTOS_BASE)}", name="clave_valida"),
        sa.CheckConstraint("length(texto) BETWEEN 1 AND 1000", name="texto_len"),
    )
    op.bulk_insert(
        plantilla,
        [{"clave": k, "idioma": "es_AR", "texto": v, "variables": _VARIABLES}
         for k, v in TEXTOS_BASE.items()],
    )  # fmt: skip

    op.create_table(
        "whatsapp_sesion",
        sa.Column("clinica_id", sa.BigInteger(), primary_key=True),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False, server_default="desconocido"),
        sa.Column("numero", sa.Text(), nullable=True),
        sa.Column("estado_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        *_timestamps(),
        _fk(["clinica_id"], "clinica", ["id"], "fk_whatsapp_sesion_clinica_id"),
        sa.UniqueConstraint("nombre", name="uq_whatsapp_sesion_nombre"),
        sa.CheckConstraint("nombre = 'clinica-' || clinica_id::text", name="nombre_coherente"),
        sa.CheckConstraint(
            "estado IN ('desconocido','iniciando','escanear_qr','activa','caida','detenida')",
            name="estado_valido",
        ),
    )  # fmt: skip

    op.create_table(
        "mensaje_whatsapp",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("turno_id", sa.BigInteger(), nullable=True),
        sa.Column("paciente_id", sa.BigInteger(), nullable=True),
        sa.Column("plantilla", sa.Text(), nullable=True),
        sa.Column("direccion", sa.Text(), nullable=False),
        sa.Column("telefono", sa.Text(), nullable=True),
        sa.Column("texto", sa.Text(), nullable=True),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("intencion", sa.Text(), nullable=True),
        sa.Column("id_externo", sa.Text(), nullable=True),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("motivo_error", sa.Text(), nullable=True),
        sa.Column("costo_ars", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("requiere_atencion", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resuelto_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resuelto_por", sa.BigInteger(), nullable=True),
        *_timestamps(),
        _fk(["clinica_id"], "clinica", ["id"], "fk_mensaje_whatsapp_clinica_id"),
        _fk(["clinica_id", "turno_id"], "turno", ["clinica_id", "id"],
            "fk_mensaje_whatsapp_turno"),
        _fk(["clinica_id", "paciente_id"], "paciente", ["clinica_id", "id"],
            "fk_mensaje_whatsapp_paciente"),
        _fk(["clinica_id", "resuelto_por"], "usuario", ["clinica_id", "id"],
            "fk_mensaje_whatsapp_resuelto_por"),
        _fk(["plantilla"], "plantilla_wa", ["clave"], "fk_mensaje_whatsapp_plantilla"),
        sa.CheckConstraint("direccion IN ('saliente','entrante')", name="direccion_valida"),
        sa.CheckConstraint(
            "estado IN ('pendiente','enviado','entregado','leido','error','recibido')",
            name="estado_valido",
        ),
        sa.CheckConstraint("(direccion = 'entrante') = (estado = 'recibido')",
                           name="estado_segun_direccion"),
        sa.CheckConstraint(
            "intencion IS NULL OR "
            "intencion IN ('confirmar','cancelar','reprogramar','desconocida')",
            name="intencion_valida",
        ),
        sa.CheckConstraint("(direccion = 'entrante') = (intencion IS NOT NULL)",
                           name="intencion_solo_entrante"),
        sa.CheckConstraint(
            "motivo_error IS NULL OR motivo_error IN "
            "('sin_telefono','no_configurado','sesion_no_activa','gateway_no_disponible','otro')",
            name="motivo_error_valido",
        ),
        sa.CheckConstraint("(estado = 'error') = (motivo_error IS NOT NULL)",
                           name="error_con_motivo"),
        sa.CheckConstraint("telefono IS NULL OR telefono ~ '^\\+[0-9]{8,15}$'",
                           name="telefono_e164"),
        sa.CheckConstraint(
            "telefono IS NOT NULL OR motivo_error IS NOT DISTINCT FROM 'sin_telefono'",
            name="telefono_requerido",
        ),
        sa.CheckConstraint("texto IS NULL OR length(texto) <= 2000", name="texto_len"),
        sa.CheckConstraint("intentos >= 0", name="intentos_no_negativos"),
        sa.CheckConstraint("costo_ars >= 0", name="costo_no_negativo"),
        sa.CheckConstraint("direccion = 'saliente' OR costo_ars = 0", name="entrante_sin_costo"),
        sa.CheckConstraint("(resuelto_at IS NULL) = (resuelto_por IS NULL)",
                           name="resolucion_coherente"),
    )  # fmt: skip
    op.create_index(
        "ix_mensaje_whatsapp_clinica_turno_estado",
        "mensaje_whatsapp",
        ["clinica_id", "turno_id", "estado"],
    )
    op.create_index(
        "ix_mensaje_whatsapp_clinica_created", "mensaje_whatsapp", ["clinica_id", "created_at"]
    )
    op.create_index(
        "ix_mensaje_whatsapp_recordatorio_telefono",
        "mensaje_whatsapp",
        ["clinica_id", "telefono", sa.text("created_at DESC")],
        postgresql_where=sa.text("direccion = 'saliente' AND plantilla = 'recordatorio_24h'"),
    )
    op.create_index(
        "ix_mensaje_whatsapp_bandeja",
        "mensaje_whatsapp",
        ["clinica_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("requiere_atencion AND resuelto_at IS NULL"),
    )
    op.create_index(
        "uq_mensaje_whatsapp_clinica_id_externo",
        "mensaje_whatsapp",
        ["clinica_id", "id_externo"],
        unique=True,
        postgresql_where=sa.text("id_externo IS NOT NULL"),
    )
    op.create_index(
        "uq_mensaje_whatsapp_recordatorio_turno",
        "mensaje_whatsapp",
        ["clinica_id", "turno_id"],
        unique=True,
        postgresql_where=sa.text("direccion = 'saliente' AND plantilla = 'recordatorio_24h'"),
    )

    _check_actores(_ACTORES_NUEVOS)


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM turno_transicion WHERE actor_tipo = 'paciente_whatsapp') THEN
            RAISE EXCEPTION 'downgrade 014 imposible: hay transiciones paciente_whatsapp '
              '(historial append-only). Roll-forward o apagar el canal con WHATSAPP_GATEWAY=';
          END IF;
        END $$;
        """
    )
    _check_actores(_ACTORES_VIEJOS)
    op.drop_table("mensaje_whatsapp")
    op.drop_table("whatsapp_sesion")
    op.drop_table("plantilla_wa")
