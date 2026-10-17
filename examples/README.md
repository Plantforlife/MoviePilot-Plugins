# 默认配置示例

这些文件直接导出自插件 2.1.0 的默认常量，可粘贴到插件配置对应文本框。更新代码默认值后，需要同步这些文件，`scripts/check_release.py` 会检查一致性。

| 文件 | 配置字段 |
| --- | --- |
| [rules.ini](rules.ini) | 分类命名规则 `rules` |
| [prefer-english.txt](prefer-english.txt) | 英文标题优先关键词 `prefer_english` |
| [group-map.txt](group-map.txt) | 发行组 → 片源 `group_map` |
| [edition-map.txt](edition-map.txt) | 片源写法统一 `edition_map` |
| [known-groups.txt](known-groups.txt) | 已知发行组及别名 `known_groups` |
| [platforms.txt](platforms.txt) | 流媒体平台及别名 `platforms` |

分类名称需要与你的 MP 分类设置对应；也可以使用稳定分类 ID。电影和剧集中的“未分类”使用 `电影/未分类`、`电视剧/未分类` 区分。

安装更新保留已有配置，不会把这里的默认表强制写进用户配置。
