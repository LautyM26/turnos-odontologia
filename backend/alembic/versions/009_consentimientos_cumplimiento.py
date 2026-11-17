"""009 consentimientos y auditoría administrativa (C-18).

``consentimiento`` guarda el documento con el texto exacto, su versión y su hash SHA-256;
``consentimiento_firma`` guarda la constancia (fecha, IP, dispositivo, hash, firmante) y su
``UNIQUE (clinica_id, consentimiento_id)`` garantiza UNA sola firma por documento. Firmar =
INSERT de la constancia; ``estado`` y ``documento_bloqueado`` se derivan. ``auditoria_admin``
registra acciones sin paciente (alta de usuarios, roles, exportación). Las tres tablas son
append-only: reutilizan ``fn_rechazar_mutacion()`` de la 004 (fila UPDATE/DELETE + TRUNCATE).
Integridad tenant por FK compuesta ``(clinica_id, x)``. Amplía los CHECK de ``auditoria_hc``
partiendo del conjunto de la 008 (entidad ``consentimiento``, acción ``firmar``).

C-05c reserva la 007: si mergea, la cadena se resuelve en la 008 y esta migración no cambia.
Antes de mergear, ``alembic heads`` debe mostrar un único head.

ROLLBACK: ``alembic downgrade 008_odontograma_evolucion`` borra consentimientos, constancias y
auditoría administrativa. NO borra ``fn_rechazar_mutacion()`` (es de la 004). Si ya hay eventos
``consentimiento``/``firmar`` en ``auditoria_hc``, restaurar los CHECK angostos falla y esas
filas no se pueden borrar (trigger): es intencional. En producción: roll-forward, no downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009_consentimientos_cumplimiento"
down_revision: str | None = "008_odontograma_evolucion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTIDADES_NUEVAS = "('paciente','ficha','adjunto','odontograma','evolucion','consentimiento')"
_ENTIDADES_VIEJAS = "('paciente','ficha','adjunto','odontograma','evolucion')"
_ACCIONES_NUEVAS = (
    "('crear','actualizar','leer','descargar',"
    "'consentimiento_otorgado','consentimiento_revocado','corregir','firmar')"
)
_ACCIONES_VIEJAS = (
    "('crear','actualizar','leer','descargar',"
    "'consentimiento_otorgado','consentimiento_revocado','corregir')"
)
_TABLAS = ("consentimiento", "consentimiento_firma", "auditoria_admin")
_HEX64 = "^[0-9a-f]{64}$"


def _pk() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True)


def _fk(cols: list[str], ref: str, refcols: list[str], name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        cols, [f"{ref}.{c}" for c in refcols], name=name, ondelete="RESTRICT"
    )


def _ts(nombre: str) -> sa.Column:
    return sa.Column(
        nombre, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _ampliar_checks_auditoria(entidades: str, acciones: str) -> None:
    for nombre, condicion in (
        ("entidad_valida", f"entidad IN {entidades}"),
        ("accion_valida", f"accion IN {acciones}"),
    ):
        op.drop_constraint(op.f(f"ck_auditoria_hc_{nombre}"), "auditoria_hc", type_="check")
        op.create_check_constraint(nombre, "auditoria_hc", condicion)


def upgrade() -> None:
    op.create_table(
        "consentimiento",
        _pk(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("texto_version", sa.Text(), nullable=False),
        sa.Column("texto_hash", sa.CHAR(64), nullable=False),
        sa.Column("autor_usuario_id", sa.BigInteger(), nullable=False),
        _ts("created_at"),
        _fk(["clinica_id"], "clinica", ["id"], "fk_consentimiento_clinica_id"),
        _fk(
            ["clinica_id", "paciente_id"],
            "paciente",
            ["clinica_id", "id"],
            "fk_consentimiento_paciente",
        ),
        _fk(
            ["clinica_id", "autor_usuario_id"],
            "usuario",
            ["clinica_id", "id"],
            "fk_consentimiento_autor_usuario_id",
        ),
        sa.UniqueConstraint(
            "clinica_id", "paciente_id", "id", name="uq_consentimiento_clinica_paciente_id"
        ),
        sa.CheckConstraint(
            "tipo IN ('tratamiento_general','extraccion','endodoncia','implante','anestesia')",
            name="tipo_valido",
        ),
        sa.CheckConstraint("length(btrim(texto)) > 0", name="texto_no_vacio"),
        sa.CheckConstraint("length(btrim(texto_version)) > 0", name="version_no_vacia"),
        sa.CheckConstraint(f"texto_hash ~ '{_HEX64}'", name="hash_formato"),
    )
    op.create_index(
        "ix_consentimiento_clinica_paciente_id",
        "consentimiento",
        ["clinica_id", "paciente_id", sa.text("id DESC")],
    )
    op.create_index(
        "ix_consentimiento_clinica_paciente_tipo",
        "consentimiento",
        ["clinica_id", "paciente_id", "tipo"],
    )

    op.create_table(
        "consentimiento_firma",
        _pk(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("consentimiento_id", sa.BigInteger(), nullable=False),
        _ts("firmado_en"),
        sa.Column("ip", sa.Text(), nullable=False),
        sa.Column("dispositivo", sa.Text(), nullable=False),
        sa.Column("texto_hash", sa.CHAR(64), nullable=False),
        sa.Column("firmante_nombre", sa.Text(), nullable=False),
        sa.Column("firmante_dni", sa.Text(), nullable=False),
        sa.Column("asistido_por_usuario_id", sa.BigInteger(), nullable=False),
        _fk(["clinica_id"], "clinica", ["id"], "fk_consentimiento_firma_clinica_id"),
        _fk(
            ["clinica_id", "paciente_id", "consentimiento_id"],
            "consentimiento",
            ["clinica_id", "paciente_id", "id"],
            "fk_consentimiento_firma_consentimiento",
        ),
        _fk(
            ["clinica_id", "asistido_por_usuario_id"],
            "usuario",
            ["clinica_id", "id"],
            "fk_consentimiento_firma_asistido_por_usuario_id",
        ),
        sa.UniqueConstraint(
            "clinica_id",
            "consentimiento_id",
            name="uq_consentimiento_firma_clinica_consentimiento",
        ),
        sa.CheckConstraint(f"texto_hash ~ '{_HEX64}'", name="hash_formato"),
        sa.CheckConstraint("length(btrim(firmante_nombre)) BETWEEN 1 AND 200", name="nombre_len"),
        sa.CheckConstraint("firmante_dni ~ '^[0-9]{7,8}$'", name="dni_formato"),
        sa.CheckConstraint("length(btrim(ip)) > 0", name="ip_no_vacia"),
        sa.CheckConstraint("length(dispositivo) BETWEEN 1 AND 512", name="dispositivo_len"),
    )

    op.create_table(
        "auditoria_admin",
        _pk(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("entidad_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "diff",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip", sa.Text(), nullable=True),
        _ts("created_at"),
        _fk(["clinica_id"], "clinica", ["id"], "fk_auditoria_admin_clinica_id"),
        _fk(
            ["clinica_id", "actor_usuario_id"],
            "usuario",
            ["clinica_id", "id"],
            "fk_auditoria_admin_actor_usuario_id",
        ),
        sa.CheckConstraint(
            "accion IN ('usuario_crear','usuario_roles','exportar')", name="accion_valida"
        ),
    )
    op.create_index(
        "ix_auditoria_admin_clinica_created", "auditoria_admin", ["clinica_id", "created_at"]
    )

    for tabla in _TABLAS:
        op.execute(
            f"CREATE TRIGGER trg_{tabla}_append_only_row BEFORE UPDATE OR DELETE ON {tabla} "
            "FOR EACH ROW EXECUTE FUNCTION fn_rechazar_mutacion()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{tabla}_append_only_truncate BEFORE TRUNCATE ON {tabla} "
            "FOR EACH STATEMENT EXECUTE FUNCTION fn_rechazar_mutacion()"
        )

    _ampliar_checks_auditoria(_ENTIDADES_NUEVAS, _ACCIONES_NUEVAS)


def downgrade() -> None:
    _ampliar_checks_auditoria(_ENTIDADES_VIEJAS, _ACCIONES_VIEJAS)
    for tabla in _TABLAS:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tabla}_append_only_truncate ON {tabla}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tabla}_append_only_row ON {tabla}")
    op.drop_table("auditoria_admin")
    op.drop_table("consentimiento_firma")
    op.drop_table("consentimiento")
