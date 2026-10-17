# 开发与发布

## 本地检查

使用独立环境安装开发依赖，运行：

```shell
python -m pip install -r requirements-dev.txt
python -m compileall -q plugins.v3 scripts tests
python scripts/check_release.py
python -m pytest -q
git diff --check
python scripts/build_release.py
```

CI 在 Linux / Windows、Python 3.14 上运行。离线测试从生产命名空间 `app.plugins.ffproberename` 导入；`tests/conftest.py` 仅在没有实际宿主时提供最小 SDK 桩，不连接数据库或真实服务。它验证逻辑，不代替真实 MP 安装验收。

插件没有额外的运行时 Python 包依赖：Jinja2 由宿主提供，ffprobe 是外部可执行文件。`requirements-dev.txt` 仅供开发 / CI，不由 MP 安装。以后新增宿主未提供的依赖时，再在插件目录声明 V3 `pyproject.toml`；不要提交插件 `uv.lock`。

## 修改与回归

测试位于 `tests/v3/ffproberename/`，采用 pytest 和生产导入命名空间。覆盖默认分类、模板渲染、技术参数、发行组、平台、事件回退和外部探测失败。新增逻辑应补充有针对性的行为用例。

模板或默认表变更后同步 `examples/`；代码和索引中的名字、作者、图标、版本、权限级别需一致。

## 发版

1. 同步插件 `plugin_version`、根 `package.v3.json` 的 `version` / 当前 `history`。
2. 更新 CHANGELOG、说明及 `docs/release-notes.md`；运行上述检查。
3. 在独立 MP V3 环境验证安装、启停、配置保存、重载、真实源整理预览。
4. 提交到 `main`，等待 Plugin checks 通过。
5. 推送格式为 `FfprobeRename_vX.Y.Z` 的 Tag。
6. Release 工作流再次检查并生成 `ffproberename_vX.Y.Z.zip` 和 `SHA256SUMS`，随后创建 GitHub Release。

插件索引声明 `release: true`，需要附件成功发布后才能通过 MP 安装该版本。压缩包顶层必须为 `ffproberename/`，包含源码、README 和许可；不打包仓库测试、缓存或开发依赖。

不要覆盖已经发布的版本。修复使用新版本号和新 Tag。用户更新前可以导出已有配置；插件升级默认保留保存的配置。

## 官方资料

- [V3 开发指南](https://github.com/jxxghp/MoviePilot-Plugins/blob/main/docs/Plugin_Development.md)
- [仓库与发布规范](https://github.com/jxxghp/MoviePilot-Plugins/blob/main/docs/Repository_Guide.md)
- [官方测试约定](https://github.com/jxxghp/MoviePilot-Plugins/blob/main/tests/README.md)
