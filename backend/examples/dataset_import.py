"""Translate the optional legacy examples into the backend's generic format."""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from dream_journey.dataset_import import import_dataset as import_manifest
from dream_journey.manifests import validate_manifest
from dream_journey.services import RESOURCE_METADATA_FIELDS

TYPE_NAMES = {
    "creative_work": "创意作品",
    "image": "图片",
    "audio": "音频",
    "report": "报告",
    "data_table": "资料表",
}


def convert_manifest(data, spec):
    if data.get("schema_version") not in {1, 2}:
        raise ValueError("Unsupported example package version")
    if data.get("dataset_key", spec.key) != spec.key:
        raise ValueError("Manifest belongs to another dataset")
    stages = {
        item["position"]: f"{spec.import_prefix}:step-{item['position']}" for item in data["stages"]
    }
    resources = {
        item["filename"]: f"{spec.import_prefix}:{item['filename']}" for item in data["assets"]
    }
    if data["schema_version"] == 2:
        expected = [
            "opening",
            *(f"step-{item['position']}" for item in data["stages"]),
            "output",
            "learning",
        ]
        if [item["key"] for item in data["sections"] if item["kind"] != "other"] != expected:
            raise ValueError("Example narrated layout does not match its source package")
        by_name = {item["filename"]: item for item in data["assets"]}
        for section in data["sections"]:
            narrations = [link for link in section["media"] if link["role"] == "narration"]
            if section["kind"] != "other" and len(narrations) != 1:
                raise ValueError("Each narrated example section requires one narration")
            for link in narrations:
                asset = by_name[link["asset"]]
                if asset.get("transcript") != section["body"] or not asset.get("duration_seconds"):
                    raise ValueError("Example narration must match the supplied transcript")
    fields = {
        key: data[key]
        for key in (
            "slug",
            "title",
            "summary",
            "background",
            "opening_question",
            "short_title",
            "content_kind",
            "content_notice",
            "content_tags",
            "learning_outcomes",
            "practical_tips",
        )
        if key in data
    }
    for key in ("cohort_id", "location", "team_name"):
        if data.get(key) is not None:
            fields[key] = data[key]
    fields.update(
        research_question="\n".join(q["question"] for q in data["questions"]),
        research_methods="\n".join(
            f"{item['label']}：{item['description']}" for item in data["methods"]
        ),
        is_demo=data.get("is_demo", True),
        is_featured=data.get("is_featured", bool(data.get("featured_reason"))),
        featured_rank=data.get("featured_rank", 100),
        featured_reason=data.get("featured_reason"),
        cover_resource_key=resources[data.get("cover_filename", "final-artwork.jpg")],
    )
    result = {
        "schema_version": 1,
        "dataset": {
            "key": spec.key,
            "version": data.get("dataset_version", data["schema_version"]),
        },
        "project": fields,
        "themes": data["themes"],
        "questions": [
            {"key": f"question-{index + 1}", "sort_order": index, **item}
            for index, item in enumerate(data["questions"])
        ],
        "stages": [],
        "resources": [],
        "sections": [],
    }
    for item in data["stages"]:
        values = {
            key: item[key]
            for key in (
                "title",
                "description",
                "challenges",
                "responses",
                "reflection",
                "method_tags",
                "occurred_on",
            )
            if key in item
        }
        result["stages"].append(
            {"key": stages[item["position"]], "sort_order": item["position"] - 1, **values}
        )
    for index, item in enumerate(data["assets"]):
        mime = item.get("mime_type", "image/jpeg")
        code = item.get("resource_type") or (
            "data_table"
            if mime == "text/csv"
            else "report"
            if mime.startswith("text/")
            else "creative_work"
            if item["usage_role"] == "output"
            else "audio"
            if mime.startswith("audio/")
            else "image"
        )
        values = {
            key: value
            for key, value in item.items()
            if key in RESOURCE_METADATA_FIELDS and key != "import_key"
        }
        result["resources"].append(
            {
                "key": resources[item["filename"]],
                "title": item["title"],
                "filename": item["filename"],
                "mime_type": mime,
                "type": {"code": code, "name": TYPE_NAMES.get(code, code)},
                "stage_key": stages.get(item.get("stage")),
                "sort_order": index,
                **values,
            }
        )
    for item in data.get("sections", []):
        result["sections"].append(
            {
                "key": item["key"],
                "kind": item["kind"],
                "title": item["title"],
                "body": item["body"],
                "stage_key": stages.get(item.get("stage")),
                "sort_order": item["sort_order"],
                "media": [
                    {
                        "resource_key": resources[link["asset"]],
                        "role": link["role"],
                        "is_optional": link["is_optional"],
                    }
                    for link in item["media"]
                ],
            }
        )
    return result


def load_manifest(spec, path: Path | None = None):
    data = json.loads((path or spec.manifest).read_text())
    validate_manifest(convert_manifest(data, spec), spec.context())
    return data


def import_dataset(session: Session, spec, *, manifest_path: Path | None = None):
    data = json.loads((manifest_path or spec.manifest).read_text())
    return import_manifest(
        session, spec.context(), manifest=convert_manifest(data, spec), default_status="published"
    )
