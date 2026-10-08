"""004 pacientes y ficha: paciente, ficha_version, adjunto, auditoria_hc (C-08).

Integridad tenant por FK compuesta (clinica_id, id), reutilizando ``uq_usuario_clinica_id``
de la 003 (no se recrea ni se elimina aqui). ``ficha_version`` y ``auditoria_hc`` son
append-only: triggers PG rechazan UPDATE/DELETE/TRUNCATE. La extension ``pg_trgm`` NO se
elimina en el downgrade.

ROLLBACK: ``alembic downgrade -1`` borra las tablas de pacientes (y la historia clinica).
En produccion con datos reales NO se hace downgrade: se hace roll-forward.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004_pacientes_ficha"
down_revision: str | None = "003_clinica_catalogo"
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


def _usuario_fk(table: str, col: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["clinica_id", col],
        ["usuario.clinica_id", "usuario.id"],
        name=f"fk_{table}_{col}",
        ondelete="RESTRICT",
    )


def _paciente_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["clinica_id", "paciente_id"],
        ["paciente.clinica_id", "paciente.id"],
        name=f"fk_{table}_paciente",
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "paciente",
        _pk_identity(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("apellido", sa.Text(), nullable=False),
        sa.Column("dni", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("telefono", sa.Text(), nullable=True),
        sa.Column("obra_social_nombre", sa.Text(), nullable=True),
        sa.Column("obra_social_plan", sa.Text(), nullable=True),
        sa.Column("nro_afiliado", sa.Text(), nullable=True),
        sa.Column("riesgo_ausencia", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("consentimiento_datos", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("consentimiento_datos_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consentimiento_datos_por", sa.BigInteger(), nullable=True),
        sa.Column("nombre_busqueda", sa.Text(), nullable=False),
        sa.Column("es_seed", sa.Boolean(), server_default=sa.false(), nullable=False),
        *_audit_columns(),
        _clinica_fk("paciente"),
        _usuario_fk("paciente", "consentimiento_datos_por"),
        sa.UniqueConstraint("clinica_id", "id", name="uq_paciente_clinica_id"),
        sa.UniqueConstraint("clinica_id", "dni", name="uq_paciente_clinica_dni"),
        sa.CheckConstraint("length(nombre) BETWEEN 1 AND 100", name="nombre_len"),
        sa.CheckConstraint("length(apellido) BETWEEN 1 AND 100", name="apellido_len"),
        sa.CheckConstraint("dni ~ '^[0-9]{7,8}$'", name="dni_formato"),
        sa.CheckConstraint("email IS NULL OR length(email) <= 320", name="email_len"),
        sa.CheckConstraint(
            "telefono IS NULL OR telefono ~ '^\\+[0-9]{8,15}$'", name="telefono_e164"
        ),
        sa.CheckConstraint("email IS NOT NULL OR telefono IS NOT NULL", name="contacto_requerido"),
        sa.CheckConstraint(
            "obra_social_nombre IS NULL OR length(obra_social_nombre) <= 120", name="os_nombre_len"
        ),
        sa.CheckConstraint(
            "obra_social_plan IS NULL OR length(obra_social_plan) <= 120", name="os_plan_len"
        ),
        sa.CheckConstraint(
            "nro_afiliado IS NULL OR length(nro_afiliado) <= 50", name="nro_afiliado_len"
        ),
        sa.CheckConstraint("riesgo_ausencia BETWEEN 0 AND 100", name="riesgo_rango"),
        sa.CheckConstraint(
            "NOT consentimiento_datos OR consentimiento_datos_at IS NOT NULL",
            name="consentimiento_con_fecha",
        ),
    )
    op.create_index("ix_paciente_clinica_telefono", "paciente", ["clinica_id", "telefono"])
    op.create_index("ix_paciente_clinica_email", "paciente", ["clinica_id", "email"])
    op.create_index(
        "ix_paciente_nombre_busqueda_trgm",
        "paciente",
        ["nombre_busqueda"],
        postgresql_using="gin",
        postgresql_ops={"nombre_busqueda": "gin_trgm_ops"},
    )

    op.create_table(
        "ficha_version",
        _pk_identity(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("anamnesis", sa.Text(), nullable=True),
        sa.Column("alergias", sa.Text(), nullable=True),
        sa.Column("antecedentes", sa.Text(), nullable=True),
        sa.Column("autor_usuario_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _clinica_fk("ficha_version"),
        _paciente_fk("ficha_version"),
        _usuario_fk("ficha_version", "autor_usuario_id"),
        sa.UniqueConstraint("paciente_id", "version", name="uq_ficha_version_paciente_version"),
        sa.CheckConstraint("version > 0", name="version_positiva"),
        sa.CheckConstraint("anamnesis IS NULL OR length(anamnesis) <= 10000", name="anamnesis_len"),
        sa.CheckConstraint("alergias IS NULL OR length(alergias) <= 10000", name="alergias_len"),
        sa.CheckConstraint(
            "antecedentes IS NULL OR length(antecedentes) <= 10000", name="antecedentes_len"
        ),
    )
    op.create_index(
        "ix_ficha_version_clinica_paciente_version",
        "ficha_version",
        ["clinica_id", "paciente_id", sa.text("version DESC")],
    )

    op.create_table(
        "adjunto",
        _pk_identity(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("evolucion_id", sa.BigInteger(), nullable=True),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("mime", sa.Text(), nullable=False),
        sa.Column("tamano_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.CHAR(64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("nombre_original", sa.Text(), nullable=True),
        sa.Column("subido_por", sa.BigInteger(), nullable=False),
        *_audit_columns(),
        _clinica_fk("adjunto"),
        _paciente_fk("adjunto"),
        _usuario_fk("adjunto", "subido_por"),
        sa.UniqueConstraint("storage_key", name="uq_adjunto_storage_key"),
        sa.CheckConstraint("tipo IN ('foto','pdf')", name="tipo_valido"),
        sa.CheckConstraint(
            "mime IN ('image/jpeg','image/png','application/pdf')", name="mime_valido"
        ),
        sa.CheckConstraint("tamano_bytes > 0", name="tamano_positivo"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_formato"),
        sa.CheckConstraint(
            "nombre_original IS NULL OR length(nombre_original) <= 255", name="nombre_len"
        ),
    )
    op.create_index(
        "ix_adjunto_clinica_paciente_created",
        "adjunto",
        ["clinica_id", "paciente_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "auditoria_hc",
        _pk_identity(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_usuario_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_tipo", sa.Text(), nullable=False),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("entidad", sa.Text(), nullable=False),
        sa.Column("entidad_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "diff",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _clinica_fk("auditoria_hc"),
        _paciente_fk("auditoria_hc"),
        _usuario_fk("auditoria_hc", "actor_usuario_id"),
        sa.CheckConstraint("actor_tipo IN ('usuario','sistema')", name="actor_tipo_valido"),
        sa.CheckConstraint(
            "actor_tipo <> 'usuario' OR actor_usuario_id IS NOT NULL",
            name="actor_usuario_requerido",
        ),
        sa.CheckConstraint(
            "accion IN ('crear','actualizar','leer','descargar',"
            "'consentimiento_otorgado','consentimiento_revocado')",
            name="accion_valida",
        ),
        sa.CheckConstraint("entidad IN ('paciente','ficha','adjunto')", name="entidad_valida"),
    )
    op.create_index(
        "ix_auditoria_hc_clinica_paciente_id",
        "auditoria_hc",
        ["clinica_id", "paciente_id", sa.text("id DESC")],
    )
    op.create_index("ix_auditoria_hc_clinica_created", "auditoria_hc", ["clinica_id", "created_at"])

    op.execute(
        """
        CREATE FUNCTION fn_rechazar_mutacion() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'tabla append-only: % no permitido sobre %', TG_OP, TG_TABLE_NAME;
        END;
        $$
        """
    )
    for tabla in ("auditoria_hc", "ficha_version"):
        op.execute(
            f"CREATE TRIGGER trg_{tabla}_append_only_row BEFORE UPDATE OR DELETE ON {tabla} "
            "FOR EACH ROW EXECUTE FUNCTION fn_rechazar_mutacion()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{tabla}_append_only_truncate BEFORE TRUNCATE ON {tabla} "
            "FOR EACH STATEMENT EXECUTE FUNCTION fn_rechazar_mutacion()"
        )


def downgrade() -> None:
    for tabla in ("auditoria_hc", "ficha_version"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tabla}_append_only_truncate ON {tabla}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tabla}_append_only_row ON {tabla}")
    op.execute("DROP FUNCTION IF EXISTS fn_rechazar_mutacion()")
    op.drop_table("auditoria_hc")
    op.drop_table("adjunto")
    op.drop_table("ficha_version")
    op.drop_table("paciente")
