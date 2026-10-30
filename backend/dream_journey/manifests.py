"""Dataset-neutral manifest validation and local resource integrity checks."""

import copy
import csv
import hashlib
import io
import json
import mimetypes
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlsplit

from dream_journey.datasets import DatasetSpec
from dream_journey.services import EDITABLE_FIELDS, RESOURCE_METADATA_FIELDS


def _text(value, label, *, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{label} must be text" + ("" if allow_empty else " and not blank"))
    return value


def _records(data, name):
    records = data.setdefault(name, [])
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValueError(f"{name} must be a list of objects")
    keys = []
    for index, item in enumerate(records):
        keys.append(_text(item.get("key"), f"{name}.key"))
        item.setdefault("sort_order", index)
        if type(item["sort_order"]) is not int:
            raise ValueError("sort_order must be an integer")
    if len(set(keys)) != len(keys):
        raise ValueError(f"{name} keys must be unique")
    return records


def _table(value):
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("columns"), list)
        or not isinstance(value.get("rows"), list)
    ):
        raise ValueError("Table data must contain columns and rows")
    columns = value["columns"]
    if not columns or any(not isinstance(column, str) or not column.strip() for column in columns):
        raise ValueError("Table columns must be nonempty text headers")
    if any(
        not isinstance(row, list)
        or len(row) != len(columns)
        or any(not isinstance(cell, str) for cell in row)
        for row in value["rows"]
    ):
        raise ValueError("Table rows must match their column headers")


def validate_manifest(source: dict, spec: DatasetSpec) -> dict:
    data = copy.deepcopy(source)
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported manifest schema_version")
    allowed = {
        "schema_version",
        "dataset",
        "project",
        "themes",
        "questions",
        "stages",
        "resources",
        "sections",
    }
    if set(data) - allowed:
        raise ValueError(f"Unknown manifest fields: {sorted(set(data) - allowed)}")
    dataset = data.get("dataset")
    if not isinstance(dataset, dict) or dataset.get("key") != spec.key:
        raise ValueError("Manifest belongs to another dataset")
    dataset.setdefault("version", 1)
    if type(dataset["version"]) is not int or dataset["version"] < 1:
        raise ValueError("Dataset version must be a positive integer")
    project = data.get("project")
    if not isinstance(project, dict):
        raise ValueError("project must be an object")
    unknown = set(project) - EDITABLE_FIELDS - {"status", "published_at", "cover_resource_key"}
    if unknown:
        raise ValueError(f"Unsupported project fields: {sorted(unknown)}")
    for field in ("slug", "title", "summary"):
        _text(project.get(field), f"project.{field}")
    if "status" in project and project["status"] not in {"draft", "published", "archived"}:
        raise ValueError("Invalid project status")
    for field in ("is_demo", "is_featured"):
        if field in project and type(project[field]) is not bool:
            raise ValueError(f"project.{field} must be a boolean")
    themes = data.setdefault("themes", [])
    if not isinstance(themes, list) or any(not isinstance(item, dict) for item in themes):
        raise ValueError("themes must be a list of objects")
    for theme in themes:
        _text(theme.get("slug"), "theme.slug")
        _text(theme.get("name"), "theme.name")
        if set(theme) - {"slug", "name", "description"}:
            raise ValueError("Unsupported theme fields")
    for question in _records(data, "questions"):
        _text(question.get("question"), "question.question")
        if set(question) - {"key", "question", "topic", "sort_order"}:
            raise ValueError("Unsupported question fields")
    stages = _records(data, "stages")
    stage_keys = {stage["key"] for stage in stages}
    for stage in stages:
        if set(stage) - {
            "key",
            "title",
            "description",
            "method_tags",
            "challenges",
            "responses",
            "reflection",
            "occurred_on",
            "sort_order",
        }:
            raise ValueError("Unsupported stage fields")
        _text(stage.get("title"), "stage.title")
        stage.setdefault("description", "")
        _text(stage["description"], "stage.description", allow_empty=True)
    resources = _records(data, "resources")
    resource_by_key = {item["key"]: item for item in resources}
    for resource in resources:
        _text(resource.get("title"), "resource.title")
        category = resource.get("type")
        if not isinstance(category, dict) or set(category) != {"code", "name"}:
            raise ValueError("Each resource type must define code and name")
        _text(category["code"], "resource.type.code")
        _text(category["name"], "resource.type.name")
        if resource.get("structured_data") is not None:
            _table(resource["structured_data"])
        if resource.get("mime_type") is not None:
            _text(resource["mime_type"], "resource.mime_type")
        if resource.get("stage_key") is not None and resource["stage_key"] not in stage_keys:
            raise ValueError("Resource references an unknown stage")
        if "filename" in resource:
            name = resource["filename"]
            _text(name, "resource.filename")
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts or "\\" in name:
                raise ValueError("Resource filename must be relative and contain no traversal")
            file = (spec.media_dir / name).resolve()
            if not file.is_relative_to(spec.media_dir.resolve()):
                raise ValueError("Media file must remain inside the import directory")
            content = file.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if (resource.get("sha256") is not None and resource["sha256"] != digest) or (
                resource.get("file_size_bytes") is not None
                and resource["file_size_bytes"] != len(content)
            ):
                raise ValueError(f"Media file differs from the manifest: {name}")
            resource["sha256"], resource["file_size_bytes"] = digest, len(content)
            if not resource.get("mime_type"):
                resource["mime_type"] = mimetypes.guess_type(name)[0] or "application/octet-stream"
            if resource["mime_type"].startswith("text/"):
                text = content.decode("utf-8-sig").replace("\r\n", "\n").strip()
                if resource.get("content_text") is not None and resource["content_text"] != text:
                    raise ValueError("Text content differs from its original file")
                resource["content_text"] = text
                if resource["mime_type"] == "text/csv":
                    rows = list(csv.reader(io.StringIO(text)))
                    if not rows:
                        raise ValueError("CSV must contain column headers")
                    table = {"columns": rows[0], "rows": rows[1:]}
                    if (
                        resource.get("structured_data") is not None
                        and resource["structured_data"] != table
                    ):
                        raise ValueError("Table data differs from its original CSV")
                    resource["structured_data"] = table
            resource["url"] = spec.media_url.rstrip("/") + "/" + quote(name, safe="/")
        else:
            url = _text(resource.get("url"), "resource.url")
            if not (url.startswith("/") and not url.startswith("//")) and urlsplit(
                url
            ).scheme not in {"http", "https"}:
                raise ValueError("Resource URL must use HTTP(S) or an absolute path")
        if resource.get("structured_data") is not None:
            _table(resource["structured_data"])
        if "is_ai_generated" in resource and type(resource["is_ai_generated"]) is not bool:
            raise ValueError("is_ai_generated must be a boolean")
        allowed_resource = RESOURCE_METADATA_FIELDS - {"import_key"} | {
            "key",
            "title",
            "type",
            "filename",
            "url",
            "mime_type",
            "description",
            "preview_url",
            "stage_key",
            "sort_order",
        }
        if set(resource) - allowed_resource:
            raise ValueError(
                f"Unsupported resource fields: {sorted(set(resource) - allowed_resource)}"
            )
    if (
        project.get("cover_resource_key") is not None
        and project["cover_resource_key"] not in resource_by_key
    ):
        raise ValueError("Cover references an unknown resource")
    for section in _records(data, "sections"):
        if set(section) - {"key", "kind", "title", "body", "stage_key", "media", "sort_order"}:
            raise ValueError("Unsupported section fields")
        _text(section.get("title"), "section.title")
        section.setdefault("kind", "other")
        section.setdefault("body", "")
        if section["kind"] not in {"opening", "journey", "output", "learning", "other"}:
            raise ValueError("Invalid section kind")
        _text(section["body"], "section.body", allow_empty=True)
        if section.get("stage_key") is not None and section["stage_key"] not in stage_keys:
            raise ValueError("Section references an unknown stage")
        if section["kind"] == "journey" and section.get("stage_key") is None:
            raise ValueError("Journey section requires a stage")
        links = section.setdefault("media", [])
        if not isinstance(links, list) or any(not isinstance(link, dict) for link in links):
            raise ValueError("section.media must be a list of objects")
        seen = set()
        for index, link in enumerate(links):
            if set(link) - {"resource_key", "role", "is_optional", "sort_order"}:
                raise ValueError("Unsupported media link fields")
            key = link.get("resource_key")
            _text(key, "media.resource_key")
            if key not in resource_by_key or key in seen:
                raise ValueError("Section media must reference unique existing resource keys")
            seen.add(key)
            link.setdefault("role", "attachment")
            link.setdefault("is_optional", False)
            link.setdefault("sort_order", index)
            if link["role"] not in {"illustration", "narration", "attachment"}:
                raise ValueError("Invalid media role")
            if type(link["is_optional"]) is not bool or type(link["sort_order"]) is not int:
                raise ValueError("Invalid media link options")
            if link["role"] == "narration" and not resource_by_key[key].get(
                "mime_type", ""
            ).startswith(("audio/", "video/")):
                raise ValueError("Narration requires audio or video media")
    return data


def load_manifest(spec: DatasetSpec, path: Path | None = None) -> dict:
    return validate_manifest(json.loads((path or spec.manifest).read_text()), spec)
