"""002 token blacklist: token_blacklist (C-03, D5).

Blacklist persistente de jti revocados/rotados. Purga por exp (btree).
Sin datos previos: tabla nueva, despliegue sin downtime.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002_token_blacklist"
down_revision: str | None = "001_core_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "token_blacklist",
        sa.Column("jti", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("exp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "revocado_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "type IN ('access', 'refresh')", name="token_blacklist_type"
        ),
        sa.PrimaryKeyConstraint("jti", name="pk_token_blacklist"),
    )
    op.create_index("ix_token_blacklist_exp", "token_blacklist", ["exp"])


def downgrade() -> None:
    op.drop_index("ix_token_blacklist_exp", table_name="token_blacklist")
    op.drop_table("token_blacklist")
