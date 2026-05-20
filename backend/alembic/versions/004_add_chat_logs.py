"""add chat_logs table

Revision ID: 004
Revises: 003
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("voice_mode", sa.Boolean(), default=False),
        sa.Column("latency_ms", sa.Numeric(10, 2), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), default=0),
        sa.Column("completion_tokens", sa.Integer(), default=0),
        sa.Column("error", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_logs_user_id", "chat_logs", ["user_id"])
    op.create_index("ix_chat_logs_created_at", "chat_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("chat_logs")
