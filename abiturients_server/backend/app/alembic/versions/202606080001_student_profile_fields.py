"""student profile fields and expulsion

Revision ID: 202606080001
Revises: 202605140001
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa


revision = "202606080001"
down_revision = "202605140001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admission_details",
        sa.Column("enrollment_type", sa.String(length=32), nullable=False, server_default="general"),
    )
    op.add_column(
        "admission_details",
        sa.Column("locality_type", sa.String(length=32), nullable=False, server_default="urban"),
    )
    op.add_column("admission_details", sa.Column("instruction_language", sa.String(length=32)))
    op.add_column(
        "admission_details",
        sa.Column("study_form", sa.String(length=32), nullable=False, server_default="full_time"),
    )
    op.add_column(
        "admission_details",
        sa.Column("needs_dormitory", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column(
        "education_details",
        sa.Column("has_scholarship", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("education_details", sa.Column("scholarship_amount", sa.Integer()))
    op.add_column(
        "education_details",
        sa.Column("academic_leave", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("education_details", sa.Column("academic_performance", sa.String(length=32)))
    op.add_column("education_details", sa.Column("expulsion_order_number", sa.String(length=100)))
    op.add_column("education_details", sa.Column("expulsion_order_date", sa.Date()))
    op.add_column("education_details", sa.Column("expulsion_reason", sa.Text()))
    op.add_column("education_details", sa.Column("expelled_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("education_details", "expelled_at")
    op.drop_column("education_details", "expulsion_reason")
    op.drop_column("education_details", "expulsion_order_date")
    op.drop_column("education_details", "expulsion_order_number")
    op.drop_column("education_details", "academic_performance")
    op.drop_column("education_details", "academic_leave")
    op.drop_column("education_details", "scholarship_amount")
    op.drop_column("education_details", "has_scholarship")

    op.drop_column("admission_details", "needs_dormitory")
    op.drop_column("admission_details", "study_form")
    op.drop_column("admission_details", "instruction_language")
    op.drop_column("admission_details", "locality_type")
    op.drop_column("admission_details", "enrollment_type")
