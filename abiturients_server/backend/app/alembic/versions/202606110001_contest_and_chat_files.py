"""contest workflow and chat attachments

Revision ID: 202606110001
Revises: 202606080001
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa


revision = "202606110001"
down_revision = "202606080001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("education_details", sa.Column("graduated_at", sa.DateTime(timezone=True)))

    op.create_table(
        "contest_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("benefit_group", sa.String(length=255)),
        sa.Column("residence_address", sa.String(length=500)),
        sa.Column("base_class", sa.String(length=64)),
        sa.Column("enrollment_type", sa.String(length=32), nullable=False, server_default="general"),
        sa.Column("locality_type", sa.String(length=32), nullable=False, server_default="urban"),
        sa.Column("instruction_language", sa.String(length=32)),
        sa.Column("study_form", sa.String(length=32), nullable=False, server_default="full_time"),
        sa.Column("needs_dormitory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("accepted_specialty_id", sa.Integer(), sa.ForeignKey("specialties.id", ondelete="SET NULL")),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_contest_profiles_base_class", "contest_profiles", ["base_class"])
    op.create_index("ix_contest_profiles_accepted_specialty_id", "contest_profiles", ["accepted_specialty_id"])

    op.create_table(
        "contest_choices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("specialty_id", sa.Integer(), sa.ForeignKey("specialties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("application_id", "specialty_id", name="uq_contest_application_specialty"),
    )
    op.create_index("ix_contest_choices_application_id", "contest_choices", ["application_id"])
    op.create_index("ix_contest_choices_specialty_id", "contest_choices", ["specialty_id"])
    op.create_index("ix_contest_choices_status", "contest_choices", ["status"])

    op.create_table(
        "chat_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_attachments_message_id", "chat_attachments", ["message_id"])


def downgrade() -> None:
    op.drop_table("chat_attachments")
    op.drop_table("contest_choices")
    op.drop_table("contest_profiles")
    op.drop_column("education_details", "graduated_at")
