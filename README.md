# Dream Journey 项目探索平台

后端提供项目档案、通用数据导入、媒体关联及公开查询，独立于具体数据集。
`frontend/` 是可替换的最小联调页，正式前端可独立接入。

- [问题背景](Problem.md) · [功能需求](Requirements.md) · [数据库设计](DatabaseDesign.md)
- [后端说明](backend/README.md) · [通用导入格式](backend/MANIFEST.md) · [API](backend/API.md)
- [最小联调页](frontend/README.md) · [可选示例数据](backend/examples/README.md)

## 启动

```bash
cd backend
uv sync --locked --extra dev
uv run --no-sync python -m dream_journey.web --migrate --static-dir ../frontend
```

访问 http://127.0.0.1:8000 。默认 SQLite，`DATABASE_URL` 可切换 PostgreSQL。
启动不导入数据，已有项目保留；新库列表为空。纯 API 服务省略 `--static-dir` 即可。

## 导入数据

新增项目使用 [通用清单](backend/MANIFEST.md)，无需修改后端：

```bash
uv run --no-sync python -m dream_journey.import_manifest \
  --manifest /path/to/project.json \
  --media-dir media/my-research --media-url /media/my-research
```

新项目默认草稿。步骤、段落、媒体与资源类型由清单定义，不限制为当前示例的七步或配音布局。

随附苗族文化与丹噶尔古城资料仅作为可选示例，专用适配器在 `backend/examples/`：

```bash
uv run --no-sync python -m examples.import_packages --dataset all
```

示例文案、来源与 AI 属性保留；相同内容重复导入跳过，修订可保留稳定记录 ID。
重新整理原 ZIP、历史演示项目和附加文件挂载见 [示例说明](backend/examples/README.md)。

## 独立前端

规范接口 `/api/v1` 返回项目、任意数量的有序段落及媒体关系，支持文本、表格、图片、音频和视频元数据。
媒体支持 HTTP Range。不同端口的前端加 `--cors-origin http://localhost:5173`。
字段、错误码、筛选及跨域配置见 [接口文档](backend/API.md)。
