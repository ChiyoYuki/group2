import uuid
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError

from dream_journey.database import transaction
from dream_journey.models import (
    Base,
    Cohort,
    JourneyEntry,
    Project,
    ProjectImpact,
    ProjectMember,
    ProjectResource,
    ProjectTheme,
    ResourceType,
    Theme,
)
from dream_journey.repositories import ProjectRepository
from dream_journey.services import ProjectNotFound, ProjectService, PublishValidationError
from tests.conftest import migration_config


def test_migrations_match_models_and_support_round_trip(engine):
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
        assert tables == set(Base.metadata.tables)
        assert len(tables) == 14
        command.check(migration_config(connection))
        command.downgrade(migration_config(connection), "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
        command.upgrade(migration_config(connection), "head")
        assert len(inspect(connection).get_table_names()) == 15


def test_public_list_and_detail_hide_drafts_and_archived(factory, complete_project):
    with transaction(factory) as session:
        draft = complete_project(session, slug="draft")
        published = complete_project(session, slug="published")
        archived = complete_project(session, slug="archived")
        service = ProjectService(session)
        service.publish(published.id)
        service.publish(archived.id)
        service.archive(archived.id)
        assert draft.status == "draft"
    with transaction(factory) as session:
        repository = ProjectRepository(session)
        assert [p.slug for p in repository.list_public().items] == ["published"]
        assert repository.get_public_by_slug("draft") is None
        assert repository.get_public_by_slug("archived") is None
        assert repository.get_public_by_slug("unknown") is None
        assert repository.get_public_by_slug("published").title == "湿地调研"


def test_filtering_pagination_and_literal_keyword(factory, catalog, complete_project):
    with transaction(factory) as session:
        service = ProjectService(session)
        for index in range(3):
            project = complete_project(session, slug=f"wetland-{index}")
            service.replace_themes(project.id, [catalog.theme_id, catalog.other_theme_id])
            service.publish(project.id)
        literal = complete_project(session, slug="literal")
        service.update_content(literal.id, title="100%_观察")
        service.publish(literal.id)
    with transaction(factory) as session:
        repository = ProjectRepository(session)
        page = repository.list_public(
            theme_slug="community",
            cohort_id=catalog.cohort_id,
            keyword="湿地",
            page_size=2,
        )
        assert page.total == 3
        next_page = repository.list_public(theme_slug="community", page=2, page_size=2)
        assert len(next_page.items) == 1
        assert not ({p.id for p in page.items} & {p.id for p in next_page.items})
        assert repository.list_public(theme_slug="missing").total == 0
        assert repository.list_public(cohort_id=uuid.uuid4()).total == 0
        assert repository.list_public(keyword="%_").total == 1
        assert repository.list_public(keyword="' OR 1=1 --").total == 0
        assert repository.list_public(page=99).items == []


@pytest.mark.parametrize("page,page_size", [(0, 10), (1, 0), (1, 101)])
def test_invalid_pagination(factory, page, page_size):
    with transaction(factory) as session, pytest.raises(ValueError):
        ProjectRepository(session).list_public(page=page, page_size=page_size)


def test_featured_order_and_stable_public_order(factory, complete_project):
    timestamp = datetime(2026, 7, 20, tzinfo=UTC)
    with transaction(factory) as session:
        service = ProjectService(session)
        for rank in (5, 20, 0):
            project = complete_project(
                session, slug=f"project-{rank}", featured=rank > 0, rank=rank
            )
            service.publish(project.id, published_at=timestamp)
    with transaction(factory) as session:
        repository = ProjectRepository(session)
        assert [p.slug for p in repository.list_public(featured_only=True).items] == [
            "project-20",
            "project-5",
        ]
        ids = [p.id for p in repository.list_public().items]
        assert ids == sorted(ids, reverse=True)


def test_detail_loads_all_relations_in_display_order(factory, complete_project):
    with transaction(factory) as session:
        project = complete_project(session, slug="detail")
        service = ProjectService(session)
        service.add_journey_entry(
            project.id, title="最后展示", description="人工编排", sort_order=99
        )
        service.add_member(project.id, display_name="老师", role="指导教师", sort_order=99)
        service.publish(project.id)
    with transaction(factory) as session:
        detail = ProjectRepository(session).get_public_by_slug("detail")
        session.expunge_all()
    assert detail.cohort.name == "2026 年暑期"
    assert detail.themes[0].slug == "ecology"
    assert [item.title for item in detail.journey_entries] == ["社区访谈", "最后展示"]
    assert [item.display_name for item in detail.members] == ["小林", "老师"]
    assert detail.resources[0].resource_type.code == "report"
    assert detail.impacts[0].category == "educational"


def test_incomplete_draft_can_be_saved_but_cannot_be_published(factory, catalog):
    with transaction(factory) as session:
        service = ProjectService(session)
        project = service.create_draft(
            cohort_id=catalog.cohort_id,
            title="未完成",
            slug="incomplete",
            summary="草稿",
        )
        with pytest.raises(PublishValidationError) as error:
            service.publish(project.id)
        assert "research_methods must not be blank" in error.value.issues
        assert "at least one theme is required" in error.value.issues
        assert "at least one journey entry is required" in error.value.issues
        assert "at least one resource is required" in error.value.issues
        assert project.status == "draft"
        assert project.published_at is None


@pytest.mark.parametrize(
    "field", ["research_question", "research_methods", "learning_outcomes", "practical_tips"]
)
def test_publication_rejects_blank_core_content(factory, complete_project, field):
    with transaction(factory) as session:
        project = complete_project(session)
        service = ProjectService(session)
        service.update_content(project.id, **{field: " \n\t "})
        with pytest.raises(PublishValidationError, match=field):
            service.publish(project.id)


def test_featured_reason_and_real_evidence_are_required(factory, complete_project):
    with transaction(factory) as session:
        project = complete_project(session)
        service = ProjectService(session)
        service.update_content(project.id, is_featured=True, featured_reason="  ", is_demo=False)
        with pytest.raises(PublishValidationError) as error:
            service.publish(project.id)
        assert "featured_reason is required for featured projects" in error.value.issues
        assert "every real impact requires an evidence_reference" in error.value.issues


def test_real_impact_scope_excludes_demo_drafts_and_archives(factory, complete_project):
    with transaction(factory) as session:
        service = ProjectService(session)
        for slug, is_demo in [
            ("real", False),
            ("demo", True),
            ("draft", False),
            ("archived", False),
        ]:
            project = complete_project(session, slug=slug, is_demo=is_demo)
            if slug != "draft":
                service.publish(project.id)
            if slug == "archived":
                service.archive(project.id)
    with transaction(factory) as session:
        repository = ProjectRepository(session)
        overview = repository.real_impact_overview()
        assert (
            overview.project_count,
            overview.cohort_count,
            overview.theme_count,
            overview.impact_count,
        ) == (1, 1, 1, 1)
        evidence = repository.list_real_impact_evidence()
        assert len(evidence) == 1
        assert evidence[0].project_slug == "real"
        assert evidence[0].impact.evidence_reference == "活动反馈记录第 2 页"


def test_lifecycle_preserves_history_and_requires_revalidation(factory, complete_project):
    with transaction(factory) as session:
        project = complete_project(session)
        service = ProjectService(session)
        service.publish(project.id)
        first_publication = project.published_at
        with pytest.raises(ValueError, match="Archive"):
            service.update_content(project.id, summary="修改")
        service.archive(project.id)
        service.update_content(project.id, research_methods="  ")
        with pytest.raises(PublishValidationError):
            service.publish(project.id)
        assert project.status == "archived"
        service.update_content(project.id, research_methods="更新后的方法")
        service.publish(project.id)
        assert project.published_at == first_publication


def test_write_refreshes_status_changed_by_another_session(factory, complete_project):
    with transaction(factory) as session:
        project_id = complete_project(session).id
    with transaction(factory) as reader:
        previously_loaded = reader.get(Project, project_id)
        assert previously_loaded.status == "draft"
        with transaction(factory) as publisher:
            ProjectService(publisher).publish(project_id)
        with pytest.raises(ValueError, match="Archive"):
            ProjectService(reader).update_content(project_id, summary="过期的编辑")
        assert previously_loaded.status == "published"


def test_publication_normalizes_timezone_and_rejects_naive_time(factory, complete_project):
    with transaction(factory) as session:
        project = complete_project(session)
        service = ProjectService(session)
        with pytest.raises(PublishValidationError, match="timezone"):
            service.publish(project.id, published_at=datetime(2026, 7, 1))
        service.publish(
            project.id, published_at=datetime(2026, 7, 1, 8, tzinfo=timezone(timedelta(hours=8)))
        )
        assert project.published_at == datetime(2026, 7, 1, tzinfo=UTC)


def test_transaction_rolls_back_the_whole_failed_publication(factory, catalog):
    with pytest.raises(PublishValidationError), transaction(factory) as session:
        project = ProjectService(session).create_draft(
            cohort_id=catalog.cohort_id,
            title="失败的项目",
            slug="rollback",
            summary="不完整",
        )
        ProjectService(session).publish(project.id)
    with transaction(factory) as session:
        assert session.scalar(select(Project).where(Project.slug == "rollback")) is None


def test_service_rejects_cross_project_stage(factory, catalog, complete_project):
    with transaction(factory) as session:
        first = complete_project(session)
        second = complete_project(session)
        stage_id = session.scalar(
            select(JourneyEntry.id).where(JourneyEntry.project_id == first.id)
        )
        with pytest.raises(ValueError, match="same project"):
            ProjectService(session).add_resource(
                second.id,
                resource_type_id=catalog.resource_type_id,
                title="错误关联",
                resource_url="test.md",
                journey_entry_id=stage_id,
            )


def test_database_defers_and_rejects_cross_project_stage(factory, catalog, complete_project):
    with transaction(factory) as session:
        first = complete_project(session)
        second = complete_project(session)
        first_id, second_id = first.id, second.id
        stage_id = session.scalar(
            select(JourneyEntry.id).where(JourneyEntry.project_id == first_id)
        )
    with pytest.raises(IntegrityError), transaction(factory) as session:
        session.add(
            ProjectResource(
                project_id=second_id,
                resource_type_id=catalog.resource_type_id,
                title="跨项目资源",
                resource_url="test.md",
                journey_entry_id=stage_id,
            )
        )
        session.flush()  # The composite foreign key is checked at COMMIT, not here.
    with transaction(factory) as session:
        assert session.scalar(select(func.count()).select_from(ProjectResource)) == 2


def test_stage_deletion_requires_unlinking_resources(factory, complete_project):
    with transaction(factory) as session:
        project = complete_project(session)
        project_id = project.id
        resource = session.scalar(
            select(ProjectResource).where(ProjectResource.project_id == project_id)
        )
        stage_id, resource_id = resource.journey_entry_id, resource.id
    with pytest.raises(IntegrityError), transaction(factory) as session:
        session.execute(delete(JourneyEntry).where(JourneyEntry.id == stage_id))
    with transaction(factory) as session:
        service = ProjectService(session)
        with pytest.raises(ValueError, match="Unlink"):
            service.remove_journey_entry(project_id, stage_id)
        service.set_resource_journey(project_id, resource_id, None)
        service.remove_journey_entry(project_id, stage_id)
    with transaction(factory) as session:
        assert session.get(JourneyEntry, stage_id) is None
        assert session.get(ProjectResource, resource_id).journey_entry_id is None


def test_project_deletion_cascades_all_children(factory, complete_project):
    with transaction(factory) as session:
        project_id = complete_project(session).id
    with transaction(factory) as session:
        ProjectService(session).delete_project(project_id)
    with transaction(factory) as session:
        for model in (
            Project,
            ProjectTheme,
            ProjectMember,
            JourneyEntry,
            ProjectResource,
            ProjectImpact,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(select(func.count()).select_from(Cohort)) == 1
        assert session.scalar(select(func.count()).select_from(Theme)) == 2


@pytest.mark.parametrize(
    "model,key", [(Cohort, "cohort_id"), (Theme, "theme_id"), (ResourceType, "resource_type_id")]
)
def test_referenced_catalog_records_cannot_be_deleted(
    factory, catalog, complete_project, model, key
):
    with transaction(factory) as session:
        complete_project(session)
    with pytest.raises(IntegrityError), transaction(factory) as session:
        session.execute(delete(model).where(model.id == getattr(catalog, key)))


@pytest.mark.parametrize(
    "metric",
    [
        {"metric_name": "人数"},
        {"metric_value": Decimal("1"), "metric_unit": "人", "metric_scope": "活动 A"},
        {
            "metric_name": "人数",
            "metric_value": Decimal("1"),
            "metric_unit": "人",
            "metric_scope": " ",
        },
    ],
)
def test_incomplete_quantitative_metrics_are_rejected(factory, complete_project, metric):
    with transaction(factory) as session:
        project_id = complete_project(session).id
    with pytest.raises(IntegrityError), transaction(factory) as session:
        ProjectService(session).add_impact(
            project_id,
            category="social",
            title="人数统计",
            description="统计方法",
            **metric,
        )


def test_complete_zero_metric_and_custom_resource_types(factory, complete_project):
    with transaction(factory) as session:
        project = complete_project(session, is_demo=False)
        custom_type = ResourceType(code="interactive-map", name="交互地图")
        session.add(custom_type)
        session.flush()
        service = ProjectService(session)
        service.add_resource(
            project.id, resource_type_id=custom_type.id, title="地图", resource_url="map.html"
        )
        impact = service.add_impact(
            project.id,
            category="social",
            title="人数统计",
            description="完整口径",
            evidence_reference="已核验活动记录",
            metric_name="人数",
            metric_value=Decimal("0"),
            metric_unit="人",
            metric_scope="2026 年 7 月活动 A，按签到人员去重",
        )
        service.publish(project.id)
        assert impact.metric_value == Decimal("0")


@pytest.mark.parametrize("field,value", [("status", "unknown"), ("featured_rank", -1)])
def test_database_rejects_invalid_status_and_sort_order(factory, complete_project, field, value):
    with transaction(factory) as session:
        project_id = complete_project(session).id
    with pytest.raises(IntegrityError), transaction(factory) as session:
        project = session.get(Project, project_id)
        setattr(project, field, value)


def test_unknown_project_and_missing_themes_are_reported(factory, catalog, complete_project):
    with transaction(factory) as session:
        service = ProjectService(session)
        with pytest.raises(ProjectNotFound):
            service.archive(uuid.uuid4())
        project = complete_project(session)
        with pytest.raises(ValueError, match="themes"):
            service.replace_themes(project.id, [uuid.uuid4()])
        with pytest.raises(ValueError, match="Unsupported"):
            service.update_content(project.id, status="published")
        assert (
            session.scalar(
                select(ProjectTheme.theme_id).where(ProjectTheme.project_id == project.id)
            )
            == catalog.theme_id
        )
