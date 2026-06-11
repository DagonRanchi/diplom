"""contingent import source rows

Revision ID: 202606110004
Revises: 202606110003
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa


revision = "202606110004"
down_revision = "202606110003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contingent_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("headers_json", sa.Text(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("normalized_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_contingent_imports_checksum", "contingent_imports", ["checksum"], unique=True)

    op.create_table(
        "contingent_source_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "import_id",
            sa.Integer(),
            sa.ForeignKey("contingent_imports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_ei", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("raw_row_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_contingent_source_rows_import_id", "contingent_source_rows", ["import_id"])
    op.create_index("ix_contingent_source_rows_external_ei", "contingent_source_rows", ["external_ei"], unique=True)
    op.create_index("ix_contingent_source_rows_external_id", "contingent_source_rows", ["external_id"])


def downgrade() -> None:
    op.drop_table("contingent_source_rows")
    op.drop_table("contingent_imports")
