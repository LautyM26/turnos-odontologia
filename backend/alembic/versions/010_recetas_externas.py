"""010 recetas emitidas vía partner ReNaPDiS (C-19, RN-CU-03).

``receta_externa`` guarda la receta u orden de estudio que emitió el partner: id externo, enlace
al PDF del partner (no el binario, DT-4), contenido enviado, ``clave_idempotencia`` (UNIQUE por
clínica) y ``huella_solicitud`` (SHA-256 del contenido, para detectar reuso de la clave). La FK
compuesta ``(clinica_id, paciente_id, evolucion_id)`` usa ``uq_evolucion_clinica_paciente_id``
de la 008: la base impide vincular una evolución de otro paciente o clínica. Append-only:
reutiliza ``fn_rechazar_mutacion()`` de la 004 (fila UPDATE/DELETE + TRUNCATE). Amplía el CHECK
de entidades de ``auditoria_hc`` partiendo del conjunto de la 009 (entidad ``receta``).

C-05c reserva la 007: si mergea, la cadena se resuelve en la 008 y esta migración no cambia.
Antes de mergear, ``alembic heads`` debe mostrar un único head.

ROLLBACK: ``alembic downgrade 009_consentimientos_cumplimiento`` borra ``receta_externa`` y sus
triggers y restaura el CHECK de la 009. NO borra ``fn_rechazar_mutacion()`` (es de la 004). Si ya
hay eventos ``receta`` en ``auditoria_hc``, restaurar el CHECK angosto falla y esas filas no se
pueden borrar (trigger): es intencional. En producción: roll-forward, no downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010_recetas_externas"
down_revision: str | None = "009_consentimientos_cumplimiento"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTIDADES_NUEVAS = (
    "('paciente','ficha','adjunto','odontograma','evolucion','consentimiento','receta')"
)
_ENTIDADES_VIEJAS = "('paciente','ficha','adjunto','odontograma','evolucion','consentimiento')"


def _fk(cols: list[str], ref: str, refcols: list[str], name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        cols, [f"{ref}.{c}" for c in refcols], name=name, ondelete="RESTRICT"
    )


def _check_entidades(entidades: str) -> None:
    op.drop_constraint(op.f("ck_auditoria_hc_entidad_valida"), "auditoria_hc", type_="check")
    op.create_check_constraint("entidad_valida", "auditoria_hc", f"entidad IN {entidades}")


def upgrade() -> None:
    op.create_table(
        "receta_externa",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("evolucion_id", sa.BigInteger(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("partner", sa.Text(), nullable=False),
        sa.Column("simulada", sa.Boolean(), nullable=False),
        sa.Column("id_externo", sa.Text(), nullable=False),
        sa.Column("pdf_url", sa.Text(), nullable=False),
        sa.Column("diagnostico", sa.Text(), nullable=False),
        sa.Column("items", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("clave_idempotencia", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("huella_solicitud", sa.CHAR(64), nullable=False),
        sa.Column("autor_usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "emitida_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _fk(["clinica_id"], "clinica", ["id"], "fk_receta_externa_clinica_id"),
        _fk(
            ["clinica_id", "paciente_id"],
            "paciente",
            ["clinica_id", "id"],
            "fk_receta_externa_paciente",
        ),
        _fk(
            ["clinica_id", "paciente_id", "evolucion_id"],
            "evolucion",
            ["clinica_id", "paciente_id", "id"],
            "fk_receta_externa_evolucion",
        ),
        _fk(
            ["clinica_id", "autor_usuario_id"],
            "usuario",
            ["clinica_id", "id"],
            "fk_receta_externa_autor_usuario_id",
        ),
        _fk(
            ["clinica_id", "profesional_id"],
            "profesional",
            ["clinica_id", "id"],
            "fk_receta_externa_profesional",
        ),
        sa.UniqueConstraint("clinica_id", "clave_idempotencia", name="uq_receta_externa_clave"),
        sa.UniqueConstraint(
            "clinica_id", "partner", "id_externo", name="uq_receta_externa_partner_id_externo"
        ),
        sa.CheckConstraint("tipo IN ('receta','orden_estudio')", name="tipo_valido"),
        sa.CheckConstraint("pdf_url ~ '^https://'", name="pdf_url_https"),
        sa.CheckConstraint("length(btrim(diagnostico)) BETWEEN 1 AND 500", name="diagnostico_len"),
        sa.CheckConstraint("jsonb_typeof(items) = 'array'", name="items_arreglo"),
        sa.CheckConstraint("huella_solicitud ~ '^[0-9a-f]{64}$'", name="huella_formato"),
    )
    op.create_index(
        "ix_receta_externa_clinica_paciente_id",
        "receta_externa",
        ["clinica_id", "paciente_id", sa.text("id DESC")],
    )
    op.execute(
        "CREATE TRIGGER trg_receta_externa_append_only_row BEFORE UPDATE OR DELETE ON "
        "receta_externa FOR EACH ROW EXECUTE FUNCTION fn_rechazar_mutacion()"
    )
    op.execute(
        "CREATE TRIGGER trg_receta_externa_append_only_truncate BEFORE TRUNCATE ON "
        "receta_externa FOR EACH STATEMENT EXECUTE FUNCTION fn_rechazar_mutacion()"
    )
    _check_entidades(_ENTIDADES_NUEVAS)


def downgrade() -> None:
    _check_entidades(_ENTIDADES_VIEJAS)
    op.execute("DROP TRIGGER IF EXISTS trg_receta_externa_append_only_truncate ON receta_externa")
    op.execute("DROP TRIGGER IF EXISTS trg_receta_externa_append_only_row ON receta_externa")
    op.drop_table("receta_externa")
