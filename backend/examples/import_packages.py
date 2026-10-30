"""Import one or all registered content datasets in a single transaction."""

import argparse
import json
from pathlib import Path

from alembic import command
from alembic.config import Config

from dream_journey.database import make_engine, make_session_factory, transaction
from examples.dataset_import import import_dataset
from examples.registry import BACKEND, DATASETS, get_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=[*DATASETS, "all"])
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.archive:
        if args.dataset == "all":
            parser.error("--archive requires one specific dataset")
        if args.dataset == "miao-culture":
            from examples.miao_package import prepare_archive
        else:
            from examples.dangar_package import prepare_archive
        prepare_archive(args.archive)
    keys = list(DATASETS) if args.dataset == "all" else [args.dataset]
    engine = make_engine()
    try:
        config = Config(str(BACKEND / "alembic.ini"))
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with transaction(make_session_factory(engine)) as session:
            results = [import_dataset(session, get_dataset(key)) for key in keys]
        print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
