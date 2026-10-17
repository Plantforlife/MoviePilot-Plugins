"""按二级分类选择命名模板并渲染最终路径。

本模块只依赖标准库和 Jinja2，不引用 MoviePilot 宿主代码，可以脱离宿主做离线测试。
规则文本用 INI 写法，每个分类一节：

    [日番|国漫|其他动画]
    audio = all
    dr = none
    extra = no
    template = {{ titles(title, en_title, original_title) }} ({{ year }})/Season {{ season }}/...

节名可以写分类 ID（tv.dongman.jp）、分类名称（日番）或 类型/名称（电影/未分类），多个用 | 隔开。
"""
import configparser
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from jinja2 import Environment, TemplateError

# Windows / SMB 不允许出现在文件名里的字符，统一换成全角（与 MP 处理标题的做法一致）；/ 是目录分隔，不在此列
_INVALID_CHARS = '\\:*?"<>|'
_FULLWIDTH = str.maketrans({c: chr(ord(c) + 0xFEE0) for c in _INVALID_CHARS})

DEFAULT_MAX_LENGTH = 180

DEFAULT_RULES = """\
# 每个分类一节，节名写分类 ID、分类名称或 类型/名称，多个用 | 隔开。
#   audio  : main = 主音轨带声道和 Atmos（TrueHD_7.1ch.Atmos）；all = 全部音轨编码、不带声道（AAC&FLAC）
#   dr     : none = 不写动态范围；hdr = 只写 HDR / 杜比视界；all = 连 SDR 也写
#   extra  : yes / no，是否写 3D、IMAX、60FPS、120FPS
#   template : Jinja2 模板，可跨多行（续行要缩进，拼接时去掉每行首尾空白）。
#              资料夹层级必须与 MP 设置里的重命名格式一致：电影 1 层、剧集 2 层（标题/Season）。
# 模板变量：MP 原有的 title en_title original_title year season season_episode episode_title fileExt 等，
#   以及插件的 ffprobe.out ffprobe.group ffprobe.resolution ffprobe.source ffprobe.video ffprobe.audio ……
# titles(a, b, c) 用「 _ 」连接不重复的标题，路径超过长度上限时只保留第一个。
# part 是 MP 识别的分段（CD1、Part2 等），写在扩展名前，媒体服务器据此合并多段文件。

[日番|国漫|其他动画]
audio = all
dr = none
extra = no
template = {{ titles(title, en_title, original_title) }} ({{ year }})/Season {{ season }}/
    {{ title }} - {{ season_episode }} - {{ ffprobe.out }}{% if ffprobe.group %} - {{ ffprobe.group }}{% endif %}{% if part %}-{{ part }}{% endif %}{{ fileExt }}

[华语电影|外语电影|电影/未分类]
audio = main
dr = all
extra = yes
template = {{ titles(title, en_title) }} ({{ year }})/
    {{ title }} - {{ ffprobe.out }}{% if ffprobe.group %} - {{ ffprobe.group }}{% endif %}{% if part %}-{{ part }}{% endif %}{{ fileExt }}

[动画电影]
audio = main
dr = hdr
extra = yes
template = {{ titles(title, original_title) }} ({{ year }})/
    {{ title }} - {{ ffprobe.out }}{% if ffprobe.group %} - {{ ffprobe.group }}{% endif %}{% if part %}-{{ part }}{% endif %}{{ fileExt }}

[国产剧|欧美剧|纪录片|综艺|儿童|电视剧/未分类]
audio = main
dr = hdr
extra = yes
template = {{ titles(title, en_title) }} ({{ year }})/Season {{ season }}/
    {{ title }} - {{ season_episode }} - {{ ffprobe.out }}{% if ffprobe.group %} - {{ ffprobe.group }}{% endif %}{% if part %}-{{ part }}{% endif %}{{ fileExt }}

[亚洲剧]
audio = main
dr = hdr
extra = yes
template = {{ titles(title, original_title) }} ({{ year }})/Season {{ season }}/
    {{ title }} - {{ season_episode }} - {{ ffprobe.out }}{% if ffprobe.group %} - {{ ffprobe.group }}{% endif %}{% if part %}-{{ part }}{% endif %}{{ fileExt }}
"""

DEFAULT_PREFER_ENGLISH = """\
# 标题里含有这些关键词（不区分大小写）时，中文标题位改用英文标题。每行一个。
BanG Dream!
"""


@dataclass(frozen=True)
class Rule:
    """一个分类的命名规则。"""

    name: str
    template: str
    audio: str = "main"
    dr: str = "hdr"
    extra: bool = True


class RuleError(ValueError):
    """规则文本格式错误。"""


def _join_template(value: str) -> str:
    """把跨行模板拼成一行：每行去掉首尾空白后直接相连，避免换行和缩进进入文件名。"""
    return "".join(line.strip() for line in str(value or "").splitlines())


def parse_rules(text: str) -> Dict[str, Rule]:
    """解析规则文本，返回 {节名中的每个键: Rule}。格式错误抛 RuleError。"""
    parser = configparser.ConfigParser(
        interpolation=None, delimiters=("=",), comment_prefixes=("#", ";"), strict=True,
    )
    try:
        parser.read_string(text or "")
    except configparser.Error as err:
        raise RuleError("规则格式错误：%s" % err) from err
    rules: Dict[str, Rule] = {}
    for section in parser.sections():
        body = parser[section]
        template = _join_template(body.get("template", ""))
        if not template:
            raise RuleError("[%s] 缺少 template" % section)
        audio = body.get("audio", "main").strip().lower()
        dr = body.get("dr", "hdr").strip().lower()
        if audio not in ("main", "all"):
            raise RuleError("[%s] audio 只能是 main 或 all" % section)
        if dr not in ("none", "hdr", "all"):
            raise RuleError("[%s] dr 只能是 none、hdr 或 all" % section)
        try:
            extra = body.getboolean("extra", True)
        except ValueError as err:
            raise RuleError("[%s] extra 只能是 yes 或 no" % section) from err
        rule = Rule(name=section, template=template, audio=audio, dr=dr, extra=extra)
        for key in section.split("|"):
            key = key.strip()
            if not key:
                continue
            if key in rules:
                raise RuleError("分类 %s 在 [%s] 和 [%s] 里重复" % (key, rules[key].name, section))
            rules[key] = rule
    return rules


def find_rule(
    rules: Dict[str, Rule],
    category_id: Optional[str],
    category_path: Optional[str],
    media_type: Optional[str],
) -> Optional[Rule]:
    """按 分类 ID → 类型/路径 → 路径 的顺序找规则，找不到返回 None。"""
    candidates = [category_id]
    if category_path:
        if media_type:
            candidates.append("%s/%s" % (media_type, category_path))
        candidates.append(category_path)
    for key in candidates:
        if key and key in rules:
            return rules[key]
    return None


def parse_keywords(text: str) -> List[str]:
    """解析每行一个的关键词列表，忽略空行和 # 注释。"""
    return [line.strip() for line in (text or "").splitlines() if line.strip() and not line.strip().startswith("#")]


def prefer_english(context: Dict[str, Any], keywords: Iterable[str]) -> Dict[str, Any]:
    """任一标题含关键词且有英文标题时，把 title 换成英文标题，返回新的上下文（不改原字典）。"""
    en_title = str(context.get("en_title") or "").strip()
    if not en_title:
        return context
    names = " ".join(str(context.get(k) or "") for k in ("title", "en_title", "original_title")).casefold()
    if any(k.casefold() in names for k in keywords if k):
        return dict(context, title=en_title)
    return context


def _title_key(name: str) -> str:
    """标题比较用的键：忽略大小写、空白，全角半角视为相同。"""
    text = str(name or "").translate({ord(c) + 0xFEE0: c for c in map(chr, range(33, 127))})
    return re.sub(r"\s+", "", text).casefold()


def unique_titles(names: Iterable[Any]) -> List[str]:
    """去掉空值和重复的标题，保持原顺序。"""
    result, seen = [], set()
    for name in names:
        text = str(name or "").strip()
        key = _title_key(text)
        if key and key not in seen:
            seen.add(key)
            result.append(text)
    return result


# MP 的分段识别把不带编号的 DVD / CD / PART 也当成分段（如 [DVD 720x480] 里的片源标记），
# 这里只认带编号的分段，避免 DVD 片源的文件名多出「-DVD」
_PART_RE = re.compile(r"^(?:(?:PART|PT)[0-9ABI]{1,2}|(?:CD|DVD|DISK|DISC)[0-9]{1,2})$", re.I)


def clean_part(part: Any) -> str:
    """返回可用的分段标记（CD1、Part2、DVD1 等），不带编号的返回空。"""
    text = str(part or "").strip()
    return text if _PART_RE.match(text.replace(" ", "")) else ""


def sanitize_path(path: str) -> str:
    """逐段清理渲染结果：非法字符换全角、折叠空白、去掉段首尾空格和段尾的点（Windows 不允许）；任一段为空返回空串。"""
    segments = []
    for segment in str(path or "").split("/"):
        # 年份等变量缺失时模板会留下空括号，一并去掉
        segment = re.sub(r"\(\s*\)|\[\s*\]", "", segment.translate(_FULLWIDTH))
        segment = re.sub(r"\s+", " ", segment).strip().rstrip(" .")
        if not segment:
            return ""
        segments.append(segment)
    return "/".join(segments)


def path_depth(text: str) -> int:
    """模板或路径的资料夹层数（按 / 计数，与 MP 计算媒体根目录的方式一致）。"""
    return len(str(text or "").split("/")) - 1


class Renderer:
    """用插件自己的 Jinja2 环境渲染分类模板，带模板缓存。"""

    def __init__(self, max_length: int = DEFAULT_MAX_LENGTH) -> None:
        """max_length 为整条相对路径的长度上限，超过时标题段只保留第一个标题。"""
        self.max_length = max_length
        self._env = Environment(autoescape=False, keep_trailing_newline=False)
        self._cache: Dict[str, Any] = {}

    def _template(self, source: str) -> Any:
        """取缓存的已编译模板。"""
        template = self._cache.get(source)
        if template is None:
            template = self._env.from_string(source)
            self._cache[source] = template
        return template

    def render(self, rule: Rule, context: Dict[str, Any]) -> str:
        """渲染规则模板并清理；没有标题（识别失败）或结果无效时返回空串，交回 MP 命名。"""
        if not str(context.get("title") or "").strip():
            return ""
        template = self._template(rule.template)

        def titles_full(*names: Any) -> str:
            """用「 _ 」连接不重复的标题。"""
            return " _ ".join(unique_titles(names))

        def titles_short(*names: Any) -> str:
            """长度超限时只保留第一个标题。"""
            return (unique_titles(names) or [""])[0]

        context = dict(context, part=clean_part(context.get("part")))
        result = sanitize_path(template.render(dict(context, titles=titles_full)))
        if result and self.max_length and len(result) > self.max_length:
            result = sanitize_path(template.render(dict(context, titles=titles_short)))
        return result


def validate_template(source: str) -> Optional[str]:
    """检查模板能否编译，返回错误信息，没有错误返回 None。"""
    try:
        Environment(autoescape=False).parse(source)
    except TemplateError as err:
        return str(err)
    return None
