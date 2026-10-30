# 通用项目清单

核心后端只接收此格式，不登记具体项目或 ZIP 包。第三方包可在应用外转换为清单，
也可直接通过 `ProjectService` 写入。示例包旧格式的转换器位于 `examples/`。

## 最小清单

```json
{
  "schema_version": 1,
  "dataset": {"key": "my-research", "version": 1},
  "project": {
    "slug": "my-first-project",
    "title": "我的研究",
    "summary": "研究内容的一句话介绍",
    "is_demo": false
  }
}
```

`schema_version` 是清单格式版本；`dataset.version` 是该项目资料的修订版本。
`dataset.key` 自行命名，可使用英文字母、数字、短横线和下划线，以字母或数字开头。
它不需要加入后端注册表。一个清单描述一个项目；同一数据来源可为多个项目使用相同的 key。
项目 `slug` 全局唯一且作为导入定位依据；导入更新时保持不变。

可省略 `themes`、`questions`、`stages`、`resources`、`sections`，它们默认为空数组。
新项目默认 `status='draft'`，公开查询不会返回草稿。导入不会自动设为精选或填写推荐理由。
`is_demo` 未指定时沿用模型默认值 `true`；真实项目应显式设置为 `false`。

## 可发布的完整示例

以下内容不依赖本仓库素材。资源可以使用外部 URL，因此不需要本地文件。

```json
{
  "schema_version": 1,
  "dataset": {"key": "garden-observation", "version": 1},
  "project": {
    "slug": "garden-temperature",
    "title": "花园温度观察",
    "summary": "比较两处测量结果",
    "status": "published",
    "is_demo": false,
    "research_methods": "定时测量",
    "learning_outcomes": "记录测量误差",
    "practical_tips": "统一仪器和测量时间"
  },
  "themes": [{"slug": "field-measurement", "name": "实地测量"}],
  "questions": [{"key": "temperature", "question": "两处温度有何差异？"}],
  "stages": [{"key": "measurement", "title": "采样", "description": "统一测量条件"}],
  "resources": [{
    "key": "readings", "title": "测量记录",
    "type": {"code": "instrument-log", "name": "仪器记录"},
    "url": "https://example.org/readings.csv", "mime_type": "text/csv",
    "usage_role": "output", "stage_key": "measurement"
  }],
  "sections": [{
    "key": "findings", "kind": "other", "title": "观察发现",
    "body": "测量条件影响结果。",
    "media": [{"resource_key": "readings", "role": "attachment"}]
  }]
}
```

示例 URL 仅说明字段格式，实际使用时替换为自己的资源地址。
发布校验要求研究问题、方法、收获、建议，以及至少一个主题、研究步骤和成果资源。
未单独填写 `project.research_question` 时，会使用 `questions` 中的问题拼接生成。
这些是平台的业务规则；步骤数量和名称、段落数量和排列、是否配音均由项目决定。

## 字段约定

| 对象 | 主要字段 |
| --- | --- |
| `project` | 必填 `slug/title/summary`；可选字段见 `services.EDITABLE_FIELDS`，另可指定 `status`、带时区的 `published_at`、`cover_resource_key` |
| `themes[]` | `slug/name` 必填，可选 `description`；不存在的目录项自动创建 |
| `questions[]` | `key/question` 必填，可选 `topic/sort_order` |
| `stages[]` | `key/title` 必填，可选 `description/method_tags/challenges/responses/reflection/occurred_on/sort_order`；日期为 `YYYY-MM-DD` |
| `resources[]` | `key/title/type` 必填；提供本地 `filename` 或远程 `url`，其他媒体元数据见 [API.md](API.md) |
| `sections[]` | `key/title` 必填，可选 `kind/body/stage_key/sort_order/media` |
| `sections[].media[]` | `resource_key` 必填，可选 `role/is_optional/sort_order` |

每种记录的 `key` 在项目内稳定且唯一，修改正文或排序时保留 key，避免新增重复记录。
各数组的 `sort_order` 未提供时取数组下标，显式值必须为非负整数。
`type` 为 `{code, name}`，可自行扩展类型，不需要改枚举或迁移。
`usage_role` 为 `output/process/reference`，默认 `output`。
媒体可附 `content_text` 和 `{columns: [...], rows: [[...]]}` 格式的 `structured_data`；单元格为字符串。

段落 `kind` 支持 `opening/journey/output/learning/other`，默认 `other`；`key` 自行命名。
`journey` 必须通过 `stage_key` 关联本清单中的步骤。其他段落可以关联步骤，也可以没有步骤。
媒体角色为 `illustration/narration/attachment`，默认 `attachment`；同一资源可由多个段落引用。
`narration` 只要求资源 MIME 为音频或视频，不要求时长已知、台词等于段落正文，也不要求使用 AI。
所有段落都可以没有媒体，清单也可以完全没有段落。

## 本地文件与导入

在 `backend/` 中执行：

```bash
uv run --no-sync python -m dream_journey.import_manifest \
  --manifest /path/to/project.json \
  --media-dir media/my-research \
  --media-url /media/my-research
```

本地资源用 `filename: "subdir/photo.jpg"`，相对于 `--media-dir`。
导入器验证文件、计算大小和 SHA-256，并检查提供的摘要、正文与表格是否一致；
UTF-8 文本正文及 CSV 表格可以自动提取。文件路径不能逃出指定目录。
**导入器不复制文件**；先将文件放入自己的媒体目录，再执行导入。

省略参数时，媒体目录为清单旁的 `media/`，URL 前缀为 `/media/{dataset.key}`。
例如文件位于 `backend/media/my-research/` 时，服务用 `--media-root media`，
导入的 URL 前缀用 `/media/my-research`，两者需要对应。
远程 URL 不会被下载或探测，可使用 HTTP(S) 或以 `/` 开头的站内绝对路径。
自定义站内路径可交给外部媒体服务，或通过 `--mount /prefix=directory` 显式挂载。

命令先执行数据库迁移，再在一个事务中写入项目及其关联。错误会回滚全部数据库变更。
相同规范化内容摘要重复导入会跳过，以保留后续人工编辑；更高数据版本可原位更新，禁止低版本覆盖高版本。
同一清单的变更即使未提升版本也会更新。未列出的已有记录保留，不将清单视为删除指令；
列出的段落会用其 `media` 替换该段原有媒体关联。
已有项目省略 `status` 时保留当前状态，新项目默认草稿。
