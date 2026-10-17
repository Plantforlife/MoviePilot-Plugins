# 验证记录

日期：2026-10-17。

## 本地发布检查

- Windows / Python 3.13：96 项 pytest 用例通过。
- 三个源码模块、测试及发布脚本编译通过。
- 官方 `check_plugin_versions.py` 检查 `package.v3.json` 通过。
- 自有发布检查核对市场元数据、版本历史、图标、许可和全部默认示例。
- 安装包按 MP 约定生成，顶层目录为 `ffproberename/`，同时输出 SHA-256 校验文件。

## 已有宿主联调

公开版本使用已部署 2.1.0 的探测与渲染实现，补充作者、图标等发布元数据。部署环境为 Linux Docker / MoviePilot 3.1.4：

- 插件运行状态 active，已启用，无待处理/失败运行时项。
- 已对真实电影源调用 MP 原生整理预览，技术参数及 Dolby Vision profile 正常写入目标名称。
- 指定 `Part1` 后，MP 原生整理预览得到带 `-Part1` 后缀的目标名称。

离线用例使用精简流样本和最小宿主桩。它们不代表所有硬件、媒体、MP 版本及远程存储均经过实测。

## GitHub 与公开安装包验收

- [Plugin checks](https://github.com/Plantforlife/MoviePilot-Plugins/actions/runs/39030259700)：Linux / Windows、Python 3.14，96 项测试均通过。
- [发布工作流](https://github.com/Plantforlife/MoviePilot-Plugins/actions/runs/39030304780)：检查、测试、打包和上传通过。
- [Release 2.1.0](https://github.com/Plantforlife/MoviePilot-Plugins/releases/tag/FfprobeRename_v2.1.0)：包含 MP 安装包和 SHA256SUMS。
- 安装包 SHA-256：`3df0e3f5e92d33df0a7283ce0329536e011353b28bd2ff03600d915c71464149`。
- 从 GitHub 下载后的校验值与 SHA256SUMS 一致，ZIP 内全部 6 个文件逐字节匹配发布 Tag 的 Git 内容。

## NAS 原生包安装器验收

使用 MoviePilot 3.1.4 当前运行环境中的真实 `PluginPackageSourceClient` 和 `PluginPackageManager`：

1. 读取公开 `package.v3.json`，检查主程序兼容范围。
2. 读取 GitHub Releases，找到 2.1.0 及规范附件名。
3. 使用原生安装器将指定 Release 下载、校验目录和解包到隔离临时插件目录，结果成功。
4. 从下载文件导入插件，使用真实宿主 SDK 验证表单、自有配置初始化、命名事件、禁用及停止方法。
5. 对真实本地媒体执行 ffprobe，得到 2160p、HEVC、10bit、Dolby Vision Profile 8.1、TrueHD 7.1 Atmos。

第 4 步是独立验证进程，通过 `object.__new__` 跳过需要已启动 Chain 组合根的宿主基类构造函数；插件自身 `init_plugin()` 和事件处理照常执行。这不等同于在另一套完整 MP 服务中进行首次启动测试；完整服务加载行为由上面的已部署 2.1.0 联调覆盖，发布代码与其实现一致。

验证前后生产插件配置和来源身份一致。隔离临时目录已自动清理，没有对媒体执行实际整理或重命名。
