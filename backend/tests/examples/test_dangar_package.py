import json
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from dream_journey.database import transaction
from dream_journey.models import Project, ProjectResource, SectionResource
from dream_journey.repositories import ProjectRepository
from dream_journey.serializers import project_detail
from examples.dataset_import import import_dataset, load_manifest
from examples.import_miao import import_project as import_miao
from examples.registry import get_dataset

DANGAR = get_dataset("dangar-old-town")
MIAO = get_dataset("miao-culture")


def test_two_datasets_are_independent_and_repeat_import_does_not_change_miao(factory):
    with transaction(factory) as session:
        first = import_miao(session)
        miao_before = project_detail(ProjectRepository(session).get_public_by_slug(first["slug"]))
        second = import_dataset(session, DANGAR)
        assert second["inserted"] and second["dataset_version"] == 1
    with transaction(factory) as session:
        assert import_dataset(session, DANGAR)["updated"] is False
        assert import_miao(session)["updated"] is False
        repository = ProjectRepository(session)
        assert repository.list_public().total == 2
        assert repository.list_public(dataset_key=DANGAR.key).total == 1
        assert repository.list_public(dataset_key=MIAO.key).total == 1
        assert repository.list_public(dataset_key="missing").total == 0
        assert repository.real_impact_overview().project_count == 0
        miao_after = project_detail(repository.get_public_by_slug(first["slug"]))
        assert miao_after == miao_before
        dangar = repository.get_public_by_slug(second["slug"])
        assert {r["id"] for r in miao_after["resources"]}.isdisjoint(
            {str(r.id) for r in dangar.resources}
        )
        assert all(r.resource_url.startswith("/media/dangar-old-town/") for r in dangar.resources)


def test_second_package_preserves_uncertainty_and_source_documents(factory):
    with transaction(factory) as session:
        result = import_dataset(session, DANGAR)
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        assert project.short_title == "古城里的马，也要“吃饭”吗？"
        assert project.content_kind == "reconstructed" and project.is_demo
        assert project.cohort is None and project.location is None
        assert project.members == [] and project.impacts == []
        assert len(project.resources) == 18 and len(project.sections) == 11
        assert len(project.questions) == 3 and len(project.journey_entries) == 7
        assert all(stage.occurred_on is None for stage in project.journey_entries)
        assert "具体地点和安排未确认" in project.content_notice
        resources = {r.import_key.split(":", 1)[1]: r for r in project.resources}
        knowledge = resources["knowledge-status.csv"].structured_data
        assert len(knowledge["rows"]) == 5
        assert {row[1] for row in knowledge["rows"]} == {
            "资料支持",
            "一般常识",
            "未确认",
            "现代类比",
        }
        assert "不能当作马店" in knowledge["rows"][3][2]
        assert len(resources["comparison.csv"].structured_data["rows"]) == 4
        assert len(resources["text-sources.csv"].structured_data["rows"]) == 3
        discovery = resources["discovery-card.md"]
        assert discovery.usage_role == "output" and discovery.resource_type.code == "report"
        assert "不代表收到了一张已有的学生成果照片" in discovery.content_text
        assert resources["comparison.csv"].resource_type.code == "data_table"
        assert resources["opening-question.png"].is_ai_generated
        assert "不是马店或客栈" in resources["gate-reference.jpg"].provenance_note


def test_second_package_media_and_attachments_follow_the_mapping_csv(factory):
    with transaction(factory) as session:
        result = import_dataset(session, DANGAR)
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        narrated = [section for section in project.sections if section.kind != "other"]
        assert len(narrated) == 10
        duration = Decimal("0")
        for index, section in enumerate(narrated, 1):
            audio = next(link.resource for link in section.media if link.role == "narration")
            assert audio.resource_url.endswith(f"narration-{index:02d}.mp3")
            assert audio.transcript == section.body and audio.is_ai_generated
            duration += audio.duration_seconds
        assert duration == Decimal("183.552")
        opening_id = next(
            link.resource_id for link in narrated[0].media if link.role == "illustration"
        )
        last_step_id = next(
            link.resource_id for link in narrated[7].media if link.role == "illustration"
        )
        assert opening_id == last_step_id
        comparison = [link.resource for link in narrated[6].media if link.role == "attachment"]
        assert len(comparison) == 1 and comparison[0].resource_url.endswith("comparison.csv")
        known = [link.resource for link in narrated[5].media if link.role == "attachment"]
        assert known[0].resource_url.endswith("knowledge-status.csv")
        sources = project.sections[-1]
        assert sources.key == "sources" and sources.kind == "other"
        assert all(link.role != "narration" for link in sources.media)
        assert sources.media[0].resource.resource_url.endswith("text-sources.csv")


def test_resource_basenames_can_repeat_across_datasets(factory):
    with transaction(factory) as session:
        import_miao(session)
        import_dataset(session, DANGAR)
        resources = list(
            session.scalars(
                select(ProjectResource).where(
                    ProjectResource.resource_url.endswith("narration-01.mp3")
                )
            )
        )
        assert len(resources) == 2
        assert resources[0].project_id != resources[1].project_id
        assert resources[0].sha256 != resources[1].sha256
        assert resources[0].resource_url != resources[1].resource_url


def test_wrong_dataset_manifest_is_rejected_before_import(factory):
    with transaction(factory) as session:
        import_miao(session)
        with pytest.raises(ValueError, match="another dataset"):
            import_dataset(session, MIAO, manifest_path=DANGAR.manifest)
        assert session.scalar(select(func.count()).select_from(Project)) == 1


def test_claim_table_cannot_silently_disagree_with_the_original_csv(tmp_path):
    manifest = json.loads(DANGAR.manifest.read_text())
    table = next(
        asset for asset in manifest["assets"] if asset["filename"] == "knowledge-status.csv"
    )
    table["structured_data"]["rows"][3][1] = "已确认"
    modified = tmp_path / "misleading.json"
    modified.write_text(json.dumps(manifest, ensure_ascii=False))
    with pytest.raises(ValueError, match="original CSV"):
        load_manifest(DANGAR, modified)


def test_table_shape_is_checked_before_writing(tmp_path):
    manifest = json.loads(DANGAR.manifest.read_text())
    table = next(asset for asset in manifest["assets"] if asset["filename"] == "comparison.csv")
    table["structured_data"]["rows"][0].pop()
    modified = tmp_path / "bad-shape.json"
    modified.write_text(json.dumps(manifest, ensure_ascii=False))
    with pytest.raises(ValueError, match="column headers"):
        load_manifest(DANGAR, modified)


def test_project_slug_collision_does_not_overwrite_the_other_dataset(factory, tmp_path):
    with transaction(factory) as session:
        original = import_miao(session)
        original_id = original["project_id"]
    manifest = json.loads(DANGAR.manifest.read_text())
    manifest["slug"] = original["slug"]
    collision = tmp_path / "collision.json"
    collision.write_text(json.dumps(manifest, ensure_ascii=False))
    with pytest.raises(ValueError, match="another dataset"), transaction(factory) as session:
        import_dataset(session, DANGAR, manifest_path=collision)
    with transaction(factory) as session:
        project = ProjectRepository(session).get_public_by_slug(original["slug"])
        assert str(project.id) == original_id and project.dataset_key == MIAO.key
        assert session.scalar(select(func.count()).select_from(SectionResource)) == 17
