"""使用精简媒体流样本验证技术参数；不访问真实媒体或网络。"""
from app.plugins.ffproberename import probe

def stream(**kw):
    """构造一个流字典。"""
    return kw
READY_PLAYER_ONE = {'streams': [stream(codec_type='video', codec_name='hevc', profile='Main 10', width=3840, height=2160, pix_fmt='yuv420p10le', color_transfer='smpte2084', avg_frame_rate='24000/1001', side_data_list=[{'side_data_type': 'DOVI configuration record', 'dv_profile': 8, 'dv_bl_signal_compatibility_id': 6}]), stream(codec_type='audio', codec_name='truehd', profile='Dolby TrueHD + Dolby Atmos', channels=8, tags={'language': 'eng', 'title': 'TrueHD 7.1'}, disposition={'default': 1}), stream(codec_type='audio', codec_name='dts', profile='DTS-HD MA', channels=8, tags={'language': 'eng'}), stream(codec_type='audio', codec_name='ac3', channels=6, tags={'language': 'fre'})]}
INTERSTELLAR = {'streams': [stream(codec_type='video', codec_name='hevc', width=3840, height=2160, pix_fmt='yuv420p10le', color_transfer='smpte2084', avg_frame_rate='24000/1001', side_data_list=[{'side_data_type': 'DOVI configuration record', 'dv_profile': 8, 'dv_bl_signal_compatibility_id': 1}]), stream(codec_type='audio', codec_name='pcm_s24le', channels=8, tags={'title': 'PCM 7.1ch'}), stream(codec_type='audio', codec_name='truehd', profile='Dolby TrueHD + Dolby Atmos', channels=8, tags={}), stream(codec_type='audio', codec_name='eac3', profile='Dolby Digital Plus + Dolby Atmos', channels=8, tags={})]}
ANI_WEB = {'streams': [stream(codec_type='video', codec_name='h264', profile='High', width=1920, height=1080, pix_fmt='yuv420p', avg_frame_rate='766035000/31950043'), stream(codec_type='audio', codec_name='aac', profile='LC', channels=2, tags={'language': 'jpn'})]}
VCB = {'streams': [stream(codec_type='video', codec_name='hevc', profile='Main 10', width=1920, height=1080, pix_fmt='yuv420p10le', avg_frame_rate='24000/1001'), stream(codec_type='audio', codec_name='flac', channels=2, tags={'language': 'jpn', 'title': 'Main Track'})]}

class TestParse:
    """ffprobe 解析。"""

    def test_dv_p81_pcm_vs_truehd(self):
        """星际穿越：杜比视界 8.1；PCM 7.1 与 TrueHD Atmos 并存时取 TrueHD。"""
        f = probe.parse_ffprobe(INTERSTELLAR)
        assert f['ffRes'] == '2160p'
        assert f['ffBit'] == '10bit'
        assert f['ffDR'] == 'DolbyVision_Profile8.1'
        assert (f['ffAudioCodec'], f['ffChannels']) == ('TrueHD', '7.1')
        assert f['ffAudio'] == 'TrueHD_7.1ch.Atmos'
        assert f['ffAtmos'] == 'Atmos'

    def test_dv_p86(self):
        """头号玩家：DV profile 8.6，首选 TrueHD Atmos 7.1。"""
        f = probe.parse_ffprobe(READY_PLAYER_ONE)
        assert f['ffDR'] == 'DolbyVision_Profile8.6'
        assert f['ffAudio'] == 'TrueHD_7.1ch.Atmos'

    def test_sdr_web_1080(self):
        """ANi 的 mp4：8bit、SDR、AAC 2.0，帧率不带标签。"""
        f = probe.parse_ffprobe(ANI_WEB)
        assert (f['ffRes'], f['ffVideo'], f['ffBit'], f['ffDR']) == ('1080p', 'AVC', '8bit', 'SDR')
        assert f['ffAudio'] == 'AAC_2.0ch'
        assert f['ffAudioNoCh'] == 'AAC'
        assert 'ffFps' not in f

    def test_hi10p_flac(self):
        """VCB 的 Ma10p：HEVC 10bit + FLAC 2.0。"""
        f = probe.parse_ffprobe(VCB)
        assert (f['ffVideo'], f['ffBit'], f['ffAudio']) == ('HEVC', '10bit', 'FLAC_2.0ch')

    def test_commentary_track_excluded(self):
        """评论音轨即使档次更高也不参与选择。"""
        data = {'streams': [stream(codec_type='audio', codec_name='aac', channels=2, tags={'title': 'Main'}), stream(codec_type='audio', codec_name='truehd', channels=8, tags={'title': "Director's Commentary"})]}
        assert probe.parse_ffprobe(data)['ffAudio'] == 'AAC_2.0ch'

    def test_fps_tolerance(self):
        """59.94 和 60 都算 60FPS，23.976 不带标签。"""
        assert probe.fps_label({'avg_frame_rate': '60000/1001'}) == '60FPS'
        assert probe.fps_label({'avg_frame_rate': '60/1'}) == '60FPS'
        assert probe.fps_label({'avg_frame_rate': '24000/1001'}) == ''
        assert probe.fps_label({'avg_frame_rate': '0/0', 'r_frame_rate': '120/1'}) == '120FPS'

    def test_ultrawide_resolution(self):
        """3840x1600 的宽银幕按宽度归到 2160p。"""
        assert probe.resolution_label(3840, 1600) == '2160p'
        assert probe.resolution_label(1920, 800) == '1080p'

    def test_bit_depth_inference(self):
        """从像素格式推位深。"""
        assert probe.bit_depth_label({'pix_fmt': 'yuv420p10le'}) == '10bit'
        assert probe.bit_depth_label({'pix_fmt': 'yuv420p'}) == '8bit'
        assert probe.bit_depth_label({'pix_fmt': 'p010le'}) == '10bit'
        assert probe.bit_depth_label({'pix_fmt': 'yuv444p12le'}) == '12bit'

    def test_dts_variants(self):
        """DTS 的几种档次。"""
        label = lambda profile: probe.audio_codec_label({'codec_name': 'dts', 'profile': profile})[0]
        assert label('DTS-HD MA') == 'DTS-HD MA'
        assert label('DTS-HD HRA') == 'DTS-HD HRA'
        assert label('DTS') == 'DTS'
        assert label('DTS-ES') == 'DTS'
        assert label('DTS 96/24') == 'DTS'
        assert label('DTS:X') == 'DTS-HD MA'
        assert label('DTS-HD MA + DTS:X') == 'DTS-HD MA'
        assert label('DTS-HD MA + DTS:X IMAX') == 'DTS-HD MA'

    def test_embedded_remux_title(self):
        """容器标题或视频轨标题注明 Remux 时打上标记。"""
        data = {'format': {'tags': {'title': 'Movie.2019.BluRay.REMUX.1080p'}}, 'streams': [ANI_WEB['streams'][0]]}
        assert probe.parse_ffprobe(data).get('ffRemux') == '1'
        assert 'ffRemux' not in probe.parse_ffprobe(ANI_WEB)

    def test_audio_every_includes_all_tracks(self):
        """全部音轨编码包括其他语言和评论音轨，按 V2 由低到高排序。"""
        assert probe.parse_ffprobe(READY_PLAYER_ONE)['ffAudioEvery'] == 'DD&DTS-HD MA&TrueHD'

class TestEdition:
    """片源版本推断。"""
    GM = probe.parse_group_map(probe.DEFAULT_GROUP_MAP)

    def test_whole_word_not_substring(self):
        """CheeseAni 不能被当成 ANi。"""
        base = {'releaseGroup': 'CheeseAni', 'resourceType': ''}
        assert probe.edition_label(base, self.GM) == ''

    def test_ani_exact(self):
        """ANi 在没有识别出片源时视为 Web-Rip。"""
        assert probe.edition_label({'releaseGroup': 'ANi', 'resourceType': ''}, self.GM) == 'Web-Rip'

    def test_force_vs_soft(self):
        """VCB 强制覆盖为 BluRay-Rip；LoliHouse 只在没有识别出片源时才用 Web-Rip。"""
        assert probe.edition_label({'releaseGroup': 'VCB-Studio', 'resourceType': 'BluRay'}, self.GM) == 'BluRay-Rip'
        em = probe.parse_edition_map(probe.DEFAULT_EDITION_MAP)
        assert probe.edition_label({'releaseGroup': 'LoliHouse', 'resourceType': 'BluRay'}, self.GM, em) == 'BluRay-Rip'

    def test_combined_group(self):
        """联合发布的组名拆开后逐个匹配。"""
        assert probe.edition_label({'releaseGroup': 'Nekomoe kissaten&VCB-Studio', 'resourceType': ''}, self.GM) == 'BluRay-Rip'

    def test_bdremux_in_name(self):
        """原名含 BDRemux 时直接是 BluRay-Remux。"""
        assert probe.edition_label({'original_name': 'Clannad BDRemux', 'releaseGroup': 'x'}, self.GM) == 'BluRay-Remux'

    def test_remux_sources(self):
        """文件名、MP 片源或内嵌标题任一处注明 Remux 都是 BluRay-Remux，VCB 等组的强制映射也让位。"""
        assert probe.edition_label({'original_name': 'X.2160p.UHD.BluRay.REMUX.mkv'}, self.GM) == 'BluRay-Remux'
        assert probe.edition_label({'resourceType': 'BluRay REMUX'}, self.GM) == 'BluRay-Remux'
        assert probe.edition_label({'isRemux': True, 'resourceType': 'BluRay'}, self.GM) == 'BluRay-Remux'

    def test_dvd_and_hdtv(self):
        """DVD / HDTV 统一成 DVD-Rip / HDTV-Rip，文件名写明的片源优先于 MP 从上层目录解析的值。"""
        em = probe.parse_edition_map(probe.DEFAULT_EDITION_MAP)
        for raw, want in [('DVD', 'DVD-Rip'), ('DVDRip', 'DVD-Rip'), ('DVD9', 'DVD-Rip'), ('HDTV', 'HDTV-Rip'), ('HDTVRip', 'HDTV-Rip')]:
            assert probe.edition_label({'resourceType': raw}, self.GM, em) == want, raw
        clannad = {'original_name': '劇場版 CLANNAD [DVD 720x480 23.976fps AVC-yuv420p10 FLAC] - fch1993.mkv', 'resourceType': 'BluRay'}
        assert probe.edition_label(clannad, self.GM, em) == 'DVD-Rip'
        assert probe.edition_label({'original_name': 'Show.S01E01.720p.HDTV.x264-GRP.mkv'}, self.GM, em) == 'HDTV-Rip'

    def test_name_source_ambiguous_falls_back(self):
        """文件名同时写了 BluRay 和 DVD 时不猜，交回 MP 的值；片名里的 Web 不算片源。"""
        em = probe.parse_edition_map(probe.DEFAULT_EDITION_MAP)
        assert probe.name_source('X [BluRay&DVD x264].mkv') == ''
        assert probe.name_source("Charlotte's.Web.2006.mkv") == ''
        assert probe.edition_label({'original_name': 'X [BluRay&DVD].mkv', 'resourceType': 'BluRay'}, self.GM, em) == 'BluRay-Rip'

    def test_bluray_without_remux_is_rip(self):
        """没注明 Remux 的蓝光一律 BluRay-Rip（含 UHD BluRay）。"""
        em = probe.parse_edition_map(probe.DEFAULT_EDITION_MAP)
        for raw in ('BluRay', 'UHD BluRay', 'BD', 'BDRip'):
            assert probe.edition_label({'resourceType': raw}, self.GM, em) == 'BluRay-Rip', raw

class TestTech:
    """out 拼装与兜底。"""
    GM = probe.parse_group_map(probe.DEFAULT_GROUP_MAP)
    EM = probe.parse_edition_map(probe.DEFAULT_EDITION_MAP)

    def test_full(self):
        """ffprobe 字段齐全时的拼法（电影规则：主音轨带声道、写动态范围）。"""
        ff = probe.parse_ffprobe(INTERSTELLAR)
        base = {'resourceType': 'BluRay', 'releaseGroup': ''}
        assert probe.build_out(ff, base, self.GM, edition_map=self.EM) == '4K BluRay-Rip HEVC_10bit TrueHD_7.1ch.Atmos DolbyVision_Profile8.1'

    def test_anime_variant(self):
        """日番规则：全部音轨编码、不带声道和 Atmos，不写动态范围和额外参数。"""
        ff = probe.parse_ffprobe(INTERSTELLAR)
        base = {'resourceType': 'BluRay', 'releaseGroup': '', 'original_name': 'X.IMAX.mkv'}
        assert probe.build_out(ff, base, self.GM, audio='all', dr='none', extra=False, edition_map=self.EM) == '4K BluRay-Rip HEVC_10bit DDP&TrueHD&PCM'
        ff2 = probe.parse_ffprobe(VCB)
        assert probe.build_out(ff2, {'releaseGroup': 'VCB-Studio'}, self.GM, audio='all', dr='none', extra=False) == '1080P BluRay-Rip HEVC_10bit FLAC'

    def test_dr_modes(self):
        """dr=hdr 时不写 SDR，dr=all 时写 SDR，dr=none 时 HDR 也不写。"""
        ff = probe.parse_ffprobe(VCB)
        base = {'resourceType': 'BluRay', 'releaseGroup': 'VCB-Studio'}
        assert probe.build_out(ff, base, self.GM) == '1080P BluRay-Rip HEVC_10bit FLAC_2.0ch'
        assert probe.build_out(ff, base, self.GM, dr='all') == '1080P BluRay-Rip HEVC_10bit FLAC_2.0ch SDR'
        hdr = probe.parse_ffprobe(INTERSTELLAR)
        assert 'DolbyVision' not in probe.build_out(hdr, base, self.GM, dr='none')

    def test_sdr_without_ffprobe(self):
        """读不到 ffprobe 时，文件名没有 HDR 标记也算 SDR（与 V2 电影模板一致）。"""
        base = {'videoFormat': '1080p', 'resourceType': 'WEBRip', 'videoCodec': 'AVC', 'audioCodec': 'DD 2.0'}
        assert probe.build_out({}, base, self.GM, dr='all', edition_map=self.EM) == '1080P Web-Rip AVC DD_2.0ch SDR'

    def test_8bit_not_written(self):
        """8bit 不写进 out，10bit / 12bit 照写。"""
        ff = probe.parse_ffprobe(ANI_WEB)
        assert probe.tech_parts(ff, {}, self.GM)['video'] == 'AVC'
        assert probe.tech_parts(ff, {}, self.GM)['bit_depth'] == '8bit'
        assert probe.tech_parts({}, {'videoCodec': 'x265', 'videoBit': '12bit'}, self.GM)['video'] == 'HEVC_12bit'

    def test_web_source_appended(self):
        """流媒体平台跟在片源后面。"""
        ff = probe.parse_ffprobe(ANI_WEB)
        base = {'releaseGroup': 'ANi', 'resourceType': '', 'webSource': 'Baha'}
        assert probe.build_out(ff, base, self.GM) == '1080P Web-Rip.Baha AVC AAC_2.0ch'

    def test_fallback_without_ffprobe(self):
        """ffprobe 读不到时，用 MP 从文件名解析的值兜底，且兜底值先统一写法（x265→HEVC，HDR 保持 HDR）。"""
        base = {'videoFormat': '1080p', 'resourceType': 'WEB-DL', 'videoCodec': 'x265', 'videoBit': '10bit', 'audioCodec': 'AAC', 'effect': 'HDR'}
        assert probe.build_out({}, base, self.GM, edition_map=self.EM) == '1080P Web-Rip HEVC_10bit AAC HDR'

    def test_fallback_codec_already_has_bit(self):
        """MP 解析出的编码已带位深时，不重复追加（HEVC_10bit 而不是 HEVC_10bit_10bit）；REMUX 统一成 BluRay-Remux。"""
        base = {'videoFormat': '4k', 'resourceType': 'BluRay REMUX', 'videoCodec': 'HEVC 10bit', 'videoBit': '10bit'}
        assert probe.build_out({}, base, self.GM) == '4K BluRay-Remux HEVC_10bit'

    def test_fallback_hi10p_and_flac(self):
        """Hi10p 统一成 AVC_10bit，flac/Flac/FLACx2 统一成 FLAC。"""
        for audio in ('flac', 'Flac', 'FLACx2'):
            base = {'videoFormat': '1080p', 'videoCodec': 'Hi10p', 'audioCodec': audio}
            assert probe.build_out({}, base, self.GM) == '1080P AVC_10bit FLAC', audio

    def test_fallback_audio_atmos_and_channels(self):
        """EAC3 Atmos 5.1 统一成 DDP_5.1ch.Atmos。"""
        base = {'audioCodec': 'EAC3 Atmos 5.1'}
        assert probe.build_out({}, base, self.GM) == 'DDP_5.1ch.Atmos'

    def test_fallback_dolbyvision_effect(self):
        """文件名标 DV 时，动态范围写成 DolbyVision；HDR10 写成 HDR_HDR10；带 P7 时补细分版本。"""
        assert probe.build_out({}, {'effect': 'DV'}, self.GM) == 'DolbyVision'
        assert probe.build_out({}, {'effect': 'HDR10'}, self.GM) == 'HDR_HDR10'
        assert probe.build_out({}, {'effect': 'DV', 'original_name': 'X.2160p.DV.P7.HDR.mkv'}, self.GM) == 'DolbyVision_Profile7'

    def test_fallback_dts_family(self):
        """兜底时 DTS 家族写法：只写 DTS-HD 的算 HRA。"""
        for raw, want in [('DTS-HD MA 5.1', 'DTS-HD MA_5.1ch'), ('DTS-HD 5.1', 'DTS-HD HRA_5.1ch'), ('DTS 5.1', 'DTS_5.1ch'), ('DTS-X 7.1', 'DTS-HD MA_7.1ch')]:
            assert probe.build_out({}, {'audioCodec': raw}, self.GM) == want, raw

    def test_extra_tags_from_name(self):
        """IMAX / 3D 取自文件名；有 ffprobe 视频时 60FPS 只信 ffprobe，不信文件名。"""
        assert probe.extra_tags('Film.2014.IMAX.2160p.mkv', '', trust_fps=True) == 'IMAX'
        assert probe.extra_tags('Film.IMAX.60fps.mkv', '', trust_fps=True) == 'IMAX'
        assert probe.extra_tags('Film.IMAX.60fps.mkv', '', trust_fps=False) == 'IMAX 60FPS'
        assert probe.extra_tags('Film.mkv', '60FPS', trust_fps=True) == '60FPS'
        assert probe.extra_tags('Film.3D.IMAX.mkv', '', trust_fps=True) == '3D IMAX'
        assert probe.extra_tags('Imaginary.mkv', '', trust_fps=True) == ''

    def test_extra_tags_in_out(self):
        """out 末尾带额外参数，extra=False 时不带。"""
        ff = {'ffRes': '2160p', 'ffFps': '60FPS'}
        assert probe.build_out(ff, {'original_name': 'X.IMAX.mkv'}, self.GM).endswith('IMAX 60FPS')
        assert probe.build_out(ff, {'original_name': 'X.IMAX.mkv'}, self.GM, extra=False) == '4K'

    def test_audio_piece(self):
        """音频段的拼法：编码_声道ch.Atmos。"""
        assert probe.audio_piece('TrueHD', '7.1', True) == 'TrueHD_7.1ch.Atmos'
        assert probe.audio_piece('TrueHD', '7.1', True, False) == 'TrueHD.Atmos'
        assert probe.audio_piece('FLAC', '', False) == 'FLAC'
        assert probe.audio_piece('', '', True) == 'Atmos'
        assert probe.audio_piece('', '5.1', False) == ''

    def test_bdmv_edition(self):
        """源文件在蓝光原盘（BDMV）里时，片源写成 BluRay，优先于 Remux 判断。"""
        base = {'isBDMV': True, 'resourceType': 'BluRay REMUX', 'videoFormat': '1080p', 'videoCodec': 'AVC'}
        assert probe.edition_label(base, self.GM, self.EM) == 'BluRay'
        assert probe.build_out({'ffRes': '1080p', 'ffVideo': 'AVC', 'ffBit': '8bit'}, base, self.GM, edition_map=self.EM) == '1080P BluRay AVC'

    def test_fallback_default_maps_collapse_web_dl(self):
        """用默认统一表时 WEB-DL 与 WEBRip 都写成 Web-Rip，平台只跟在 Web 系后面。"""
        pb = probe.PlatformBook(probe.DEFAULT_PLATFORMS)
        base = {'original_name': 'Show.S01E01.1080p.NF.WEB-DL.DDP5.1.H.264-GRP.mkv', 'resourceType': 'WEB-DL', 'videoFormat': '1080p', 'videoCodec': 'H264', 'audioCodec': 'DDP 5.1'}
        assert probe.build_out({}, base, self.GM, edition_map=self.EM, platform_book=pb) == '1080P Web-Rip.Netflix AVC DDP_5.1ch'
        bd = dict(base, resourceType='BluRay', original_name='Show.1080p.BluRay.NF.x264-GRP.mkv')
        assert probe.build_out({}, bd, self.GM, edition_map=self.EM, platform_book=pb) == '1080P BluRay-Rip AVC DDP_5.1ch'

    def test_res_options(self):
        """分辨率写法选项：默认 4K / 1080P，可以关掉。"""
        ff = {'ffRes': '2160p'}
        assert probe.build_out(ff, {}, self.GM).startswith('4K')
        assert probe.build_out(ff, {}, self.GM, res_4k_label=False).startswith('2160P')
        assert probe.build_out(ff, {}, self.GM, res_upper=False, res_4k_label=False).startswith('2160p')
        assert probe.build_out({'ffRes': '1080p'}, {}, self.GM).startswith('1080P')
        assert probe.build_out({'ffRes': '720p'}, {}, self.GM).startswith('720P')

class TestEditionNormalize:
    """片源写法统一。"""
    EM = probe.parse_edition_map(probe.DEFAULT_EDITION_MAP)
    GM = probe.parse_group_map(probe.DEFAULT_GROUP_MAP)

    def test_variants_collapse(self):
        """语料里实际出现的几种写法统一后一致。"""
        for raw, want in [('BDRIP', 'BluRay-Rip'), ('BD', 'BluRay-Rip'), ('BD BluRay', 'BluRay-Rip'), ('BluRay REMUX', 'BluRay-Remux'), ('UHD BluRay REMUX', 'BluRay-Remux'), ('BD REMUX', 'BluRay-Remux'), ('REMUX', 'BluRay-Remux'), ('WEB', 'Web-Rip'), ('WEBRip', 'Web-Rip'), ('WEB-DL', 'Web-Rip'), ('BluRay', 'BluRay-Rip'), ('UHD BluRay', 'BluRay-Rip'), ('HDTV', 'HDTV-Rip')]:
            assert probe.normalize_edition(raw, self.EM) == want, raw

    def test_passthrough(self):
        """表里没有的写法原样保留。"""
        for raw in ('VHSRip', 'LaserDisc', ''):
            assert probe.normalize_edition(raw, self.EM) == raw

    def test_no_map_means_no_change(self):
        """不传统一表时行为与之前一致。"""
        assert probe.normalize_edition('BDRIP', None) == 'BDRIP'

    def test_edition_label_uses_map(self):
        """edition_label 对 MP 的 BDRIP 给出统一写法，发行组强制覆盖仍然生效。"""
        assert probe.edition_label({'resourceType': 'BDRIP', 'releaseGroup': 'LoliHouse'}, self.GM, self.EM) == 'BluRay-Rip'
        assert probe.edition_label({'resourceType': 'WEB', 'releaseGroup': 'VCB-Studio'}, self.GM, self.EM) == 'BluRay-Rip'

    def test_parse_edition_map(self):
        """统一表解析：忽略注释和空行，键转小写并折叠空白。"""
        assert probe.parse_edition_map('# x\n\nUHD  BluRay REMUX = BluRay-Remux\nbad\n') == {'uhd bluray remux': 'BluRay-Remux'}

class TestNormalize:
    """MP 初步识别值的统一写法。"""

    def test_codec(self):
        """编码：x265/H265/HEVC→HEVC，x264/x.264/H264/Hi10p→AVC，VC1→VC-1，并带出位深。"""
        cases = [('x265', ('HEVC', '')), ('H265', ('HEVC', '')), ('HEVC', ('HEVC', '')), ('x265 10bit', ('HEVC', '10bit')), ('HEVC 10bit', ('HEVC', '10bit')), ('H265 10bit', ('HEVC', '10bit')), ('x264', ('AVC', '')), ('x.264', ('AVC', '')), ('H264', ('AVC', '')), ('h264', ('AVC', '')), ('Hi10p', ('AVC', '10bit')), ('Hi10P', ('AVC', '10bit')), ('AVC 10bit', ('AVC', '10bit')), ('VC1', ('VC-1', '')), ('AV1', ('AV1', '')), ('', ('', ''))]
        for raw, want in cases:
            assert probe.normalize_codec(raw) == want, raw

    def test_audio(self):
        """音频：大小写、FLACx2、EAC3/AC3 的各种写法，带出声道和 Atmos。"""
        cases = [('flac', ('FLAC', '', False)), ('Flac', ('FLAC', '', False)), ('FLACx2', ('FLAC', '', False)), ('aac', ('AAC', '', False)), ('DDP 5.1', ('DDP', '5.1', False)), ('DDP 5.1 Atmos', ('DDP', '5.1', True)), ('EAC3 Atmos 5.1', ('DDP', '5.1', True)), ('ac3', ('DD', '', False)), ('AC3', ('DD', '', False)), ('DTS 5.1', ('DTS', '5.1', False)), ('DTS-HD MA 5.1', ('DTS-HD MA', '5.1', False)), ('DTS-HD 5.1', ('DTS-HD HRA', '5.1', False)), ('DTS-HD.MA.7.1', ('DTS-HD MA', '7.1', False)), ('DTS-HD HRA 7.1', ('DTS-HD HRA', '7.1', False)), ('DTS-X 7.1', ('DTS-HD MA', '7.1', False)), ('DTS:X', ('DTS-HD MA', '', False)), ('DTS.x264', ('DTS', '', False)), ('DTS-HD MA DTS-X', ('DTS-HD MA', '', False)), ('DDP AAC', ('AAC&DDP', '', False)), ('DD+', ('DDP', '', False)), ('Atmos', ('', '', True)), ('OPUS', ('OPUS', '', False)), ('DTS5.1', ('DTS', '5.1', False)), ('AAC2.0', ('AAC', '2.0', False))]
        for raw, want in cases:
            assert probe.normalize_audio(raw) == want, raw

    def test_effect(self):
        """特效：沿用上游「动态范围_细分版本」写法，DolbyVision / HDR_HDR10+ / HDR_HDR10 / HDR_HLG / HDR。"""
        for raw, want in [('DV', 'DolbyVision'), ('Dolby Vision', 'DolbyVision'), ('HDR', 'HDR'), ('HDR10+', 'HDR_HDR10+'), ('HDR10', 'HDR_HDR10'), ('HLG', 'HDR_HLG'), ('', ''), ('DVD', '')]:
            assert probe.normalize_effect(raw) == want, raw

    def test_pix(self):
        """分辨率：4k→2160p，非标准档（362p）不采用。"""
        for raw, want in [('4k', '2160p'), ('4K', '2160p'), ('2160p', '2160p'), ('1080p', '1080p'), ('1080i', '1080p'), ('2k', '1440p'), ('362p', ''), ('', '')]:
            assert probe.normalize_pix(raw) == want, raw
        assert probe.resolution_display('2160p', k_label=True) == '4K'
        assert probe.resolution_display('1440p', k_label=True) == '2K'
        assert probe.resolution_display('1080p', k_label=True) == '1080p'

class TestGroup:
    """发行组从文件名识别。"""
    BOOK = probe.GroupBook(probe.DEFAULT_KNOWN_GROUPS)

    def g(self, name):
        """提取发行组的简写。"""
        return probe.extract_group(name, self.BOOK)

    def test_leading_bracket(self):
        """开头的 [组名]，已知组统一拼写，未知组原样保留。"""
        assert self.g('[ANi] BanG Dream！YUME∞MITA - 01 [1080P][Baha][WEB-DL][AAC AVC][CHT].mp4') == 'ANi'
        assert self.g('[vcb-studio] K-ON! [01][Ma10p_1080p][x265_flac].mkv') == 'VCB-Studio'
        assert self.g('[DMG&VCB-Studio] BOCCHI THE ROCK! [01][Ma10p_1080p][x265_flac].mkv') == 'DMG&VCB-Studio'
        assert self.g('[Nekomoe kissaten&VCB-Studio] X [01][Ma10p_1080p].mkv') == 'Nekomoe kissaten&VCB-Studio'
        assert self.g('[Prejudice-Studio] 我们不可能成为恋人 - OVA02 [WebRip 1080P].mkv') == 'Prejudice-Studio'

    def test_leading_bracket_not_a_group(self):
        """开头括号里是分辨率、集号这类内容时不当作发行组。"""
        assert self.g('[1080P] Title.mkv') == ''
        assert self.g('[01] Title.mkv') == ''
        assert self.g('【高清影视之家发布 www.HDBTHD.com】片名.2160p.WEB-DL.mkv') == ''

    def test_trailing_bracket_known(self):
        """结尾的 [已知组]。"""
        assert self.g('Anora  - 4K Bluray HEVC DDP5.1 HDR [Xcat].mkv') == 'Xcat'

    def test_dash_suffix(self):
        """结尾的 -组名，要求前面出现过分辨率、片源或编码等技术词。"""
        assert self.g('Sai.2025.S01E01.1080p.NF.WEB-DL.AAC2.0.H.264-SmartWeb.mkv') == 'SmartWeb'
        assert self.g('火锅艺术家.Hot.Pot.Artist.2025.2160p.HQ.WEB-DL.DTS5.1.H265.60fps-ParkHD.mkv') == 'ParkHD'
        assert self.g('Hidden.Love.S01E06.Episode.6.1080p.NF.WEB-DL.DDP.2.0.H.264-yiiha.mkv') == 'yiiha'

    def test_dash_suffix_needs_tech_mark(self):
        """没有技术词时，末尾的 -xxx 不是发行组（避免 Spider-Man 之类）。"""
        assert self.g('Spider-Man.mkv') == ''
        assert self.g('民国奇探 - S01E01 - 1080p Web-Dl HEVC.mp4') == ''

    def test_spaced_dash_known_suffix(self):
        """「 - 组名」且组名已知。"""
        assert self.g('Clannad 2007 EP08 [BluRay 1920x1080p 23.976fps x264-Hi10P FLACx2] - mawen1250.mkv') == 'mawen1250'

    def test_at_sign_and_alias(self):
        """@ 统一成 &；别名 XLYS 统一成规范名。"""
        assert self.g('Breaking.Bad.S01E03.2008.2160p.WEBrip.x265.10bit.AC3￡cXcY@FRDS.mkv') == 'cXcY&FRDS'
        assert self.g('I.Am.Nobody.2025.S02E01.4K.HQ.60FPS.X265.AAC.Mandarin.CHS.XLYS.mkv') == '修罗影视'

    def test_copy_suffix_stripped(self):
        """重复下载产生的 (1) 后缀不属于组名，且仍能统一到规范拼写。"""
        assert self.g('Under.the.Light.2023.1080p.WEB-DL.H.264.AAC-Q66(1).mkv') == 'Q66'
        assert self.g('Breaking.Bad.S01E03.2008.2160p.WEBrip.x265.10bit.AC3￡cXcY@FRDS(1).mkv') == 'cXcY&FRDS'

    def test_bracket_title_is_not_group(self):
        """[中文片名].Title.xxx 里开头的方括号是片名；已知组即使这样写也认。"""
        assert self.g("[无人区].No.Man's.Land.2013.WEB-DL.2160P.H265.AAC.Mandarin.CHS-OurTV.mp4") == 'OurTV'
        assert self.g('[VCB-Studio].Some.Show.01.1080p.mkv') == 'VCB-Studio'

    def test_platform_is_not_group(self):
        """结尾的平台名（bilibili 等）不是发行组。"""
        assert self.g('李献计历险记 (2011) - 4K HEVC AAC - bilibili.mp4') == ''

    def test_language_tag_stripped(self):
        """组名后跟的语言标记（.ZH）不进组名。"""
        assert self.g('Cosmic.Princess.Kaguya.2026.2160p.NF.WEB-DL.JPN.DDP5.1.H.265-shenghuo2.ZH.mkv') == 'shenghuo2'

    def test_v2_groups_added(self):
        """从 V2 自定义制作组补进来的 17 个都在已知组表里，且小写写法会统一成规范拼写。"""
        names = ['BlackTV', 'ParkHD', 'LelveTV', 'playWEB', 'TeamSyndicate', 'Lieqiwang', 'PanWEB', 'DVT', 'QTS', 'Curly', 'WiLDCAT', 'ALT', 'MOMOHD', '幻月字幕组', 'NUMTV', 'BestWEB', 'Vampire']
        for name in names:
            assert self.BOOK.lookup(name) == name, name
            assert self.BOOK.lookup(name.lower()) == name, name.lower()
        assert self.g('Sample.Show.2020.S01E01.1080p.WEB-DL.H264-playwEB.mkv') == 'playWEB'
        assert self.g('[幻月字幕组] 某番 - 01 [1080P][WebRip].mkv') == '幻月字幕组'
        assert self.g('[Vampire] Dragon Raja - 01 [1080p].mkv') == 'Vampire'

    def test_site_tag_is_not_group(self):
        """发布站点标记（4KHDR世界）不是发行组。"""
        assert self.g('不日成婚[4KHDR.CN].Ready.O.R.Knot.2021.2160p.WEB-DL.H265.HDR.DDP5.1.2Audio[国粤双音轨_中字]-4KHDR世界.mkv') == ''

    def test_no_group(self):
        """识别不出就返回空。"""
        assert self.g('Severance (2022) - S01E01 - Good News About Hell (1080p ATVP WEB-DL x265 t3nzin).mkv') == ''
        assert self.g('') == ''

    def test_resolve_prefers_filename(self):
        """文件名识别优先，识别不出再统一 MP 给的值。"""
        base = {'original_name': '[VCB-Studio] X [01][Ma10p_1080p].mkv', 'releaseGroup': 'Nekomoe kissaten'}
        assert probe.resolve_group(base, self.BOOK) == 'VCB-Studio'
        base = {'original_name': 'Title.mkv', 'releaseGroup': 'cXcY@FRDS'}
        assert probe.resolve_group(base, self.BOOK) == 'cXcY&FRDS'
        assert probe.resolve_group({'original_name': 'Title.mkv'}, self.BOOK) == ''

class TestPlatform:
    """流媒体平台识别与统一。"""
    PB = probe.PlatformBook(probe.DEFAULT_PLATFORMS)

    def test_from_filename(self):
        """从文件名技术信息部分找平台。"""
        assert self.PB.find('Show.S01E01.1080p.NF.WEB-DL.DDP5.1.H.264-GRP.mkv') == 'Netflix'
        assert self.PB.find('[ANi] X - 01 [1080P][Baha][WEB-DL][AAC AVC][CHT].mp4') == 'Baha'
        assert self.PB.find('Severance (2022) - S01E01 - Title (1080p ATVP WEB-DL x265 t3nzin).mkv') == 'AppleTV'

    def test_title_words_do_not_count(self):
        """片名里的 Prime、NF 不算平台，只看第一个技术标记之后。"""
        assert self.PB.find('Prime.Suspect.1991.1080p.BluRay.x264-GRP.mkv') == ''
        assert self.PB.find('The NF Story 1080p BluRay x264.mkv') == ''

    def test_unify_mp_value(self):
        """MP 识别出的平台名统一成表里的写法，不在表里的原样保留。"""
        assert self.PB.unify('Apple TV+') == 'AppleTV'
        assert self.PB.unify('Amazon') == 'Amazon'
        assert self.PB.unify('friDay') == 'friDay'
        assert self.PB.unify('SomethingElse') == 'SomethingElse'
        assert self.PB.unify(None) == ''

    def test_label_prefers_filename(self):
        """文件名里找到的优先于 MP 的值。"""
        base = {'original_name': 'X.1080p.NF.WEB-DL.mkv', 'webSource': 'Amazon'}
        assert probe.platform_label(base, self.PB) == 'Netflix'
        assert probe.platform_label({'original_name': 'X.mkv', 'webSource': 'Apple TV+'}, self.PB) == 'AppleTV'

class TestGroupMap:
    """发行组映射文本解析。"""

    def test_parse(self):
        """注释、空行、强制标记。"""
        m = probe.parse_group_map('# c\n\nvcb-studio=BluRay-Rip!\nlolihouse = Web-Rip \nbad line\n')
        assert m == {'vcb-studio': ('BluRay-Rip', True), 'lolihouse': ('Web-Rip', False)}
