"""Exercise imports with unrelated, generated content and no bundled assets."""

import copy
import json
import os
import shutil
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from dream_journey.database import transaction
from dream_journey.dataset_import import import_dataset
from dream_journey.datasets import DatasetSpec
from dream_journey.manifests import validate_manifest
from dream_journey.models import Project, ProjectQuestion, ResourceType
from dream_journey.repositories import ProjectRepository
from dream_journey.serializers import project_detail
from tests.conftest import BACKEND


@pytest.fixture
def manifest_context(tmp_path):
    media = tmp_path / "assets"
    media.mkdir()
    (media / "readings.csv").write_text("time,value\n09:00,23\n", encoding="utf-8")
    return DatasetSpec("garden-observation", tmp_path / "project.json", media, "/media/garden")


def project_manifest(*, published=False):
    return {
        "schema_version": 1,
        "dataset": {"key": "garden-observation", "version": 1},
        "project": {
            "slug": "garden-temperature",
            "title": "花园温度观察",
            "summary": "比较两处测量结果",
            "research_methods": "定时测量",
            "learning_outcomes": "记录测量误差",
            "practical_tips": "统一仪器和测量时间",
            "is_demo": False,
            "is_featured": False,
            **({"status": "published"} if published else {}),
        },
        "themes": [{"slug": "field-measurement", "name": "实地测量"}],
        "questions": [
            {"key": "temperature", "question": "两处温度有何差异？"},
            {"key": "error", "question": "仪器误差如何影响结果？"},
        ],
        "stages": [
            {"key": "measure-east", "title": "东侧采样", "sort_order": 20},
            {"key": "measure-west", "title": "西侧采样", "sort_order": 10},
        ],
        "resources": [
            {
                "key": "measurements",
                "title": "原始测量表",
                "filename": "readings.csv",
                "type": {"code": "instrument-log", "name": "仪器记录"},
                "stage_key": "measure-east",
            }
        ],
        "sections": [
            {
                "key": "appendix",
                "title": "附表",
                "sort_order": 80,
                "media": [{"resource_key": "measurements"}],
            },
            {
                "key": "comparison",
                "title": "观察比较",
                "body": "测量条件需要一致。",
                "kind": "journey",
                "stage_key": "measure-west",
                "sort_order": 2,
            },
        ],
    }


def test_unrelated_project_has_arbitrary_layout_and_resource_type(factory, manifest_context):
    with transaction(factory) as session:
        result = import_dataset(
            session, manifest_context, manifest=project_manifest(published=True)
        )
        detail = ProjectRepository(session).get_public_by_slug(result["slug"])
        payload = project_detail(detail)
        assert payload["is_demo"] is False and payload["is_featured"] is False
        assert len(payload["journey_entries"]) == 2
        assert [section["key"] for section in payload["sections"]] == ["comparison", "appendix"]
        assert payload["sections"][0]["media"] == []
        resource = payload["resources"][0]
        assert resource["type"] == {"code": "instrument-log", "name": "仪器记录"}
        assert resource["structured_data"] == {
            "columns": ["time", "value"],
            "rows": [["09:00", "23"]],
        }
        assert resource["resource_url"] == "/media/garden/readings.csv"
        assert resource["sha256"] and resource["duration_seconds"] is None
        assert session.scalar(select(func.count()).select_from(ResourceType)) == 1


def test_minimal_manifest_creates_only_a_draft(factory, manifest_context):
    data = project_manifest()
    data = {key: data[key] for key in ("schema_version", "dataset", "project")}
    with transaction(factory) as session:
        result = import_dataset(session, manifest_context, manifest=data)
        project = session.get(Project, uuid.UUID(result["project_id"]))
        assert project.status == "draft" and project.published_at is None
        assert not project.is_demo and not project.is_featured and project.featured_rank == 0
        session.refresh(project, ["journey_entries", "resources", "sections"])
        assert not project.journey_entries and not project.resources and not project.sections
        assert ProjectRepository(session).list_public().total == 0


def test_narration_can_be_remote_without_duration_or_matching_body(factory, manifest_context):
    data = project_manifest(published=True)
    data["resources"].append(
        {
            "key": "interview",
            "title": "现场补充访谈",
            "url": "https://media.example.test/clip.webm",
            "mime_type": "video/webm",
            "type": {"code": "interview", "name": "访谈"},
            "transcript": "受访者的补充观点",
            "is_ai_generated": False,
        }
    )
    data["sections"][1]["media"] = [{"resource_key": "interview", "role": "narration"}]
    with transaction(factory) as session:
        result = import_dataset(session, manifest_context, manifest=data)
        section = ProjectRepository(session).get_public_by_slug(result["slug"]).sections[0]
        assert section.media[0].resource.transcript != section.body
        assert section.media[0].resource.duration_seconds is None


def test_keys_preserve_identity_after_reordering_and_changing_content(factory, manifest_context):
    data = project_manifest(published=True)
    with transaction(factory) as session:
        first = import_dataset(session, manifest_context, manifest=data)
        project = ProjectRepository(session).get_public_by_slug(first["slug"])
        ids = {item.import_key: item.id for item in project.questions}
        stage_ids = {item.import_key: item.id for item in project.journey_entries}
        resource_id = project.resources[0].id
    data["dataset"]["version"] = 2
    data["questions"][0].update(question="修订后的温度问题？", sort_order=9)
    data["questions"][1]["sort_order"] = 1
    data["stages"][0].update(title="修订后的东侧采样", sort_order=1)
    with transaction(factory) as session:
        updated = import_dataset(session, manifest_context, manifest=data)
        assert updated["updated"] and first["project_id"] == updated["project_id"]
        project = ProjectRepository(session).get_public_by_slug(first["slug"])
        assert {item.import_key: item.id for item in project.questions} == ids
        assert {item.import_key: item.id for item in project.journey_entries} == stage_ids
        assert project.resources[0].id == resource_id
        assert project.questions[-1].question == "修订后的温度问题？"
        assert import_dataset(session, manifest_context, manifest=data)["updated"] is False
        assert session.scalar(select(func.count()).select_from(ProjectQuestion)) == 2


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda data: data["dataset"].update(key="another-source"), "another dataset"),
        (lambda data: data["resources"][0].update(filename="../secret.csv"), "traversal"),
        (lambda data: data["resources"][0].update(sha256="0" * 64), "differs"),
        (lambda data: data["sections"][1].update(stage_key="absent"), "unknown stage"),
        (
            lambda data: data["sections"][0]["media"][0].update(resource_key="absent"),
            "existing resource",
        ),
    ],
)
def test_invalid_manifests_do_not_create_projects(factory, manifest_context, change, match):
    data = project_manifest()
    change(data)
    with pytest.raises(ValueError, match=match), transaction(factory) as session:
        import_dataset(session, manifest_context, manifest=data)
    with transaction(factory) as session:
        assert session.scalar(select(func.count()).select_from(Project)) == 0


def test_file_and_manifest_are_not_mutated_by_validation(manifest_context):
    data = project_manifest()
    before = copy.deepcopy(data)
    validated = validate_manifest(data, manifest_context)
    assert data == before and "sha256" in validated["resources"][0]


def test_late_failure_rolls_back_existing_project(factory, manifest_context):
    data = project_manifest(published=True)
    with transaction(factory) as session:
        import_dataset(session, manifest_context, manifest=data)
    data["project"]["summary"] = "不得部分写入"
    data["sections"][-1]["sort_order"] = -1
    with pytest.raises(IntegrityError), transaction(factory) as session:
        import_dataset(session, manifest_context, manifest=data)
    with transaction(factory) as session:
        project = ProjectRepository(session).get_public_by_slug(data["project"]["slug"])
        assert project.summary == "比较两处测量结果"


def test_core_runs_with_no_example_modules_manifests_media_or_frontend(tmp_path):
    for name in ("dream_journey", "migrations"):
        shutil.copytree(
            BACKEND / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    shutil.copyfile(BACKEND / "alembic.ini", tmp_path / "alembic.ini")
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'empty.db'}"}
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            """
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from dream_journey.database import make_engine, make_session_factory, transaction
from dream_journey.repositories import CatalogRepository, ProjectRepository
from dream_journey.web import initialize_database
from dream_journey.dataset_import import import_dataset
from dream_journey.datasets import DatasetSpec
engine = make_engine()
initialize_database(engine)
factory = make_session_factory(engine)
with transaction(factory) as session:
    assert ProjectRepository(session).list_public().total == 0
    assert CatalogRepository(session).list_themes() == []
    spec = DatasetSpec.from_manifest(Path('new.json'), 'cold-source')
    result = import_dataset(session, spec, manifest={
        'schema_version': 1, 'dataset': {'key': 'cold-source'},
        'project': {'slug': 'cold-project', 'title': 'Cold project', 'summary': 'No sample data'}
    })
    assert result['inserted']
assert not any(name == 'examples' or name.startswith('examples.') for name in sys.modules)
engine.dispose()
print(json.dumps({'isolated': True}))
""",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    assert json.loads(result.stdout) == {"isolated": True}
