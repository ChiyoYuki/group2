import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.exc import IntegrityError

from dream_journey.database import make_engine, make_session_factory, transaction
from dream_journey.models import JourneyEntry, Project, ProjectQuestion, ProjectResource
from dream_journey.repositories import ProjectRepository
from dream_journey.services import ProjectService, PublishValidationError
from dream_journey.web import project_detail
from examples.import_miao import import_project, load_manifest
from tests.conftest import migration_config


def test_package_import_preserves_missing_facts_and_provenance(factory):
    with transaction(factory) as session:
        result = import_project(session)
        assert result["inserted"]
    with transaction(factory) as session:
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        assert project.content_kind == "reconstructed"
        assert project.is_demo
        assert project.cohort is None
        assert project.location is None and project.team_name is None
        assert project.members == []
        assert project.impacts == []
        assert len(project.questions) == 3
        assert len(project.journey_entries) == 7
        assert all(entry.occurred_on is None for entry in project.journey_entries)
        assert len(project.resources) == 16
        assert len(project.sections) == 10
        outputs = [r for r in project.resources if r.usage_role == "output"]
        references = [r for r in project.resources if r.usage_role == "reference"]
        assert len(outputs) == 1 and len(references) == 4
        assert outputs[0].width == 1280 and outputs[0].height == 886
        assert references[0].creator_credit == "磨桂宾"
        assert references[0].source_name == "金台资讯／新浪网"
        assert (
            references[-1].journey_entry_id is None
        )  # Different subject, excluded from the story.
        assert all(r.rights_status == "unconfirmed" for r in project.resources)
        assert ProjectRepository(session).real_impact_overview().project_count == 0


def test_import_is_idempotent_and_leaves_existing_edits_intact(factory):
    with transaction(factory) as session:
        result = import_project(session)
        project_id = uuid.UUID(result["project_id"])
        service = ProjectService(session)
        service.archive(project_id)
        service.update_content(project_id, title="编辑维护后的项目标题")
        service.publish(project_id)
    with transaction(factory) as session:
        assert import_project(session)["inserted"] is False
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        assert project.title == "编辑维护后的项目标题"
        assert len(project.questions) == 3
        assert len(project.resources) == 16


def test_browser_payload_contains_structured_content_and_usable_media_metadata(factory):
    with transaction(factory) as session:
        result = import_project(session)
        project = ProjectRepository(session).get_public_by_slug(result["slug"])
        payload = project_detail(project)
        assert payload["cohort"] is None
        assert len(payload["questions"]) == 3
        assert payload["questions"][2]["topic"] == "蜡染"
        assert "重构" in payload["content_notice"]
        assert payload["journey_entries"][3]["challenges"]
        assert payload["journey_entries"][3]["responses"]
        assert payload["journey_entries"][1]["method_tags"] == ["观察制作"]
        assert payload["resources"][0]["resource_url"].startswith("/media/miao-culture/")
        assert payload["resources"][1]["source_url"].startswith("https://")
        assert payload["resources"][1]["mime_type"] == "image/jpeg"


def test_research_questions_can_be_searched_and_media_match_manifest(factory):
    assert len(load_manifest()["assets"]) == 16  # Verifies images and narration size/SHA-256.
    with transaction(factory) as session:
        import_project(session)
        page = ProjectRepository(session).list_public(keyword="蜡染")
        assert page.total == 1
        assert page.items[0].slug == "miao-culture-needlework"


def test_external_references_alone_do_not_satisfy_publication(factory, complete_project):
    with transaction(factory) as session:
        project = complete_project(session)
        resource = session.scalar(
            sa.select(ProjectResource).where(ProjectResource.project_id == project.id)
        )
        resource.usage_role = "reference"
        with pytest.raises(PublishValidationError, match="resource"):
            ProjectService(session).publish(project.id)
        assert project.status == "draft"


@pytest.mark.parametrize(
    "metadata",
    [{"file_size_bytes": -1}, {"width": 0}, {"duration_seconds": -1}, {"usage_role": "invalid"}],
)
def test_invalid_media_metadata_is_rejected(factory, complete_project, metadata):
    with transaction(factory) as session:
        project_id = complete_project(session).id
    with pytest.raises(IntegrityError), transaction(factory) as session:
        resource = session.scalar(
            sa.select(ProjectResource).where(ProjectResource.project_id == project_id)
        )
        for key, value in metadata.items():
            setattr(resource, key, value)


def test_questions_are_deleted_with_project(factory):
    with transaction(factory) as session:
        project_id = uuid.UUID(import_project(session)["project_id"])
    with transaction(factory) as session:
        ProjectService(session).delete_project(project_id)
    with transaction(factory) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(ProjectQuestion)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(ProjectResource)) == 0


def test_populated_v1_database_survives_sqlite_table_rebuild(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'old-database.db'}")
    identifiers = {
        name: uuid.uuid4().hex
        for name in ["cohort", "theme", "type", "project", "stage", "resource"]
    }
    try:
        with engine.connect() as connection:
            command.upgrade(migration_config(connection), "0001")
        old = sa.MetaData()
        old.reflect(engine)
        with engine.begin() as connection:
            connection.execute(
                old.tables["cohorts"]
                .insert()
                .values(id=identifiers["cohort"], name="既有届次", year=2025)
            )
            connection.execute(
                old.tables["themes"]
                .insert()
                .values(id=identifiers["theme"], name="旧主题", slug="old")
            )
            connection.execute(
                old.tables["resource_types"]
                .insert()
                .values(id=identifiers["type"], name="图片", code="image")
            )
            connection.execute(
                old.tables["projects"]
                .insert()
                .values(
                    id=identifiers["project"],
                    cohort_id=identifiers["cohort"],
                    title="既有项目",
                    slug="old-project",
                    summary="保留原数据",
                    research_question="原问题",
                )
            )
            connection.execute(
                old.tables["project_themes"]
                .insert()
                .values(project_id=identifiers["project"], theme_id=identifiers["theme"])
            )
            connection.execute(
                old.tables["journey_entries"]
                .insert()
                .values(
                    id=identifiers["stage"],
                    project_id=identifiers["project"],
                    title="既有阶段",
                    description="原过程",
                )
            )
            connection.execute(
                old.tables["project_resources"]
                .insert()
                .values(
                    id=identifiers["resource"],
                    project_id=identifiers["project"],
                    journey_entry_id=identifiers["stage"],
                    resource_type_id=identifiers["type"],
                    title="旧图",
                    resource_url="old.jpg",
                )
            )
        with engine.connect() as connection:
            command.upgrade(migration_config(connection), "head")
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        with transaction(make_session_factory(engine)) as session:
            assert session.get(Project, uuid.UUID(identifiers["project"])).title == "既有项目"
            assert (
                session.get(JourneyEntry, uuid.UUID(identifiers["stage"])).description == "原过程"
            )
            resource = session.get(ProjectResource, uuid.UUID(identifiers["resource"]))
            assert resource.journey_entry_id == uuid.UUID(identifiers["stage"])
            assert resource.usage_role == "output"
    finally:
        engine.dispose()


def test_downgrade_requires_assigning_unknown_cohorts(engine, factory):
    with transaction(factory) as session:
        import_project(session)
    with engine.connect() as connection, pytest.raises(RuntimeError, match="Assign cohorts"):
        command.downgrade(migration_config(connection), "0001")
    with transaction(factory) as session:
        assert ProjectRepository(session).list_public().total == 1
