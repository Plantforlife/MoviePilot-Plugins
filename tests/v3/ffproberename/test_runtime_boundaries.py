"""Failure recovery and cache invalidation at the external process boundary."""
import subprocess
from types import SimpleNamespace

from app.plugins.ffproberename import FfprobeRename, probe


def test_probe_passes_filename_as_one_argument(monkeypatch):
    """Special shell characters in a media filename must remain literal."""
    calls = []

    def run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return SimpleNamespace(stdout=b'{"streams": []}')

    monkeypatch.setattr(probe.subprocess, 'run', run)
    filename = '/media/Film $(ignored); title.mkv'
    assert probe.run_ffprobe(filename, '/tools/ffprobe', 12) == {'streams': []}
    args, options = calls[0]
    assert args[-2:] == ['-i', filename]
    assert args[0] == '/tools/ffprobe'
    assert options['timeout'] == 12
    assert not options.get('shell', False)


def test_probe_timeout_returns_fallback(monkeypatch):
    """A slow external process must not abort a media transfer."""
    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired('ffprobe', 5)

    monkeypatch.setattr(probe.subprocess, 'run', run)
    assert probe.run_ffprobe('sample.mkv', timeout=5) is None


def test_probe_invalid_json_returns_fallback(monkeypatch):
    """A successful process with invalid output is still a probe failure."""
    monkeypatch.setattr(probe.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=b'not json'))
    assert probe.run_ffprobe('sample.mkv') is None


def test_cache_rechecks_replaced_file(tmp_path, monkeypatch):
    """Replacing a download at the same path must invalidate cached metadata."""
    media = tmp_path / 'video.mkv'
    media.write_bytes(b'first')
    calls = []

    def run(*args):
        calls.append(args)
        return {'streams': []}

    monkeypatch.setattr(probe, 'run_ffprobe', run)
    plugin = FfprobeRename()
    plugin.init_plugin({'enabled': False})
    plugin._probe_fields(media)
    plugin._probe_fields(media)
    assert len(calls) == 1
    media.write_bytes(b'replaced with another download')
    plugin._probe_fields(media)
    assert len(calls) == 2


def test_reinitialization_does_not_share_instance_state():
    """Reloading settings and creating another instance must isolate caches."""
    first, second = FfprobeRename(), FfprobeRename()
    first.init_plugin({'enabled': True})
    second.init_plugin({'enabled': False})
    first._cache[('sample', 1, 1)] = {'ffVideo': 'AVC'}
    assert second._cache == {}
    first.init_plugin({'enabled': False})
    assert not first.get_state()
    assert first._cache == {}


def test_disabled_plugin_does_not_touch_event():
    """Disabled handlers must leave the original rename context intact."""
    plugin = FfprobeRename()
    plugin.init_plugin({'enabled': False})
    data = SimpleNamespace(rename_dict={'title': 'Example'})
    event = SimpleNamespace(event_data=data)
    plugin.on_transfer_rename_build(event)
    plugin.on_transfer_rename(event)
    assert data.rename_dict == {'title': 'Example'}
