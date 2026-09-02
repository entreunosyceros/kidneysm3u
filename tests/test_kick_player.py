"""Módulo de test kick player."""

import app_config
from kick_player import (
    curl_cffi_available,
    fetch_kick_channel_vods,
    fetch_kick_latest_vod,
    inspect_kick_session,
    is_kick_channel_url,
    is_kick_offline_error,
    is_kick_url,
    is_kick_vod_url,
    kick_auth_blocked,
    kick_auth_help,
    kick_cookies_file_path,
    kick_default_title,
    kick_display_name_from_url,
    kick_favorite_url,
    kick_loading_detail,
    kick_ydl_opts,
    normalize_kick_channel_input,
    pick_kick_stream,
    _kick_impersonate_target,
)


def test_is_kick_url_accepts_common_links():
    """Prueba is kick URL accepts common links."""
    assert is_kick_url('https://kick.com/somechannel')
    assert is_kick_url('https://www.kick.com/other')
    assert is_kick_url('https://kick.com/demo/videos/abc-123-def')
    assert is_kick_url('https://kick.com/demo/clips/clip-id')


def test_is_kick_url_rejects_other_sites():
    """Prueba is kick URL rejects other sites."""
    assert not is_kick_url('https://youtube.com/watch?v=abc')
    assert not is_kick_url('https://example.com/fakechannel')
    assert not is_kick_url('')
    assert not is_kick_url('kick.com/channel')
    assert not is_kick_url('https://kick.com/')


def test_is_kick_channel_url():
    """Prueba is kick canal URL."""
    assert is_kick_channel_url('https://kick.com/shroud')
    assert not is_kick_channel_url('https://kick.com/shroud/videos/uuid')
    assert not is_kick_channel_url('https://kick.com/shroud/clips/abc')
    assert not is_kick_channel_url('https://kick.com/about')


def test_is_kick_vod_url():
    """Prueba is kick vod URL."""
    assert is_kick_vod_url('https://kick.com/demo/videos/abc-123')
    assert is_kick_vod_url('https://kick.com/video/abc-123')
    assert not is_kick_vod_url('https://kick.com/demo')
    assert not is_kick_vod_url('https://kick.com/demo/clips/x')


def test_kick_display_name_from_url():
    """Prueba kick display name from URL."""
    assert kick_display_name_from_url('https://kick.com/demo') == 'demo'
    assert kick_display_name_from_url('https://kick.com/demo/videos/uuid-here') == 'demo'


def test_kick_default_title():
    """Prueba kick default title."""
    assert kick_default_title('https://kick.com/demo', 'Mi título') == 'Mi título'
    assert kick_default_title('https://kick.com/demo') == 'demo'


def test_normalize_kick_channel_input():
    """Prueba normalize kick canal input."""
    assert normalize_kick_channel_input('srgalileo1') == 'srgalileo1'
    assert normalize_kick_channel_input('@Demo') == 'demo'
    assert normalize_kick_channel_input('https://kick.com/SrGalileo1') == 'srgalileo1'


def test_fetch_kick_channel_vods(monkeypatch):
    """Prueba fetch kick canal vods."""
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    'session_title': 'Stream de ayer',
                    'duration': 3600000,
                    'video': {'uuid': '98438a71-421e-4de8-bb31-9c0379f4b5f8'},
                },
            ]

    monkeypatch.setattr('requests.get', lambda *a, **k: _Resp())
    videos, channel = fetch_kick_channel_vods('srgalileo1', limit=5)
    assert channel == 'srgalileo1'
    assert len(videos) == 1
    assert videos[0]['title'] == 'Stream de ayer'
    assert videos[0]['url'].endswith('98438a71-421e-4de8-bb31-9c0379f4b5f8')
    assert videos[0]['duration'] == 3600


def test_fetch_kick_latest_vod(monkeypatch):
    """Prueba fetch kick latest vod."""
    monkeypatch.setattr(
        'kick_player.fetch_kick_channel_vods',
        lambda channel, limit=1: (
            [{
                'url': 'https://kick.com/demo/videos/uuid-123',
                'title': 'Último directo',
                'id': 'uuid-123',
            }],
            'demo',
        ),
    )
    latest = fetch_kick_latest_vod('demo')
    assert latest['url'] == 'https://kick.com/demo/videos/uuid-123'
    assert latest['title'] == 'Último directo'
    assert latest['channel'] == 'demo'


def test_is_kick_offline_error():
    """Prueba is kick offline error."""
    assert is_kick_offline_error(Exception('channel is not currently live'))
    assert is_kick_offline_error(Exception('ERROR: [kick:live] demo: The channel is not currently live'))
    assert not is_kick_offline_error(Exception('network timeout'))


def test_kick_history(tmp_path, monkeypatch):
    """Prueba kick historial."""
    previous = app_config._cache
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    try:
        url = 'https://kick.com/demo'
        app_config.remember_kick_watch(url, title='Canal demo')
        items = app_config.kick_history()
        assert len(items) == 1
        assert items[0]['name'] == 'Canal demo'
        assert app_config.kick_history_item_by_url(url)['name'] == 'Canal demo'
        assert app_config.kick_history_label(items[0]) == 'Kick · Canal demo'
        app_config.clear_kick_history()
        assert app_config.kick_history() == []
    finally:
        app_config._cache = previous


def test_kick_vod_resume(tmp_path, monkeypatch):
    """Prueba kick vod resume."""
    previous = app_config._cache
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    try:
        url = 'https://kick.com/demo/videos/uuid-123'
        app_config.remember_kick_watch(url, title='VOD demo')
        app_config.update_kick_position(url, 120, duration_s=3600)
        item = app_config.kick_history_item_by_url(url)
        assert item['kind'] == 'vod'
        assert item['s'] == 120
        assert app_config.kick_resume_seconds(url, duration_s=3600) == 120
        assert '02:00' in app_config.kick_history_label(item, with_time=True)
        watching = app_config.kick_continue_watching()
        assert len(watching) == 1
        app_config.clear_kick_position(url)
        assert app_config.kick_resume_seconds(url) == 0
        assert app_config.kick_continue_watching() == []
    finally:
        app_config._cache = previous


def test_inspect_kick_session(tmp_path):
    """Prueba inspect kick session."""
    path = tmp_path / 'kick_cookies.txt'
    path.write_text(
        '# Netscape HTTP Cookie File\n'
        '.kick.com\tTRUE\t/\tFALSE\t4102444800\tsession\tabc123\n',
        encoding='utf-8',
    )
    info = inspect_kick_session(str(path))
    assert info['ok'] is True
    assert info['label'] == 'OK'


def test_kick_ydl_opts_uses_cookiefile(tmp_path, monkeypatch):
    """Prueba kick ydl opts uses cookiefile."""
    cookie_path = tmp_path / 'kick_cookies.txt'
    cookie_path.write_text('# empty\n', encoding='utf-8')
    monkeypatch.setattr('kick_player.kick_cookies_file_path', lambda: str(cookie_path))
    monkeypatch.setattr('kick_player.curl_cffi_available', lambda: False)
    opts = kick_ydl_opts(skip_download=True)
    assert opts.get('cookiefile') == str(cookie_path)
    assert 'impersonate' not in opts
    headers = opts.get('http_headers') or {}
    assert headers.get('Referer') == 'https://kick.com/'


def test_kick_ydl_opts_impersonate_when_curl_cffi(tmp_path, monkeypatch):
    """Prueba kick ydl opts impersonate when curl cffi."""
    monkeypatch.setattr('kick_player.curl_cffi_available', lambda: True)
    opts = kick_ydl_opts(skip_download=True, use_cookiefile=False)
    impersonate = opts.get('impersonate')
    assert impersonate is not None
    assert 'chrome' in str(impersonate).lower()


def test_kick_auth_blocked():
    """Prueba kick auth blocked."""
    assert kick_auth_blocked(Exception('HTTP Error 403: Forbidden'))
    assert kick_auth_blocked(Exception('Cloudflare challenge'))
    assert not kick_auth_blocked(Exception('network timeout'))


def test_kick_auth_help_mentions_curl_cffi(monkeypatch):
    """Prueba kick auth help mentions curl cffi."""
    monkeypatch.setattr('kick_player.curl_cffi_available', lambda: False)
    assert 'curl-cffi' in kick_auth_help()
    monkeypatch.setattr('kick_player.curl_cffi_available', lambda: True)
    assert 'curl-cffi' not in kick_auth_help()


def test_kick_favorite_url():
    """Prueba kick favorito URL."""
    assert kick_favorite_url('https://kick.com/demo') == 'https://kick.com/demo'
    assert kick_favorite_url('https://kick.com/demo/videos/uuid-123') == (
        'https://kick.com/demo/videos/uuid-123'
    )


def test_pick_kick_stream():
    """Prueba pick kick stream."""
    info = {
        'title': 'Directo de prueba',
        'is_live': True,
        'formats': [
            {
                'url': 'https://example.com/live.m3u8',
                'protocol': 'm3u8',
                'vcodec': 'avc1',
                'acodec': 'mp4a',
                'height': 720,
            },
        ],
    }
    stream = pick_kick_stream(info, max_height=720)
    assert stream['url'].endswith('live.m3u8')
    assert stream['is_live'] is True
    assert stream['title'] == 'Directo de prueba'


def test_kick_loading_detail():
    """Prueba kick loading detail."""
    stream = {
        'channel': 'demo',
        'title': 'Ranked all day',
        'is_live': True,
        'used_cookies': True,
    }
    detail = kick_loading_detail(stream, url='https://kick.com/demo')
    assert 'Canal: demo' in detail
    assert 'En directo' in detail
    assert 'Con cookies de sesión' in detail


def test_kick_cookies_file_path_under_data_dir(monkeypatch, tmp_path):
    """Prueba kick cookies file path under data dir."""
    monkeypatch.setattr('kick_player.data_dir', lambda: str(tmp_path))
    assert kick_cookies_file_path().endswith('kick_cookies.txt')
