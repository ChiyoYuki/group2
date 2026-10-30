"""Translate the supplied CSV/text/audio ZIP into a checked, portable dataset.

Archive documents are content, never commands. Output names are controlled here.
"""

import csv
import hashlib
import io
import json
import re
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from dream_journey.package_utils import image_dimensions
from dream_journey.package_utils import write_bytes as _write

BACKEND = Path(__file__).resolve().parents[1]
CONTENT = BACKEND / "content/miao-culture"
MEDIA = BACKEND / "media/miao-culture"


def prepare_archive(path: Path) -> dict:
    manifest = json.loads((CONTENT / "history/v1.json").read_text())
    with ZipFile(path) as archive:
        maps = [name for name in archive.namelist() if name.endswith("/00_图片文字音频对应表.csv")]
        if len(maps) != 1:
            raise ValueError("The updated package must contain one image/text/audio mapping CSV")
        prefix = maps[0].removesuffix("00_图片文字音频对应表.csv")

        def binary(relative: str) -> bytes:
            parts = PurePosixPath(relative)
            if parts.is_absolute() or ".." in parts.parts:
                raise ValueError("Invalid archive member path")
            member = archive.getinfo(prefix + relative)
            if member.file_size > 32 * 1024 * 1024:
                raise ValueError("Package member exceeds the import limit")
            return archive.read(member)

        def text(relative: str) -> str:
            return binary(relative).decode("utf-8-sig").replace("\r\n", "\n").strip()

        rows = list(csv.DictReader(io.StringIO(text("00_图片文字音频对应表.csv"))))
        if [int(row["编号"]) for row in rows] != list(range(1, 11)):
            raise ValueError("Expected the ten ordered narration segments")
        manifest.update(
            {
                "schema_version": 2,
                "archive_filename": path.name,
                "summary": text("01_项目基础信息/02_一句话简介.txt"),
                "background": text("01_项目基础信息/03_项目起因.txt"),
                "opening_question": re.search(
                    r"开场提问：(.+)", text("01_项目基础信息/01_项目标题与标签.txt")
                ).group(1),
                "learning_outcomes": text("04_成果与收获/03_学习收获.txt").split("\n\n")[0],
                "cover_filename": "opening-question.png",
            }
        )
        questions = re.findall(r"^\d+\. (.+)$", text("02_研究内容/01_研究问题.txt"), re.M)
        manifest["questions"] = [
            {"topic": topic, "question": question}
            for topic, question in zip(["苗绣", "银饰", "蜡染"], questions, strict=True)
        ]
        manifest["methods"] = [
            {"label": line.split("：", 1)[0], "description": line.split("：", 1)[1]}
            for line in text("02_研究内容/02_研究方法.txt").splitlines()
            if "：" in line and not line.startswith(("用于", "页面"))
        ]
        for stage in manifest["stages"]:
            raw = text(stage["source_file"])
            stage["title"] = re.search(r"标题：(.+)", raw).group(1)
            stage["description"] = (
                re.search(r"旁白：\n(.*?)(?:\n\n|\Z)", raw, re.S).group(1).strip()
            )
        assets = []
        contents = {}

        def add_asset(source: str, filename: str, mime: str, **metadata) -> dict:
            data = binary(source)
            contents[filename] = data
            item = {
                "filename": filename,
                "source_file": source,
                "mime_type": mime,
                "file_size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                **metadata,
            }
            if mime.startswith("image/"):
                item["width"], item["height"] = image_dimensions(data)
            assets.append(item)
            return item

        # Preserve the five original image identities for in-place upgrades.
        original = manifest.pop("assets")
        for item in original:
            metadata = {
                key: value
                for key, value in item.items()
                if key
                not in {"source_file", "filename", "width", "height", "file_size_bytes", "sha256"}
            }
            if item["usage_role"] == "output":
                metadata["caption"] = text("04_成果与收获/02_成果介绍.txt")
            add_asset(item["source_file"], item["filename"], "image/jpeg", **metadata)
        add_asset(
            "00_开场图片/01_开场提问.png",
            "opening-question.png",
            "image/png",
            title=manifest["opening_question"],
            caption="用户提供的开场提问图。",
            alt_text=manifest["opening_question"],
            usage_role="process",
            stage=None,
            source_name="用户提供的开场图",
            rights_status="unconfirmed",
            provenance_note="来源为本次素材包，保留原图内容。",
        )
        source_to_name = {asset["source_file"]: asset["filename"] for asset in assets}
        sections = []
        for row in rows:
            ordinal = int(row["编号"])
            stage_number = ordinal - 1 if 2 <= ordinal <= 8 else None
            key = (
                f"step-{stage_number}"
                if stage_number
                else {1: "opening", 9: "output", 10: "learning"}[ordinal]
            )
            kind = "journey" if stage_number else key
            transcript = text(row["逐字台词文件"])
            expected = (
                manifest["stages"][stage_number - 1]["description"]
                if stage_number
                else {
                    1: manifest["background"],
                    9: text("04_成果与收获/02_成果介绍.txt"),
                    10: manifest["learning_outcomes"],
                }[ordinal]
            )
            if transcript != expected:
                raise ValueError(f"Narration transcript differs from displayed text: {key}")
            audio_name = f"narration-{ordinal:02d}.mp3"
            add_asset(
                row["音频文件"],
                audio_name,
                "audio/mpeg",
                title=f"{row['标题']} · AI配音",
                usage_role="process",
                stage=stage_number,
                transcript=transcript,
                duration_seconds=row["时长_秒"],
                is_ai_generated=True,
                generation_note=text("07_分段配音/00_使用说明.txt"),
                source_name="素材包内的AI合成配音",
                rights_status="unconfirmed",
                provenance_note="AI合成声音，不是真实学生录音。",
            )
            media = []
            if row["图片文件"]:
                media.append(
                    {
                        "asset": source_to_name[row["图片文件"]],
                        "role": "illustration",
                        "is_optional": ordinal == 7,
                    }
                )
            media.append({"asset": audio_name, "role": "narration", "is_optional": False})
            sections.append(
                {
                    "key": key,
                    "kind": kind,
                    "title": row["标题"],
                    "body": transcript,
                    "stage": stage_number,
                    "sort_order": ordinal - 1,
                    "media": media,
                }
            )
        manifest["assets"] = assets
        manifest["sections"] = sections
        manifest["source_notice"] = text("06_图片说明与来源/图片来源说明.txt").split("\n\n01_")[0]
        for filename, data in contents.items():
            _write(MEDIA / filename, data)
        for source, target in [
            ("00_全部文案预览.md", "original-copy.md"),
            ("00_图片文字音频对应表.csv", "text-media-map.csv"),
            ("06_图片说明与来源/图片与步骤对应表.csv", "image-sources.csv"),
            ("06_图片说明与来源/图片来源说明.txt", "image-sources.txt"),
            ("07_分段配音/00_使用说明.txt", "narration-notice.txt"),
        ]:
            _write(CONTENT / target, (text(source) + "\n").encode())
        _write(
            CONTENT / "project.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        )
    return manifest
