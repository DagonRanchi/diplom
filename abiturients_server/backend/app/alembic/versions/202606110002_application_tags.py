"""application tags

Revision ID: 202606110002
Revises: 202606110001
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa


revision = "202606110002"
down_revision = "202606110001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("application_id", "name", name="uq_application_tag_name"),
    )
    op.create_index("ix_application_tags_application_id", "application_tags", ["application_id"])
    op.create_index("ix_application_tags_name", "application_tags", ["name"])


def downgrade() -> None:
    op.drop_table("application_tags")
