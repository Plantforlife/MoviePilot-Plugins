# MoviePilot Plugins · Plantforlife

[![Plugin checks](https://github.com/Plantforlife/MoviePilot-Plugins/actions/workflows/ci.yml/badge.svg)](https://github.com/Plantforlife/MoviePilot-Plugins/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Plantforlife/MoviePilot-Plugins)](https://github.com/Plantforlife/MoviePilot-Plugins/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

适用于 **MoviePilot V3** 的个人插件源。

| 插件 | ID | 版本 | 最低 MP 版本 |
| --- | --- | --- | --- |
| [FFprobe命名增强](plugins.v3/ffproberename/README.md) | `FfprobeRename` | 2.1.0 | 3.1.4 |

## 添加插件源

在 MoviePilot 的插件市场设置中，添加这个 **GitHub 仓库地址**：

```text
https://github.com/Plantforlife/MoviePilot-Plugins
```

保存并刷新插件市场，搜索 **FFprobe命名增强** 后安装。在插件配置中启用，检查 ffprobe 路径和分类规则。

如果通过环境变量维护源，把地址追加到 `PLUGIN_MARKET`，多个仓库用英文逗号分隔。仓库使用 `main` 分支；地址不需要加 `/tree/main`、`package.v3.json` 或插件子目录。MP 必须能访问 GitHub API、raw 内容和 Release 附件；遇到限流可在 MP 中配置自己的 GitHub Token。

这是独立维护的第三方插件源。

## FFprobe命名增强

<img src="icons/ffproberename.png" alt="FFprobe命名增强" width="96" height="96">

在 MP 整理重命名时读取真实媒体流信息，补充分辨率、编码、位深、音轨、HDR / Dolby Vision 等变量，按媒体分类选择 Jinja2 模板。

- 动画、动画电影、普通电影和电视剧分别设置命名规则。
- 保留完整联合发行组名称，统一平台、编码和片源写法。
- 电影可以使用主音轨及声道、Atmos；动画可以使用所有音轨编码。
- 支持 `Part1`、`CD2` 等带编号分段，字幕/外挂音轨优先匹配同目录同名前缀的视频。
- 探测失败使用文件名信息兜底；模板报错、分类未匹配或目录层数不一致时保留 MP 命名结果。

示例（最终信息取决于媒体本身）：

```text
示例电影 _ Example Film (2024)/示例电影 - 4K BluRay-Remux HEVC_10bit TrueHD_7.1ch.Atmos DolbyVision_Profile8.1 - ExampleGroup.mkv

示例动画 _ Example Anime _ サンプル (2024)/Season 1/示例动画 - S01E01 - 1080P BluRay-Rip HEVC_10bit AAC&FLAC - GroupA&GroupB.mkv
```

**完整设置、默认模板、变量和边界见 [插件使用说明](plugins.v3/ffproberename/README.md)。**

## 文档与维护

- [默认分类模板与映射数据](examples/README.md)
- [配置、命名空间和行为参考](docs/reference.md)
- [更新记录](CHANGELOG.md)
- [开发与发布](CONTRIBUTING.md)
- [验证记录](docs/validation.md)
- [问题反馈](https://github.com/Plantforlife/MoviePilot-Plugins/issues/new/choose)

本插件只增强整理命名：媒体身份、标题、年份和季集来自 MP；TMDB 别名归季、OVA 集号偏移和特别篇内容筛选不在当前功能范围内。插件不会主动扫描、移动或删除已有媒体。下一次整理的目标名称由 MP 和插件配置共同决定。

## 许可与来源

代码和自绘图标按 [MIT License](LICENSE) 发布。部分默认模板、发行组映射和命名约定继承自 [Plantforlife/moviepilot_templates_jinja2](https://github.com/Plantforlife/moviepilot_templates_jinja2)，来源及原许可见 [第三方说明](THIRD_PARTY_NOTICES.md)。MoviePilot、Jinja2 和 FFmpeg / ffprobe 保留各自的许可；本仓库不分发它们的二进制。
