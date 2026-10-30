"""Transport-independent JSON payloads consumed by any frontend."""

from dream_journey.models import Project, ProjectResource
from dream_journey.services import RESOURCE_METADATA_FIELDS


def resource_payload(resource: ProjectResource) -> dict:
    metadata = {key: getattr(resource, key) for key in RESOURCE_METADATA_FIELDS}
    if metadata["duration_seconds"] is not None:
        metadata["duration_seconds"] = float(metadata["duration_seconds"])
    return {
        "id": str(resource.id),
        "title": resource.title,
        "description": resource.description,
        "resource_url": resource.resource_url,
        "preview_url": resource.preview_url,
        "mime_type": resource.mime_type,
        "journey_entry_id": str(resource.journey_entry_id) if resource.journey_entry_id else None,
        "sort_order": resource.sort_order,
        "type": {"code": resource.resource_type.code, "name": resource.resource_type.name},
        **metadata,
    }


def project_card(project: Project) -> dict:
    return {
        "id": str(project.id),
        "slug": project.slug,
        "title": project.title,
        "short_title": project.short_title,
        "summary": project.summary,
        "location": project.location,
        "team_name": project.team_name,
        "cover_url": project.cover_url,
        "is_demo": project.is_demo,
        "is_featured": project.is_featured,
        "featured_reason": project.featured_reason,
        "content_kind": project.content_kind,
        "content_tags": project.content_tags,
        "published_at": project.published_at.isoformat(),
        "cohort": {
            "id": str(project.cohort.id),
            "name": project.cohort.name,
            "year": project.cohort.year,
        }
        if project.cohort
        else None,
        "themes": [
            {"id": str(item.id), "slug": item.slug, "name": item.name} for item in project.themes
        ],
        "dataset": {
            "key": project.dataset_key,
            "version": project.dataset_version,
            "digest": project.dataset_digest,
            "imported_at": project.dataset_imported_at.isoformat()
            if project.dataset_imported_at
            else None,
        }
        if project.dataset_key
        else None,
    }


def project_detail(project: Project) -> dict:
    result = project_card(project)
    result.update(
        {
            "api_version": 1,
            "background": project.background,
            "opening_question": project.opening_question,
            "content_notice": project.content_notice,
            "questions": [
                {"topic": item.topic, "question": item.question} for item in project.questions
            ],
            "research_question": project.research_question,
            "research_methods": project.research_methods,
            "learning_outcomes": project.learning_outcomes,
            "practical_tips": project.practical_tips,
            "members": [
                {
                    "display_name": item.display_name,
                    "role": item.role,
                    "school_name": item.school_name,
                }
                for item in project.members
            ],
            "journey_entries": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "description": item.description,
                    "challenges": item.challenges,
                    "responses": item.responses,
                    "reflection": item.reflection,
                    "method_tags": item.method_tags,
                    "sort_order": item.sort_order,
                    "occurred_on": item.occurred_on.isoformat() if item.occurred_on else None,
                }
                for item in project.journey_entries
            ],
            "resources": [resource_payload(item) for item in project.resources],
            "sections": [
                {
                    "id": str(section.id),
                    "key": section.key,
                    "kind": section.kind,
                    "title": section.title,
                    "body": section.body,
                    "sort_order": section.sort_order,
                    "journey_entry_id": str(section.journey_entry_id)
                    if section.journey_entry_id
                    else None,
                    "media": [
                        {
                            "role": link.role,
                            "is_optional": link.is_optional,
                            "sort_order": link.sort_order,
                            "resource": resource_payload(link.resource),
                        }
                        for link in section.media
                    ],
                }
                for section in project.sections
            ],
            "impacts": [
                {
                    "category": item.category,
                    "title": item.title,
                    "description": item.description,
                    "evidence_reference": item.evidence_reference,
                    "evidence_url": item.evidence_url,
                    "metric_name": item.metric_name,
                    "metric_value": str(item.metric_value)
                    if item.metric_value is not None
                    else None,
                    "metric_unit": item.metric_unit,
                    "metric_scope": item.metric_scope,
                }
                for item in project.impacts
            ],
        }
    )
    return result
