"""Read-only smoke check: python -m dream_journey."""

import json
from dataclasses import asdict

from dream_journey.database import make_engine, make_session_factory, transaction
from dream_journey.repositories import ProjectRepository


def main() -> None:
    engine = make_engine()
    try:
        with transaction(make_session_factory(engine)) as session:
            repository = ProjectRepository(session)
            page = repository.list_public()
            result = {
                "published_projects": page.total,
                "projects": [
                    {"slug": item.slug, "title": item.title, "is_demo": item.is_demo}
                    for item in page.items
                ],
                "real_impact_overview": asdict(repository.real_impact_overview()),
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
