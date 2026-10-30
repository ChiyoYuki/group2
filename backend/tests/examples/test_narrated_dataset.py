import json
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from dream_journey.database import transaction
from dream_journey.models import (
    JourneyEntry,
    Project,
    ProjectResource,
    ProjectSection,
    SectionResource,
)
from dream_journey.repositories import ProjectRepository
from dream_journey.serializers import project_detail
from dream_journey.services import ProjectService
from examples.import_miao import MANIFEST, import_project


def test_audio_segments_follow_csv_order_and_share_images(factory):
    with transaction(factory) as session:
        result = import_project(session)
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        assert project.dataset_version == 2
        assert project.cover_url.endswith("opening-question.png")
        assert [s.key for s in project.sections] == [
            "opening",
            *[f"step-{i}" for i in range(1, 8)],
            "output",
            "learning",
        ]
        narration = []
        for index, section in enumerate(project.sections, 1):
            links = [link for link in section.media if link.role == "narration"]
            assert len(links) == 1
            audio = links[0].resource
            assert audio.resource_url.endswith(f"narration-{index:02d}.mp3")
            assert audio.transcript == section.body
            assert audio.is_ai_generated
            assert audio.mime_type == "audio/mpeg"
            assert audio.sha256 and len(audio.sha256) == 64
            narration.append(audio)
        assert sum(audio.duration_seconds for audio in narration) == Decimal("177.840")
        assert project.sections[1].journey_entry_id == project.journey_entries[0].id
        assert project.sections[7].journey_entry_id == project.journey_entries[6].id
        assert project.sections[0].journey_entry_id is None
        assert project.sections[8].journey_entry_id is None
        optional = [link for link in project.sections[6].media if link.is_optional]
        assert len(optional) == 1 and optional[0].resource.resource_url.endswith(
            "other-theme-reference.jpg"
        )
        step7_image = next(
            link.resource_id for link in project.sections[7].media if link.role == "illustration"
        )
        output_image = next(
            link.resource_id for link in project.sections[8].media if link.role == "illustration"
        )
        assert step7_image == output_image


def test_legacy_package_is_upgraded_in_place(factory):
    with transaction(factory) as session:
        result = import_project(session, manifest_path=MANIFEST.parent / "history/v1.json")
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        project_id = project.id
        original_stages = [stage.id for stage in project.journey_entries]
        original_media = {resource.resource_url: resource.id for resource in project.resources}
        service = ProjectService(session)
        service.archive(project_id)
        service.update_content(project_id, location="后来核实的地点")
        service.add_member(project_id, display_name="后来补充的成员", role="学生")
        service.publish(project_id)
        project.dataset_key = project.dataset_digest = (
            None  # Database imported before revision tracking.
        )
        project.dataset_version = None
    with transaction(factory) as session:
        result = import_project(session)
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        assert result["updated"] and not result["inserted"]
        assert project.id == project_id
        assert [stage.id for stage in project.journey_entries] == original_stages
        assert all(
            resource.id == original_media[resource.resource_url]
            for resource in project.resources
            if resource.resource_url in original_media
        )
        assert project.location == "后来核实的地点"
        assert project.members[0].display_name == "后来补充的成员"
        assert len(project.resources) == 16 and len(project.sections) == 10


def test_changed_revision_updates_content_without_id_churn(factory, tmp_path):
    with transaction(factory) as session:
        first = import_project(session)
        original = ProjectRepository(session).get_public_by_slug(first["slug"])
        section_ids = [section.id for section in original.sections]
        audio_ids = [r.id for r in original.resources if r.mime_type == "audio/mpeg"]
    data = json.loads(MANIFEST.read_text())
    data["summary"] = "修订后的一句话简介"
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(data, ensure_ascii=False))
    with transaction(factory) as session:
        assert import_project(session, manifest_path=changed)["updated"]
        project = ProjectRepository(session).get_public_by_slug(first["slug"])
        assert project.summary == "修订后的一句话简介"
        assert [s.id for s in project.sections] == section_ids
        assert [r.id for r in project.resources if r.mime_type == "audio/mpeg"] == audio_ids
        assert import_project(session, manifest_path=changed)["updated"] is False


def test_failed_update_rolls_back_the_whole_graph(factory, tmp_path):
    with transaction(factory) as session:
        result = import_project(session)
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        previous_digest = project.dataset_digest
        previous_summary = project.summary
    data = json.loads(MANIFEST.read_text())
    data["summary"] = "不能部分保存"
    data["sections"][-1]["sort_order"] = -1
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(IntegrityError), transaction(factory) as session:
        import_project(session, manifest_path=broken)
    with transaction(factory) as session:
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        assert project.summary == previous_summary
        assert project.dataset_digest == previous_digest
        assert len(project.sections) == 10
        assert session.scalar(select(func.count()).select_from(SectionResource)) == 17


def test_payload_can_be_serialized_after_session_closes(factory):
    with transaction(factory) as session:
        result = import_project(session)
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        session.expunge_all()
    payload = project_detail(project)
    assert len(payload["sections"]) == 10
    assert payload["sections"][0]["media"][-1]["resource"]["duration_seconds"] == 20.016
    assert payload["dataset"]["version"] == 2
    json.dumps(payload)


def test_cross_project_media_link_is_rejected_by_service_and_database(factory, complete_project):
    with transaction(factory) as session:
        first, second = complete_project(session), complete_project(session)
        service = ProjectService(session)
        section = service.add_section(
            first.id, key="other", kind="other", title="内容", body="正文"
        )
        other_resource = session.scalar(
            select(ProjectResource).where(ProjectResource.project_id == second.id)
        )
        with pytest.raises(ValueError, match="same project"):
            service.link_section_resource(
                first.id, section.id, other_resource.id, role="attachment"
            )
        first_id, section_id, other_id = first.id, section.id, other_resource.id
    with pytest.raises(IntegrityError), transaction(factory) as session:
        session.add(
            SectionResource(
                project_id=first_id, section_id=section_id, resource_id=other_id, role="attachment"
            )
        )


def test_cross_project_stage_in_section_fails_at_commit(factory, complete_project):
    with transaction(factory) as session:
        first, second = complete_project(session), complete_project(session)
        first_id = first.id
        second_stage = session.scalar(
            select(JourneyEntry.id).where(JourneyEntry.project_id == second.id)
        )
    with pytest.raises(IntegrityError), transaction(factory) as session:
        session.add(
            ProjectSection(
                project_id=first_id,
                key="bad",
                kind="journey",
                title="错误阶段",
                body="正文",
                journey_entry_id=second_stage,
            )
        )
        session.flush()


def test_project_delete_cascades_sections_and_media_links(factory):
    with transaction(factory) as session:
        project_id = uuid.UUID(import_project(session)["project_id"])
    with transaction(factory) as session:
        ProjectService(session).delete_project(project_id)
    with transaction(factory) as session:
        for model in (Project, ProjectSection, SectionResource, ProjectResource):
            assert session.scalar(select(func.count()).select_from(model)) == 0
