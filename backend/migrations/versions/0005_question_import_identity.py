"""Generic stable identifiers for imported research questions.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import context, op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_questions") as batch:
        batch.add_column(sa.Column("import_key", sa.Text(), nullable=True))
        batch.create_unique_constraint(
            "uq_project_questions_project_import_key", ["project_id", "import_key"]
        )


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
    with op.batch_alter_table("project_questions") as batch:
        batch.drop_constraint("uq_project_questions_project_import_key", type_="unique")
        batch.drop_column("import_key")
