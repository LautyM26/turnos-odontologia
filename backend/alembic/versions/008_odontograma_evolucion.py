"""008 odontograma y evolucion: historia clínica append-only (C-09).

``odontograma`` guarda un snapshot completo por versión (JSONB disperso por código FDI);
``evolucion`` guarda cada atención con autor profesional y se corrige con una fila nueva
(``corrige_a_id``). Ambas son inmutables: reutilizan ``fn_rechazar_mutacion()`` de la 004 con
triggers por fila (UPDATE/DELETE) y por sentencia (TRUNCATE). Integridad tenant por FK compuesta
``(clinica_id, x)``. Amplía los CHECK de ``auditoria_hc`` (entidades ``odontograma``/``evolucion``,
acción ``corregir``).

``down_revision`` apunta a la 006 (C-05c / 007 aún sin mergear). Si C-05c mergea antes, re-apuntar
a ``007_sobreturno_huecos`` y verificar ``alembic heads`` (un único head).

ROLLBACK: ``alembic downgrade 006_turno_transicion`` borra odontogramas y evoluciones. NO borra
``fn_rechazar_mutacion()`` (es de la 004). Si ya hay eventos ``odontograma``/``evolucion``/
``corregir`` en ``auditoria_hc``, restaurar los CHECK angostos falla y esas filas no se pueden
borrar (trigger): es intencional. En producción no se hace downgrade, se hace roll-forward.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_odontograma_evolucion"
down_revision: str | None = "006_turno_transicion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTIDADES_NUEVAS = "('paciente','ficha','adjunto','odontograma','evolucion')"
_ENTIDADES_VIEJAS = "('paciente','ficha','adjunto')"
_ACCIONES_NUEVAS = (
    "('crear','actualizar','leer','descargar',"
    "'consentimiento_otorgado','consentimiento_revocado','corregir')"
)
_ACCIONES_VIEJAS = (
    "('crear','actualizar','leer','descargar','consentimiento_otorgado','consentimiento_revocado')"
)
_TABLAS = ("odontograma", "evolucion")


def _pk() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True)


def _fk(
    table: str, cols: list[str], ref: str, refcols: list[str], name: str
) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        cols, [f"{ref}.{c}" for c in refcols], name=name, ondelete="RESTRICT"
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
        "odontograma",
        _pk(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("denticion", sa.Text(), nullable=False),
        sa.Column(
            "piezas",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("autor_usuario_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        _fk("odontograma", ["clinica_id"], "clinica", ["id"], "fk_odontograma_clinica_id"),
        _fk(
            "odontograma",
            ["clinica_id", "paciente_id"],
            "paciente",
            ["clinica_id", "id"],
            "fk_odontograma_paciente",
        ),
        _fk(
            "odontograma",
            ["clinica_id", "autor_usuario_id"],
            "usuario",
            ["clinica_id", "id"],
            "fk_odontograma_autor_usuario_id",
        ),
        sa.UniqueConstraint(
            "clinica_id", "paciente_id", "version", name="uq_odontograma_clinica_paciente_version"
        ),
        sa.CheckConstraint("version > 0", name="version_positiva"),
        sa.CheckConstraint(
            "denticion IN ('permanente','temporal','mixta')", name="denticion_valida"
        ),
        sa.CheckConstraint("jsonb_typeof(piezas) = 'object'", name="piezas_objeto"),
    )
    op.create_index(
        "ix_odontograma_piezas_gin",
        "odontograma",
        ["piezas"],
        postgresql_using="gin",
        postgresql_ops={"piezas": "jsonb_path_ops"},
    )

    op.create_table(
        "evolucion",
        _pk(),
        sa.Column("clinica_id", sa.BigInteger(), nullable=False),
        sa.Column("paciente_id", sa.BigInteger(), nullable=False),
        sa.Column("autor_usuario_id", sa.BigInteger(), nullable=False),
        sa.Column("profesional_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "fecha_hora", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("pieza_fdi", sa.SmallInteger(), nullable=True),
        sa.Column("corrige_a_id", sa.BigInteger(), nullable=True),
        sa.Column("motivo_correccion", sa.Text(), nullable=True),
        _fk("evolucion", ["clinica_id"], "clinica", ["id"], "fk_evolucion_clinica_id"),
        _fk(
            "evolucion",
            ["clinica_id", "paciente_id"],
            "paciente",
            ["clinica_id", "id"],
            "fk_evolucion_paciente",
        ),
        _fk(
            "evolucion",
            ["clinica_id", "autor_usuario_id"],
            "usuario",
            ["clinica_id", "id"],
            "fk_evolucion_autor_usuario_id",
        ),
        _fk(
            "evolucion",
            ["clinica_id", "profesional_id"],
            "profesional",
            ["clinica_id", "id"],
            "fk_evolucion_profesional",
        ),
        sa.UniqueConstraint(
            "clinica_id", "paciente_id", "id", name="uq_evolucion_clinica_paciente_id"
        ),
        sa.CheckConstraint("length(btrim(texto)) BETWEEN 1 AND 10000", name="texto_len"),
        sa.CheckConstraint(
            "pieza_fdi IS NULL "
            "OR (pieza_fdi / 10 BETWEEN 1 AND 4 AND pieza_fdi % 10 BETWEEN 1 AND 8) "
            "OR (pieza_fdi / 10 BETWEEN 5 AND 8 AND pieza_fdi % 10 BETWEEN 1 AND 5)",
            name="pieza_fdi_valida",
        ),
        sa.CheckConstraint(
            "(corrige_a_id IS NULL) = (motivo_correccion IS NULL)", name="correccion"
        ),
        sa.CheckConstraint(
            "motivo_correccion IS NULL OR length(btrim(motivo_correccion)) BETWEEN 1 AND 500",
            name="motivo_len",
        ),
        sa.CheckConstraint("corrige_a_id IS NULL OR corrige_a_id <> id", name="no_se_autocorrige"),
    )
    # FK propia: la base impide corregir una evolución de otro paciente o de otra clínica.
    op.create_foreign_key(
        "fk_evolucion_corrige_a",
        "evolucion",
        "evolucion",
        ["clinica_id", "paciente_id", "corrige_a_id"],
        ["clinica_id", "paciente_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_evolucion_clinica_paciente_id",
        "evolucion",
        ["clinica_id", "paciente_id", sa.text("id DESC")],
    )
    op.create_index(
        "uq_evolucion_corrige_a",
        "evolucion",
        ["clinica_id", "corrige_a_id"],
        unique=True,
        postgresql_where=sa.text("corrige_a_id IS NOT NULL"),
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
    op.drop_table("evolucion")
    op.drop_table("odontograma")
