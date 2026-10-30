"""Run every test against the real migration, optionally in an isolated PostgreSQL schema."""

import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from dream_journey.database import make_engine, make_session_factory, transaction
from dream_journey.models import Cohort, ResourceType, Theme
from dream_journey.services import ProjectService

BACKEND = Path(__file__).resolve().parents[1]


def migration_config(connection) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
def engine(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL")
    admin_engine = None
    schema = None
    if url:
        if not url.startswith("postgresql+psycopg://"):
            raise ValueError("TEST_DATABASE_URL must use postgresql+psycopg://")
        admin_engine = make_engine(url)
        schema = f"test_dream_journey_{uuid.uuid4().hex}"
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        scoped_engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        scoped_engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with scoped_engine.connect() as connection:
            command.upgrade(migration_config(connection), "head")
        yield scoped_engine
    finally:
        scoped_engine.dispose()
        if admin_engine is not None:
            with admin_engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
            admin_engine.dispose()


@pytest.fixture
def factory(engine):
    return make_session_factory(engine)


@pytest.fixture
def catalog(factory):
    with transaction(factory) as session:
        cohort = Cohort(name="2026 年暑期", year=2026)
        theme = Theme(name="生态", slug="ecology")
        other_theme = Theme(name="社区研究", slug="community")
        resource_type = ResourceType(code="report", name="报告")
        session.add_all([cohort, theme, other_theme, resource_type])
        session.flush()
        return SimpleNamespace(
            cohort_id=cohort.id,
            theme_id=theme.id,
            other_theme_id=other_theme.id,
            resource_type_id=resource_type.id,
        )


@pytest.fixture
def complete_project(catalog):
    def create(session, *, slug=None, is_demo=True, featured=False, rank=0):
        service = ProjectService(session)
        project = service.create_draft(
            cohort_id=catalog.cohort_id,
            title="湿地调研",
            slug=slug or uuid.uuid4().hex,
            summary="访谈社区居民并记录湿地变化",
            research_question="如何保护湿地？",
            research_methods="定点观察与访谈",
            learning_outcomes="区分事实与推断",
            practical_tips="先试访再完善提纲",
            theme_ids=[catalog.theme_id],
            is_demo=is_demo,
            is_featured=featured,
            featured_reason="展示完整过程" if featured else None,
            featured_rank=rank,
        )
        service.add_member(project.id, display_name="小林", role="学生")
        stage = service.add_journey_entry(
            project.id, title="社区访谈", description="开展半结构访谈"
        )
        service.add_resource(
            project.id,
            resource_type_id=catalog.resource_type_id,
            title="报告",
            resource_url="https://example.test/report.md",
            journey_entry_id=stage.id,
        )
        service.add_impact(
            project.id,
            category="educational",
            title="学习访谈方法",
            description="对比前后提纲",
            evidence_reference=None if is_demo else "活动反馈记录第 2 页",
        )
        return project

    return create
