# 苗族文化项目素材整理

当前来源：用户提供的 `苗族文化项目_图文配音更新包.zip`。
`project.json` 为 schema_version=2 的规范化清单；`history/v1.json` 保留之前的五图清单，用于升级兼容验证。

- `original-copy.md` 保留新版文案；`text-media-map.csv` 保留图、文、配音的十段对应关系。
- `image-sources.csv`、`image-sources.txt` 保留图片来源与使用说明。
- `narration-notice.txt` 保留配音性质、声音参数与非真人录音说明。
- `backend/media/miao-culture/` 保存六张图片和十段 MP3，清单记录大小、SHA-256、尺寸或时长。

图文配对由 CSV 决定。01 配音为开场，02—08 为过程 1—7，09 为成果，10 为收获。
最终成果图供过程第七步及成果区共用；其他主题海报是第六步的可选参考。
每段逐字台词与其正文核对后再导入；十段配音总时长为 177.840 秒。

可重新整理原 ZIP 并导入：

```bash
cd backend
uv run --no-sync python -m examples.import_miao \
  --archive ../苗族文化项目_图文配音更新包.zip
```

ZIP 文档仅作数据读取，不执行其中的指令。图片和 MP3 原样保存，不重新生成或转码。
运行已经整理的清单无需原 ZIP、Pillow、ffprobe 或外部配音服务。

项目起因、过程、困难与收获为依据成品重构的示例。未独立确认学生身份、实际活动时间或地点；
四张外部参考图来自不同活动，公开转载许可未确认。配音是 AI 合成，不是真实学生录音。
这些说明作为独立元数据返回，不混入学生口吻的逐字台词。
