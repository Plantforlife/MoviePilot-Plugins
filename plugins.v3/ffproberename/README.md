# FFprobe命名增强

MoviePilot V3 整理命名插件 · ID `FfprobeRename` · 版本 **2.1.0** · 需要 **MP >= 3.1.4**。

## 安装与首次配置

1. 在 MP 插件市场添加 `https://github.com/Plantforlife/MoviePilot-Plugins`，刷新并安装“FFprobe命名增强”。
2. 打开插件设置，确认 **ffprobe 路径**。默认从运行 MP 的环境 `PATH` 查找；Docker 部署需要填容器内路径。
3. 检查“分类命名规则”：默认分类是示例，可按你的分类名称、分类 ID 修改。
4. 检查 MP 自身重命名模板的目录层数：默认插件电影模板为 `标题/文件`，剧集为 `标题/Season/文件`。
5. 启用并保存；先使用 MP 的整理预览核对目标路径，再整理真实文件。

ffprobe 属于 FFmpeg 工具集。可在 MP 运行环境执行 `ffprobe -version` 检查。插件不安装 ffmpeg、不自动下载可执行程序；找不到 ffprobe、文件不可读或探测失败时使用文件名解析信息。

## 它如何工作

在 `TransferRenameBuild` 事件生成 `ffprobe` 命名空间，在 `TransferRename` 事件按分类重新渲染模板。标题、媒体 ID、分类和季集仍由 MP 识别。

优先读取 **本地可访问的视频源文件**。字幕和外挂音轨会寻找同目录内文件名是其前缀的视频，优先最长匹配。远程存储条目、没有源路径的命名预览、不匹配的视频及探测失败使用文件名信息。它不会仅为探测而下载远程媒体。

缓存按路径、文件大小和修改时间区分，最多 512 个条目。重新初始化清空缓存。没有定时扫描任务。

## 配置

| 字段 | 默认值 | 作用 |
| --- | --- | --- |
| 启用插件 `enabled` | 关闭 | 开启命名增强 |
| ffprobe 路径 `ffprobe_path` | 自动查找 | MP 进程可执行的本地路径 |
| 单文件超时 `timeout` | 30 秒 | 限定为 5～300 秒 |
| 主音轨选择 `audio_mode` | `best` | `best` 优先档次高的音轨；`default` 优先默认音轨；优先排除评论音轨，只有评论音轨时使用现有音轨 |
| 分辨率大写 `res_upper` | 开启 | 如 `1080P` |
| 2160p 显示为 4K `res_4k_label` | 开启 | 同时支持 1440p → 2K、4320p → 8K |
| 路径长度上限 `max_length` | 180 | 超出后标题组合只留第一个；0 关闭，无法保证回退后一定低于上限 |
| 分类命名规则 `rules` | 内置规则 | INI 格式；[完整默认值](https://github.com/Plantforlife/MoviePilot-Plugins/blob/main/examples/rules.ini) |
| 英文优先 `prefer_english` | `BanG Dream!` | 任意标题含关键词且有英文标题时使用英文主标题 |
| 发行组映射 `group_map` | 内置表 | 发行组小写名 → 片源写法；末尾 `!` 强制覆盖 |
| 片源写法 `edition_map` | 内置表 | MP / 文件名片源标记 → 统一写法 |
| 已知发行组 `known_groups` | 内置表 | 规范拼写或 `别名=规范名`；不区分大小写 |
| 平台别名 `platforms` | 内置表 | `统一名=别名1,别名2` |

配置修改后由 MP 保存并重新初始化。更新插件不会强制覆盖已经保存的规则；如果需要新的默认规则，从仓库示例复制到配置中。

## 分类模板

```ini
[日番|国漫|其他动画]
audio = all
dr = none
extra = no
template = {{ titles(title, en_title, original_title) }} ({{ year }})/Season {{ season }}/
    {{ title }} - {{ season_episode }} - {{ ffprobe.out }}{% if ffprobe.group %} - {{ ffprobe.group }}{% endif %}{% if part %}-{{ part }}{% endif %}{{ fileExt }}
```

节名可以是分类 ID、`类型/分类路径` 或分类路径，按这个顺序匹配。`|` 让多个分类共用一套规则。没有匹配项就保留 MP 原来的结果。

- `audio = main`：主音轨、声道及 Atmos；`all`：所有音轨编码去重合并，不带声道。
- `dr = none`：不写动态范围；`hdr`：写 HDR / Dolby Vision，省略 SDR；`all`：同时写 SDR。
- `extra = yes/no`：是否写 3D、IMAX、60FPS、120FPS。
- 模板续行必须缩进；续行首尾空白去掉后直接拼接，需要的空格写在行内。
- `titles(a, b, c)` 使用 ` _ ` 合并非空标题，忽略大小写、空白及全角半角去重。
- `part` 使用 MP 识别出的编号分段，支持 `Part1`、`PartB`、`CD2`、`DVD1`、`Disc 2` 等；单独的 `DVD`、`CD`、`PART` 不写入结果。

**插件模板和 MP 自身模板的目录层数必须相同。** MP 使用原模板的层数计算媒体目录；不一致时插件拒绝替换并写日志。

## 默认分类行为

| 分类 | 目录标题 | 音轨 | 动态范围 | 额外标签 |
| --- | --- | --- | --- | --- |
| 日番、国漫、其他动画 | 中文 / 英文 / 原文去重合并 | 全部编码 | 不写 | 不写 |
| 华语电影、外语电影、电影/未分类 | 中文 / 英文 | 主音轨 | 含 SDR | 写 |
| 动画电影 | 中文 / 原文 | 主音轨 | 只写 HDR / DV | 写 |
| 国产剧、欧美剧、纪录片、综艺、儿童、电视剧/未分类 | 中文 / 英文 | 主音轨 | 只写 HDR / DV | 写 |
| 亚洲剧 | 中文 / 原文 | 主音轨 | 只写 HDR / DV | 写 |

## 变量与默认约定

常用变量：`ffprobe.out`（组合技术参数）、`ffprobe.group`、`ffprobe.resolution`、`ffprobe.source`、`ffprobe.video`、`ffprobe.audio`、`ffprobe.audio_codecs`、`ffprobe.dynamic_range`、`ffprobe.subtitle`。完整字段见 [参考文档](https://github.com/Plantforlife/MoviePilot-Plugins/blob/main/docs/reference.md)。

默认统一方式是这套命名规则的选择，不代表对发行方式的独立鉴定：

- `WEB-DL` / `WebRip` 默认合并写 `Web-Rip`，平台后缀如 `.Netflix` 只放在 Web 片源后。
- 蓝光文件未标明 Remux 时写 `BluRay-Rip`；明确 Remux 写 `BluRay-Remux`；源目录含 `BDMV` 时写 `BluRay`。`DVD` / `HDTV` 默认写 `DVD-Rip` / `HDTV-Rip`。
- 视频显示编码，10 / 12 bit 显示位深；8 bit 不写进组合编码名。
- 音频区分 DTS、DTS-HD HRA、DTS-HD MA；DTS:X 合并为 DTS-HD MA。
- Dolby Vision 可按流元数据或文件名补 profile；探测信息缺失时可能只得到文件名标记。
- 联合发布组使用完整名字，以 `&` 连接；映射表和平台表均可编辑。

## 常见问题

**预览和实际整理技术参数不一样？** 没有可读取源文件的命名预览只使用文件名兜底；带真实本地源路径的整理预览能使用 ffprobe。

**目录仍沿用 MP 原名称？** 先查看日志里的分类未匹配、规则格式错误、模板报错、空结果或目录层数不一致提示。规则中任意一节无效会停用整套分类替换；修正后保存。

**已有字幕名和视频不同？** 仅支持同目录同名前缀匹配，不会推断任意旧字幕和视频的关系，也不保证为历史外挂音轨恢复语言标签。

**能自动把第二季别名或 OVA 改到 TMDB 对应季集吗？** 当前只处理命名；媒体身份、季集纠正和内容筛选需要 MP 识别规则或另外的插件。它也不会自动跳过广告、原盘或特别篇。

**能批量重命名已有库吗？** 插件在 MP 整理事件发生时生效；它没有独立的全库重命名或迁移入口。

## 反馈

请到 [GitHub Issues](https://github.com/Plantforlife/MoviePilot-Plugins/issues) 提交 MP 版本、插件版本、脱敏文件名、分类规则、预期结果和相关日志。不要上传 API Key、Token、账号信息或完整私人配置。

MIT License；默认模板及映射来源说明见本目录 `THIRD_PARTY_NOTICES.md`。
