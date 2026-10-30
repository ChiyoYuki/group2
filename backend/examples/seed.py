"""Idempotent demo content. All sample projects are explicitly marked is_demo=True."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dream_journey.database import make_engine, make_session_factory, transaction
from dream_journey.models import Cohort, Project, ResourceType, Theme
from dream_journey.services import ProjectService

THEMES = (
    ("culture", "文化"),
    ("heritage", "文化遗产"),
    ("ecology", "生态"),
    ("architecture", "建筑"),
    ("museums", "博物馆"),
    ("agriculture", "农业"),
    ("community", "社区研究"),
)
RESOURCE_TYPES = (
    ("report", "报告"),
    ("creative_work", "创意作品"),
    ("video", "视频"),
    ("model", "模型"),
    ("presentation", "演示文稿"),
)

SAMPLES = (
    {
        "slug": "demo-wetland-observation",
        "year": 2026,
        "title": "【示例】湿地里的社区观察",
        "location": "示例湿地公园",
        "summary": "通过定点观察和访谈，理解湿地生态与社区生活之间的联系。",
        "question": "社区如何在日常使用湿地空间的同时保护生态？",
        "methods": "定点观察、半结构访谈、路线记录；本项目为虚构教学示例。",
        "outcomes": "学会区分观察事实与个人推断，并比较不同受访者的观点。",
        "tips": "先试访再完善提纲；记录观察时段与天气，避免把单次观察概括为长期趋势。",
        "themes": ("ecology", "community"),
        "featured_rank": 20,
        "reason": "展示从观察到访谈，再到反思研究局限的完整路径。",
        "stage": "沿湿地步道开展定点观察",
        "challenge": "不同时间的观察结果不一致。",
        "response": "增加观察时段，并在记录中注明天气和路线。",
        "resource": "demo-resources/wetland-report.md",
    },
    {
        "slug": "demo-heritage-walk",
        "year": 2025,
        "title": "【示例】老街建筑与地方记忆",
        "location": "示例历史街区",
        "summary": "结合建筑速写和口述访谈，整理老街公共空间的变化与居民记忆。",
        "question": "老街建筑的用途变化如何影响居民的地方记忆？",
        "methods": "建筑观察、经同意的口述访谈、公开资料对照；内容为虚构示例。",
        "outcomes": "理解个人记忆的差异，学会将访谈材料与公开资料交叉核对。",
        "tips": "先征求访谈和拍摄同意；公开展示时使用昵称，并区分回忆与可核实事实。",
        "themes": ("culture", "heritage", "architecture"),
        "featured_rank": 10,
        "reason": "将建筑观察与居民叙事结合，提供可借鉴的访谈准备方法。",
        "stage": "比较街区用途变化",
        "challenge": "受访者对同一建筑的回忆存在差异。",
        "response": "保留不同叙述，并标注哪些细节仍待进一步核实。",
        "resource": "demo-resources/heritage-report.md",
    },
    {
        "slug": "demo-farm-learning",
        "year": 2024,
        "title": "【示例】从农田到餐桌的学习路线",
        "location": "示例社区农园",
        "summary": "记录农作物种植流程，探索农园活动如何帮助学生理解食物来源。",
        "question": "哪些农园活动能帮助学生理解食物生产中的劳动？",
        "methods": "流程观察、活动日志、匿名反馈；本项目为虚构教学示例。",
        "outcomes": "学会把宽泛问题拆分为可观察的活动，并辨别反馈能支持的结论范围。",
        "tips": "安排可重复的观察任务；如需汇总参与人数，先约定时间范围与去重方式。",
        "themes": ("agriculture", "community"),
        "featured_rank": 0,
        "reason": None,
        "stage": "绘制农园劳动流程",
        "challenge": "一次访问无法观察完整的种植周期。",
        "response": "在成果中说明观察时段，后续结合公开资料补充并标明来源。",
        "resource": "demo-resources/farm-report.md",
    },
)


def seed_database(session: Session) -> dict[str, int]:
    """Insert missing catalog/demo records; never overwrite existing content or commit."""
    for slug, name in THEMES:
        if session.scalar(select(Theme).where(Theme.slug == slug)) is None:
            session.add(Theme(slug=slug, name=name))
    for code, name in RESOURCE_TYPES:
        if session.scalar(select(ResourceType).where(ResourceType.code == code)) is None:
            session.add(ResourceType(code=code, name=name))
    session.flush()

    themes = {item.slug: item.id for item in session.scalars(select(Theme))}
    report_type = session.scalar(select(ResourceType).where(ResourceType.code == "report"))
    service = ProjectService(session)
    inserted = 0
    for sample in SAMPLES:
        if session.scalar(select(Project.id).where(Project.slug == sample["slug"])) is not None:
            continue
        name = f"{sample['year']} 年暑期（示例）"
        cohort = session.scalar(select(Cohort).where(Cohort.name == name))
        if cohort is None:
            cohort = Cohort(name=name, year=sample["year"], description="用于演示的虚构届次。")
            session.add(cohort)
            session.flush()
        project = service.create_draft(
            cohort_id=cohort.id,
            title=sample["title"],
            slug=sample["slug"],
            summary=sample["summary"],
            research_question=sample["question"],
            research_methods=sample["methods"],
            learning_outcomes=sample["outcomes"],
            practical_tips=sample["tips"],
            location=sample["location"],
            team_name="示例调研小组",
            theme_ids=[themes[slug] for slug in sample["themes"]],
            is_demo=True,
            is_featured=sample["reason"] is not None,
            featured_reason=sample["reason"],
            featured_rank=sample["featured_rank"],
        )
        service.add_member(project.id, display_name="示例学生", role="学生", sort_order=0)
        service.add_member(project.id, display_name="示例教师", role="指导教师", sort_order=1)
        service.add_journey_entry(
            project.id,
            title="准备研究问题与记录表",
            description=sample["methods"],
            reflection="先进行小范围试行，再调整研究问题和记录方法。",
            sort_order=0,
        )
        stage = service.add_journey_entry(
            project.id,
            title=sample["stage"],
            description=sample["summary"],
            challenges=sample["challenge"],
            responses=sample["response"],
            reflection=sample["outcomes"],
            occurred_on=date(sample["year"], 7, 15),
            sort_order=1,
        )
        service.add_resource(
            project.id,
            resource_type_id=report_type.id,
            title="示例调研报告",
            resource_url=sample["resource"],
            journey_entry_id=stage.id,
            description="仓库内的可读示例文件；内容不构成真实项目证据。",
            mime_type="text/markdown",
        )
        service.add_impact(
            project.id,
            category="educational",
            title="【示例】形成有依据的研究反思",
            description=sample["outcomes"],
            evidence_reference="虚构示例，无真实影响结论。",
        )
        service.publish(project.id)
        inserted += 1

    return {
        "inserted_projects": inserted,
        "total_projects": session.scalar(select(func.count()).select_from(Project)) or 0,
    }


def main() -> None:
    engine = make_engine()
    try:
        with transaction(make_session_factory(engine)) as session:
            result = seed_database(session)
        print(f"Seed complete: {result}. All seeded projects are demo content.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
