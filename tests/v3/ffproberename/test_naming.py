"""分类规则、路径渲染与两个整理事件的离线回归。"""
import pytest
from types import SimpleNamespace
from app.plugins.ffproberename import naming

class TestRuleParse:
    """规则文本解析。"""

    def test_default_rules_cover_all_v3_categories(self):
        """默认规则覆盖 V3 默认分类策略里的全部电影、剧集分类。"""
        rules = naming.parse_rules(naming.DEFAULT_RULES)
        for name in ('日番', '国漫', '其他动画', '华语电影', '外语电影', '动画电影', '国产剧', '欧美剧', '亚洲剧', '纪录片', '综艺', '儿童', '电影/未分类', '电视剧/未分类'):
            assert name in rules, name
        assert (rules['日番'].audio, rules['日番'].dr, rules['日番'].extra) == ('all', 'none', False)
        assert (rules['华语电影'].audio, rules['华语电影'].dr) == ('main', 'all')
        assert rules['动画电影'].dr == 'hdr'
        assert '\n' not in rules['日番'].template

    def test_multiline_template_joined(self):
        """续行去掉首尾空白后直接拼接。"""
        rules = naming.parse_rules('[a]\ntemplate = {{ title }}/\n    {{ title }}{{ fileExt }}\n')
        assert rules['a'].template == '{{ title }}/{{ title }}{{ fileExt }}'

    def test_errors(self):
        """缺模板、非法取值、重复分类都报错。"""
        for text in ('[a]\naudio = main\n', '[a]\naudio = x\ntemplate = t\n', '[a]\ndr = x\ntemplate = t\n', '[a]\nextra = maybe\ntemplate = t\n', '[a|b]\ntemplate = t\n[b]\ntemplate = t\n', 'no section'):
            with pytest.raises(naming.RuleError):
                naming.parse_rules(text)

    def test_find_rule_order(self):
        """分类 ID 优先，其次 类型/名称，最后名称；两个「未分类」靠类型区分。"""
        rules = naming.parse_rules(naming.DEFAULT_RULES)
        assert naming.find_rule(rules, 'tv.dongman.jp', '日番', '电视剧').name == '日番|国漫|其他动画'
        assert '华语电影' in naming.find_rule(rules, None, '未分类', '电影').name
        assert '国产剧' in naming.find_rule(rules, None, '未分类', '电视剧').name
        assert naming.find_rule(rules, 'music.album', 'Album', '音乐') is None
        custom = naming.parse_rules('[tv.dongman.jp]\ntemplate = x\n[日番]\ntemplate = y\n')
        assert naming.find_rule(custom, 'tv.dongman.jp', '日番', '电视剧').template == 'x'

class TestHelper:
    """标题去重、英文优先、路径清理。"""

    def test_unique_titles(self):
        """空值和重复（忽略大小写、空白、全角半角）都去掉。"""
        assert naming.unique_titles(['夜王', 'Night King', None, ' night  king ']) == ['夜王', 'Night King']
        assert naming.unique_titles(['活着', '活着', 'To Live']) == ['活着', 'To Live']
        assert naming.unique_titles(['K-ON！', 'K-ON!']) == ['K-ON！']

    def test_prefer_english(self):
        """命中关键词时 title 换成英文标题，不改原字典。"""
        ctx = {'title': '迷途之子!!!!!', 'en_title': "BanG Dream! It's MyGO!!!!!", 'original_title': "BanG Dream! It's MyGO!!!!!"}
        out = naming.prefer_english(ctx, ['BanG Dream!'])
        assert out['title'] == "BanG Dream! It's MyGO!!!!!"
        assert ctx['title'] == '迷途之子!!!!!'
        assert naming.prefer_english({'title': '夜王', 'en_title': 'Night King'}, ['BanG Dream!'])['title'] == '夜王'
        assert naming.prefer_english({'title': 'BanG Dream!'}, ['BanG Dream!'])['title'] == 'BanG Dream!'

    def test_sanitize(self):
        """非法字符换全角，折叠空白，段尾的点去掉，空段判无效。"""
        assert naming.sanitize_path('A  B (2020)/A - 4K DTS:X.mkv') == 'A B (2020)/A - 4K DTS：X.mkv'
        assert naming.sanitize_path('Title./x.mkv') == 'Title/x.mkv'
        assert naming.sanitize_path(' (2020)/ /x.mkv') == ''

    def test_depth(self):
        """资料夹层数按 / 计数。"""
        assert naming.path_depth('{{title}}/{{title}}{{fileExt}}') == 1
        assert naming.path_depth('a/Season 1/b.mkv') == 2

class TestRender:
    """渲染与长度回退。"""
    RULES = naming.parse_rules(naming.DEFAULT_RULES)

    def render(self, category, ctx, max_length=180):
        """按分类名渲染。"""
        return naming.Renderer(max_length).render(self.RULES[category], ctx)

    def test_movie(self):
        """华语电影：中文 _ 英文 (年)，out 和发行组。"""
        ctx = {'title': '活着', 'en_title': 'To Live', 'original_title': '活着', 'year': '1994', 'fileExt': '.mkv', 'ffprobe': {'out': '1080P BluRay-Remux AVC PCM_2.0ch SDR', 'group': 'QSD&CMCT'}}
        assert self.render('华语电影', ctx) == '活着 _ To Live (1994)/活着 - 1080P BluRay-Remux AVC PCM_2.0ch SDR - QSD&CMCT.mkv'

    def test_missing_en_title_no_dangling_separator(self):
        """英文标题缺失时不留「 _  」。"""
        ctx = {'title': '夜王', 'year': '2026', 'fileExt': '.mkv', 'ffprobe': {'out': '1080P'}}
        assert self.render('华语电影', ctx) == '夜王 (2026)/夜王 - 1080P.mkv'

    def test_documentary_typo_fixed(self):
        """纪录片 / 综艺不再出现 V2 的「 _ (年)」。"""
        ctx = {'title': '地球脉动', 'en_title': 'Planet Earth', 'year': '2006', 'season': 1, 'season_episode': 'S01E01', 'fileExt': '.mkv', 'ffprobe': {'out': '1080P'}}
        assert self.render('纪录片', ctx) == '地球脉动 _ Planet Earth (2006)/Season 1/地球脉动 - S01E01 - 1080P.mkv'

    def test_anime_three_titles(self):
        """日番：中文 _ 英文 _ 原文。"""
        ctx = {'title': '孤独摇滚！', 'en_title': 'BOCCHI THE ROCK!', 'original_title': 'ぼっち・ざ・ろっく！', 'year': '2022', 'season': 1, 'season_episode': 'S01E01', 'fileExt': '.mkv', 'ffprobe': {'out': '1080P BluRay-Rip HEVC_10bit FLAC', 'group': 'DMG&VCB-Studio'}}
        assert self.render('日番', ctx) == '孤独摇滚！ _ BOCCHI THE ROCK! _ ぼっち・ざ・ろっく！ (2022)/Season 1/孤独摇滚！ - S01E01 - 1080P BluRay-Rip HEVC_10bit FLAC - DMG&VCB-Studio.mkv'

    def test_length_fallback(self):
        """超过长度上限时标题段只留第一个标题，文件名不变。"""
        ctx = {'title': '甲' * 40, 'en_title': 'B' * 80, 'original_title': 'C' * 80, 'year': '2020', 'season': 1, 'season_episode': 'S01E01', 'fileExt': '.mkv', 'ffprobe': {'out': '1080P'}}
        assert self.render('日番', ctx) == '%s (2020)/Season 1/%s - S01E01 - 1080P.mkv' % ('甲' * 40, '甲' * 40)

    def test_empty_title_invalid(self):
        """没有标题时判为无效，交回 MP 命名。"""
        assert self.render('华语电影', {'fileExt': '.mkv', 'ffprobe': {'out': ''}}) == ''
        assert self.render('华语电影', {'title': ' ', 'year': '2020', 'fileExt': '.mkv'}) == ''

    def test_part_suffix(self):
        """分段文件在扩展名前加 -分段，没有分段时不加。"""
        ctx = {'title': '活着', 'en_title': 'To Live', 'year': '1994', 'fileExt': '.mkv', 'part': 'CD2', 'ffprobe': {'out': '480P DVD-Rip AVC', 'group': 'GRP'}}
        assert self.render('华语电影', ctx) == '活着 _ To Live (1994)/活着 - 480P DVD-Rip AVC - GRP-CD2.mkv'
        ctx = {'title': '孤独摇滚！', 'year': '2022', 'season': 1, 'season_episode': 'S01E01', 'fileExt': '.mkv', 'part': 'Part1', 'ffprobe': {'out': '1080P'}}
        assert self.render('日番', ctx) == '孤独摇滚！ (2022)/Season 1/孤独摇滚！ - S01E01 - 1080P-Part1.mkv'

    def test_part_without_number_ignored(self):
        """MP 把不带编号的 DVD / CD / PART 也认成分段，这类不写进文件名。"""
        for part, want in [('DVD', ''), ('CD', ''), ('PART', ''), ('DVD1', 'DVD1'), ('CD2', 'CD2'), ('PartB', 'PartB'), ('Disc 2', 'Disc 2'), (None, '')]:
            assert naming.clean_part(part) == want, part
        ctx = {'title': 'CLANNAD 剧场版', 'year': '2007', 'fileExt': '.mkv', 'part': 'DVD', 'ffprobe': {'out': '480P DVD-Rip'}}
        assert self.render('动画电影', ctx) == 'CLANNAD 剧场版 (2007)/CLANNAD 剧场版 - 480P DVD-Rip.mkv'

    def test_missing_year_drops_empty_brackets(self):
        """年份缺失时不留空括号。"""
        ctx = {'title': '夜王', 'en_title': 'Night King', 'fileExt': '.mkv', 'ffprobe': {'out': '1080P'}}
        assert self.render('华语电影', ctx) == '夜王 _ Night King/夜王 - 1080P.mkv'

class TestPlugin:
    """两个事件串起来的端到端行为（无源文件，即重命名预览场景）。"""
    MOVIE_FMT = '{{title}}{% if year %} ({{year}}){% endif %}/{{title}}{{fileExt}}'
    TV_FMT = '{{title}}{% if year %} ({{year}}){% endif %}/Season {{season}}/{{title}} - {{season_episode}}{{fileExt}}'

    @pytest.fixture(autouse=True)
    def plugin_instance(self):
        """Create fresh state for each event integration case."""
        from app.plugins.ffproberename import FfprobeRename
        self.plugin = FfprobeRename()
        self.plugin.init_plugin({'enabled': True, 'ffprobe_path': '/nonexistent/ffprobe'})

    def run_events(self, rename_dict, category_id, template):
        """依次触发 TransferRenameBuild 和 TransferRename，返回最终字符串。"""
        selection = SimpleNamespace(category_id=category_id)
        rename_dict = dict(rename_dict, __mediainfo__=SimpleNamespace(classification=SimpleNamespace(effective=selection, recommended=None), category=rename_dict.get('category')))
        build = SimpleNamespace(rename_dict=rename_dict, template_string=template, source_path=None, source_item=None)
        self.plugin.on_transfer_rename_build(SimpleNamespace(event_data=build))
        data = SimpleNamespace(rename_dict=build.rename_dict, template_string=template, render_str='MP', source_path=None, source_item=None, updated=False, updated_str=None, source='')
        self.plugin.on_transfer_rename(SimpleNamespace(event_data=data))
        return data.updated_str if data.updated else data.render_str

    def test_asian_drama_from_v2_history(self):
        """V2 日韩剧样本 → V3 亚洲剧：中文 _ 原文，WEB-DL 统一成 Web-Rip，补上 friDay 平台。"""
        rd = {'type': '电视剧', 'category': '亚洲剧', 'title': '现在不是出轨的问题', 'en_title': 'The Affair Was Just the Beginning', 'original_title': '지금 불륜이 문제가 아닙니다', 'year': '2026', 'season': 1, 'season_episode': 'S01E08', 'fileExt': '.mkv', 'original_name': 'The.Affair.Was.Just.The.Beginning.S01E08.2026.1080p.friDay.WEB-DL.H264.AAC', 'videoFormat': '1080p', 'resourceType': 'WEB-DL', 'videoCodec': 'H264', 'audioCodec': 'AAC', 'webSource': 'friDay'}
        assert self.run_events(rd, 'tv.asian', self.TV_FMT) == '现在不是出轨的问题 _ 지금 불륜이 문제가 아닙니다 (2026)/Season 1/现在不是出轨的问题 - S01E08 - 1080P Web-Rip.friDay AVC AAC.mkv'

    def test_anime_bang_dream_prefers_english(self):
        """BanG Dream! 系列用英文标题；联合发布组写全名；日番不带声道。"""
        rd = {'type': '电视剧', 'category': '日番', 'title': 'BanG Dream! YUME∞MITA', 'en_title': 'BanG Dream! YUME∞MITA', 'original_title': 'バンドリ！ ゆめ∞みた', 'year': '2026', 'season': 1, 'season_episode': 'S01E12', 'fileExt': '.mkv', 'original_name': '[hyakuhuyu&LoliHouse] BanG Dream Yumemita - 12 [WebRip 1080p HEVC-10bit AAC ASSx2]', 'videoFormat': '1080p', 'resourceType': 'WebRip', 'videoCodec': 'HEVC', 'audioCodec': 'AAC', 'releaseGroup': 'LoliHouse'}
        assert self.run_events(rd, 'tv.dongman.jp', self.TV_FMT) == 'BanG Dream! YUME∞MITA _ バンドリ！ ゆめ∞みた (2026)/Season 1/BanG Dream! YUME∞MITA - S01E12 - 1080P Web-Rip HEVC_10bit AAC - hyakuhuyu&LoliHouse.mkv'

    def test_chinese_movie_remux_shows_sdr(self):
        """华语电影：Remux 写 BluRay-Remux，SDR 显式写出，@ 统一成 &。"""
        rd = {'type': '电影', 'category': '华语电影', 'title': '活着', 'en_title': 'To Live', 'original_title': '活着', 'year': '1994', 'fileExt': '.mkv', 'original_name': 'To.Live.1994.AUS.BluRay.REMUX.1080p.AVC.LPCM2.0-QSD@CMCT', 'videoFormat': '1080p', 'resourceType': 'BluRay REMUX', 'videoCodec': 'AVC', 'audioCodec': 'LPCM 2.0'}
        assert self.run_events(rd, 'movie.chinese', self.MOVIE_FMT) == '活着 _ To Live (1994)/活着 - 1080P BluRay-Remux AVC PCM_2.0ch SDR - QSD&CMCT.mkv'

    def test_theatrical_hides_sdr(self):
        """动画电影：中文 _ 原文，SDR 不写。"""
        rd = {'type': '电影', 'category': '动画电影', 'title': '天气之子', 'en_title': 'Weathering with You', 'original_title': '天気の子', 'year': '2019', 'fileExt': '.mkv', 'original_name': 'Weathering.with.You.2019.1080p.BluRay.x264.DTS-HD.MA.5.1-WiKi', 'videoFormat': '1080p', 'resourceType': 'BluRay', 'videoCodec': 'x264', 'audioCodec': 'DTS-HD MA 5.1'}
        assert self.run_events(rd, 'movie.animation', self.MOVIE_FMT) == '天气之子 _ 天気の子 (2019)/天气之子 - 1080P BluRay-Rip AVC DTS-HD MA_5.1ch - WiKi.mkv'

    def test_depth_mismatch_keeps_mp(self):
        """MP 模板层数与插件模板不一致时不替换。"""
        rd = {'type': '电影', 'category': '华语电影', 'title': '夜王', 'year': '2026', 'fileExt': '.mkv'}
        assert self.run_events(rd, 'movie.chinese', '{{title}}{{fileExt}}') == 'MP'

    def test_music_untouched(self):
        """没有规则的分类（音乐）保持 MP 命名。"""
        rd = {'type': '音乐', 'category': 'Album', 'title': 'x', 'fileExt': '.flac'}
        assert self.run_events(rd, 'music.album', '{{title}}/{{title}}{{fileExt}}') == 'MP'
