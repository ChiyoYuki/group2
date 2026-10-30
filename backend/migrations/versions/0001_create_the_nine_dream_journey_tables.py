"""create the nine Dream Journey tables

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cohorts",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_cohorts_name_not_blank")),
        sa.CheckConstraint("year >= 1", name=op.f("ck_cohorts_positive_year")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cohorts")),
        sa.UniqueConstraint("name", name=op.f("uq_cohorts_name")),
    )
    op.create_table(
        "resource_types",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(code)) > 0", name=op.f("ck_resource_types_code_not_blank")),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_resource_types_name_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resource_types")),
        sa.UniqueConstraint("code", name=op.f("uq_resource_types_code")),
    )
    op.create_table(
        "themes",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_themes_name_not_blank")),
        sa.CheckConstraint("length(trim(slug)) > 0", name=op.f("ck_themes_slug_not_blank")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_themes")),
        sa.UniqueConstraint("name", name=op.f("uq_themes_name")),
        sa.UniqueConstraint("slug", name=op.f("uq_themes_slug")),
    )
    op.create_table(
        "projects",
        sa.Column("cohort_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("team_name", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("research_question", sa.Text(), nullable=False),
        sa.Column("research_methods", sa.Text(), server_default="", nullable=False),
        sa.Column("learning_outcomes", sa.Text(), server_default="", nullable=False),
        sa.Column("practical_tips", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_featured", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("featured_reason", sa.Text(), nullable=True),
        sa.Column("featured_rank", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status != 'published' OR published_at IS NOT NULL",
            name=op.f("ck_projects_published_at_required"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')", name=op.f("ck_projects_valid_status")
        ),
        sa.CheckConstraint(
            "featured_rank >= 0", name=op.f("ck_projects_nonnegative_featured_rank")
        ),
        sa.CheckConstraint("length(trim(slug)) > 0", name=op.f("ck_projects_slug_not_blank")),
        sa.CheckConstraint("length(trim(title)) > 0", name=op.f("ck_projects_title_not_blank")),
        sa.ForeignKeyConstraint(
            ["cohort_id"],
            ["cohorts.id"],
            name=op.f("fk_projects_cohort_id_cohorts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint("slug", name=op.f("uq_projects_slug")),
    )
    op.create_index(
        "ix_projects_featured",
        "projects",
        [
            sa.literal_column("featured_rank DESC"),
            sa.literal_column("published_at DESC"),
            sa.literal_column("id DESC"),
        ],
        unique=False,
        postgresql_where=sa.text("status = 'published' AND is_featured = true"),
        sqlite_where=sa.text("status = 'published' AND is_featured = true"),
    )
    op.create_index(
        "ix_projects_public_cohort",
        "projects",
        ["cohort_id", sa.literal_column("published_at DESC"), sa.literal_column("id DESC")],
        unique=False,
        postgresql_where=sa.text("status = 'published'"),
        sqlite_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "ix_projects_public_published",
        "projects",
        [sa.literal_column("published_at DESC"), sa.literal_column("id DESC")],
        unique=False,
        postgresql_where=sa.text("status = 'published'"),
        sqlite_where=sa.text("status = 'published'"),
    )
    op.create_table(
        "journey_entries",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("challenges", sa.Text(), nullable=True),
        sa.Column("responses", sa.Text(), nullable=True),
        sa.Column("reflection", sa.Text(), nullable=True),
        sa.Column("occurred_on", sa.Date(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0", name=op.f("ck_journey_entries_title_not_blank")
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_journey_entries_nonnegative_sort_order")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_journey_entries_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_journey_entries")),
        sa.UniqueConstraint("project_id", "id", name=op.f("uq_journey_entries_project_id")),
    )
    op.create_index(
        "ix_journey_entries_display",
        "journey_entries",
        ["project_id", "sort_order", "id"],
        unique=False,
    )
    op.create_table(
        "project_impacts",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=True),
        sa.Column("evidence_url", sa.Text(), nullable=True),
        sa.Column("metric_name", sa.Text(), nullable=True),
        sa.Column("metric_value", sa.Numeric(), nullable=True),
        sa.Column("metric_unit", sa.Text(), nullable=True),
        sa.Column("metric_scope", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('educational', 'social')", name=op.f("ck_project_impacts_valid_category")
        ),
        sa.CheckConstraint(
            "(metric_name IS NULL AND metric_value IS NULL AND metric_unit IS NULL "
            "AND metric_scope IS NULL) OR (metric_name IS NOT NULL AND metric_value IS NOT NULL "
            "AND metric_unit IS NOT NULL AND metric_scope IS NOT NULL "
            "AND length(trim(metric_name)) > 0 AND length(trim(metric_unit)) > 0 "
            "AND length(trim(metric_scope)) > 0)",
            name=op.f("ck_project_impacts_complete_metric"),
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0", name=op.f("ck_project_impacts_title_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_impacts_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_impacts")),
    )
    op.create_index(
        "ix_project_impacts_project_id", "project_impacts", ["project_id"], unique=False
    )
    op.create_table(
        "project_members",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("school_name", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(display_name)) > 0", name=op.f("ck_project_members_display_name_not_blank")
        ),
        sa.CheckConstraint(
            "length(trim(role)) > 0", name=op.f("ck_project_members_role_not_blank")
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_project_members_nonnegative_sort_order")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_members_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_members")),
    )
    op.create_index(
        "ix_project_members_display",
        "project_members",
        ["project_id", "sort_order", "id"],
        unique=False,
    )
    op.create_table(
        "project_themes",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("theme_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_themes_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["theme_id"],
            ["themes.id"],
            name=op.f("fk_project_themes_theme_id_themes"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("project_id", "theme_id", name=op.f("pk_project_themes")),
    )
    op.create_index(
        "ix_project_themes_theme_id", "project_themes", ["theme_id", "project_id"], unique=False
    )
    op.create_table(
        "project_resources",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("journey_entry_id", sa.Uuid(), nullable=True),
        sa.Column("resource_type_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("resource_url", sa.Text(), nullable=False),
        sa.Column("preview_url", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(resource_url)) > 0", name=op.f("ck_project_resources_url_not_blank")
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0", name=op.f("ck_project_resources_title_not_blank")
        ),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_project_resources_nonnegative_sort_order")
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "journey_entry_id"],
            ["journey_entries.project_id", "journey_entries.id"],
            name="fk_project_resources_same_project_journey",
            ondelete="NO ACTION",
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_resources_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resource_type_id"],
            ["resource_types.id"],
            name=op.f("fk_project_resources_resource_type_id_resource_types"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_resources")),
    )
    op.create_index(
        "ix_project_resources_display",
        "project_resources",
        ["project_id", "sort_order", "id"],
        unique=False,
    )
    op.create_index(
        "ix_project_resources_journey",
        "project_resources",
        ["project_id", "journey_entry_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_resources_resource_type_id",
        "project_resources",
        ["resource_type_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_project_resources_resource_type_id", table_name="project_resources")
    op.drop_index("ix_project_resources_journey", table_name="project_resources")
    op.drop_index("ix_project_resources_display", table_name="project_resources")
    op.drop_table("project_resources")
    op.drop_index("ix_project_themes_theme_id", table_name="project_themes")
    op.drop_table("project_themes")
    op.drop_index("ix_project_members_display", table_name="project_members")
    op.drop_table("project_members")
    op.drop_index("ix_project_impacts_project_id", table_name="project_impacts")
    op.drop_table("project_impacts")
    op.drop_index("ix_journey_entries_display", table_name="journey_entries")
    op.drop_table("journey_entries")
    op.drop_index(
        "ix_projects_public_published",
        table_name="projects",
        postgresql_where=sa.text("status = 'published'"),
        sqlite_where=sa.text("status = 'published'"),
    )
    op.drop_index(
        "ix_projects_public_cohort",
        table_name="projects",
        postgresql_where=sa.text("status = 'published'"),
        sqlite_where=sa.text("status = 'published'"),
    )
    op.drop_index(
        "ix_projects_featured",
        table_name="projects",
        postgresql_where=sa.text("status = 'published' AND is_featured = true"),
        sqlite_where=sa.text("status = 'published' AND is_featured = true"),
    )
    op.drop_table("projects")
    op.drop_table("themes")
    op.drop_table("resource_types")
    op.drop_table("cohorts")
