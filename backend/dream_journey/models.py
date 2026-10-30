"""Project archive, structured questions, media and content provenance."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
    true,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from dream_journey.types import UTCDateTime


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class RecordMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        default=utc_now,
        server_default=func.now(),
        onupdate=utc_now,
        nullable=False,
    )


class User(RecordMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(username)) >= 3", name="username_min_length"),
        CheckConstraint("length(trim(password_hash)) > 0", name="password_hash_not_blank"),
    )

    username: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)


class AuthSession(RecordMixin, Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user_id", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_digest: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class Cohort(RecordMixin, Base):
    __tablename__ = "cohorts"
    __table_args__ = (
        CheckConstraint("year >= 1", name="positive_year"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )

    name: Mapped[str] = mapped_column(Text, unique=True)
    year: Mapped[int] = mapped_column(SmallInteger)
    description: Mapped[str | None] = mapped_column(Text)


class Theme(RecordMixin, Base):
    __tablename__ = "themes"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("length(trim(slug)) > 0", name="slug_not_blank"),
    )

    name: Mapped[str] = mapped_column(Text, unique=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class Project(RecordMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        CheckConstraint("length(trim(slug)) > 0", name="slug_not_blank"),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="valid_status"),
        CheckConstraint("featured_rank >= 0", name="nonnegative_featured_rank"),
        CheckConstraint(
            "content_kind IN ('unspecified', 'documented', 'reconstructed', 'fictional')",
            name="valid_content_kind",
        ),
        CheckConstraint(
            "status != 'published' OR published_at IS NOT NULL",
            name="published_at_required",
        ),
    )

    cohort_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cohorts.id", ondelete="RESTRICT")
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(Text)
    short_title: Mapped[str | None] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    summary: Mapped[str] = mapped_column(Text)
    background: Mapped[str | None] = mapped_column(Text)
    opening_question: Mapped[str | None] = mapped_column(Text)
    dataset_key: Mapped[str | None] = mapped_column(Text)
    dataset_version: Mapped[int | None] = mapped_column(Integer)
    dataset_digest: Mapped[str | None] = mapped_column(Text)
    dataset_imported_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    content_kind: Mapped[str] = mapped_column(
        Text, default="unspecified", server_default="unspecified"
    )
    content_notice: Mapped[str | None] = mapped_column(Text)
    content_tags: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        server_default="[]",
    )
    location: Mapped[str | None] = mapped_column(Text)
    team_name: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(Text)
    research_question: Mapped[str] = mapped_column(Text)
    research_methods: Mapped[str] = mapped_column(Text, default="", server_default="")
    learning_outcomes: Mapped[str] = mapped_column(Text, default="", server_default="")
    practical_tips: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(Text, default="draft", server_default="draft")
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    featured_reason: Mapped[str | None] = mapped_column(Text)
    featured_rank: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    cohort: Mapped[Cohort | None] = relationship(lazy="raise")
    themes: Mapped[list[Theme]] = relationship(secondary="project_themes", lazy="raise")
    questions: Mapped[list[ProjectQuestion]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="(ProjectQuestion.sort_order, ProjectQuestion.id)",
    )
    sections: Mapped[list[ProjectSection]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="(ProjectSection.sort_order, ProjectSection.id)",
    )
    members: Mapped[list[ProjectMember]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="(ProjectMember.sort_order, ProjectMember.id)",
    )
    journey_entries: Mapped[list[JourneyEntry]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="(JourneyEntry.sort_order, JourneyEntry.id)",
    )
    resources: Mapped[list[ProjectResource]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="(ProjectResource.sort_order, ProjectResource.id)",
    )
    impacts: Mapped[list[ProjectImpact]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="(ProjectImpact.created_at, ProjectImpact.id)",
    )


class ProjectTheme(Base):
    __tablename__ = "project_themes"
    __table_args__ = (Index("ix_project_themes_theme_id", "theme_id", "project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("themes.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class ProjectQuestion(RecordMixin, Base):
    __tablename__ = "project_questions"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "import_key", name="uq_project_questions_project_import_key"
        ),
        CheckConstraint("length(trim(question)) > 0", name="question_not_blank"),
        CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        Index("ix_project_questions_display", "project_id", "sort_order", "id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    import_key: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class ProjectMember(RecordMixin, Base):
    __tablename__ = "project_members"
    __table_args__ = (
        CheckConstraint("length(trim(display_name)) > 0", name="display_name_not_blank"),
        CheckConstraint("length(trim(role)) > 0", name="role_not_blank"),
        CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        Index("ix_project_members_display", "project_id", "sort_order", "id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    display_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    school_name: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class JourneyEntry(RecordMixin, Base):
    __tablename__ = "journey_entries"
    __table_args__ = (
        UniqueConstraint("project_id", "id"),
        UniqueConstraint("project_id", "import_key", name="uq_journey_entries_project_import_key"),
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        Index("ix_journey_entries_display", "project_id", "sort_order", "id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    import_key: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    method_tags: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        default=list,
        server_default="[]",
    )
    challenges: Mapped[str | None] = mapped_column(Text)
    responses: Mapped[str | None] = mapped_column(Text)
    reflection: Mapped[str | None] = mapped_column(Text)
    occurred_on: Mapped[date | None] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class ResourceType(RecordMixin, Base):
    __tablename__ = "resource_types"
    __table_args__ = (
        CheckConstraint("length(trim(code)) > 0", name="code_not_blank"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )

    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)


class ProjectResource(RecordMixin, Base):
    __tablename__ = "project_resources"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_project_resources_project_identity"),
        UniqueConstraint(
            "project_id", "import_key", name="uq_project_resources_project_import_key"
        ),
        ForeignKeyConstraint(
            ["project_id", "journey_entry_id"],
            ["journey_entries.project_id", "journey_entries.id"],
            name="fk_project_resources_same_project_journey",
            ondelete="NO ACTION",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        CheckConstraint("length(trim(resource_url)) > 0", name="url_not_blank"),
        CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        CheckConstraint(
            "usage_role IN ('output', 'process', 'reference')", name="valid_usage_role"
        ),
        CheckConstraint(
            "rights_status IN ('unconfirmed', 'permission_confirmed', 'open_license')",
            name="valid_rights_status",
        ),
        CheckConstraint("file_size_bytes IS NULL OR file_size_bytes >= 0", name="nonnegative_size"),
        CheckConstraint("width IS NULL OR width > 0", name="positive_width"),
        CheckConstraint("height IS NULL OR height > 0", name="positive_height"),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="nonnegative_duration",
        ),
        Index("ix_project_resources_display", "project_id", "sort_order", "id"),
        Index("ix_project_resources_journey", "project_id", "journey_entry_id"),
        Index("ix_project_resources_resource_type_id", "resource_type_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    import_key: Mapped[str | None] = mapped_column(Text)
    journey_entry_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    resource_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resource_types.id", ondelete="RESTRICT"),
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    structured_data: Mapped[dict | None] = mapped_column(MutableDict.as_mutable(JSON))
    resource_url: Mapped[str] = mapped_column(Text)
    preview_url: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    usage_role: Mapped[str] = mapped_column(Text, default="output", server_default="output")
    caption: Mapped[str | None] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    original_url: Mapped[str | None] = mapped_column(Text)
    creator_credit: Mapped[str | None] = mapped_column(Text)
    original_activity: Mapped[str | None] = mapped_column(Text)
    provenance_note: Mapped[str | None] = mapped_column(Text)
    rights_status: Mapped[str] = mapped_column(
        Text, default="unconfirmed", server_default="unconfirmed"
    )
    rights_note: Mapped[str | None] = mapped_column(Text)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    transcript: Mapped[str | None] = mapped_column(Text)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    generation_note: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    resource_type: Mapped[ResourceType] = relationship(lazy="raise")


class ProjectSection(RecordMixin, Base):
    __tablename__ = "project_sections"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_project_sections_project_identity"),
        UniqueConstraint("project_id", "key", name="uq_project_sections_project_key"),
        ForeignKeyConstraint(
            ["project_id", "journey_entry_id"],
            ["journey_entries.project_id", "journey_entries.id"],
            name="fk_project_sections_same_project_journey",
            ondelete="NO ACTION",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "kind IN ('opening', 'journey', 'output', 'learning', 'other')", name="valid_kind"
        ),
        CheckConstraint(
            "kind != 'journey' OR journey_entry_id IS NOT NULL", name="journey_required"
        ),
        CheckConstraint("length(trim(key)) > 0", name="key_not_blank"),
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        Index("ix_project_sections_display", "project_id", "sort_order", "id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    journey_entry_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    media: Mapped[list[SectionResource]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="(SectionResource.sort_order, SectionResource.resource_id)",
    )


class SectionResource(Base):
    __tablename__ = "section_resources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "section_id"],
            ["project_sections.project_id", "project_sections.id"],
            name="fk_section_resources_same_project_section",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["project_id", "resource_id"],
            ["project_resources.project_id", "project_resources.id"],
            name="fk_section_resources_same_project_resource",
            ondelete="CASCADE",
        ),
        CheckConstraint("role IN ('illustration', 'narration', 'attachment')", name="valid_role"),
        CheckConstraint("sort_order >= 0", name="nonnegative_sort_order"),
        Index("ix_section_resources_resource", "project_id", "resource_id"),
    )

    section_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    role: Mapped[str] = mapped_column(Text)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    resource: Mapped[ProjectResource] = relationship(viewonly=True, lazy="raise")


class ProjectImpact(RecordMixin, Base):
    __tablename__ = "project_impacts"
    __table_args__ = (
        CheckConstraint("category IN ('educational', 'social')", name="valid_category"),
        CheckConstraint("length(trim(title)) > 0", name="title_not_blank"),
        CheckConstraint(
            "(metric_name IS NULL AND metric_value IS NULL AND metric_unit IS NULL "
            "AND metric_scope IS NULL) OR (metric_name IS NOT NULL AND metric_value IS NOT NULL "
            "AND metric_unit IS NOT NULL AND metric_scope IS NOT NULL "
            "AND length(trim(metric_name)) > 0 AND length(trim(metric_unit)) > 0 "
            "AND length(trim(metric_scope)) > 0)",
            name="complete_metric",
        ),
        Index("ix_project_impacts_project_id", "project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    evidence_reference: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(Text)
    metric_name: Mapped[str | None] = mapped_column(Text)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric)
    metric_unit: Mapped[str | None] = mapped_column(Text)
    metric_scope: Mapped[str | None] = mapped_column(Text)


# Matching partial indexes are installed on PostgreSQL and SQLite.
for name, columns, condition in [
    (
        "ix_projects_public_published",
        [Project.published_at.desc(), Project.id.desc()],
        "status = 'published'",
    ),
    (
        "ix_projects_public_cohort",
        [Project.cohort_id, Project.published_at.desc(), Project.id.desc()],
        "status = 'published'",
    ),
    (
        "ix_projects_featured",
        [Project.featured_rank.desc(), Project.published_at.desc(), Project.id.desc()],
        "status = 'published' AND is_featured = true",
    ),
]:
    Index(name, *columns, postgresql_where=text(condition), sqlite_where=text(condition))
