"""Normalize the second, independently sourced Dangar old town package."""

import csv
import hashlib
import io
import json
import re
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from dream_journey.package_utils import image_dimensions, write_bytes
from examples.registry import get_dataset

SPEC = get_dataset("dangar-old-town")


def prepare_archive(path: Path) -> dict:
    with ZipFile(path) as archive:
        maps = [name for name in archive.namelist() if name.endswith("/00_图片文字音频对应表.csv")]
        if len(maps) != 1:
            raise ValueError("Expected one text/image/audio mapping CSV")
        prefix = maps[0].removesuffix("00_图片文字音频对应表.csv")

        def binary(relative):
            member_path = PurePosixPath(relative)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError("Invalid archive member path")
            info = archive.getinfo(prefix + relative)
            if info.file_size > 32 * 1024 * 1024:
                raise ValueError("Package member exceeds the import limit")
            return archive.read(info)

        def text(relative):
            return binary(relative).decode("utf-8-sig").replace("\r\n", "\n").strip()

        def rows(relative):
            return list(csv.DictReader(io.StringIO(text(relative))))

        mapping = rows("00_图片文字音频对应表.csv")
        if [int(row["编号"]) for row in mapping] != list(range(1, 11)):
            raise ValueError("Expected ten ordered narration segments")
        basics = dict(
            line.split("：", 1)
            for line in text("01_项目基础信息/01_项目标题与标签.txt").splitlines()
            if "：" in line
        )
        methods = [
            {"label": line.split("：", 1)[0], "description": line.split("：", 1)[1]}
            for line in text("02_研究内容/02_研究方法.txt").splitlines()
            if "：" in line
        ]
        question_texts = re.findall(r"^\d+\. (.+)$", text("02_研究内容/01_研究问题.txt"), re.M)
        method_tags = [
            ["整理表达"],
            ["照片观察"],
            ["资料查找"],
            ["资料查找"],
            ["照片观察", "区分证据"],
            ["概念比较"],
            ["区分证据", "整理表达"],
        ]
        difficulties = text("02_研究内容/03_困难与解决办法.txt").split("\n\n")
        challenges = {}
        for position, paragraph in zip([5, 6, 7], difficulties, strict=True):
            lines = paragraph.splitlines()
            challenges[position] = (lines[0].split("：", 1)[1], lines[1].split("：", 1)[1])
        stages = []
        for row in mapping[1:8]:
            raw = text(row["正文文件"])
            position = int(re.search(r"步骤：(\d+)", raw).group(1))
            stage = {
                "position": position,
                "title": re.search(r"标题：(.+)", raw).group(1),
                "description": re.search(r"旁白：\n(.*?)(?:\n\n|\Z)", raw, re.S).group(1).strip(),
                "source_file": row["正文文件"],
                "method_tags": method_tags[position - 1],
            }
            if position in challenges:
                stage["challenges"], stage["responses"] = challenges[position]
            stages.append(stage)
        if [stage["position"] for stage in stages] != list(range(1, 8)):
            raise ValueError("Expected seven ordered research steps")
        assets, contents = [], {}

        def add_asset(source, filename, mime, **metadata):
            data = binary(source)
            contents[filename] = data
            asset = {
                "filename": filename,
                "source_file": source,
                "mime_type": mime,
                "file_size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "rights_status": "unconfirmed",
                "stage": None,
                **metadata,
            }
            if mime.startswith("image/"):
                asset["width"], asset["height"] = image_dimensions(data)
            if mime.startswith("text/"):
                asset["content_text"] = text(source)
            if mime == "text/csv":
                table = list(csv.reader(io.StringIO(asset["content_text"])))
                asset["structured_data"] = {"columns": table[0], "rows": table[1:]}
            assets.append(asset)
            return asset

        photo_names = [
            "opening-question.png",
            "street-reference.jpg",
            "courtyard-reference.jpg",
            "gate-reference.jpg",
        ]
        photo_stages = [None, 2, 5, 3]
        generation_note = text("06_素材说明与来源/开场图生成说明.txt")
        for index, (row, filename, stage) in enumerate(
            zip(
                rows("06_素材说明与来源/图片图注与来源.csv"), photo_names, photo_stages, strict=True
            )
        ):
            add_asset(
                row["文件"],
                filename,
                "image/png" if index == 0 else "image/jpeg",
                title=row["图注"],
                caption=row["图注"],
                alt_text=row["图注"],
                usage_role="process" if index == 0 else "reference",
                stage=stage,
                source_name=row["来源"],
                provenance_note=row["说明"],
                is_ai_generated=index == 0,
                generation_note=generation_note if index == 0 else None,
            )
        common = {
            "source_name": "用户提供的第二个素材包",
            "provenance_note": "按素材包原文整理；不代表独立核验或已发生的学生实地活动。",
        }
        add_asset(
            "04_成果与收获/01_我们的发现卡.md",
            "discovery-card.md",
            "text/markdown",
            title="我们的发现卡",
            usage_role="output",
            resource_type="report",
            caption="本次整理的展示内容，不是已有学生作品的证明。",
            **common,
        )
        add_asset(
            "04_成果与收获/02_古城与服务区对照.csv",
            "comparison.csv",
            "text/csv",
            title="古城与服务区对照",
            usage_role="output",
            stage=6,
            **common,
        )
        add_asset(
            "02_研究内容/04_已知与待确认.csv",
            "knowledge-status.csv",
            "text/csv",
            title="已知与待确认",
            usage_role="process",
            stage=5,
            **common,
        )
        add_asset(
            "06_素材说明与来源/文字资料来源.csv",
            "text-sources.csv",
            "text/csv",
            title="文字资料来源",
            usage_role="reference",
            **common,
        )
        source_to_name = {asset["source_file"]: asset["filename"] for asset in assets}
        sections = []
        background = text("01_项目基础信息/03_项目起因.txt")
        output = text("04_成果与收获/03_成果介绍.txt")
        learning = text("04_成果与收获/04_学习收获.txt")
        for row in mapping:
            ordinal = int(row["编号"])
            stage = ordinal - 1 if 2 <= ordinal <= 8 else None
            key = f"step-{stage}" if stage else {1: "opening", 9: "output", 10: "learning"}[ordinal]
            transcript = text(row["逐字台词"])
            expected = (
                stages[stage - 1]["description"]
                if stage
                else {1: background, 9: output, 10: learning}[ordinal]
            )
            if transcript != expected:
                raise ValueError(f"Narration does not match section body: {key}")
            audio_name = f"narration-{ordinal:02d}.mp3"
            add_asset(
                row["音频"],
                audio_name,
                "audio/mpeg",
                title=f"{row['标题']} · AI配音",
                usage_role="process",
                stage=stage,
                transcript=transcript,
                duration_seconds=row["时长_秒"],
                is_ai_generated=True,
                generation_note=text("07_分段配音/00_使用说明.txt"),
                source_name="素材包内的AI合成配音",
                provenance_note="合成示例，不是真实学生录音。",
            )
            media = []
            if row["图片"]:
                media.append(
                    {
                        "asset": source_to_name[row["图片"]],
                        "role": "illustration",
                        "is_optional": False,
                    }
                )
            if row["辅助内容"]:
                media.append(
                    {
                        "asset": source_to_name[row["辅助内容"]],
                        "role": "attachment",
                        "is_optional": False,
                    }
                )
            if stage == 5:
                media.append(
                    {"asset": "knowledge-status.csv", "role": "attachment", "is_optional": False}
                )
            media.append({"asset": audio_name, "role": "narration", "is_optional": False})
            sections.append(
                {
                    "key": key,
                    "kind": "journey" if stage else key,
                    "title": row["标题"],
                    "body": transcript,
                    "stage": stage,
                    "sort_order": ordinal - 1,
                    "media": media,
                }
            )
        sections.append(
            {
                "key": "sources",
                "kind": "other",
                "title": "文字资料来源与事实边界",
                "body": text("06_素材说明与来源/来源与事实说明.txt"),
                "stage": None,
                "sort_order": 10,
                "media": [
                    {"asset": "text-sources.csv", "role": "attachment", "is_optional": False}
                ],
            }
        )
        manifest = {
            "schema_version": 2,
            "dataset_key": SPEC.key,
            "dataset_version": 1,
            "archive_filename": path.name,
            "slug": "dangar-old-town-inquiry",
            "title": basics["项目标题"],
            "short_title": basics["列表短标题"],
            "summary": text("01_项目基础信息/02_一句话简介.txt"),
            "background": background,
            "opening_question": basics["项目标题"],
            "content_kind": "reconstructed",
            "content_notice": text("01_项目基础信息/04_内容性质说明.txt")
            + "\n发现卡是本次整理的展示内容，不是已完成学生作品的证明。"
            "喂马的具体地点和安排未确认；现代‘服务区’只是类比。",
            "content_tags": basics["标签"].split("、"),
            "is_demo": True,
            "cover_filename": "opening-question.png",
            "themes": [
                {"slug": "history-culture", "name": "历史文化"},
                {"slug": "old-town-architecture", "name": "古城建筑"},
                {"slug": "trade-exchange", "name": "商贸交流"},
            ],
            "questions": [
                {"topic": topic, "question": question}
                for topic, question in zip(
                    ["古城功能", "商旅与歇家", "尚待确认的马匹问题"], question_texts, strict=True
                )
            ],
            "methods": methods,
            "stages": stages,
            "sections": sections,
            "assets": assets,
            "learning_outcomes": learning,
            "practical_tips": (
                "先观察照片，再查资料；把看见的、查到的和猜想分开。"
                "用现代概念类比时说明相似与不同，具体喂马地点无证据时保留‘待确认’。"
            ),
            "featured_reason": (
                "从一个关于马的提问出发，用照片、文字资料、发现卡和比较表区分证据与类比。"
            ),
        }
        for filename, data in contents.items():
            write_bytes(SPEC.media_dir / filename, data)
        for source, target in [
            ("00_全部文案预览.md", "original-copy.md"),
            ("00_图片文字音频对应表.csv", "text-media-map.csv"),
            ("06_素材说明与来源/图片图注与来源.csv", "image-sources.csv"),
            ("06_素材说明与来源/来源与事实说明.txt", "source-notes.txt"),
            ("07_分段配音/00_使用说明.txt", "narration-notice.txt"),
        ]:
            write_bytes(SPEC.content_dir / target, (text(source) + "\n").encode())
        write_bytes(
            SPEC.manifest, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
        )
    return manifest
