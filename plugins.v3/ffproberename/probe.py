"""ffprobe 结果解析、词汇统一、发行组识别与技术参数拼装。

本模块只依赖标准库，不引用 MoviePilot 宿主代码，因此可以脱离宿主做离线测试。
统一后的写法沿用 V2 模板 https://github.com/Plantforlife/moviepilot_templates_jinja2 ，
并按 V3 迁移时确认的规则调整：片源未注明 Remux 一律 BluRay-Rip、原盘写 BluRay，
DTS 家族写成 DTS / DTS-HD HRA / DTS-HD MA（DTS:X 归入 MA），8bit 不写进文件名。
"""
import json
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

# 发行组到片源版本的默认映射。行尾带 ! 表示即使 MP 已识别出片源也强制覆盖，
# 不带 ! 表示只在 MP 没识别出片源时才使用。匹配方式是整词相等，不做子串匹配。
DEFAULT_GROUP_MAP = """\
# 格式：发行组小写名=片源版本[!]
vcb-studio=BluRay-Rip!
moozzi2=BluRay-Rip!
mawen1250=BluRay-Rip!
mai=BluRay-Rip!
ye=BluRay-Rip!
acgnation=BluRay-Rip!
mysilu=BluRay-Rip!
lolihouse=Web-Rip
sakurato=Web-Rip
dynamis one=Web-Rip
ani=Web-Rip
"""

# MP 从文件名里识别出的片源写法不统一（BDRIP / BD / WEB-DL 等），这里统一成同一种写法。
# 键是 MP 识别结果的小写形式，不在表里的写法原样保留。WEB-DL / WebRip / WEB 合并成 Web-Rip、
# HDTV 写成 HDTV-Rip 是 V2「重命名插件替换词」的做法；没注明 Remux 的蓝光一律算 BluRay-Rip，
# 只有 BDMV 原盘目录才写 BluRay（由插件按源路径判断，不走这张表）。
DEFAULT_EDITION_MAP = """\
# 格式：MP 识别出的片源写法（小写）=统一后的写法
web-dl=Web-Rip
webdl=Web-Rip
webrip=Web-Rip
web-rip=Web-Rip
web=Web-Rip
hdtv=HDTV-Rip
hdtvrip=HDTV-Rip
hdtv-rip=HDTV-Rip
dvd=DVD-Rip
dvdrip=DVD-Rip
dvd-rip=DVD-Rip
dvd5=DVD-Rip
dvd9=DVD-Rip
bd=BluRay-Rip
bdrip=BluRay-Rip
brrip=BluRay-Rip
bd bluray=BluRay-Rip
bluray=BluRay-Rip
uhd bluray=BluRay-Rip
uhd=BluRay-Rip
remux=BluRay-Remux
bdremux=BluRay-Remux
bd remux=BluRay-Remux
bluray remux=BluRay-Remux
uhd bluray remux=BluRay-Remux
"""

# 已知发行组：用来统一拼写，并识别「-组名」「.别名」这类位置不固定的写法。
# 前一段来自上游仓库的「自定义字幕组」，后一段是语料里常见但上游表没有的。
DEFAULT_KNOWN_GROUPS = """\
# 每行一个发行组（写规范拼写），别名写成 别名=规范名。不区分大小写，@ 与 & 视为同一个符号。
Acgnation
AI-Raws
Airota&VCB-Studio
CTRLWEB
cXcY&FRDS
DreamHD
Dynamis One
FGT
GPTHD
Haruhana
H-Enc
LP-Raws
LPSub
LoliHouse
MAI
mawen1250
Moozzi2
Mysilu
Nekomoe kissaten&LoliHouse
Nekomoe kissaten&VCB-Studio
Prejudice-Studio
UH
VCB-Studio
Xiaomi
YE
ZeroTV
Tsundere
修罗影视
路基艾尔-Raws
老K
Xcat
subbers
xlys=修罗影视
BlackTV
ParkHD
LelveTV
playWEB
TeamSyndicate
Lieqiwang
PanWEB
DVT
QTS
Curly
WiLDCAT
ALT
MOMOHD
幻月字幕组
NUMTV
BestWEB
Vampire
"""

# 流媒体平台：统一名=别名列表。别名整词匹配、不区分大小写，只在文件名的技术信息部分里找（避开片名里的 Prime 之类）。
# 只有片源是 Web 系时才会写进 tech。MP 识别出的平台名也会经过这张表统一。
DEFAULT_PLATFORMS = """\
# 格式：统一名=别名1,别名2
CR=cr,crunchyroll
Baha=baha,bahamut
BiliBili-Global=b-global,bilibili global
BiliBili=bilibili
ABEMA=abema
Netflix=netflix,nfx,nf
Amazon=amazon,amazonprime,prime,amzn
Hulu=hulu
DisneyPlus=disneyplus,disney+,disney plus
HBO=hbo,hbomax,hbo max
YouTubePremium=youtube,ytpremium,ytp
AppleTV=appletv,apple tv,apple tv+,atvp
Funimation=funimation,funi
Vimeo=vimeo
Peacock=peacock
ParamountPlus=paramountplus,paramount+,paramount plus
DAZN=dazn
Tubi=tubi
RakutenTV=rakuten,rakutentv
TencentVideo=tencent,tencentvideo
iQIYI=iqiyi,爱奇艺,iqy
Youku=youku,优酷
MangoTV=mangotv,芒果tv,mgtv
friDay=friday
iTunes=itunes
"""

_VIDEO_CODEC_LABELS = {
    "hevc": "HEVC",
    "h264": "AVC",
    "av1": "AV1",
    "vp9": "VP9",
    "mpeg2video": "MPEG2",
    "vc1": "VC-1",
    "mpeg4": "MPEG4",
}

_CHANNEL_LABELS = {1: "1.0", 2: "2.0", 3: "2.1", 6: "5.1", 7: "6.1", 8: "7.1"}

# 评论音轨不参与“最佳音轨”选择
_COMMENTARY_RE = re.compile(r"comment|评论|解说|导评", re.I)

# DTS 家族的统一写法：核心 DTS、高解析 HRA（只写 DTS-HD 没注明 MA 的都算 HRA）、无损 MA。
# DTS:X 承载在 MA 之上，按迁移时的决定不单独标，统一写 MA（冒号在 Windows 文件名里也不合法）。
DTS = "DTS"
DTS_HRA = "DTS-HD HRA"
DTS_MA = "DTS-HD MA"

# 多个音频编码连写时的先后顺序（沿用 V2 日番模板的 standard_audio_list，由低到高），如 AAC&FLAC
_AUDIO_ORDER = ["MP3", "AAC", "DD", "DDP", "FLAC", "OPUS", DTS, DTS_HRA, DTS_MA, "TrueHD", "PCM"]


def join_audio(labels: List[str]) -> str:
    """去重后按 V2 顺序用 & 连接多个音频编码，不在顺序表里的排在最后。
    同一家族只留最高档：有 MA 时不再写 HRA / DTS，有 HRA 时不再写 DTS，有 DDP 时不再写 DD。"""
    unique = [x for x in dict.fromkeys(labels) if x]
    drop = set()
    if DTS_MA in unique:
        drop.update((DTS_HRA, DTS))
    elif DTS_HRA in unique:
        drop.add(DTS)
    if "DDP" in unique:
        drop.add("DD")
    rank = {name: i for i, name in enumerate(_AUDIO_ORDER)}
    return "&".join(sorted((x for x in unique if x not in drop), key=lambda x: rank.get(x, len(rank))))

# 音频编码档次，数值越大越优先
_AUDIO_RANK = {
    "TrueHD": 100,
    DTS_MA: 95,
    "PCM": 94,
    "FLAC": 92,
    DTS_HRA: 80,
    "DDP": 70,
    "DTS": 65,
    "DD": 60,
    "OPUS": 50,
    "AAC": 45,
    "MP3": 30,
}


def to_int(value: Any) -> int:
    """把任意值安全转成整数，失败返回 0。"""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------- 分辨率

_PIX_ALIASES = {
    "4k": "2160p", "uhd": "2160p", "2160p": "2160p", "2160": "2160p",
    "8k": "4320p", "4320p": "4320p",
    "2k": "1440p", "1440p": "1440p",
    "1080p": "1080p", "1080i": "1080p", "fhd": "1080p",
    "720p": "720p", "576p": "576p", "480p": "480p",
}
_K_LABELS = {"2160p": "4K", "1440p": "2K", "4320p": "8K"}


def resolution_label(width: int, height: int) -> str:
    """按宽高归类分辨率，宽屏裁切片源（如 3840x1600）按宽度归到 2160p。"""
    if width >= 7000 or height >= 4000:
        return "4320p"
    if width >= 3400 or height >= 2000:
        return "2160p"
    if width >= 2400 or height >= 1300:
        return "1440p"
    if width >= 1800 or height >= 1000:
        return "1080p"
    if width >= 1200 or height >= 700:
        return "720p"
    if height >= 560:
        return "576p"
    if height > 0:
        return "480p"
    return ""


def normalize_pix(text: Any) -> str:
    """把 MP 识别出的分辨率写法统一成标准档（2160p/1080p…），不是标准档的（如 362p）返回空。"""
    return _PIX_ALIASES.get(str(text or "").strip().lower(), "")


def resolution_display(label: str, upper: bool = False, k_label: bool = False) -> str:
    """按显示选项输出分辨率：k_label 时 2160p/1440p 写成 4K/2K，upper 时 p 大写。"""
    if not label:
        return ""
    if k_label and label in _K_LABELS:
        return _K_LABELS[label]
    return label.upper() if upper else label


# ---------------------------------------------------------------- 视频

def video_codec_label(stream: Dict[str, Any]) -> str:
    """把 ffprobe 的视频编码名转成命名里常用的写法。"""
    name = str(stream.get("codec_name") or "").lower()
    return _VIDEO_CODEC_LABELS.get(name, name.upper())


def normalize_codec(text: Any) -> Tuple[str, str]:
    """把 MP 识别出的视频编码写法统一，返回（编码, 位深）。x265/H265→HEVC，x264/Hi10p→AVC，VC1→VC-1。"""
    low = str(text or "").lower()
    codec = ""
    if re.search(r"hevc|x\.?265|h\.?265", low):
        codec = "HEVC"
    elif re.search(r"avc|x\.?264|h\.?264|hi10", low):
        codec = "AVC"
    elif "av1" in low:
        codec = "AV1"
    elif re.search(r"vc-?1", low):
        codec = "VC-1"
    elif "vp9" in low:
        codec = "VP9"
    elif "ma10" in low:
        codec = "HEVC"
    bit = ""
    # 只认视频常见的 8/10/12bit，避免把音轨的 24bit 当成色深
    match = re.search(r"(?<![0-9])(8|10|12)\s*-?\s*bit", low)
    if match:
        bit = "%sbit" % match.group(1)
    elif re.search(r"hi10|ma10", low):
        bit = "10bit"
    return codec, bit


def bit_depth_label(stream: Dict[str, Any]) -> str:
    """推断位深。ffprobe 常不给 bits_per_raw_sample，所以从像素格式推。"""
    raw = to_int(stream.get("bits_per_raw_sample"))
    if raw:
        return "%dbit" % raw
    pix_fmt = str(stream.get("pix_fmt") or "")
    match = re.search(r"p(9|1[0-6])(?:le|be)$", pix_fmt) or re.search(r"^p0?(10|12|16)(?:le|be)$", pix_fmt)
    if match:
        return "%dbit" % int(match.group(1))
    if pix_fmt.startswith(("yuv", "nv", "gray")):
        return "8bit"
    return ""


def dynamic_range_label(stream: Dict[str, Any]) -> str:
    """判断动态范围：杜比视界（带 profile）、HDR10+、HDR10、HLG，否则为 SDR。"""
    side_list: List[Dict[str, Any]] = stream.get("side_data_list") or []
    dovi = None
    hdr10plus = False
    for side in side_list:
        side_type = str(side.get("side_data_type") or "")
        if "DOVI" in side_type.upper():
            dovi = side
        if "2094-40" in side_type or "HDR10+" in side_type:
            hdr10plus = True
    # 命名沿用上游 README 的「动态范围_细分版本」：DolbyVision_Profile8.1 / HDR_HDR10 / HDR_HDR10+ / HDR_HLG
    if dovi is not None:
        profile = to_int(dovi.get("dv_profile"))
        label = "DolbyVision_Profile%d" % profile if profile else "DolbyVision"
        # 只有 profile 8 习惯带子版本号（8.1 / 8.2 / 8.4）
        if profile == 8 and dovi.get("dv_bl_signal_compatibility_id") is not None:
            label += ".%d" % to_int(dovi.get("dv_bl_signal_compatibility_id"))
        return label
    transfer = str(stream.get("color_transfer") or "").lower()
    if hdr10plus:
        return "HDR_HDR10+"
    if transfer == "smpte2084":
        return "HDR_HDR10"
    if transfer == "arib-std-b67":
        return "HDR_HLG"
    return "SDR"


def normalize_effect(text: Any) -> str:
    """把 MP 识别出的特效写法统一成 DolbyVision / HDR_HDR10+ / HDR_HDR10 / HDR_HLG / HDR。"""
    low = str(text or "").lower()
    if re.search(r"dolby\s*vision|dovi|(?<![a-z])dv(?![a-z])", low):
        return "DolbyVision"
    if re.search(r"hdr10\+|hdr10plus", low):
        return "HDR_HDR10+"
    if "hdr10" in low:
        return "HDR_HDR10"
    if "hlg" in low:
        return "HDR_HLG"
    if "hdr" in low:
        return "HDR"
    return ""


def dv_profile_from_name(original_name: Any) -> str:
    """从文件名里找杜比视界 profile（P8.1 / P8 / P7 / P5 / Profile8.1），返回 8.1 这样的写法，找不到返回空。"""
    low = str(original_name or "").lower()
    match = re.search(r"(?<![a-z0-9])(?:p|profile)\s*([5789])(?:\.([0-9]))?(?![0-9])", low)
    if not match:
        return ""
    return match.group(1) + ("." + match.group(2) if match.group(2) else "")


def fps_label(stream: Dict[str, Any]) -> str:
    """只在高帧率时给出标签（60FPS / 120FPS），其余帧率不进文件名。"""
    for key in ("avg_frame_rate", "r_frame_rate"):
        text = str(stream.get(key) or "0/0")
        if "/" in text:
            num, _, den = text.partition("/")
            try:
                fps = float(num) / float(den) if float(den) else 0.0
            except ValueError:
                fps = 0.0
        else:
            try:
                fps = float(text)
            except ValueError:
                fps = 0.0
        if fps <= 0:
            continue
        if abs(fps - 60) <= 1.5:
            return "60FPS"
        if abs(fps - 120) <= 3:
            return "120FPS"
        return ""
    return ""


# ---------------------------------------------------------------- 音频

def audio_codec_label(stream: Dict[str, Any]) -> Tuple[str, bool]:
    """返回（音频编码标签，是否 Atmos）。"""
    name = str(stream.get("codec_name") or "").lower()
    profile = str(stream.get("profile") or "")
    upper = profile.upper()
    atmos = "ATMOS" in upper
    if name == "truehd":
        return "TrueHD", atmos
    if name == "eac3":
        return "DDP", atmos
    if name == "ac3":
        return "DD", False
    if name == "dts":
        # ffprobe 的 profile：DTS / DTS-ES / DTS 96/24 / DTS Express 都算核心 DTS，
        # DTS-HD HRA 是高解析；DTS-HD MA 与 DTS-HD MA + DTS:X 都写 MA
        if re.search(r"\bMA\b", upper) or "DTS:X" in upper or "DTS-X" in upper:
            return DTS_MA, False
        if "HRA" in upper or "DTS-HD" in upper:
            return DTS_HRA, False
        return DTS, False
    if name.startswith("pcm_"):
        return "PCM", False
    labels = {"flac": "FLAC", "aac": "AAC", "opus": "OPUS", "mp3": "MP3"}
    return labels.get(name, name.upper()), False


# (正则, 统一写法)，按顺序匹配，匹配到的片段会被抹掉，避免短写法在长写法里重复命中
_AUDIO_RULES = [
    (r"truehd", "TrueHD"),
    # 文件名写 DTS-X / DTS:X 的归入 MA；x 后面不能是字母数字，避免把 DTS.x264 认成 DTS:X
    (r"dts[\s\-._:]*x(?![0-9a-z])", DTS_MA),
    (r"dts[\s\-._]*hd[\s\-._]*(?:ma|master)", DTS_MA),
    (r"dts[\s\-._]*hd[\s\-._]*hra", DTS_HRA),
    (r"dts[\s\-._]*hd", DTS_HRA),
    (r"dts", DTS),
    (r"e[\s\-._]?ac[\s\-._]?3|ddp|dd\+", "DDP"),
    (r"(?<![a-z])(?:ac[\s\-._]?3|dd)(?![a-z+])", "DD"),
    (r"flac", "FLAC"),
    (r"opus", "OPUS"),
    (r"aac", "AAC"),
    (r"l?pcm", "PCM"),
    (r"mp3", "MP3"),
]


def normalize_audio(text: Any) -> Tuple[str, str, bool]:
    """把 MP 识别出的音频写法统一，返回（编码, 声道, 是否 Atmos）。多个编码用 & 连接，如 DDP&AAC。"""
    low = str(text or "").lower()
    work = low
    labels: List[str] = []
    for pattern, label in _AUDIO_RULES:
        match = re.search(pattern, work)
        if match:
            if label not in labels:
                labels.append(label)
            work = work[:match.start()] + " " * (match.end() - match.start()) + work[match.end():]
    # 只排除「数字.」开头的情况（如 1.5.1 这类版本号），不排除前面是字母加点的写法（DTS-HD.MA.7.1）
    channel = re.search(r"(?<![0-9])(?<![0-9]\.)([1-9])\.([0-2])(?![0-9])", low)
    return join_audio(labels), channel.group(0) if channel else "", "atmos" in low


def _audio_pool(streams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """全部音轨中排除评论音轨；如果只有评论音轨，就用全部音轨。"""
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    normal = [s for s in audios if not _COMMENTARY_RE.search(str((s.get("tags") or {}).get("title") or ""))]
    return normal or audios


def pick_audio_stream(streams: List[Dict[str, Any]], mode: str = "best") -> Optional[Dict[str, Any]]:
    """选一条主音轨（决定声道数和 Atmos）。default 取默认音轨，其余模式取档次最高的。评论音轨始终排除。"""
    pool = _audio_pool(streams)
    if not pool:
        return None
    if mode == "default":
        for stream in pool:
            if (stream.get("disposition") or {}).get("default") == 1:
                return stream
        return pool[0]

    def score(item: Tuple[int, Dict[str, Any]]) -> Tuple[int, int, int]:
        """排序键：档次（含 Atmos 加成）、声道数、靠前优先。"""
        index, stream = item
        label, atmos = audio_codec_label(stream)
        return (_AUDIO_RANK.get(label, 10) + (5 if atmos else 0), to_int(stream.get("channels")), -index)

    return max(enumerate(pool), key=score)[1]


def channel_label(stream: Dict[str, Any]) -> str:
    """按声道数给出 7.1 / 5.1 / 2.0 这样的写法。"""
    return _CHANNEL_LABELS.get(to_int(stream.get("channels")), "")


def audio_piece(codec: str, channels: str, atmos: bool, with_channels: bool = True) -> str:
    """拼音频段，沿用上游 README 的「音频编码_声道数ch.Atmos」，例如 TrueHD_7.1ch.Atmos；无声道时只有编码。"""
    text = codec or ""
    if text and with_channels and channels:
        text = "%s_%sch" % (text, channels)
    if atmos:
        text = "%s.Atmos" % text if text else "Atmos"
    return text


def extra_tags(original_name: Any, fps_tag: str = "", trust_fps: bool = False) -> str:
    """额外参数：3D / IMAX / 60FPS / 120FPS。trust_fps 为真时帧率只信 ffprobe，不看文件名里的 60fps 字样。"""
    low = str(original_name or "").lower()
    wanted = ("3d", "imax") if trust_fps else ("3d", "imax", "60fps", "120fps")
    found = [t.upper() for t in wanted if re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % t, low)]
    if fps_tag and fps_tag not in found:
        found.append(fps_tag)
    order = {"3D": 0, "IMAX": 1, "60FPS": 2, "120FPS": 3}
    return " ".join(sorted(set(found), key=lambda x: order.get(x, 9)))


def parse_ffprobe(data: Dict[str, Any], audio_mode: str = "best") -> Dict[str, str]:
    """把 ffprobe 的 JSON 解析成命名字段，只返回非空值。"""
    streams: List[Dict[str, Any]] = data.get("streams") or []
    fields: Dict[str, str] = {}
    video = next(
        (s for s in streams if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")),
        None,
    )
    if video:
        fields["ffRes"] = resolution_label(to_int(video.get("width")), to_int(video.get("height")))
        fields["ffVideo"] = video_codec_label(video)
        fields["ffBit"] = bit_depth_label(video)
        fields["ffDR"] = dynamic_range_label(video)
        fields["ffFps"] = fps_label(video)
    audio = pick_audio_stream(streams, audio_mode)
    if audio:
        codec, atmos = audio_codec_label(audio)
        channels = channel_label(audio)
        # 多音轨：与主音轨同语言（或没标语言）的非评论音轨，编码去重后用 & 连接，如 AAC&FLAC
        main_lang = str((audio.get("tags") or {}).get("language") or "").lower()
        same = [s for s in _audio_pool(streams)
                if not main_lang or str((s.get("tags") or {}).get("language") or "").lower() in ("", main_lang)]
        all_codecs = join_audio([audio_codec_label(s)[0] for s in same]) or codec
        fields["ffAudioCodec"] = codec
        fields["ffAudioAll"] = all_codecs
        # 全部音轨（含评论、其他语言）的编码，对应 V2 日番模板按文件名列出全部音轨的做法，如 VCB 的 FLAC + 2AAC
        fields["ffAudioEvery"] = join_audio(
            [audio_codec_label(s)[0] for s in streams if s.get("codec_type") == "audio"]
        ) or all_codecs
        fields["ffChannels"] = channels
        fields["ffAtmos"] = "Atmos" if atmos else ""
        fields["ffAudio"] = audio_piece(codec, channels, atmos, True)
        fields["ffAudioNoCh"] = audio_piece(all_codecs, channels, atmos, False)
    fields["ffSub"] = subtitle_label(streams)
    if embedded_remux(data):
        fields["ffRemux"] = "1"
    return {k: v for k, v in fields.items() if v}


def embedded_remux(data: Dict[str, Any]) -> bool:
    """容器标题或视频轨标题里注明了 Remux（很多 Remux 只在内嵌标题里写，文件名不写）。"""
    titles = [str(((data.get("format") or {}).get("tags") or {}).get("title") or "")]
    for stream in data.get("streams") or []:
        if stream.get("codec_type") == "video":
            titles.append(str((stream.get("tags") or {}).get("title") or ""))
    return any(re.search(r"remux", t, re.I) for t in titles)


# ---------------------------------------------------------------- 字幕

# 字幕语言的输出顺序；不在表里的语言不写进 ffSub，避免多语种原盘把文件名撑得过长
_SUB_ORDER = ["CHS", "CHT", "CHI", "JPN", "ENG", "KOR"]
_SUB_LANG = {"chi": "CHI", "zho": "CHI", "zh": "CHI", "jpn": "JPN", "ja": "JPN", "eng": "ENG", "en": "ENG",
             "kor": "KOR", "ko": "KOR"}


def subtitle_lang(stream: Dict[str, Any]) -> str:
    """判断一条字幕轨的语言：中文按标题细分简/繁，没标语言时从标题推断。"""
    tags = stream.get("tags") or {}
    title = str(tags.get("title") or "").lower()
    lang = _SUB_LANG.get(str(tags.get("language") or "").lower(), "")
    simp = re.search(r"简|簡|simplified|(?<![a-z])(?:chs|sc|gb)(?![a-z])", title)
    trad = re.search(r"繁|traditional|(?<![a-z])(?:cht|tc|big5)(?![a-z])", title)
    if not lang:
        if simp or trad or "中" in title or "chinese" in title:
            lang = "CHI"
        elif re.search(r"日本語|日语|japanese", title):
            lang = "JPN"
        elif re.search(r"english|英语", title):
            lang = "ENG"
        elif re.search(r"korean|韩语|한국어", title):
            lang = "KOR"
    if lang == "CHI":
        if simp and not trad:
            return "CHS"
        if trad and not simp:
            return "CHT"
    return lang


def subtitle_label(streams: List[Dict[str, Any]]) -> str:
    """内封字幕语言，如 CHS&CHT&JPN。强制字幕（只翻外语对白）不算；已细分出简/繁时不再写笼统的 CHI。"""
    langs = []
    for stream in streams:
        if stream.get("codec_type") != "subtitle":
            continue
        title = str((stream.get("tags") or {}).get("title") or "")
        if (stream.get("disposition") or {}).get("forced") == 1 or re.search(r"forced|强制", title, re.I):
            continue
        lang = subtitle_lang(stream)
        if lang in _SUB_ORDER and lang not in langs:
            langs.append(lang)
    if "CHI" in langs and ("CHS" in langs or "CHT" in langs):
        langs.remove("CHI")
    return "&".join(sorted(langs, key=_SUB_ORDER.index))


# ---------------------------------------------------------------- 发行组（从文件名识别）

_VIDEO_EXTS = (
    "mkv|mp4|m2ts|ts|avi|wmv|mov|rmvb|flv|webm|iso|ass|ssa|srt|sup|sub|nfo|jpg|png"
)
_EXT_RE = re.compile(r"\.(?:%s)$" % _VIDEO_EXTS, re.I)
# 文件名里出现这些词，才相信末尾那一段是发行组（避免把 Spider-Man 的 Man 当成发行组）
_TECH_MARK = re.compile(
    r"(?<![a-z0-9])(?:480p|576p|720p|1080[pi]|2160p|4320p|[248]k|uhd|blu-?ray|bdrip|bd|web-?dl|webrip|web|hdtv|"
    r"dvdrip|remux|x\.?26[45]|h\.?26[45]|hevc|avc)(?![a-z0-9])",
    re.I,
)
_NOT_GROUP_RE = re.compile(
    r"^(?:\d{3,4}[pi]|[248]k|\d+bit|s\d{1,2}(?:e\d{1,3})*|e\d{1,3}|ep\d{1,3}|ova\d*|oad\d*|sp\d*|v\d|\d+(?:\.\d+)*)$",
    re.I,
)
_NOT_GROUP_WORDS = frozenset(
    "bdmv bdrip bd dvd dvdrip web webrip web-dl webdl bluray blu-ray remux uhd hdtv hevc avc x264 x265 h264 h265 "
    "hdr dv sdr aac flac ddp dd dts atmos truehd pcm opus mkv mp4 chs cht gb big5 jpn eng chi dl rip hd ma hra "
    "proper repack extended complete "
    "bilibili netflix nf amzn atvp hulu hbo baha cr abema friday itunes "
    "4khdr世界".split()
)
# 网站广告、发布站标记，不是发行组
_AD_RE = re.compile(r"www\.|\.com|\.net|\.org|\.cc|发布|高清|影视|更多|下载|访问|论坛", re.I)


def tech_region(original_name: Any) -> str:
    """文件名从第一个技术标记（分辨率、片源、编码等）开始的部分，避开片名里的单词；没有技术标记返回空。"""
    stem = _EXT_RE.sub("", str(original_name or ""))
    mark = _TECH_MARK.search(stem)
    return stem[mark.start():] if mark else ""


def _group_key(text: Any) -> str:
    """发行组比较用的键：去空白、小写、@ 视为 &。"""
    return re.sub(r"\s+", "", str(text or "").replace("@", "&")).lower()


class GroupBook:
    """已知发行组表：负责统一拼写，以及识别位置不固定的「-组名」「.别名」写法。"""

    def __init__(self, text: str) -> None:
        """解析发行组文本，每行一个规范拼写，或 别名=规范名。"""
        self.canon: Dict[str, str] = {}
        self.suffixes: List[Tuple["re.Pattern[str]", str]] = []
        entries: List[Tuple[str, str]] = []
        for line in (text or "").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                alias, _, name = line.partition("=")
                alias, name = alias.strip().replace("@", "&"), name.strip().replace("@", "&")
                if alias and name:
                    entries.append((alias, name))
            else:
                name = line.replace("@", "&")
                entries.append((name, name))
        for match_text, name in entries:
            self.canon[_group_key(match_text)] = name
        for match_text, name in sorted(entries, key=lambda e: -len(e[0])):
            pattern = re.escape(match_text).replace("\\ ", r"\s+")
            self.suffixes.append((re.compile(r"(?<![0-9A-Za-z])" + pattern + r"$", re.I), name))

    def lookup(self, raw: Any) -> str:
        """按规范表返回统一拼写，不在表里返回空。"""
        return self.canon.get(_group_key(raw), "")


def normalize_group(raw: Any, book: GroupBook) -> str:
    """把候选发行组清洗成统一写法。看起来是技术词、集号、网站广告的返回空。"""
    text = str(raw or "").replace("@", "&").strip(" .-_　")
    text = re.sub(r"\s*&\s*", "&", text)
    # 重复下载产生的 (1) 后缀、结尾的语言标记（.ZH / .CHS 等）都不属于组名
    text = re.sub(r"\(\d+\)$", "", text).strip(" .-_")
    text = re.sub(r"\.(?:zh|chs|cht|cn|jp|jpn|en|eng)$", "", text, flags=re.I).strip(" .-_")
    if len(text) < 2 or len(text) > 40 or _AD_RE.search(text):
        return ""
    low = text.lower()
    for part in re.split(r"[&.]", low):
        if part and (part in _NOT_GROUP_WORDS or _NOT_GROUP_RE.match(part)):
            return ""
    if not re.search(r"[a-z一-鿿]", low):
        return ""
    known = book.lookup(text)
    if known:
        return known
    # 联合发布（DMG&VCB-Studio）整体不在表里时，逐个成员统一拼写后再用 & 合并，成员顺序保持原样
    if "&" in text:
        return "&".join(book.lookup(part) or part for part in text.split("&") if part)
    return text


def extract_group(filename: str, book: GroupBook) -> str:
    """从文件名识别发行组，识别不出返回空。依次尝试：开头的 [组名]、结尾的 [已知组]、
    已知组/别名后缀、结尾的 - 组名（要求前面出现过分辨率、片源、编码等技术词）。"""
    stem = _EXT_RE.sub("", str(filename or "").strip()).replace("@", "&")
    if not stem:
        return ""
    lead = re.match(r"\s*(?:\[([^\[\]]{1,60})\]|【([^【】]{1,60})】)", stem)
    if lead:
        name = lead.group(1) or lead.group(2)
        # 点号风格的发布名里，开头的 [中文片名].Title.2013... 是片名，不是发行组；已知组例外
        is_title = stem[lead.end():lead.end() + 1] == "." and not book.lookup(name)
        group = "" if is_title else normalize_group(name, book)
        if group:
            return group
    tail = re.search(r"\[([^\[\]]{1,40})\]\s*$", stem)
    if tail:
        known = book.lookup(tail.group(1))
        if known:
            return known
    body = stem
    while True:
        match = re.search(r"\s*\[[^\[\]]*\]\s*$", body)
        if not match:
            break
        body = body[:match.start()]
    if not body:
        return ""
    for pattern, name in book.suffixes:
        match = pattern.search(body)
        if match and _TECH_MARK.search(body[:match.start()]):
            return name
    match = re.search(r"(?:\s+-\s+|[-￡£])([^\s\-￡£\[\]]{2,40})\s*$", body)
    if match and _TECH_MARK.search(body[:match.start()]):
        return normalize_group(match.group(1), book)
    return ""


# ---------------------------------------------------------------- 片源版本

def _plat_norm(text: Any) -> str:
    """平台匹配用的归一化：小写，除字母数字、加号、汉字外的符号都当作分隔，折叠空白。"""
    low = re.sub(r"[^0-9a-z+一-鿿\s]+", " ", str(text or "").lower())
    return re.sub(r"\s+", " ", low).strip()


class PlatformBook:
    """流媒体平台表：从文件名找平台，并把 MP 识别出的平台名统一成同一种写法。"""

    def __init__(self, text: str) -> None:
        """解析 统一名=别名1,别名2 的文本，统一名本身也算别名。"""
        self.entries: List[Tuple[str, List[str]]] = []
        self.index: Dict[str, str] = {}
        for line in (text or "").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, aliases = line.partition("=")
            name = name.strip()
            alias_list = [_plat_norm(a) for a in aliases.split(",") if a.strip()] + [_plat_norm(name)]
            alias_list = [a for a in dict.fromkeys(alias_list) if a]
            if not name or not alias_list:
                continue
            self.entries.append((name, alias_list))
            for alias in alias_list:
                self.index.setdefault(alias, name)

    def find(self, original_name: str) -> str:
        """在文件名第一个技术标记（分辨率、片源、编码等）之后的部分里找平台，取出现最早的一个。"""
        tech = tech_region(original_name)
        if not tech:
            return ""
        region = " %s " % _plat_norm(tech)
        best, best_pos = "", len(region) + 1
        for name, aliases in self.entries:
            for alias in aliases:
                pos = region.find(" %s " % alias)
                if 0 <= pos < best_pos:
                    best, best_pos = name, pos
        return best

    def unify(self, mp_web: Any) -> str:
        """把 MP 识别出的平台名统一成表里的写法，不在表里的原样返回。"""
        raw = str(mp_web or "").strip()
        return self.index.get(_plat_norm(raw), raw) if raw else ""


def platform_label(base: Dict[str, Any], book: Optional[PlatformBook]) -> str:
    """得到平台：文件名里找到的优先，找不到再用 MP 识别的值（经统一表改写）。"""
    if book is None:
        return str(base.get("webSource") or "").strip()
    return book.find(str(base.get("original_name") or "")) or book.unify(base.get("webSource"))


def resolve_group(base: Dict[str, Any], book: GroupBook) -> str:
    """得到最终发行组：先从完整原文件名识别，识别不出再统一 MP 已识别的值。"""
    group = extract_group(str(base.get("original_name") or ""), book)
    return group or normalize_group(base.get("releaseGroup"), book)


def parse_group_map(text: str) -> Dict[str, Tuple[str, bool]]:
    """解析发行组映射文本，返回 {发行组: (片源版本, 是否强制覆盖)}。"""
    result: Dict[str, Tuple[str, bool]] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip().lower(), value.strip()
        force = value.endswith("!")
        value = value.rstrip("!").strip()
        if key and value:
            result[key] = (value, force)
    return result


def parse_edition_map(text: str) -> Dict[str, str]:
    """解析片源写法统一表，返回 {小写写法: 统一写法}。"""
    result: Dict[str, str] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = re.sub(r"\s+", " ", key.strip().lower()), value.strip()
        if key and value:
            result[key] = value
    return result


def normalize_edition(label: str, edition_map: Optional[Dict[str, str]]) -> str:
    """按统一表改写片源写法，表里没有的原样返回。"""
    if not label or not edition_map:
        return label
    return edition_map.get(re.sub(r"\s+", " ", label.strip().lower()), label)


BDMV_EDITION = "BluRay"
REMUX_EDITION = "BluRay-Remux"


def is_remux(base: Dict[str, Any]) -> bool:
    """文件名、MP 识别的片源或内嵌标题（isRemux）里任一处注明 Remux（含 BDRemux）即视为 Remux。"""
    text = "%s %s" % (base.get("original_name") or "", base.get("resourceType") or "")
    return bool(base.get("isRemux")) or bool(re.search(r"remux", text, re.I))


# 文件名自身写明的片源家族：MP 有时从上层目录名解析片源（如 [BluRay&DVD ...] 目录下的 DVD 文件），
# 文件名里明确写了且只写了一个家族时以文件名为准。Web 只认 WEB-DL / WebRip 这类明确写法，避免片名里的 Web。
_NAME_SOURCES = [
    (re.compile(r"(?<![a-z0-9])(?:blu-?ray|bdrip|brrip|bd)(?![a-z0-9])", re.I), "BluRay-Rip"),
    (re.compile(r"(?<![a-z0-9])(?:web-?dl|web-?rip)(?![a-z0-9])", re.I), "Web-Rip"),
    (re.compile(r"(?<![a-z0-9])(?:dvd(?:rip|-rip|5|9)?)(?![a-z0-9])", re.I), "DVD-Rip"),
    (re.compile(r"(?<![a-z0-9])(?:hdtv(?:rip|-rip)?)(?![a-z0-9])", re.I), "HDTV-Rip"),
]


def name_source(original_name: Any) -> str:
    """文件名里明确写了且只写了一个片源家族时返回统一写法，没写或写了多个返回空。"""
    stem = _EXT_RE.sub("", str(original_name or ""))
    found = {label for pattern, label in _NAME_SOURCES if pattern.search(stem)}
    return found.pop() if len(found) == 1 else ""


def edition_label(
    base: Dict[str, Any],
    group_map: Dict[str, Tuple[str, bool]],
    edition_map: Optional[Dict[str, str]] = None,
) -> str:
    """推断片源版本，优先级：BDMV 原盘 → Remux → 发行组强制映射 → 文件名写明的片源
    → MP 识别值（经统一表改写）→ 发行组普通映射。发行组按整词匹配，避免 CheeseAni 被误判成 ANi。"""
    if base.get("isBDMV"):
        return BDMV_EDITION
    if is_remux(base):
        return REMUX_EDITION
    group = str(base.get("releaseGroup") or "").strip().lower()
    tokens = {t.strip() for t in re.split(r"[&/,@]", group) if t.strip()}
    if group:
        tokens.add(group)
    matched = [(label, force) for key, (label, force) in group_map.items() if key in tokens]
    for label, force in matched:
        if force:
            return label
    resource_type = name_source(base.get("original_name")) or normalize_edition(
        str(base.get("resourceType") or "").strip(), edition_map
    )
    if not resource_type and matched:
        return matched[0][0]
    return resource_type


# out 的音频写法：main 只写主音轨并带声道和 Atmos（电影、剧集）；all 写全部音轨编码、不带声道（日番、国漫）
AUDIO_MODES = ("main", "all")
# out 的动态范围写法：none 不写；hdr 只写 HDR/杜比视界；all 连 SDR 也写（V2 只有华语/外语电影这样做）
DR_MODES = ("none", "hdr", "all")
# 只有这些位深写进文件名，8bit 是默认值不写
_SHOWN_BITS = ("10bit", "12bit")


def tech_parts(
    ff: Dict[str, str],
    base: Dict[str, Any],
    group_map: Dict[str, Tuple[str, bool]],
    res_upper: bool = True,
    res_4k_label: bool = True,
    edition_map: Optional[Dict[str, str]] = None,
    platform_book: Optional[PlatformBook] = None,
) -> Dict[str, str]:
    """算出 out 的各个组成部分（同时作为模板变量暴露）。
    ffprobe 字段缺失时，用 MP 从文件名解析出的值兜底，兜底值同样先统一写法。"""
    res = resolution_display(ff.get("ffRes") or normalize_pix(base.get("videoFormat")), res_upper, res_4k_label)
    edition = edition_label(base, group_map, edition_map)
    web = platform_label(base, platform_book)
    # 平台只跟在 Web 系片源后面，BluRay 之类的片源不带平台
    source = edition
    if edition and web and "web" in edition.lower() and web.lower() not in edition.lower():
        source = "%s.%s" % (edition, web)
    region = tech_region(base.get("original_name"))
    codec, bit = ff.get("ffVideo", ""), ff.get("ffBit", "")
    if not codec:
        # MP 认不出 HEVC-10bit / x265-10Bit / AVC-8bit 这类连写时，再从文件名的技术信息部分找
        codec, name_bit = normalize_codec(base.get("videoCodec"))
        region_codec, region_bit = normalize_codec(region)
        codec = codec or region_codec or str(base.get("videoCodec") or "")
        bit = (bit or name_bit or normalize_codec(base.get("videoBit"))[1] or region_bit)
        # VCB 系的 [Ma10p_1080p] 写在分辨率前面，不在技术信息部分里；Ma10p / Hi10p 不会出现在片名里，可以全名找
        if not bit and re.search(r"(?<![a-z0-9])(?:ma10p|hi10p)", str(base.get("original_name") or ""), re.I):
            bit = "10bit"
    if codec and bit:
        # MP 兜底的编码有时自带位深（HEVC 10bit），统一拆出来，避免 HEVC_10bit_10bit
        codec = re.sub(r"[\s_\-.]*(?:8|10|12)\s*-?\s*bit", "", codec, flags=re.I).strip() or codec
    shown_bit = bit if bit.lower() in _SHOWN_BITS else ""
    video = "%s_%s" % (codec, shown_bit) if codec and shown_bit else codec
    if ff.get("ffAudioCodec"):
        a_codec, a_channels, a_atmos = ff["ffAudioCodec"], ff.get("ffChannels", ""), bool(ff.get("ffAtmos"))
        a_every = ff.get("ffAudioEvery") or ff.get("ffAudioAll") or a_codec
    else:
        a_codec, a_channels, a_atmos = normalize_audio(base.get("audioCodec"))
        # MP 只取第一个音频编码（x265_flac_2aac 只给 flac），全部音轨要把文件名里列出的都带上
        a_every = join_audio(a_codec.split("&") + normalize_audio(region)[0].split("&"))
        if not a_codec:
            a_codec = re.sub(r"atmos", "", str(base.get("audioCodec") or ""), flags=re.I).strip()
            a_every = a_every or a_codec
    dr = ff.get("ffDR") or normalize_effect(base.get("effect"))
    if dr == "DolbyVision":
        # ffprobe 没给出 profile 或者只能靠文件名时，从 DoVi.P8.1 这类写法补上细分版本
        profile = dv_profile_from_name(base.get("original_name"))
        if profile:
            dr = "DolbyVision_Profile%s" % profile
    # 与 V2 模板一致：没有任何 HDR / 杜比视界标记就是 SDR，是否写出由分类规则的 dr 决定
    dr = dr or "SDR"
    extras = extra_tags(base.get("original_name"), ff.get("ffFps", ""), trust_fps=bool(ff.get("ffRes")))
    return {
        "resolution": res,
        "edition": edition,
        "platform": web if source != edition else "",
        "source": source,
        "video_codec": codec,
        "bit_depth": bit,
        "video": video,
        "audio_codec": a_codec,
        "audio_codecs": a_every,
        "channels": a_channels,
        "atmos": "Atmos" if a_atmos else "",
        "audio": audio_piece(a_codec, a_channels, a_atmos, True),
        "dynamic_range": dr,
        "extra": extras,
    }


def assemble_out(parts: Dict[str, str], audio: str = "main", dr: str = "hdr", extra: bool = True) -> str:
    """按分类规则把 tech_parts 拼成 out，顺序是 分辨率 片源.平台 编码_位深 音频 动态范围 额外参数。"""
    audio_text = parts.get("audio_codecs", "") if audio == "all" else parts.get("audio", "")
    dr_text = parts.get("dynamic_range", "")
    if dr == "none" or (dr == "hdr" and dr_text == "SDR"):
        dr_text = ""
    pieces = [parts.get("resolution"), parts.get("source"), parts.get("video"), audio_text, dr_text,
              parts.get("extra") if extra else ""]
    return " ".join(p for p in pieces if p)


def build_out(
    ff: Dict[str, str],
    base: Dict[str, Any],
    group_map: Dict[str, Tuple[str, bool]],
    audio: str = "main",
    dr: str = "hdr",
    extra: bool = True,
    **options: Any,
) -> str:
    """tech_parts + assemble_out 的便捷组合，options 透传给 tech_parts。"""
    return assemble_out(tech_parts(ff, base, group_map, **options), audio, dr, extra)


def run_ffprobe(path: str, ffprobe_path: str = "ffprobe", timeout: int = 30) -> Optional[Dict[str, Any]]:
    """调用 ffprobe 读取文件头，失败或超时返回 None。路径作为参数列表传入，不经过 shell。"""
    try:
        done = subprocess.run(
            [ffprobe_path, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", "-i", path],
            capture_output=True,
            timeout=timeout,
            check=True,
        )
        return json.loads(done.stdout.decode("utf-8", "replace"))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
