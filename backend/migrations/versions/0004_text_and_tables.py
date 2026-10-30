"""Short project titles and portable Markdown/CSV resource content.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import context, op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("short_title", sa.Text(), nullable=True))
    with op.batch_alter_table("project_resources") as batch:
        batch.add_column(sa.Column("content_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("structured_data", sa.JSON(), nullable=True))


def downgrade() -> None:
    if not context.is_offline_mode() and context.get_revision_argument() in {None, "0001"}:
        missing = (
            op.get_bind()
            .execute(sa.text("SELECT count(*) FROM projects WHERE cohort_id IS NULL"))
            .scalar()
        )
        if missing:
            raise RuntimeError(
                "Assign cohorts to projects with unknown cohorts before downgrading to 0001"
            )
    with op.batch_alter_table("project_resources") as batch:
        batch.drop_column("structured_data")
        batch.drop_column("content_text")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("short_title")
