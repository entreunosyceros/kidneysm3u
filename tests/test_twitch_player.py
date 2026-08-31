import app_config
from twitch_player import (
    _jar_has_live_twitch_login,
    _twitch_cookie_keep,
    fetch_twitch_channel_vods,
    fetch_twitch_latest_vod,
    inspect_twitch_session,
    is_twitch_channel_url,
    is_twitch_offline_error,
    is_twitch_url,
    is_twitch_vod_url,
    normalize_twitch_channel_input,
    normalize_twitch_url,
    pick_twitch_stream,
    probe_twitch_channel_live,
    twitch_auth_blocked,
    twitch_cookies_file_path,
    twitch_default_title,
    twitch_display_name_from_url,
    twitch_favorite_url,
    twitch_history_id,
    twitch_loading_detail,
    twitch_ydl_opts,
)


def test_is_twitch_url_accepts_common_links():
    assert is_twitch_url('https://www.twitch.tv/somechannel')
    assert is_twitch_url('https://m.twitch.tv/other')
    assert is_twitch_url('https://www.twitch.tv/videos/1234567890')
    assert is_twitch_url('https://clips.twitch.tv/CleverClipName')
    assert is_twitch_url('https://www.twitch.tv/streamer/clip/FunnyMoment')


def test_is_twitch_url_rejects_other_sites():
    assert not is_twitch_url('https://youtube.com/watch?v=abc')
    assert not is_twitch_url('https://example.com/twitch.tv/fake')
    assert not is_twitch_url('')
    assert not is_twitch_url('twitch.tv/channel')


def test_is_twitch_channel_url():
    assert is_twitch_channel_url('https://www.twitch.tv/shroud')
    assert is_twitch_channel_url('https://m.twitch.tv/ninja')
    assert not is_twitch_channel_url('https://www.twitch.tv/videos/1234567890')
    assert not is_twitch_channel_url('https://clips.twitch.tv/FancyClip')
    assert not is_twitch_channel_url('https://www.twitch.tv/streamer/clip/MyClip')
    assert not is_twitch_channel_url('https://www.twitch.tv/shroud/videos')


def test_is_twitch_offline_error():
    assert is_twitch_offline_error(Exception('shroud: The channel is not currently live'))
    assert not is_twitch_offline_error(Exception('network timeout'))


def test_normalize_twitch_channel_input():
    assert normalize_twitch_channel_input('shroud') == 'shroud'
    assert normalize_twitch_channel_input('@ninja') == 'ninja'
    assert normalize_twitch_channel_input('https://www.twitch.tv/shroud') == 'shroud'
    assert normalize_twitch_channel_input('https://www.twitch.tv/videos/123') == ''


def test_fetch_twitch_latest_vod(monkeypatch):
    monkeypatch.setattr(
        'twitch_player.fetch_twitch_channel_vods',
        lambda channel, limit=1: (
            [{'url': 'https://www.twitch.tv/videos/999', 'title': 'Stream de ayer', 'id': '999'}],
            'demo',
        ),
    )
    latest = fetch_twitch_latest_vod('demo')
    assert latest['url'] == 'https://www.twitch.tv/videos/999'
    assert latest['title'] == 'Stream de ayer'
    assert latest['channel'] == 'demo'


def test_fetch_twitch_channel_vods(monkeypatch):
    class _FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=False):
            assert '/videos' in url
            assert self.opts.get('playlistend') == 30
            return {
                'channel': 'DemoChannel',
                'entries': [
                    {
                        'url': 'https://www.twitch.tv/videos/111',
                        'title': 'Partida 1',
                        'duration': 3661,
                    },
                    {
                        'url': 'https://www.twitch.tv/videos/222',
                        'title': 'Partida 2',
                        'duration': 120,
                    },
                ],
            }

    monkeypatch.setattr('yt_dlp.YoutubeDL', _FakeYDL)
    videos, name = fetch_twitch_channel_vods('demo', limit=30)
    assert name == 'DemoChannel'
    assert len(videos) == 2
    assert videos[0]['url'] == 'https://www.twitch.tv/videos/111'
    assert videos[0]['duration'] == 3661


def test_probe_twitch_channel_live(monkeypatch):
    class _LiveYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=False):
            return {'is_live': True, 'title': 'Ranked grind'}

    monkeypatch.setattr('yt_dlp.YoutubeDL', _LiveYDL)
    info = probe_twitch_channel_live('shroud')
    assert info['live'] is True
    assert info['title'] == 'Ranked grind'
    assert info['url'] == 'https://www.twitch.tv/shroud'


def test_probe_twitch_channel_offline(monkeypatch):
    class _OfflineYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def extract_info(self, url, download=False):
            raise Exception('The channel is not currently live')

    monkeypatch.setattr('yt_dlp.YoutubeDL', _OfflineYDL)
    info = probe_twitch_channel_live('offlinechan')
    assert info['live'] is False


def test_normalize_and_history_id():
    url = 'https://WWW.Twitch.tv/Channel/?referrer=home'
    assert normalize_twitch_url(url) == url
    assert twitch_history_id(url).endswith('/channel')


def test_twitch_display_name_from_url():
    assert twitch_display_name_from_url('https://www.twitch.tv/shroud') == 'shroud'
    assert twitch_display_name_from_url('https://m.twitch.tv/ninja') == 'ninja'
    assert twitch_display_name_from_url('https://www.twitch.tv/videos/1234567890') == 'VOD 1234567890'
    assert twitch_display_name_from_url('https://clips.twitch.tv/FancyClip') == 'FancyClip'
    assert twitch_display_name_from_url('https://www.twitch.tv/streamer/clip/MyClip') == 'MyClip'


def test_twitch_default_title_prefers_real_title():
    url = 'https://www.twitch.tv/shroud'
    assert twitch_default_title(url) == 'shroud'
    assert twitch_default_title(url, 'Shroud en directo') == 'Shroud en directo'
    assert twitch_default_title(url, 'Twitch') == 'shroud'


def test_pick_twitch_stream_prefers_hls():
    info = {
        'title': 'Directo de prueba',
        'is_live': True,
        'http_headers': {'Referer': 'https://www.twitch.tv/'},
        'formats': [
            {
                'url': 'https://example.com/prog.mp4',
                'protocol': 'https',
                'vcodec': 'avc1',
                'acodec': 'mp4a',
                'height': 720,
            },
            {
                'url': 'https://example.com/live.m3u8',
                'protocol': 'm3u8',
                'vcodec': 'avc1',
                'acodec': 'mp4a',
                'height': 720,
            },
        ],
    }
    stream = pick_twitch_stream(info, max_height=720)
    assert stream['url'].endswith('live.m3u8')
    assert stream['is_live'] is True
    assert stream['title'] == 'Directo de prueba'


def test_twitch_history(tmp_path, monkeypatch):
    previous = app_config._cache
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    try:
        url = 'https://www.twitch.tv/demo'
        app_config.remember_twitch_watch(url, title='Canal demo')
        items = app_config.twitch_history()
        assert len(items) == 1
        assert items[0]['name'] == 'Canal demo'
        assert app_config.twitch_history_item_by_url(url)['name'] == 'Canal demo'
        assert app_config.twitch_history_label(items[0]) == 'Twitch · Canal demo'
        app_config.clear_twitch_history()
        assert app_config.twitch_history() == []
    finally:
        app_config._cache = previous


def test_twitch_vod_resume(tmp_path, monkeypatch):
    previous = app_config._cache
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    try:
        url = 'https://www.twitch.tv/videos/1234567890'
        app_config.remember_twitch_watch(url, title='VOD demo')
        app_config.update_twitch_position(url, 120, duration_s=3600)
        item = app_config.twitch_history_item_by_url(url)
        assert item['kind'] == 'vod'
        assert item['s'] == 120
        assert app_config.twitch_resume_seconds(url, duration_s=3600) == 120
        assert '02:00' in app_config.twitch_history_label(item, with_time=True)
        watching = app_config.twitch_continue_watching()
        assert len(watching) == 1
        app_config.clear_twitch_position(url)
        assert app_config.twitch_resume_seconds(url) == 0
        assert app_config.twitch_continue_watching() == []
    finally:
        app_config._cache = previous


def test_is_twitch_vod_url():
    assert is_twitch_vod_url('https://www.twitch.tv/videos/1234567890')
    assert not is_twitch_vod_url('https://www.twitch.tv/shroud')
    assert not is_twitch_vod_url('https://clips.twitch.tv/FancyClip')


class _FakeCookie:
    def __init__(self, name, value, domain='.twitch.tv', expires=None):
        self.name = name
        self.value = value
        self.domain = domain
        self.expires = expires


def test_jar_has_live_twitch_login():
    assert _jar_has_live_twitch_login([_FakeCookie('auth-token', 'abc123')])
    assert not _jar_has_live_twitch_login([_FakeCookie('auth-token', 'abc123', expires=1)])
    assert not _jar_has_live_twitch_login([_FakeCookie('session', 'x')])


def test_twitch_cookie_keep():
    now = 2_000_000_000
    assert _twitch_cookie_keep(_FakeCookie('auth-token', 'x'), now=now)
    assert not _twitch_cookie_keep(_FakeCookie('auth-token', 'x', expires=now - 10), now=now)
    assert not _twitch_cookie_keep(_FakeCookie('auth-token', 'x', domain='youtube.com'), now=now)


def test_inspect_twitch_session(tmp_path):
    path = tmp_path / 'twitch_cookies.txt'
    assert inspect_twitch_session(str(path))['ok'] is False
    path.write_text(
        '# Netscape HTTP Cookie File\n'
        '.twitch.tv\tTRUE\t/\tTRUE\t0\tauth-token\tsecret\n',
        encoding='utf-8',
    )
    info = inspect_twitch_session(str(path))
    assert info['ok'] is True
    assert info['label'] == 'OK'


def test_twitch_ydl_opts_uses_cookiefile(tmp_path, monkeypatch):
    cookie_path = tmp_path / 'twitch_cookies.txt'
    cookie_path.write_text('# empty\n', encoding='utf-8')
    monkeypatch.setattr('twitch_player.twitch_cookies_file_path', lambda: str(cookie_path))
    opts = twitch_ydl_opts(skip_download=True)
    assert opts.get('cookiefile') == str(cookie_path)


def test_twitch_auth_blocked():
    assert twitch_auth_blocked(Exception('This video is subscribers-only'))
    assert not twitch_auth_blocked(Exception('network timeout'))


def test_twitch_favorite_url():
    assert twitch_favorite_url('https://www.twitch.tv/shroud') == 'https://www.twitch.tv/shroud'
    assert twitch_favorite_url('https://www.twitch.tv/videos/1234567890') == (
        'https://www.twitch.tv/videos/1234567890'
    )
    assert twitch_favorite_url('https://clips.twitch.tv/FancyClip') == (
        'https://clips.twitch.tv/FancyClip'
    )


def test_twitch_loading_detail():
    stream = {
        'channel': 'shroud',
        'title': 'Ranked all day',
        'is_live': True,
        'used_cookies': True,
        'subscriber_only': True,
    }
    detail = twitch_loading_detail(stream, 'https://www.twitch.tv/shroud')
    assert 'Canal: shroud' in detail
    assert 'Ranked all day' in detail
    assert 'En directo' in detail
    assert 'Con cookies' in detail
    assert 'suscriptor' in detail.lower()


def test_effective_twitch_quality_independent(tmp_path, monkeypatch):
    previous = app_config._cache
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    try:
        app_config.save({'youtube_quality': 360, 'twitch_quality': 1080})
        assert app_config.effective_youtube_quality() == 360
        assert app_config.effective_twitch_quality() == 1080
        assert app_config.twitch_quality_label() == '1080p'
    finally:
        app_config._cache = previous
