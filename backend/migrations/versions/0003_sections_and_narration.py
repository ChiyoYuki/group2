"""Ordered content sections, media links and narrated package updates.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import context, op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("opening_question", sa.Text()))
        batch.add_column(sa.Column("dataset_key", sa.Text()))
        batch.add_column(sa.Column("dataset_version", sa.Integer()))
        batch.add_column(sa.Column("dataset_digest", sa.Text()))
        batch.add_column(sa.Column("dataset_imported_at", sa.DateTime(timezone=True)))
    with op.batch_alter_table("journey_entries") as batch:
        batch.add_column(sa.Column("import_key", sa.Text()))
        batch.create_unique_constraint(
            "uq_journey_entries_project_import_key", ["project_id", "import_key"]
        )
    with op.batch_alter_table("project_resources") as batch:
        batch.add_column(sa.Column("import_key", sa.Text()))
        batch.add_column(sa.Column("transcript", sa.Text()))
        batch.add_column(
            sa.Column("is_ai_generated", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(sa.Column("generation_note", sa.Text()))
        batch.add_column(sa.Column("sha256", sa.Text()))
        batch.create_unique_constraint(
            "uq_project_resources_project_identity", ["project_id", "id"]
        )
        batch.create_unique_constraint(
            "uq_project_resources_project_import_key", ["project_id", "import_key"]
        )
    op.create_table(
        "project_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("journey_entry_id", sa.Uuid()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_sections"),
        sa.UniqueConstraint("project_id", "id", name="uq_project_sections_project_identity"),
        sa.UniqueConstraint("project_id", "key", name="uq_project_sections_project_key"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
            name="fk_project_sections_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "journey_entry_id"],
            ["journey_entries.project_id", "journey_entries.id"],
            ondelete="NO ACTION",
            deferrable=True,
            initially="DEFERRED",
            name="fk_project_sections_same_project_journey",
        ),
        sa.CheckConstraint(
            "kind IN ('opening', 'journey', 'output', 'learning', 'other')",
            name=op.f("ck_project_sections_valid_kind"),
        ),
        sa.CheckConstraint(
            "kind != 'journey' OR journey_entry_id IS NOT NULL",
            name=op.f("ck_project_sections_journey_required"),
        ),
        sa.CheckConstraint("length(trim(key)) > 0", name=op.f("ck_project_sections_key_not_blank")),
        sa.CheckConstraint(
            "length(trim(title)) > 0", name=op.f("ck_project_sections_title_not_blank")
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_project_sections_nonnegative_sort_order")
        ),
    )
    op.create_index(
        "ix_project_sections_display", "project_sections", ["project_id", "sort_order", "id"]
    )
    op.create_table(
        "section_resources",
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("section_id", "resource_id", name="pk_section_resources"),
        sa.ForeignKeyConstraint(
            ["project_id", "section_id"],
            ["project_sections.project_id", "project_sections.id"],
            ondelete="CASCADE",
            name="fk_section_resources_same_project_section",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "resource_id"],
            ["project_resources.project_id", "project_resources.id"],
            ondelete="CASCADE",
            name="fk_section_resources_same_project_resource",
        ),
        sa.CheckConstraint(
            "role IN ('illustration', 'narration', 'attachment')",
            name=op.f("ck_section_resources_valid_role"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_section_resources_nonnegative_sort_order")
        ),
    )
    op.create_index(
        "ix_section_resources_resource", "section_resources", ["project_id", "resource_id"]
    )


def downgrade() -> None:
    # Check the older revision's prerequisite before SQLite performs any DDL.
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
    op.drop_table("section_resources")
    op.drop_table("project_sections")
    with op.batch_alter_table("project_resources") as batch:
        batch.drop_constraint("uq_project_resources_project_import_key", type_="unique")
        batch.drop_constraint("uq_project_resources_project_identity", type_="unique")
        for name in ("sha256", "generation_note", "is_ai_generated", "transcript", "import_key"):
            batch.drop_column(name)
    with op.batch_alter_table("journey_entries") as batch:
        batch.drop_constraint("uq_journey_entries_project_import_key", type_="unique")
        batch.drop_column("import_key")
    with op.batch_alter_table("projects") as batch:
        for name in (
            "dataset_imported_at",
            "dataset_digest",
            "dataset_version",
            "dataset_key",
            "opening_question",
        ):
            batch.drop_column(name)
