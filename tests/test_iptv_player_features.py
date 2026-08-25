import os

import app_config
from iptv_quality import (
    detect_iptv_quality,
    fallback_urls,
    pick_iptv_variant,
    strip_quality_tokens,
    variants_for_channel,
)
from m3u_parse import probe_iptv_url
from iptv_record import StreamRecorder, _ffmpeg_copy_cmd, _safe_filename, default_recording_path


def _isolate_config(tmp_path, monkeypatch):
    previous = app_config._cache
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    return previous


def test_detect_and_strip_quality_tokens():
    assert detect_iptv_quality('La 1 FHD') == ('FHD', 1080)
    assert detect_iptv_quality('La 1 HD') == ('HD', 720)
    assert detect_iptv_quality('La 1 SD', 'España') == ('SD', 480)
    assert detect_iptv_quality('La 1 UHD') == ('UHD', 2160)
    assert strip_quality_tokens('La 1 HD') == 'La 1'
    assert strip_quality_tokens('La 1 [FHD]') == 'La 1'


def test_iptv_variants_pick_sd_hd_fhd():
    entries = [
        ('La 1 SD', 'http://panel.example/live/sd', 'SD', 'la1'),
        ('La 1 HD', 'http://panel.example/live/hd', 'HD', 'la1'),
        ('La 1 FHD', 'http://panel.example/live/fhd', 'FHD', 'la1'),
    ]
    variants = variants_for_channel(entries, 'La 1 HD', 'http://panel.example/live/hd', 'la1')
    assert [item['url'] for item in variants] == [
        'http://panel.example/live/sd',
        'http://panel.example/live/hd',
        'http://panel.example/live/fhd',
    ]
    assert pick_iptv_variant(variants, 0)['url'] == 'http://panel.example/live/fhd'
    assert pick_iptv_variant(variants, 720)['url'] == 'http://panel.example/live/hd'
    assert pick_iptv_variant(variants, 480)['url'] == 'http://panel.example/live/sd'
    assert pick_iptv_variant(variants, 2160)['url'] == 'http://panel.example/live/fhd'


def test_fallback_same_name_then_backup_does_not_invent_urls():
    entries = [
        ('La 1', 'http://panel.example/live/a', 'España', 'la1'),
        ('La 1', 'http://panel.example/live/b', 'Internacional', 'la1'),
        ('Otro', 'http://panel.example/live/x', 'España', 'otro'),
    ]
    backup = [
        ('La 1', 'http://backup.example/live/c', 'Respaldo', 'la1'),
        ('La 1 HD', 'http://backup.example/live/d', 'Respaldo', ''),
    ]
    found = fallback_urls(
        entries,
        'La 1',
        'http://panel.example/live/a',
        backup_entries=backup,
    )
    urls = [item['url'] for item in found]
    assert urls == [
        'http://panel.example/live/b',
        'http://backup.example/live/c',
        'http://backup.example/live/d',
    ]
    assert 'http://panel.example/live/a' not in urls
    assert 'http://panel.example/live/x' not in urls
    assert all(url.startswith('http://') for url in urls)
    assert not any('xmltv.php' in url or 'get.php' in url for url in urls)


def test_ffmpeg_copy_command_is_local_copy():
    cmd = _ffmpeg_copy_cmd(
        'ffmpeg',
        'http://panel.example/live/1',
        '/tmp/canal.ts',
        headers={'Referer': 'http://panel.example/'},
    )
    assert cmd[:3] == ['ffmpeg', '-hide_banner', '-loglevel']
    assert '-c' in cmd and 'copy' in cmd
    copy_at = cmd.index('-c')
    assert cmd[copy_at + 1] == 'copy'
    assert '-f' in cmd and 'mpegts' in cmd
    assert 'http://panel.example/live/1' in cmd
    assert not any(flag in cmd for flag in ('-c:v', 'widevine', 'clearkey'))
    mkv = _ffmpeg_copy_cmd('ffmpeg', 'http://panel.example/live/1', '/tmp/canal.mkv')
    assert 'matroska' in mkv
    assert _safe_filename('La 1 / HD?') == 'La 1  HD'


def test_default_recording_path_uses_download_folder(tmp_path, monkeypatch):
    previous = app_config._cache
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    try:
        folder = str(tmp_path / 'Descargas')
        os.makedirs(folder)
        app_config.set_download_dir(folder)
        path = default_recording_path('La 1 HD', when='20260825-134500')
        assert path == os.path.join(folder, 'La 1 HD_20260825-134500.ts')
    finally:
        app_config._cache = previous


def test_recorder_reads_iptv_and_youtube_source():
    class IptvDummy:
        _playing_youtube = False
        _iptv_source_url = 'http://panel.example/live/1'
        _iptv_retry_name = 'La 1 HD'

    url, headers, name = StreamRecorder(IptvDummy()).current_source()
    assert url == 'http://panel.example/live/1'
    assert name == 'La 1 HD'
    assert headers == {}

    class YtHandler:
        _direct_url = 'https://googlevideo.example/video'
        _direct_headers = {'Referer': 'https://www.youtube.com/'}
        _loading_title_text = 'Un vídeo'

    class YtDummy:
        _playing_youtube = True
        youtube_handler = YtHandler()

    url, headers, name = StreamRecorder(YtDummy()).current_source()
    assert url == 'https://googlevideo.example/video'
    assert name == 'Un vídeo'
    assert headers['Referer'] == 'https://www.youtube.com/'


def test_iptv_quality_and_backup_config(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        assert app_config.normalize_iptv_quality(900) == 1080
        assert app_config.normalize_iptv_quality(0) == 0
        app_config.set_iptv_quality(720)
        assert app_config.get_iptv_quality() == 720
        app_config.set_backup_playlist('/tmp/respaldo.m3u', 'file')
        path, kind = app_config.get_backup_playlist()
        assert path == '/tmp/respaldo.m3u'
        assert kind == 'file'
        app_config.set_backup_playlist('', '')
        path, kind = app_config.get_backup_playlist()
        assert path == ''
        assert kind == ''
    finally:
        app_config._cache = previous


class _FakeHttp:
    def __init__(self, body, content_type='application/octet-stream', status=200):
        self.body = body
        self.status = status
        self.headers = {'Content-Type': content_type}

    def read(self, n=512):
        return self.body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_probe_iptv_url_rejects_html(monkeypatch):
    monkeypatch.setattr(
        'urllib.request.urlopen',
        lambda *args, **kwargs: _FakeHttp(b'<!DOCTYPE html><html>error</html>', 'text/html'),
    )
    assert probe_iptv_url('http://panel.example/live/1') is False


def test_probe_iptv_url_accepts_mpegts(monkeypatch):
    monkeypatch.setattr(
        'urllib.request.urlopen',
        lambda *args, **kwargs: _FakeHttp(b'\x47' + b'\x00' * 187, 'video/mp2t'),
    )
    assert probe_iptv_url('http://panel.example/live/1') is True


def test_group_buckets_keeps_first_seen_order():
    from channel_sidebar import COMBO_MAX_GROUPS, UNGROUPED, _group_buckets

    order, buckets = _group_buckets(['España', 'Deportes', 'España', '', 'Deportes'])
    assert order == ['España', 'Deportes', UNGROUPED]
    assert buckets['España'] == [0, 2]
    assert buckets['Deportes'] == [1, 4]
    assert buckets[UNGROUPED] == [3]
    assert COMBO_MAX_GROUPS > 8
