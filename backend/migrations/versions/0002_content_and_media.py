"""Structured questions, content provenance, media metadata and unknown cohorts.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import context, op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

RESOURCE_CHECKS = {
    "valid_usage_role": "usage_role IN ('output', 'process', 'reference')",
    "valid_rights_status": (
        "rights_status IN ('unconfirmed', 'permission_confirmed', 'open_license')"
    ),
    "nonnegative_size": "file_size_bytes IS NULL OR file_size_bytes >= 0",
    "positive_width": "width IS NULL OR width > 0",
    "positive_height": "height IS NULL OR height > 0",
    "nonnegative_duration": "duration_seconds IS NULL OR duration_seconds >= 0",
}


def resource_columns():
    return [
        sa.Column("usage_role", sa.Text(), nullable=False, server_default="output"),
        sa.Column("caption", sa.Text()),
        sa.Column("alt_text", sa.Text()),
        sa.Column("source_name", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("original_url", sa.Text()),
        sa.Column("creator_credit", sa.Text()),
        sa.Column("original_activity", sa.Text()),
        sa.Column("provenance_note", sa.Text()),
        sa.Column("rights_status", sa.Text(), nullable=False, server_default="unconfirmed"),
        sa.Column("rights_note", sa.Text()),
        sa.Column("file_size_bytes", sa.BigInteger()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("duration_seconds", sa.Numeric(12, 3)),
    ]


def upgrade():
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("cohort_id", existing_type=sa.Uuid(), nullable=True)
        batch.add_column(sa.Column("background", sa.Text()))
        batch.add_column(
            sa.Column("content_kind", sa.Text(), nullable=False, server_default="unspecified")
        )
        batch.add_column(sa.Column("content_notice", sa.Text()))
        batch.add_column(sa.Column("content_tags", sa.JSON(), nullable=False, server_default="[]"))
        batch.create_check_constraint(
            op.f("ck_projects_valid_content_kind"),
            "content_kind IN ('unspecified', 'documented', 'reconstructed', 'fictional')",
        )
    with op.batch_alter_table("journey_entries") as batch:
        batch.add_column(sa.Column("method_tags", sa.JSON(), nullable=False, server_default="[]"))
    with op.batch_alter_table("project_resources") as batch:
        for column in resource_columns():
            batch.add_column(column)
        for name, expression in RESOURCE_CHECKS.items():
            batch.create_check_constraint(op.f(f"ck_project_resources_{name}"), expression)
    op.create_table(
        "project_questions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.Text()),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name=op.f("fk_project_questions_project_id_projects"),
        ),
        sa.CheckConstraint(
            "length(trim(question)) > 0", name=op.f("ck_project_questions_question_not_blank")
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_project_questions_nonnegative_sort_order")
        ),
    )
    op.create_index(
        "ix_project_questions_display", "project_questions", ["project_id", "sort_order", "id"]
    )


def downgrade():
    if not context.is_offline_mode():
        missing = (
            op.get_bind()
            .execute(sa.text("SELECT count(*) FROM projects WHERE cohort_id IS NULL"))
            .scalar()
        )
        if missing:
            raise RuntimeError(
                "Assign cohorts to projects with unknown cohorts before downgrading to 0001"
            )
    op.drop_table("project_questions")
    with op.batch_alter_table("project_resources") as batch:
        for name in RESOURCE_CHECKS:
            batch.drop_constraint(op.f(f"ck_project_resources_{name}"), type_="check")
        for column in reversed(resource_columns()):
            batch.drop_column(column.name)
    with op.batch_alter_table("journey_entries") as batch:
        batch.drop_column("method_tags")
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint(op.f("ck_projects_valid_content_kind"), type_="check")
        for name in ("content_tags", "content_notice", "content_kind", "background"):
            batch.drop_column(name)
        batch.alter_column("cohort_id", existing_type=sa.Uuid(), nullable=False)
