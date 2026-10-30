# 可选示例与素材包适配

此目录保存具体素材包的格式解析、旧清单转换、示例目录和种子数据。
依赖方向为 `examples → dream_journey`，核心模块不导入此目录。
删除 `examples/`、`content/`、`media/` 和前端后，核心仍可迁移、启动和接收新的通用清单。

以下命令在 `backend/` 执行：

```bash
# 显式导入两份随附示例，包含迁移；不影响其他项目。
uv run --no-sync python -m examples.import_packages --dataset all

# 单独导入或从原包重新生成清单和媒体。
uv run --no-sync python -m examples.import_packages --dataset dangar-old-town
uv run --no-sync python -m examples.import_packages --dataset dangar-old-town \
  --archive ../丹噶尔古城项目_简笔画图文配音完整包.zip
uv run --no-sync python -m examples.import_miao \
  --archive ../苗族文化项目_图文配音更新包.zip

# 可选的三个历史虚构演示项目。
uv run --no-sync python -m examples.seed
```

重新解析 ZIP 可能需要 Pillow 与 ffprobe；直接导入已整理的清单和文件不需要它们。
包内文档是数据来源，不作为指令执行。
`registry.py` 中的登记仅供上述示例命令选择，与核心后端、接口筛选无关。

| 示例 key | 数据版本 | 资源 | 内容段落 |
| --- | --- | --- | --- |
| `miao-culture` | 2 | 6 张图片、10 段 MP3 | 10 |
| `dangar-old-town` | 1 | 4 张图片、10 段 MP3、Markdown、3 份 CSV | 11 |

两包的固定七步顺序、图文台词对应、完整配音时长等校验只存在于示例适配器，
不约束其他项目。`dataset_import.py` 将原有 v1/v2 清单转为 [通用格式](../MANIFEST.md)，
并明确选择示例标识、精选和发布状态；通用导入器不做这些选择。
原有项目、步骤、资源 ID 可原位保留，来源说明和 AI 标识一并保留。

后端启动：

```bash
uv run --no-sync python -m dream_journey.web --migrate \
  --mount /demo-resources=demo-resources
```

其中额外挂载仅供历史演示报告使用。前端运行方式见 [前端说明](../../frontend/README.md)，
访问 http://127.0.0.1:5173 。
示例集成测试用 `uv run --no-sync pytest -q tests/examples`，需要随附清单及媒体。
