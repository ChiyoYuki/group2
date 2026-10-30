# Dream Journey 项目探索平台

后端提供用户注册登录、项目发布、通用数据导入、媒体关联及公开查询，独立于具体数据集。

- [问题背景](Problem.md) · [功能需求](Requirements.md) · [数据库设计](DatabaseDesign.md)
- [后端说明](backend/README.md) · [通用导入格式](backend/MANIFEST.md) · [API](backend/API.md)
- [可选示例数据](backend/examples/README.md)

## 启动

```bash
cd backend
uv sync --locked --extra dev
uv run --no-sync python -m dream_journey.web --migrate --static-dir static --media-root media
```

打开 http://127.0.0.1:8000 。内置页面支持注册、登录、附件上传和项目发布，提交后自动公开。
API 健康检查地址为 http://127.0.0.1:8000/api/v1/health 。
默认使用 SQLite，`DATABASE_URL` 可切换 PostgreSQL。启动不导入数据，已有项目保留。

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
