"""Explicit import context; the application has no built-in datasets."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    manifest: Path
    media_dir: Path
    media_url: str

    def __post_init__(self):
        if not isinstance(self.key, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]*", self.key
        ):
            raise ValueError("Dataset key must be an identifier using letters, digits, '-' or '_'")
        if (
            not self.media_url.startswith("/")
            or self.media_url.startswith("//")
            or ".." in self.media_url.split("/")
        ):
            raise ValueError("media_url must be an absolute URL path without traversal")

    @classmethod
    def from_manifest(
        cls, path: Path, key: str, *, media_dir: Path | None = None, media_url: str | None = None
    ):
        path = path.resolve()
        return cls(key, path, media_dir or path.parent / "media", media_url or f"/media/{key}")
