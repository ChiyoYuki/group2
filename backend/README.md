# Dream Journey 后端

Python 3.11+、SQLAlchemy 2.0、Alembic；支持 PostgreSQL 和本地 SQLite。
核心 `dream_journey/` 提供数据模型、事务服务、通用清单导入及只读 HTTP API，独立于具体数据集。
项目来源、步骤数量、资源类型和段落安排均由数据提供；服务启动只执行显式请求的迁移。

## 启动

从仓库根目录执行：

```bash
cd backend
uv sync --locked --extra dev
uv run --no-sync python -m dream_journey.web --migrate
```

API 地址为 http://127.0.0.1:8000/api/v1/health 。空库可以直接运行，列表为空。
命令不自动导入示例。已有数据库执行迁移后保留原数据。
需要最小联调页时加 `--static-dir ../frontend`，然后访问 http://127.0.0.1:8000 。
独立前端使用 [API.md](API.md)，可加 `--cors-origin http://localhost:5173`。

所有命令建议在 `backend/` 下执行。`DATABASE_URL` 可指定数据库，命令行导入和 Alembic
默认使用当前目录的 `dream_journey.db`；HTTP 服务默认使用 `backend/dream_journey.db`。
`.env.example` 仅为模板，程序不会自动加载 `.env`。

## 导入自己的数据

清单格式、完整示例和媒体字段见 [MANIFEST.md](MANIFEST.md)。
新增数据集无需改代码或在核心登记名称：

```bash
uv run --no-sync python -m dream_journey.import_manifest \
  --manifest /path/to/project.json \
  --media-dir media/my-research --media-url /media/my-research
```

导入器先验证本地文件的摘要、正文和 CSV 表格，再在同一事务内更新数据。
它不复制文件；请先将媒体放入指定目录。也可只使用远程媒体 URL。
本地服务 `--media-root media` 对应 `/media/`，默认根目录可通过 `MEDIA_ROOT` 设置。
其他媒体目录可显式设置 `--mount /files=/path/to/files`。

新项目默认草稿，显式设置 `project.status='published'` 后通过通用发布校验才会公开。
资源类型按清单中的 `{code, name}` 创建，不依赖预置目录。段落可以为空、没有音频或只有附件。
相同内容重复导入跳过；修订更新保留稳定 key 对应的 ID，未列出的人工记录保留，失败整体回滚。

## 可选示例

素材包专用代码、旧格式转换和种子数据均在 `examples/`，核心不引用它。
两份原有示例清单和媒体保留，可显式导入：

```bash
uv run --no-sync python -m examples.import_packages --dataset all
uv run --no-sync python -m dream_journey.web --migrate --static-dir ../frontend
```

具体包的重新整理命令、历史示例报告挂载及素材说明见 [examples/README.md](examples/README.md)。
删除这些示例文件不影响核心迁移、启动和导入其他数据。

## PostgreSQL 与迁移

```bash
docker compose up -d --wait
export DATABASE_URL='postgresql+psycopg://dream_journey:dream_journey_dev@localhost:5432/dream_journey'
uv run --no-sync alembic upgrade head
uv run --no-sync python -m dream_journey.web
```

Compose 使用 PostgreSQL 18 和命名卷，开发账号可通过 `POSTGRES_PASSWORD`、`POSTGRES_PORT` 配置。
也可对空 PostgreSQL 数据库依次执行 `sql/001_initial.sql` 至 `sql/005_question_import_identity.sql`，
与 Alembic 二选一初始化；SQL 包含迁移版本记录，后续统一用 Alembic 升级。

当前共十二张业务表。迁移 `0001` 建立项目、目录和关系；`0002` 加入问题、来源及媒体元数据，
并允许未知届次；`0003` 加入有序段落、媒体关联与数据修订记录；`0004` 加入短标题和文本表格；
`0005` 为问题加入项目内唯一、可空的 `import_key`，避免问题改写或重排时重复创建。

SQLite 批量重建表时暂时关闭外键动作，完成后检查全部外键并恢复，避免误删关联数据。
程序化调用迁移使用未开启写事务的 `engine.connect()`。
回退至 `0001` 前需为未知届次补充已确认数据；不会自动编造届次。

## 模块边界

| 模块 | 职责 |
| --- | --- |
| `dream_journey/models.py`、`types.py` | 通用表结构、约束、UTC 类型 |
| `database.py`、`repositories.py` | 引擎、事务、查询、筛选、分页和真实影响统计 |
| `services.py` | 草稿维护、子记录、发布校验、归档、删除 |
| `datasets.py`、`manifests.py` | 显式导入上下文、通用格式和本地文件校验 |
| `dataset_import.py`、`import_manifest.py` | 按稳定标识事务更新、命令行导入 |
| `serializers.py`、`web.py` | JSON 契约、HTTP、媒体 Range 和可选静态目录 |
| `examples/` | 具体 ZIP 包适配、示例注册和种子数据；依赖核心 |
| `tests/core/` | 不依赖随附数据的默认测试 |
| `tests/examples/` | 可选素材包与联调页兼容测试 |

## 应用内读写

应用通过 `make_session_factory` 和 `transaction(factory)` 管理事务，
`ProjectService` 方法执行 flush，由外层统一提交。可使用 ORM 维护 `Theme`、`Cohort`、
`ResourceType`，不需要种子数据。示例：

```python
from dream_journey.database import make_engine, make_session_factory, transaction
from dream_journey.services import ProjectService

engine = make_engine()
try:
    with transaction(make_session_factory(engine)) as session:
        project = ProjectService(session).create_draft(
            title="我的研究",
            slug="my-project",
            summary="研究简介",
            is_demo=False,
        )
finally:
    engine.dispose()
```

发布要求标题、简介、研究问题、方法、收获及建议非空，至少有一个主题、研究步骤和成果。
精选需推荐理由；真实影响记录需证据出处。显式发布时间须带时区，会归一为 UTC。
已发布项目先归档再修改；重新发布默认保留首次发布时间。
PostgreSQL 服务写入使用项目行锁；直接 ORM/SQL 写入需遵守相同约定。

读取使用 `ProjectRepository.list_public()`、`get_public_by_slug()`；仅返回公开项目。
详情批量加载关联，脱离会话后可用 `serializers.project_detail()` 序列化。
真实影响统计仅包含已发布且非示例的项目，不自动累加可能重叠的参与人数。
跨项目步骤与媒体关联受复合外键保护，项目删除级联清除子记录，目录删除受限制。
数据库仅管理文件元数据，文件生命周期由应用或对象存储管理。

## 验证

```bash
uv run --no-sync pytest -q                  # 核心测试，无需示例素材
uv run --no-sync pytest -q tests            # 包含可选示例集成测试
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync alembic check
```

测试通过真实迁移创建临时 SQLite 数据库。核心测试还将代码和迁移复制到无示例的独立目录，
验证空库初始化及新清单导入。HTTP 测试需要本机临时端口。
使用 `TEST_DATABASE_URL=postgresql+psycopg://...` 可在独立随机 schema 中运行 PostgreSQL 测试，
完成后清理，测试账号需有创建 schema 的权限。

新增结构变化应新增迁移，不改已执行的历史迁移。离线导出本次 PostgreSQL SQL：

```bash
DATABASE_URL='postgresql+psycopg://unused:unused@localhost/dream_journey' \
  uv run --no-sync alembic upgrade 0004:0005 --sql > sql/005_question_import_identity.sql
```
