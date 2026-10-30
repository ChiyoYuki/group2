from dream_journey.database import transaction
from dream_journey.repositories import CatalogRepository, ProjectRepository
from examples.registry import BACKEND
from examples.seed import seed_database


def test_seed_is_idempotent_and_has_local_resources(factory):
    with transaction(factory) as session:
        assert seed_database(session)["inserted_projects"] == 3
    with transaction(factory) as session:
        assert seed_database(session)["inserted_projects"] == 0
        repository = ProjectRepository(session)
        assert repository.list_public().total == 3
        assert repository.real_impact_overview().project_count == 0
        assert len(CatalogRepository(session).list_themes()) == 7
        assert len(CatalogRepository(session).list_resource_types()) == 5
        assert len(CatalogRepository(session).list_cohorts()) == 3
        for project in repository.list_public().items:
            detail = repository.get_public_by_slug(project.slug)
            assert detail.is_demo
            for resource in detail.resources:
                assert (BACKEND / resource.resource_url).is_file()
