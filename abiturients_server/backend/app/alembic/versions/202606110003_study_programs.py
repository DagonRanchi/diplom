"""study program durations and academic year transitions

Revision ID: 202606110003
Revises: 202606110002
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa


revision = "202606110003"
down_revision = "202606110002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("education_details", sa.Column("nobd_specialty_code", sa.String(length=32)))
    op.add_column("education_details", sa.Column("study_duration_years", sa.Integer()))
    op.add_column("education_details", sa.Column("course_start_date", sa.Date()))
    op.add_column("education_details", sa.Column("course_end_date", sa.Date()))

    op.create_table(
        "academic_year_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("start_year", sa.Integer(), nullable=False),
        sa.Column("run_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("promoted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("graduated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_academic_year_transitions_start_year",
        "academic_year_transitions",
        ["start_year"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("academic_year_transitions")
    op.drop_column("education_details", "course_end_date")
    op.drop_column("education_details", "course_start_date")
    op.drop_column("education_details", "study_duration_years")
    op.drop_column("education_details", "nobd_specialty_code")
