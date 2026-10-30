"""Upsert a validated project manifest without any built-in content or layout."""

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dream_journey.datasets import DatasetSpec
from dream_journey.manifests import load_manifest, validate_manifest
from dream_journey.models import (
    JourneyEntry,
    Project,
    ProjectQuestion,
    ProjectResource,
    ProjectSection,
    ProjectTheme,
    ResourceType,
    SectionResource,
    Theme,
    utc_now,
)
from dream_journey.services import RESOURCE_METADATA_FIELDS, ProjectService


def _one(candidates, label):
    values = list(candidates)
    if len(values) > 1:
        raise ValueError(f"Ambiguous legacy {label}; resolve duplicates before importing")
    return values[0] if values else None


def import_dataset(
    session: Session,
    spec: DatasetSpec,
    *,
    manifest_path: Path | None = None,
    manifest: dict | None = None,
    default_status: str = "draft",
) -> dict:
    """The caller owns the transaction; omitted records and unchanged revisions are retained."""
    if manifest_path is not None and manifest is not None:
        raise ValueError("Supply a manifest object or a file, not both")
    if default_status not in {"draft", "published", "archived"}:
        raise ValueError("Invalid default status")
    data = (
        validate_manifest(manifest, spec)
        if manifest is not None
        else load_manifest(spec, manifest_path)
    )
    digest = hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    incoming = dict(data["project"])
    project = session.scalar(
        select(Project).where(Project.slug == incoming["slug"]).with_for_update()
    )
    inserted = project is None
    if project is not None:
        if project.dataset_key not in {None, spec.key}:
            raise ValueError("Project slug belongs to another dataset")
        if (project.dataset_version or 0) > data["dataset"]["version"]:
            raise ValueError("Importing an older dataset version is not supported")
        if project.dataset_digest == digest:
            return {
                "slug": project.slug,
                "inserted": False,
                "updated": False,
                "project_id": str(project.id),
                "dataset_version": project.dataset_version,
            }
    desired_status = incoming.pop("status", project.status if project else default_status)
    published_at = incoming.pop("published_at", None)
    if published_at is not None:
        published_at = datetime.fromisoformat(published_at)
        if published_at.utcoffset() is None:
            raise ValueError("published_at must include a timezone")
        published_at = published_at.astimezone(UTC)
    if incoming.get("cohort_id") is not None:
        incoming["cohort_id"] = uuid.UUID(incoming["cohort_id"])
    cover_key = incoming.pop("cover_resource_key", None)
    if cover_key is not None:
        incoming["cover_url"] = next(
            item["url"] for item in data["resources"] if item["key"] == cover_key
        )
    if "research_question" not in incoming and data["questions"]:
        incoming["research_question"] = "\n".join(item["question"] for item in data["questions"])
    service = ProjectService(session)
    if project is not None and project.status == "published":
        service.archive(project.id)
    theme_ids = set()
    for item in data["themes"]:
        theme = session.scalar(select(Theme).where(Theme.slug == item["slug"]))
        if theme is None:
            theme = Theme(**item)
            session.add(theme)
            session.flush()
        theme_ids.add(theme.id)
    if project is None:
        project = service.create_draft(theme_ids=theme_ids, **incoming)
    else:
        service.update_content(project.id, **incoming)
        theme_ids.update(
            session.scalars(
                select(ProjectTheme.theme_id).where(ProjectTheme.project_id == project.id)
            )
        )
        service.replace_themes(project.id, theme_ids)
    for item in data["questions"]:
        question = session.scalar(
            select(ProjectQuestion).where(
                ProjectQuestion.project_id == project.id, ProjectQuestion.import_key == item["key"]
            )
        )
        if question is None:
            question = _one(
                session.scalars(
                    select(ProjectQuestion).where(
                        ProjectQuestion.project_id == project.id,
                        ProjectQuestion.import_key.is_(None),
                        ProjectQuestion.topic == item.get("topic"),
                        ProjectQuestion.question == item["question"],
                        ProjectQuestion.sort_order == item["sort_order"],
                    )
                ),
                "question",
            )
        values = {
            "question": item["question"],
            "topic": item.get("topic"),
            "sort_order": item["sort_order"],
        }
        if question is None:
            question = service.add_question(project.id, **values)
        else:
            for field, value in values.items():
                setattr(question, field, value)
        question.import_key = item["key"]
    stages = {}
    for item in data["stages"]:
        stage = session.scalar(
            select(JourneyEntry).where(
                JourneyEntry.project_id == project.id, JourneyEntry.import_key == item["key"]
            )
        )
        if stage is None:
            stage = _one(
                session.scalars(
                    select(JourneyEntry).where(
                        JourneyEntry.project_id == project.id,
                        JourneyEntry.import_key.is_(None),
                        JourneyEntry.title == item["title"],
                        JourneyEntry.sort_order == item["sort_order"],
                    )
                ),
                "stage",
            )
        values = {key: value for key, value in item.items() if key != "key"}
        if values.get("occurred_on") is not None:
            values["occurred_on"] = date.fromisoformat(values["occurred_on"])
        if stage is None:
            stage = service.add_journey_entry(project.id, **values)
        else:
            for field, value in values.items():
                setattr(stage, field, value)
        stage.import_key = item["key"]
        session.flush()
        stages[item["key"]] = stage.id
    resource_ids = {}
    for item in data["resources"]:
        category = item["type"]
        resource_type = session.scalar(
            select(ResourceType).where(ResourceType.code == category["code"])
        )
        if resource_type is None:
            resource_type = ResourceType(**category)
            session.add(resource_type)
            session.flush()
        resource = session.scalar(
            select(ProjectResource).where(
                ProjectResource.project_id == project.id, ProjectResource.import_key == item["key"]
            )
        )
        if resource is None:
            resource = _one(
                session.scalars(
                    select(ProjectResource).where(
                        ProjectResource.project_id == project.id,
                        ProjectResource.import_key.is_(None),
                        ProjectResource.resource_url == item["url"],
                    )
                ),
                "resource",
            )
        values = {
            key: value
            for key, value in item.items()
            if key in RESOURCE_METADATA_FIELDS and key != "import_key"
        }
        if values.get("duration_seconds") is not None:
            values["duration_seconds"] = Decimal(str(values["duration_seconds"]))
        values.update(
            title=item["title"],
            resource_type_id=resource_type.id,
            resource_url=item["url"],
            mime_type=item.get("mime_type"),
            description=item.get("description"),
            preview_url=item.get("preview_url"),
            journey_entry_id=stages.get(item.get("stage_key")),
            sort_order=item["sort_order"],
            import_key=item["key"],
        )
        if resource is None:
            resource = service.add_resource(project.id, **values)
        else:
            for field, value in values.items():
                setattr(resource, field, value)
            session.flush()
        resource_ids[item["key"]] = resource.id
    for item in data["sections"]:
        section = session.scalar(
            select(ProjectSection).where(
                ProjectSection.project_id == project.id, ProjectSection.key == item["key"]
            )
        )
        values = dict(
            kind=item["kind"],
            title=item["title"],
            body=item["body"],
            journey_entry_id=stages.get(item.get("stage_key")),
            sort_order=item["sort_order"],
        )
        if section is None:
            section = service.add_section(project.id, key=item["key"], **values)
        else:
            for field, value in values.items():
                setattr(section, field, value)
            session.flush()
        session.execute(delete(SectionResource).where(SectionResource.section_id == section.id))
        for link in item["media"]:
            service.link_section_resource(
                project.id,
                section.id,
                resource_ids[link["resource_key"]],
                role=link["role"],
                is_optional=link["is_optional"],
                sort_order=link["sort_order"],
            )
    project.dataset_key = spec.key
    project.dataset_version = data["dataset"]["version"]
    project.dataset_digest = digest
    project.dataset_imported_at = utc_now()
    if desired_status == "published":
        service.publish(project.id, published_at=published_at)
    else:
        project.status = desired_status
        if published_at is not None:
            project.published_at = published_at
    session.flush()
    return {
        "slug": project.slug,
        "inserted": inserted,
        "updated": not inserted,
        "project_id": str(project.id),
        "dataset_version": project.dataset_version,
        "questions": len(data["questions"]),
        "stages": len(stages),
        "media": len(data["resources"]),
        "sections": len(data["sections"]),
    }
