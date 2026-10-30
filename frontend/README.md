# 梦想足迹前端

参考 `origin/lei` 的 `f2aa311` 实现，沿用 React / Vite、中国地图资源以及深蓝与暖金色视觉，
将写死的项目与占位详情替换为当前后端 API。前端不包含项目数据集，主题、届次、段落及媒体均从接口读取。

## 本地启动

终端一，从仓库根目录启动后端：

```bash
cd backend
uv sync --locked --extra dev
uv run --no-sync python -m dream_journey.web --migrate --mount /demo-resources=demo-resources
```

终端二，从仓库根目录启动前端（Node.js 22.12+ 或 24）：

```bash
cd frontend
npm ci
npm run dev
```

打开 http://127.0.0.1:5173 。Vite 将 `/api`、`/media`、`/demo-resources` 转发至
`http://127.0.0.1:8000`，默认无需额外设置跨域。已有项目直接显示；空库会显示空状态。
修改代理地址可在 `.env.local` 设置 `API_PROXY_TARGET=http://127.0.0.1:其他端口`。

## 页面

- `/`：地图、项目推荐、届次时间轴、主题入口、价值概览。
- `/projects`：关键词、主题、届次与精选筛选，卡片与时间轴视图，分批展开。
- `/themes`、`/impact`：动态主题目录及基于 API 的统计。
- `/project/:slug`：研究问题、方法、有序段落、图片与音视频、文本与 CSV、实践建议和证据。
- `/contribute`：使用现有注册、登录及项目上传接口；单个附件最大 8 MB，发布前显示立即公开提示。

地图仅依据明确的 `location` 中的省级名称展示示意位置，不从项目标题或素材包推断经纬度。
地点或届次缺失时明确标为待补充。示例项目保留标识，真实影响统计直接使用后端口径。
Markdown 以纯文本显示；台词、来源、AI 属性和可选素材说明保留。
认证会话保存在当前标签页的 `sessionStorage` 中，退出账号会清除。

## 构建与部署

```bash
npm run build
```

输出为 `dist/`。部署时由静态服务器提供前端，并将所有前端路由回退至 `index.html`，
同时代理 `/api` 与媒体路径到后端。Python 后端的可选静态目录仅供旧测试页面使用，不负责提供 Vite 构建资源。

如前后端分域，在构建前设置 `VITE_API_BASE_URL=https://api.example.org`（后端站点根地址，
不包含 `/api/v1`），并通过后端 `--cors-origin` 放行前端 Origin。
媒体 URL 始终相对于后端地址解析。接口见 [API.md](../backend/API.md)。
