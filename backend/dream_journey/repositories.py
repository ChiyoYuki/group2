"""Public reads always exclude drafts and archived projects."""

import uuid
from dataclasses import dataclass

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from dream_journey.models import (
    Cohort,
    Project,
    ProjectImpact,
    ProjectQuestion,
    ProjectResource,
    ProjectSection,
    ProjectTheme,
    ResourceType,
    SectionResource,
    Theme,
)


@dataclass(frozen=True)
class ProjectPage:
    items: list[Project]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class ImpactOverview:
    project_count: int
    cohort_count: int
    theme_count: int
    impact_count: int


@dataclass(frozen=True)
class ImpactEvidence:
    project_slug: str
    project_title: str
    impact: ProjectImpact


def _pagination(page: int, page_size: int) -> None:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("page must be positive and page_size must be between 1 and 100")


class CatalogRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_cohorts(self) -> list[Cohort]:
        return list(self.session.scalars(select(Cohort).order_by(Cohort.year.desc(), Cohort.name)))

    def list_themes(self) -> list[Theme]:
        return list(self.session.scalars(select(Theme).order_by(Theme.slug)))

    def list_resource_types(self) -> list[ResourceType]:
        return list(self.session.scalars(select(ResourceType).order_by(ResourceType.code)))


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_public(
        self,
        *,
        cohort_id: uuid.UUID | None = None,
        dataset_key: str | None = None,
        theme_slug: str | None = None,
        keyword: str | None = None,
        featured_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> ProjectPage:
        _pagination(page, page_size)
        conditions = [Project.status == "published"]
        if dataset_key is not None:
            conditions.append(Project.dataset_key == dataset_key)
        if cohort_id is not None:
            conditions.append(Project.cohort_id == cohort_id)
        if theme_slug is not None:
            # EXISTS avoids duplicate projects and incorrect pagination on multi-theme projects.
            conditions.append(Project.themes.any(Theme.slug == theme_slug))
        if keyword and keyword.strip():
            literal = keyword.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{literal}%"
            conditions.append(
                or_(
                    Project.title.ilike(pattern, escape="\\"),
                    Project.summary.ilike(pattern, escape="\\"),
                    Project.research_question.ilike(pattern, escape="\\"),
                    Project.questions.any(ProjectQuestion.question.ilike(pattern, escape="\\")),
                )
            )
        if featured_only:
            conditions.append(Project.is_featured.is_(True))
        order = [Project.published_at.desc(), Project.id.desc()]
        if featured_only:
            order.insert(0, Project.featured_rank.desc())

        total = self.session.scalar(select(func.count()).select_from(Project).where(*conditions))
        statement = (
            select(Project)
            .where(*conditions)
            .order_by(*order)
            .options(joinedload(Project.cohort), selectinload(Project.themes))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return ProjectPage(list(self.session.scalars(statement)), total or 0, page, page_size)

    def get_public_by_slug(self, slug: str) -> Project | None:
        statement = (
            select(Project)
            .where(Project.slug == slug, Project.status == "published")
            .options(
                joinedload(Project.cohort),
                selectinload(Project.themes),
                selectinload(Project.questions),
                selectinload(Project.sections)
                .selectinload(ProjectSection.media)
                .joinedload(SectionResource.resource)
                .joinedload(ProjectResource.resource_type),
                selectinload(Project.members),
                selectinload(Project.journey_entries),
                selectinload(Project.resources).joinedload(ProjectResource.resource_type),
                selectinload(Project.impacts),
            )
            .execution_options(populate_existing=True)
        )
        return self.session.scalar(statement)

    def real_impact_overview(self) -> ImpactOverview:
        """Counts share one SQL snapshot and the same published/non-demo scope."""
        scope = (Project.status == "published", Project.is_demo.is_(False))
        statement = select(
            select(func.count())
            .select_from(Project)
            .where(*scope)
            .scalar_subquery()
            .label("project_count"),
            select(func.count(distinct(Project.cohort_id)))
            .where(*scope)
            .scalar_subquery()
            .label("cohort_count"),
            select(func.count(distinct(ProjectTheme.theme_id)))
            .join(Project)
            .where(*scope)
            .scalar_subquery()
            .label("theme_count"),
            select(func.count())
            .select_from(ProjectImpact)
            .join(Project)
            .where(*scope)
            .scalar_subquery()
            .label("impact_count"),
        )
        row = self.session.execute(statement).one()
        return ImpactOverview(**row._mapping)

    def list_real_impact_evidence(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> list[ImpactEvidence]:
        """Return sources and metric scopes; never sum incomparable or overlapping metrics."""
        _pagination(page, page_size)
        statement = (
            select(Project.slug, Project.title, ProjectImpact)
            .join(ProjectImpact)
            .where(Project.status == "published", Project.is_demo.is_(False))
            .order_by(ProjectImpact.created_at.desc(), ProjectImpact.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [
            ImpactEvidence(slug, title, impact)
            for slug, title, impact in self.session.execute(statement)
        ]
