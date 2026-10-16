"""initial payments and outbox

Revision ID: 001
Revises:
Create Date: 2026-03-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

currency_enum = postgresql.ENUM("RUB", "USD", "EUR", name="currency_enum", create_type=False)
payment_status_enum = postgresql.ENUM(
    "pending", "succeeded", "failed", name="payment_status_enum", create_type=False
)
outbox_status_enum = postgresql.ENUM(
    "pending", "published", "failed", name="outbox_status_enum", create_type=False
)


def upgrade() -> None:
    op.execute("CREATE TYPE currency_enum AS ENUM ('RUB', 'USD', 'EUR')")
    op.execute("CREATE TYPE payment_status_enum AS ENUM ('pending', 'succeeded', 'failed')")
    op.execute("CREATE TYPE outbox_status_enum AS ENUM ('pending', 'published', 'failed')")

    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", currency_enum, nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            payment_status_enum,
            server_default="pending",
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("webhook_url", sa.String(length=2048), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_payments_status", "payments", ["status"], unique=False)
    op.create_index("ix_payments_created_at", "payments", ["created_at"], unique=False)

    op.create_table(
        "outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            outbox_status_enum,
            server_default="pending",
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outbox_status_created_at", "outbox", ["status", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_status_created_at", table_name="outbox")
    op.drop_table("outbox")
    op.drop_index("ix_payments_created_at", table_name="payments")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_table("payments")
    op.execute("DROP TYPE outbox_status_enum")
    op.execute("DROP TYPE payment_status_enum")
    op.execute("DROP TYPE currency_enum")
