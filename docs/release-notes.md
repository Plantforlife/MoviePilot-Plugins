FFprobe命名增强 2.1.0 首次公开发布，需要 MoviePilot >= 3.1.4。

- 根据实际本地媒体流读取分辨率、编码、位深、音轨、声道、Atmos、HDR / Dolby Vision。
- 按分类选择命名模板，统一平台、片源和完整联合发行组。
- 支持编号 Part/CD 分段；探测或渲染失败时保留回退行为。
- 附带完整使用说明、默认配置和来源说明。

插件源：`https://github.com/Plantforlife/MoviePilot-Plugins`

添加仓库地址后，在 MP 插件市场安装“FFprobe命名增强”。ffprobe 路径使用 MP 运行环境中的路径。

`ffproberename_v2.1.0.zip` 是 MP 使用的安装包，`SHA256SUMS` 提供校验值。GitHub 自动生成的整个仓库源码包不是插件安装附件。

当前不包含媒体识别修正、别名归季、OVA 集号偏移或特别篇筛选。完整变量、默认命名约定和已知边界见仓库 README。
