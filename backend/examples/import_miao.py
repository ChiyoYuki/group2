"""Compatibility entry point for the Miao culture dataset."""

import argparse
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from dream_journey.database import make_engine, make_session_factory, transaction
from examples.dataset_import import import_dataset
from examples.dataset_import import load_manifest as load_dataset_manifest
from examples.registry import BACKEND, get_dataset

SPEC = get_dataset("miao-culture")
MANIFEST = SPEC.manifest
MEDIA = SPEC.media_dir
DATASET_KEY = SPEC.key


def load_manifest(path: Path | None = None) -> dict:
    return load_dataset_manifest(SPEC, path)


def import_project(session: Session, *, manifest_path: Path | None = None) -> dict:
    return import_dataset(session, SPEC, manifest_path=manifest_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--archive", type=Path, help="Prepare the updated ZIP before importing")
    inputs.add_argument("--manifest", type=Path, help="Use a specific normalized manifest")
    args = parser.parse_args()
    if args.archive:
        from examples.miao_package import prepare_archive

        prepare_archive(args.archive)
    engine = make_engine()
    try:
        with engine.connect() as connection:
            config = Config(str(BACKEND / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with transaction(make_session_factory(engine)) as session:
            result = import_project(session, manifest_path=args.manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
