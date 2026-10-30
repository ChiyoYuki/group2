"""Content writes and publication rules. Methods flush but never commit."""

import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from dream_journey.models import (
    JourneyEntry,
    Project,
    ProjectImpact,
    ProjectMember,
    ProjectQuestion,
    ProjectResource,
    ProjectSection,
    ProjectTheme,
    SectionResource,
    Theme,
    utc_now,
)


class ProjectNotFound(LookupError):
    pass


class PublishValidationError(ValueError):
    def __init__(self, issues: list[str]):
        self.issues = tuple(issues)
        super().__init__("Cannot publish project: " + "; ".join(issues))


EDITABLE_FIELDS = frozenset(
    {
        "cohort_id",
        "title",
        "short_title",
        "slug",
        "summary",
        "background",
        "opening_question",
        "content_kind",
        "content_notice",
        "content_tags",
        "location",
        "team_name",
        "cover_url",
        "research_question",
        "research_methods",
        "learning_outcomes",
        "practical_tips",
        "is_demo",
        "is_featured",
        "featured_reason",
        "featured_rank",
    }
)

RESOURCE_METADATA_FIELDS = frozenset(
    {
        "usage_role",
        "caption",
        "alt_text",
        "source_name",
        "source_url",
        "original_url",
        "creator_credit",
        "original_activity",
        "provenance_note",
        "rights_status",
        "rights_note",
        "file_size_bytes",
        "width",
        "height",
        "duration_seconds",
        "transcript",
        "is_ai_generated",
        "generation_note",
        "sha256",
        "import_key",
        "content_text",
        "structured_data",
    }
)


def string_list(value: list[str]) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError("Tags must be a list of nonblank strings")
    return list(dict.fromkeys(item.strip() for item in value))


class ProjectService:
    def __init__(self, session: Session):
        self.session = session

    def _locked_project(self, project_id: uuid.UUID) -> Project:
        # All service writes lock the parent, serializing publication and child edits on PostgreSQL.
        project = self.session.scalar(
            select(Project)
            .where(Project.id == project_id)
            .with_for_update()
            .execution_options(populate_existing=True),
        )
        if project is None:
            raise ProjectNotFound(str(project_id))
        return project

    def _editable_project(self, project_id: uuid.UUID) -> Project:
        project = self._locked_project(project_id)
        if project.status == "published":
            raise ValueError("Archive the published project before editing, then publish it again")
        return project

    def create_draft(
        self,
        *,
        cohort_id: uuid.UUID | None = None,
        title: str,
        slug: str,
        summary: str,
        research_question: str = "",
        theme_ids: Iterable[uuid.UUID] = (),
        **content,
    ) -> Project:
        unknown = content.keys() - EDITABLE_FIELDS
        if unknown:
            raise ValueError(f"Unsupported project fields: {sorted(unknown)}")
        if "content_tags" in content:
            content["content_tags"] = string_list(content["content_tags"])
        project = Project(
            cohort_id=cohort_id,
            title=title,
            slug=slug,
            summary=summary,
            research_question=research_question,
            status="draft",
            **content,
        )
        self.session.add(project)
        self.session.flush()
        self.replace_themes(project.id, theme_ids)
        return project

    def update_content(self, project_id: uuid.UUID, **changes) -> Project:
        unknown = changes.keys() - EDITABLE_FIELDS
        if unknown:
            raise ValueError(f"Unsupported project fields: {sorted(unknown)}")
        if "content_tags" in changes:
            changes["content_tags"] = string_list(changes["content_tags"])
        project = self._editable_project(project_id)
        for field, value in changes.items():
            setattr(project, field, value)
        self.session.flush()
        return project

    def replace_themes(self, project_id: uuid.UUID, theme_ids: Iterable[uuid.UUID]) -> None:
        project = self._editable_project(project_id)
        ids = set(theme_ids)
        existing = set(self.session.scalars(select(Theme.id).where(Theme.id.in_(ids))))
        if ids != existing:
            raise ValueError("One or more themes do not exist")
        self.session.execute(delete(ProjectTheme).where(ProjectTheme.project_id == project_id))
        self.session.add_all(
            ProjectTheme(project_id=project_id, theme_id=theme_id) for theme_id in ids
        )
        project.updated_at = utc_now()
        self.session.flush()
        self.session.expire(project, ["themes"])

    def _add_child(self, project_id: uuid.UUID, child):
        project = self._editable_project(project_id)
        child.project_id = project_id
        self.session.add(child)
        project.updated_at = utc_now()
        self.session.flush()
        self.session.expire(
            project, ["questions", "sections", "members", "journey_entries", "resources", "impacts"]
        )
        return child

    def add_member(
        self,
        project_id: uuid.UUID,
        *,
        display_name: str,
        role: str,
        school_name: str | None = None,
        sort_order: int = 0,
    ) -> ProjectMember:
        return self._add_child(
            project_id,
            ProjectMember(
                display_name=display_name,
                role=role,
                school_name=school_name,
                sort_order=sort_order,
            ),
        )

    def add_question(
        self,
        project_id: uuid.UUID,
        *,
        question: str,
        topic: str | None = None,
        sort_order: int = 0,
    ) -> ProjectQuestion:
        return self._add_child(
            project_id,
            ProjectQuestion(
                question=question,
                topic=topic,
                sort_order=sort_order,
            ),
        )

    def add_journey_entry(
        self,
        project_id: uuid.UUID,
        *,
        title: str,
        description: str,
        challenges: str | None = None,
        responses: str | None = None,
        reflection: str | None = None,
        occurred_on: date | None = None,
        sort_order: int = 0,
        method_tags: list[str] | None = None,
    ) -> JourneyEntry:
        return self._add_child(
            project_id,
            JourneyEntry(
                title=title,
                description=description,
                challenges=challenges,
                responses=responses,
                reflection=reflection,
                occurred_on=occurred_on,
                sort_order=sort_order,
                method_tags=string_list(method_tags or []),
            ),
        )

    def add_resource(
        self,
        project_id: uuid.UUID,
        *,
        resource_type_id: uuid.UUID,
        title: str,
        resource_url: str,
        journey_entry_id: uuid.UUID | None = None,
        description: str | None = None,
        preview_url: str | None = None,
        mime_type: str | None = None,
        sort_order: int = 0,
        **metadata,
    ) -> ProjectResource:
        unknown = metadata.keys() - RESOURCE_METADATA_FIELDS
        if unknown:
            raise ValueError(f"Unsupported resource fields: {sorted(unknown)}")
        self._editable_project(project_id)
        self._check_journey(project_id, journey_entry_id)
        return self._add_child(
            project_id,
            ProjectResource(
                resource_type_id=resource_type_id,
                title=title,
                resource_url=resource_url,
                journey_entry_id=journey_entry_id,
                description=description,
                preview_url=preview_url,
                mime_type=mime_type,
                sort_order=sort_order,
                **metadata,
            ),
        )

    def add_section(
        self,
        project_id: uuid.UUID,
        *,
        key: str,
        kind: str,
        title: str,
        body: str,
        journey_entry_id: uuid.UUID | None = None,
        sort_order: int = 0,
    ) -> ProjectSection:
        self._editable_project(project_id)
        self._check_journey(project_id, journey_entry_id)
        return self._add_child(
            project_id,
            ProjectSection(
                key=key,
                kind=kind,
                title=title,
                body=body,
                journey_entry_id=journey_entry_id,
                sort_order=sort_order,
            ),
        )

    def link_section_resource(
        self,
        project_id: uuid.UUID,
        section_id: uuid.UUID,
        resource_id: uuid.UUID,
        *,
        role: str,
        is_optional: bool = False,
        sort_order: int = 0,
    ) -> SectionResource:
        self._editable_project(project_id)
        section = self.session.get(ProjectSection, section_id)
        resource = self.session.get(ProjectResource, resource_id)
        if (
            section is None
            or resource is None
            or section.project_id != project_id
            or resource.project_id != project_id
        ):
            raise ValueError("Section and resource must belong to the same project")
        if role == "narration" and not (resource.mime_type or "").startswith(("audio/", "video/")):
            raise ValueError("Narration requires audio or video media")
        link = SectionResource(
            project_id=project_id,
            section_id=section_id,
            resource_id=resource_id,
            role=role,
            is_optional=is_optional,
            sort_order=sort_order,
        )
        self.session.add(link)
        self.session.flush()
        self.session.expire(section, ["media"])
        return link

    def add_impact(
        self,
        project_id: uuid.UUID,
        *,
        category: str,
        title: str,
        description: str,
        evidence_reference: str | None = None,
        evidence_url: str | None = None,
        metric_name: str | None = None,
        metric_value: Decimal | None = None,
        metric_unit: str | None = None,
        metric_scope: str | None = None,
    ) -> ProjectImpact:
        return self._add_child(
            project_id,
            ProjectImpact(
                category=category,
                title=title,
                description=description,
                evidence_reference=evidence_reference,
                evidence_url=evidence_url,
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
                metric_scope=metric_scope,
            ),
        )

    def _check_journey(self, project_id: uuid.UUID, journey_entry_id: uuid.UUID | None) -> None:
        if (
            journey_entry_id is not None
            and self.session.scalar(
                select(JourneyEntry.id).where(
                    JourneyEntry.id == journey_entry_id,
                    JourneyEntry.project_id == project_id,
                )
            )
            is None
        ):
            raise ValueError("The research stage must belong to the same project")

    def set_resource_journey(
        self,
        project_id: uuid.UUID,
        resource_id: uuid.UUID,
        journey_entry_id: uuid.UUID | None,
    ) -> None:
        project = self._editable_project(project_id)
        self._check_journey(project_id, journey_entry_id)
        resource = self.session.scalar(
            select(ProjectResource).where(
                ProjectResource.id == resource_id,
                ProjectResource.project_id == project_id,
            )
        )
        if resource is None:
            raise ValueError("Resource does not belong to this project")
        resource.journey_entry_id = journey_entry_id
        project.updated_at = utc_now()
        self.session.flush()

    def remove_journey_entry(self, project_id: uuid.UUID, journey_entry_id: uuid.UUID) -> None:
        project = self._editable_project(project_id)
        self._check_journey(project_id, journey_entry_id)
        if (
            self.session.scalar(
                select(ProjectResource.id)
                .where(
                    ProjectResource.project_id == project_id,
                    ProjectResource.journey_entry_id == journey_entry_id,
                )
                .limit(1)
            )
            is not None
        ):
            raise ValueError("Unlink or reassign the stage's resources before deleting it")
        self.session.execute(delete(JourneyEntry).where(JourneyEntry.id == journey_entry_id))
        project.updated_at = utc_now()
        self.session.flush()
        self.session.expire(project, ["journey_entries"])

    def publish(self, project_id: uuid.UUID, *, published_at: datetime | None = None) -> Project:
        project = self._locked_project(project_id)
        self.session.flush()
        issues = []
        for field in (
            "title",
            "summary",
            "research_question",
            "research_methods",
            "learning_outcomes",
            "practical_tips",
        ):
            if not getattr(project, field, "").strip():
                issues.append(f"{field} must not be blank")
        for model, label in (
            (ProjectTheme, "theme"),
            (JourneyEntry, "journey entry"),
            (ProjectResource, "resource"),
        ):
            condition = [model.project_id == project_id]
            if model is ProjectResource:
                condition.append(ProjectResource.usage_role == "output")
            count = self.session.scalar(select(func.count()).select_from(model).where(*condition))
            if not count:
                issues.append(f"at least one {label} is required")
        if project.is_featured and not (project.featured_reason or "").strip():
            issues.append("featured_reason is required for featured projects")
        if not project.is_demo:
            impacts = self.session.scalars(
                select(ProjectImpact).where(
                    ProjectImpact.project_id == project_id,
                )
            )
            if any(not (impact.evidence_reference or "").strip() for impact in impacts):
                issues.append("every real impact requires an evidence_reference")
        if published_at is not None and published_at.utcoffset() is None:
            issues.append("published_at must include a timezone")
        if issues:
            raise PublishValidationError(issues)
        project.published_at = (
            published_at.astimezone(UTC)
            if published_at is not None
            else project.published_at or utc_now()
        )
        project.status = "published"
        project.updated_at = utc_now()
        self.session.flush()
        return project

    def archive(self, project_id: uuid.UUID) -> Project:
        project = self._locked_project(project_id)
        project.status = "archived"
        project.updated_at = utc_now()
        self.session.flush()
        return project

    def delete_project(self, project_id: uuid.UUID) -> None:
        """Delete metadata; object storage files must be handled by the hosting application."""
        self._locked_project(project_id)
        self.session.execute(delete(Project).where(Project.id == project_id))
        self.session.flush()
