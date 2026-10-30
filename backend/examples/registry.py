"""Registered content packages and their independent media namespaces."""

from dataclasses import dataclass
from pathlib import Path

from dream_journey.datasets import DatasetSpec as ImportContext

BACKEND = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    import_prefix: str

    @property
    def content_dir(self) -> Path:
        return BACKEND / "content" / self.key

    @property
    def manifest(self) -> Path:
        return self.content_dir / "project.json"

    @property
    def media_dir(self) -> Path:
        return BACKEND / "media" / self.key

    @property
    def media_url(self) -> str:
        return f"/media/{self.key}"

    def context(self) -> ImportContext:
        return ImportContext(self.key, self.manifest, self.media_dir, self.media_url)


DATASETS = {
    "miao-culture": DatasetSpec("miao-culture", "miao"),
    "dangar-old-town": DatasetSpec("dangar-old-town", "dangar"),
}


def get_dataset(key: str) -> DatasetSpec:
    try:
        return DATASETS[key]
    except KeyError:
        raise ValueError(f"Unknown dataset: {key}") from None
