import shutil
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.plugins import _PluginBase
from app.schemas.types import ChainEventType

from . import naming, probe

# 视频文件扩展名；其余（字幕、外挂音轨）按同目录的视频文件探测，保证与视频同名
_VIDEO_SUFFIXES = frozenset(
    ".mkv .mp4 .m2ts .ts .avi .wmv .mov .rmvb .flv .webm .iso .mpg .mpeg .vob .m4v".split()
)


class FfprobeRename(_PluginBase):
    """整理时用 ffprobe 读取技术参数，并按二级分类选择命名模板，替代 MP 自带的技术变量。"""

    plugin_name = "FFprobe命名增强"
    plugin_desc = "按二级分类选择命名模板；用 ffprobe 读取分辨率、编码、位深、动态范围、音频，生成 ffprobe.out 等变量"
    plugin_version = "2.1.0"
    plugin_author = "Plantforlife"
    author_url = "https://github.com/Plantforlife"
    plugin_icon = "https://raw.githubusercontent.com/Plantforlife/MoviePilot-Plugins/main/icons/ffproberename.png"
    plugin_config_prefix = "ffproberename_"
    plugin_order = 20
    auth_level = 1

    _enabled = False
    _ffprobe_path = ""
    _timeout = 30
    _audio_mode = "best"
    _res_upper = True
    _res_4k_label = True
    _max_length = naming.DEFAULT_MAX_LENGTH
    _rules: Dict[str, naming.Rule] = {}
    _prefer_english: List[str] = []
    _group_map: Dict[str, Tuple[str, bool]] = {}
    _edition_map: Dict[str, str] = {}
    _book: Optional[probe.GroupBook] = None
    _platforms: Optional[probe.PlatformBook] = None
    _renderer: Optional[naming.Renderer] = None
    _cache: Optional["OrderedDict[Tuple[str, int, int], Dict[str, str]]"] = None
    _lock: Optional[threading.Lock] = None

    def init_plugin(self, config: dict = None) -> None:
        """读取配置、解析分类规则。缓存和锁在这里创建，避免覆写宿主基类的构造函数。"""
        self._cache = OrderedDict()
        self._lock = threading.Lock()
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._ffprobe_path = config.get("ffprobe_path") or shutil.which("ffprobe") or ""
        self._timeout = max(5, min(300, probe.to_int(config.get("timeout")) or 30))
        self._audio_mode = config.get("audio_mode") if config.get("audio_mode") in ("best", "default") else "best"
        self._res_upper = bool(config.get("res_upper", True))
        self._res_4k_label = bool(config.get("res_4k_label", True))
        self._max_length = max(0, probe.to_int(config.get("max_length", naming.DEFAULT_MAX_LENGTH)))
        self._renderer = naming.Renderer(self._max_length)
        self._prefer_english = naming.parse_keywords(config.get("prefer_english", naming.DEFAULT_PREFER_ENGLISH))
        self._group_map = probe.parse_group_map(config.get("group_map", probe.DEFAULT_GROUP_MAP))
        self._edition_map = probe.parse_edition_map(config.get("edition_map", probe.DEFAULT_EDITION_MAP))
        self._book = probe.GroupBook(config.get("known_groups", probe.DEFAULT_KNOWN_GROUPS))
        self._platforms = probe.PlatformBook(config.get("platforms", probe.DEFAULT_PLATFORMS))
        self._rules = self._load_rules(config.get("rules", naming.DEFAULT_RULES))
        if self._enabled and not self._ffprobe_available():
            logger.warning("FFprobe命名增强：找不到 ffprobe（%s），只能用文件名解析的值" % (self._ffprobe_path or "未配置"))

    @staticmethod
    def _load_rules(text: str) -> Dict[str, naming.Rule]:
        """解析分类规则并预编译模板；有错误时整套规则不生效，避免一半分类按新格式、一半按旧格式。"""
        try:
            rules = naming.parse_rules(text)
        except naming.RuleError as err:
            logger.error("FFprobe命名增强：%s，分类模板全部不生效" % err)
            return {}
        for rule in set(rules.values()):
            error = naming.validate_template(rule.template)
            if error:
                logger.error("FFprobe命名增强：[%s] 模板无法编译：%s，分类模板全部不生效" % (rule.name, error))
                return {}
        return rules

    def _ffprobe_available(self) -> bool:
        """ffprobe 是否可执行。"""
        return bool(shutil.which(self._ffprobe_path or "ffprobe"))

    def get_state(self) -> bool:
        """插件启用即运行；ffprobe 不可用时仍按文件名兜底命名。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """本插件不注册命令。"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """本插件不提供 API。"""
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """返回 Vuetify JSON 配置表单和默认值。"""
        def col(md: int, content: dict) -> dict:
            """生成一个栅格列。"""
            return {"component": "VCol", "props": {"cols": 12, "md": md}, "content": [content]}

        def area(model: str, label: str, rows: int) -> dict:
            """生成一个整行的多行文本框。"""
            return {"component": "VRow", "content": [col(12, {
                "component": "VTextarea", "props": {"model": model, "label": label, "rows": rows},
            })]}

        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            col(4, {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}),
                            col(4, {"component": "VSwitch", "props": {"model": "res_upper", "label": "分辨率大写（1080P）"}}),
                            col(4, {"component": "VSwitch", "props": {"model": "res_4k_label", "label": "2160p 显示为 4K"}}),
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            col(4, {"component": "VTextField", "props": {"model": "ffprobe_path", "label": "ffprobe 路径", "placeholder": "ffprobe"}}),
                            col(2, {"component": "VTextField", "props": {"model": "timeout", "label": "单文件超时（秒）", "type": "number"}}),
                            col(3, {"component": "VTextField", "props": {"model": "max_length", "label": "路径长度上限（超过只留中文标题）", "type": "number"}}),
                            col(3, {
                                "component": "VSelect",
                                "props": {
                                    "model": "audio_mode",
                                    "label": "主音轨选择",
                                    "items": [
                                        {"title": "档次最高（排除评论音轨）", "value": "best"},
                                        {"title": "默认音轨", "value": "default"},
                                    ],
                                },
                            }),
                        ],
                    },
                    area("rules", "分类命名规则（INI 格式，每个分类一节；说明见文本开头的注释）", 26),
                    area("prefer_english", "优先使用英文标题的关键词（每行一个）", 3),
                    area("group_map", "发行组 → 片源版本（每行 发行组小写名=版本，行尾加 ! 表示强制覆盖）", 8),
                    area("edition_map", "片源写法统一（每行 MP 识别的写法小写=统一写法，表里没有的原样保留）", 8),
                    area("known_groups", "已知发行组（每行一个规范拼写，或 别名=规范名；用于统一拼写和识别「-组名」写法）", 10),
                    area("platforms", "流媒体平台（统一名=别名1,别名2；只在 Web 系片源后面写入）", 8),
                    {
                        "component": "VAlert",
                        "props": {
                            "type": "info",
                            "variant": "tonal",
                            "text": (
                                "插件变量都在 ffprobe 下：ffprobe.out（按分类规则拼好的技术参数）、ffprobe.group（发行组全名，联合发布用 & 连接）、"
                                "ffprobe.resolution、ffprobe.source（片源.平台）、ffprobe.edition、ffprobe.platform、ffprobe.video（编码_位深）、"
                                "ffprobe.video_codec、ffprobe.bit_depth、ffprobe.audio（主音轨_声道ch.Atmos）、ffprobe.audio_codecs（全部音轨）、"
                                "ffprobe.audio_codec、ffprobe.channels、ffprobe.atmos、ffprobe.dynamic_range、ffprobe.extra、ffprobe.subtitle、"
                                "ffprobe.category、ffprobe.category_id。标题、年份、季集沿用 MP 的 title / en_title / original_title / year / "
                                "season / season_episode / fileExt。没有匹配规则的分类保持 MP 自带命名。"
                                "重命名预览没有源文件，预览里只有文件名解析的兜底值。"
                            ),
                        },
                    },
                ],
            }
        ], {
            "enabled": False,
            "res_upper": True,
            "res_4k_label": True,
            "ffprobe_path": shutil.which("ffprobe") or "ffprobe",
            "timeout": 30,
            "max_length": naming.DEFAULT_MAX_LENGTH,
            "audio_mode": "best",
            "rules": naming.DEFAULT_RULES,
            "prefer_english": naming.DEFAULT_PREFER_ENGLISH,
            "group_map": probe.DEFAULT_GROUP_MAP,
            "edition_map": probe.DEFAULT_EDITION_MAP,
            "known_groups": probe.DEFAULT_KNOWN_GROUPS,
            "platforms": probe.DEFAULT_PLATFORMS,
        }

    def get_page(self) -> Optional[List[dict]]:
        """本插件没有详情页。"""
        return None

    def stop_service(self) -> None:
        """本插件没有后台服务。"""
        return None

    # ------------------------------------------------------------------ 事件

    @eventmanager.register(ChainEventType.TransferRenameBuild)
    def on_transfer_rename_build(self, event: Event) -> None:
        """渲染前探测源文件，把 ffprobe 命名空间写入 rename_dict。无源文件（预览）时只用文件名兜底。"""
        if not self.get_state() or not event or not event.event_data:
            return
        event_data = event.event_data
        base = event_data.rename_dict
        try:
            base["ffprobe"] = self._build_namespace(base, event_data.source_path, event_data.source_item)
        except Exception as err:  # 命名增强失败不能影响整理本身
            logger.warning("FFprobe命名增强：生成变量失败：%s" % err)

    @eventmanager.register(ChainEventType.TransferRename)
    def on_transfer_rename(self, event: Event) -> None:
        """按二级分类选模板重新渲染，整串替换 MP 的渲染结果；资料夹层级与 MP 模板不一致时放弃替换。"""
        if not self.get_state() or not self._rules or not event or not event.event_data:
            return
        event_data = event.event_data
        base = event_data.rename_dict
        category_id, category_path, media_type = self._category(base)
        rule = naming.find_rule(self._rules, category_id, category_path, media_type)
        if not rule:
            logger.debug("FFprobe命名增强：分类 %s（%s）没有命名规则，保持 MP 命名" % (category_path, category_id))
            return
        try:
            if "ffprobe" not in base:
                base["ffprobe"] = self._build_namespace(base, event_data.source_path, event_data.source_item)
            context = naming.prefer_english(base, self._prefer_english)
            result = self._renderer.render(rule, context)
        except Exception as err:  # 模板运行期错误不能影响整理本身
            logger.error("FFprobe命名增强：[%s] 渲染失败，保持 MP 命名：%s" % (rule.name, err))
            return
        if not result:
            logger.warning("FFprobe命名增强：[%s] 渲染结果为空或含空目录，保持 MP 命名" % rule.name)
            return
        if naming.path_depth(result) != naming.path_depth(event_data.template_string):
            logger.warning(
                "FFprobe命名增强：[%s] 结果有 %d 层资料夹，MP 重命名格式是 %d 层，保持 MP 命名：%s"
                % (rule.name, naming.path_depth(result), naming.path_depth(event_data.template_string), result)
            )
            return
        current = event_data.updated_str if event_data.updated and event_data.updated_str else event_data.render_str
        if result != current:
            event_data.updated_str = result
            event_data.updated = True
            event_data.source = self.plugin_name
        logger.info("FFprobe命名增强：[%s] %s" % (rule.name, result))

    # ------------------------------------------------------------------ 变量

    @staticmethod
    def _category(base: Dict[str, Any]) -> Tuple[Optional[str], str, str]:
        """取媒体的（分类 ID，分类路径，媒体类型）。ID 来自 V3 分类策略的生效结果。"""
        media = base.get("__mediainfo__")
        category_id = None
        classification = getattr(media, "classification", None)
        for selection in (getattr(classification, "effective", None), getattr(classification, "recommended", None)):
            if selection is not None and getattr(selection, "category_id", None):
                category_id = selection.category_id
                break
        category_path = str(base.get("category") or getattr(media, "category", "") or "")
        return category_id, category_path, str(base.get("type") or "")

    def _build_namespace(self, base: Dict[str, Any], source_path: Optional[str], source_item: Any) -> Dict[str, str]:
        """生成 ffprobe 命名空间：技术参数各部分、按分类规则拼好的 out、发行组等。"""
        probe_path = self._probe_target(source_path, source_item)
        fields = self._probe_fields(probe_path) if probe_path else {}
        view = dict(base)
        if probe_path:
            # 有源文件时按真实文件名解析（字幕、外挂音轨用同名视频），不受识别词改写影响
            view["original_name"] = probe_path.name
        group = probe.resolve_group(view, self._book)
        view["releaseGroup"] = group
        view["isBDMV"] = self._is_bdmv(source_path, source_item)
        view["isRemux"] = bool(fields.get("ffRemux"))
        parts = probe.tech_parts(
            fields, view, self._group_map, self._res_upper, self._res_4k_label,
            edition_map=self._edition_map, platform_book=self._platforms,
        )
        category_id, category_path, media_type = self._category(base)
        rule = naming.find_rule(self._rules, category_id, category_path, media_type)
        out = probe.assemble_out(parts, rule.audio, rule.dr, rule.extra) if rule else probe.assemble_out(parts)
        namespace = dict(parts)
        namespace.update({
            "out": out,
            "group": group,
            "subtitle": fields.get("ffSub", ""),
            "fps": fields.get("ffFps", ""),
            "category": category_path,
            "category_id": category_id or "",
            "probed": "1" if fields else "",
        })
        return namespace

    @staticmethod
    def _is_bdmv(source_path: Optional[str], source_item: Any) -> bool:
        """源是蓝光原盘：路径里有 BDMV 目录，或整理的是一个含 BDMV 子目录的文件夹。"""
        text = "/%s/" % str(source_path or "").replace("\\", "/").strip("/").lower()
        if "/bdmv/" in text:
            return True
        if source_path and getattr(source_item, "type", None) == "dir":
            try:
                return (Path(source_path) / "BDMV").is_dir()
            except OSError:
                return False
        return False

    @staticmethod
    def _probe_target(source_path: Optional[str], source_item: Any) -> Optional[Path]:
        """要探测的本地视频文件：视频本身，或字幕/外挂音轨同目录里文件名是其前缀的视频。"""
        if not source_path:
            return None
        if source_item and getattr(source_item, "storage", None) not in (None, "local"):
            return None
        path = Path(source_path)
        try:
            if not path.is_file():
                return None
            if path.suffix.lower() in _VIDEO_SUFFIXES:
                return path
            best: Optional[Path] = None
            for sibling in path.parent.iterdir():
                if sibling.suffix.lower() not in _VIDEO_SUFFIXES or not sibling.is_file():
                    continue
                if path.stem.startswith(sibling.stem) and (best is None or len(sibling.stem) > len(best.stem)):
                    best = sibling
            return best
        except OSError:
            return None

    def _probe_fields(self, media_path: Path) -> Dict[str, str]:
        """读取 ffprobe 字段，按（路径，大小，修改时间）缓存。读取失败返回空字典。"""
        if not self._ffprobe_available():
            return {}
        try:
            stat = media_path.stat()
        except OSError:
            return {}
        key = (str(media_path), stat.st_size, stat.st_mtime_ns)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return dict(cached)
        data = probe.run_ffprobe(str(media_path), self._ffprobe_path or "ffprobe", self._timeout)
        if data is None:
            logger.warning("FFprobe命名增强：读取失败，使用文件名兜底：%s" % media_path.name)
            return {}
        fields = probe.parse_ffprobe(data, self._audio_mode)
        with self._lock:
            self._cache[key] = fields
            while len(self._cache) > 512:
                self._cache.popitem(last=False)
        return dict(fields)
