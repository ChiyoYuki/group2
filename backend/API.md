# 前端接入接口

服务默认地址：`http://127.0.0.1:8000`。接口前缀为 `/api/v1`，JSON 使用 UTF-8。
原 `/api/...` 路径继续作为兼容别名。当前为只读接口，数据通过导入命令维护。

API 版本为 `1`，数据库迁移版本为 `0005`。项目的 `dataset.version` 由其数据来源自行指定，
分别表示接口约定、数据库结构和资料修订。服务不登记数据集名称，也不在启动时导入内容。
通用导入格式见 [MANIFEST.md](MANIFEST.md)，素材包示例见 [examples/README.md](examples/README.md)。

## 接口列表

| 方法与路径 | 返回内容 |
| --- | --- |
| `GET /api/v1/health` | 服务状态、API 版本、数据库迁移版本 |
| `GET /api/v1/catalog` | 主题、届次及成果类型目录 |
| `GET /api/v1/projects` | 公开项目的筛选、分页列表 |
| `GET /api/v1/projects/{slug}` | 项目详情，含问题、研究历程、资源及有序图文配音段落 |
| `GET /api/v1/projects/{slug}/sections` | 只返回 `project_id`、`slug` 和 `sections` |
| `GET /api/v1/overview` | 公开项目数及排除示例后的真实影响统计 |
| `GET /media/{path}` | 媒体内容，支持单段 HTTP Range |

支持 `HEAD` 与 CORS `OPTIONS`。项目列表和详情均只返回 `status='published'` 的项目。

列表参数：

| 参数 | 类型与默认值 | 说明 |
| --- | --- | --- |
| `q` | 字符串，可省略 | 匹配标题、简介或研究问题；`%`、`_` 按字面匹配 |
| `theme` | 主题 slug，可省略 | 如 `traditional-crafts` |
| `cohort` | 届次 UUID，可省略 | 缺少实际届次的项目字段为 `null` |
| `dataset` | 数据集 key，可省略 | 任意已导入的 key；未知值返回空列表，不传返回所有数据集 |
| `featured` | `true` / `false`，默认 `false` | 只看精选 |
| `page` | 正整数，默认 `1` | 页码 |
| `page_size` | `1`—`100`，默认 `12` | 每页数量 |

列表响应例如 `{ "items": [...], "total": 2, "page": 1, "page_size": 12 }`，数量随已导入项目变化。
普通列表按发布时间、ID 降序；精选列表优先按精选排序值降序。

## 图文配音段落

新前端应按 `sections` 返回顺序渲染，按 `section.key` 标识内容。
不要通过音频文件名推断步骤，也不要将配音编号直接作为过程编号。

段落数量、key 和顺序由项目内容决定，不固定为开场或七个步骤。
`sections` 可以为空，段落可以只有正文、只有附件或含多个媒体。

每个段落包含：

```json
{
  "id": "段落UUID",
  "key": "findings",
  "kind": "other",
  "title": "观察发现",
  "body": "测量条件会影响结果。",
  "sort_order": 0,
  "journey_entry_id": null,
  "media": [
    {
      "role": "illustration",
      "is_optional": false,
      "sort_order": 0,
      "resource": {
        "id": "图片UUID",
        "resource_url": "/media/my-research/comparison.png",
        "mime_type": "image/png",
        "alt_text": "两处测量点的对比图"
      }
    },
    {
      "role": "narration",
      "is_optional": false,
      "sort_order": 1,
      "resource": {
        "id": "音频UUID",
        "resource_url": "/media/my-research/interview.mp3",
        "mime_type": "audio/mpeg",
        "duration_seconds": 20.016,
        "transcript": "测量条件会影响结果。",
        "is_ai_generated": true,
        "generation_note": "AI合成声音，不是真实学生录音。"
      }
    }
  ]
}
```

上例省略了其他资源元数据。`media.role` 为 `illustration`、`narration` 或 `attachment`。
`is_optional` 表示可选素材。`kind` 为 `opening/journey/output/learning/other`，只表达语义类别，
不限制 key 的命名或展示顺序。`journey` 段落必须关联本项目步骤，其他类别可选。

同一资源可以由多个段落引用，`resource.id` 相同；不要重复存储或按文件名推断配对。
配音台词、时长可为空，台词也可以与正文不同。没有段落时仍可用 `journey_entries`、`resources` 展示。
项目卡片及详情含可空 `short_title`，完整标题为 `title`。

## 资源字段

项目详情的 `resources` 是完整资源列表；段落中的 `resource` 使用相同结构。

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `id`、`title`、`description` | 字符串 / 可空文本 | 资源标识与说明 |
| `resource_url`、`preview_url` | 路径或 URL / 可空 | 原文件与预览地址 |
| `mime_type` | 字符串 / 可空 | 按 `image/`、`audio/`、`video/` 选择展示方式 |
| `type` | `{code, name}` | 成果类型，与文件格式分开 |
| `usage_role` | `output` / `process` / `reference` | 最终成果、过程素材、外部参考 |
| `caption`、`alt_text` | 文本 / 可空 | 图注与替代文本 |
| `content_text` | 文本 / `null` | Markdown 或 CSV 的 UTF-8 正文；不会返回预渲染 HTML |
| `structured_data` | 对象 / `null` | CSV 的 `{columns: [表头...], rows: [[单元格...], ...]}` |
| `duration_seconds` | 数值 / `null` | 时长，单位秒 |
| `transcript` | 文本 / `null` | 音频或视频台词，不要求与段落正文相同 |
| `is_ai_generated`、`generation_note` | 布尔值、文本 / 可空 | 合成媒体说明；展示时应保留 AI 标识 |
| `file_size_bytes`、`width`、`height` | 整数 / `null` | 大小及图像尺寸 |
| `sha256` | 字符串 / `null` | 原始文件的 SHA-256 |
| `source_name`、`source_url`、`original_url` | 文本 / 可空 | 来源及原始地址 |
| `creator_credit`、`original_activity`、`provenance_note` | 文本 / 可空 | 摄影署名、原活动和素材性质 |
| `rights_status`、`rights_note` | 字符串、文本 / 可空 | 许可状态与说明 |
| `journey_entry_id`、`sort_order`、`import_key` | UUID / `null`、整数、可空字符串 | 关联、排序与导入标识 |

资源相对路径需相对于**后端服务地址**解析，例如 `new URL(resource.resource_url, API_ORIGIN)`，
不能默认相对于另一个前端的站点地址解析。

姓名、学校、日期、届次等未知信息返回空值或空数组，不应从图片中的署名或日期补推。
`content_kind`、`content_notice`、来源、权利状态及 `is_ai_generated` 由项目资料指定，
前端按返回值展示，不假设全部项目都是示例或全部媒体都是 AI 生成。
`is_demo=true` 的项目不计入真实影响统计。`type` 是业务成果类型，来自数据库目录，可以新增，
不要将其写成固定类型列表；文件展示方式应结合 `mime_type` 选择。

表格所有单元格均为字符串，保留来源中的顺序与措辞。示例：

```json
{
  "columns": ["测量点", "时间", "温度"],
  "rows": [["东侧", "09:00", "23"]]
}
```

## 音频读取

按每个资源的 MIME 选择 `<audio>` 或 `<video>`。不假设文件数量、总时长或固定配音编号。

媒体响应提供 `Accept-Ranges: bytes`。例如 `Range: bytes=0-1023` 返回 `206`、
`Content-Range: bytes 0-1023/总字节数` 及对应二进制内容；支持开放末尾和后缀范围。
不支持多段 Range；无效或不可满足的范围返回 `416` 和 `Content-Range: bytes */总字节数`。
`HEAD` 返回完整文件长度和 MIME，不返回文件内容。

## 跨域配置

同源联调页无需跨域配置。独立前端可通过启动参数或环境变量设置允许的 Origin：

```bash
uv run --no-sync python -m dream_journey.web --migrate \
  --cors-origin http://localhost:5173 \
  --cors-origin http://127.0.0.1:5173
```

或设置 `CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`。
Origin 包含协议、主机和端口。配置适用于 JSON 和媒体响应，允许 `GET, HEAD, OPTIONS`，
允许请求 `Range`，并暴露 `Content-Range`、`Accept-Ranges`、`Content-Length`。
未配置时仅使用同源访问；未允许的预检请求返回 `403`。

## 错误响应

API 错误为 `{ "error": "错误说明" }`：参数不正确 `400`，项目不存在或未公开 `404`，
数据库不可用 `503`。媒体缺失返回 `404`，范围错误返回 `416`。

默认只提供 API 与配置目录中的媒体，不绑定测试前端。需要联调页时加 `--static-dir ../frontend`。
媒体目录可通过 `--media-root` 或 `MEDIA_ROOT` 设置；外部对象存储 URL 直接返回给前端。
