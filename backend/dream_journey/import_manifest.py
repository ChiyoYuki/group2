"""Import an explicit manifest; no sample datasets are registered in the backend."""

import argparse
import json
from pathlib import Path

from alembic import command
from alembic.config import Config

from dream_journey.database import make_engine, make_session_factory, transaction
from dream_journey.dataset_import import import_dataset
from dream_journey.datasets import DatasetSpec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--media-dir", type=Path)
    parser.add_argument("--media-url")
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text())
    spec = DatasetSpec.from_manifest(
        args.manifest, data["dataset"]["key"], media_dir=args.media_dir, media_url=args.media_url
    )
    engine = make_engine()
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        with transaction(make_session_factory(engine)) as session:
            result = import_dataset(session, spec, manifest=data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
