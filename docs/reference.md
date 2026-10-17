# 配置与命名空间参考

## 模板上下文

MP 原有上下文继续可用，例如 `title`、`en_title`、`original_title`、`year`、`season`、`season_episode`、`episode_title`、`fileExt`。来源和具体值由 MP 决定。插件提供 `titles(...)` 标题合并函数，并将 `part` 过滤成带编号的分段标记。

插件新增 `ffprobe` 字典，缺失字段通常为空字符串：

| 变量 | 含义 / 示例 |
| --- | --- |
| `ffprobe.out` | 按分类 `audio` / `dr` / `extra` 组合的技术参数 |
| `ffprobe.group` | 发行组规范名，联合组如 `GroupA&GroupB` |
| `ffprobe.resolution` | `1080P`、`4K` 等显示分辨率 |
| `ffprobe.edition` | 片源写法，如 `BluRay-Remux` |
| `ffprobe.platform` | 写入 Web 片源的平台后缀，不适用时为空 |
| `ffprobe.source` | 片源及平台，如 `Web-Rip.Netflix` |
| `ffprobe.video_codec` | `AVC`、`HEVC`、`AV1` 等 |
| `ffprobe.bit_depth` | 真实/推导位深，可能为 `8bit`；组合 `video` 不显示 8 bit |
| `ffprobe.video` | 编码及显示位深，如 `HEVC_10bit` |
| `ffprobe.audio_codec` | 选定主音轨的编码 |
| `ffprobe.audio_codecs` | 全部音轨编码去重合并，如 `AAC&FLAC` |
| `ffprobe.channels` | 主音轨声道，如 `5.1`、`7.1` |
| `ffprobe.atmos` | 检出时为 `Atmos`，否则为空 |
| `ffprobe.audio` | 主音轨完整显示，如 `TrueHD_7.1ch.Atmos` |
| `ffprobe.dynamic_range` | 如 `SDR`、`HDR_HDR10`、`HDR_HDR10+`、`DolbyVision_Profile8.1` |
| `ffprobe.extra` | 3D、IMAX、60FPS、120FPS 等额外标签 |
| `ffprobe.subtitle` | 内封字幕语言摘要；只来自实际探测 |
| `ffprobe.fps` | 探测得到的帧率标签 |
| `ffprobe.category` | MP 分类路径 |
| `ffprobe.category_id` | V3 生效或推荐分类 ID |
| `ffprobe.probed` | 得到非空探测字段时为字符串 `1`，否则为空 |

`dynamic_range` 和 `audio` 的原始变量不会因为分类选择省略它们；分类参数只控制 `out` 的拼接。可自行使用这些字段。

## 默认数据

[examples](../examples/README.md) 保存可直接粘贴的默认配置。发布检查会确认它们与代码里的默认值一致。

- 发行组到片源：`组名小写=片源`，追加 `!` 强制覆盖；优先级细节见源文件 `probe.edition_label`。
- 平台：`规范名=别名1,别名2`，技术信息区域优先于 MP 解析值，避免将标题里的平台同名词误认成平台。
- 未知发行组/平台尽量保留可识别的原写法；静态表无法覆盖所有资源。

## 路径处理

`\ : * ? " < > |` 转为全角，`/` 用于分隔目录；多余空白折叠、段尾点及空白清理。空目录段和空标题导致放弃替换。路径超过 `max_length` 后，仅将 `titles(...)` 缩成第一个标题；文件名和技术参数不额外截断。

目录层数以 `/` 数量计算，必须与 MP 配置的重命名模板相同。此行为是配合 MP 媒体目录计算的约束。

## 外部程序与失败行为

使用参数数组运行 ffprobe，不通过 shell。默认超时 30 秒，可配置 5～300 秒；读取失败、超时、无效 JSON 返回探测失败，后续命名使用文件名兜底。

只探测本地可读文件。分类规则解析或任意模板编译失败时，全部分类替换不生效；单个文件渲染失败则保留该文件的 MP 结果。插件不会改变 MP 的整理方式、刮削来源或存储目的地。
