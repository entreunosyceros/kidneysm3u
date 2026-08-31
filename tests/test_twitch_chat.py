import urllib.request

from twitch_chat import (
    _ChatServer,
    can_show_twitch_chat,
    chat_backend_status,
    chat_embed_html,
    pywebview_gtk_ready,
    resolve_twitch_channel,
    system_python_with_gi,
    twitch_chat_window_url,
    twitch_popout_chat_url,
)


class _FakeHandler:
    def __init__(self, stream=None, url=''):
        self._current_stream = stream or {}
        self._current_url = url


def test_chat_embed_html_uses_matching_parent():
    html = chat_embed_html('DemoChannel', '127.0.0.1')
    assert 'embed/demochannel/chat?parent=127.0.0.1' in html.lower()
    assert 'darkpopout' in html
    assert 'allow-scripts' in html


def test_twitch_chat_window_url_uses_popout():
    assert twitch_chat_window_url('DemoChannel') == (
        'https://www.twitch.tv/popout/demochannel/chat?popout='
    )


def test_twitch_popout_chat_url():
    assert twitch_popout_chat_url('DemoChannel') == (
        'https://www.twitch.tv/popout/demochannel/chat?popout='
    )


def test_can_show_twitch_chat_only_for_live():
    live = _FakeHandler({'is_live': True, 'channel': 'demo'}, 'https://www.twitch.tv/demo')
    vod = _FakeHandler({'is_live': False, 'channel': 'demo'}, 'https://www.twitch.tv/videos/1')
    assert can_show_twitch_chat(live) is True
    assert can_show_twitch_chat(vod) is False


def test_resolve_twitch_channel_prefers_stream_name():
    handler = _FakeHandler({'is_live': True, 'channel': 'DemoChannel'}, 'https://www.twitch.tv/other')
    assert resolve_twitch_channel(handler) == 'demochannel'


def test_resolve_twitch_channel_from_url():
    handler = _FakeHandler({'is_live': True, 'channel': ''}, 'https://www.twitch.tv/livechannel')
    assert resolve_twitch_channel(handler) == 'livechannel'


def test_chat_server_serves_embed_page():
    server = _ChatServer()
    port = server.start('demo')
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=2) as response:
            body = response.read().decode('utf-8')
        assert 'embed/demo/chat?parent=127.0.0.1' in body
    finally:
        server.stop()


def test_chat_backend_status_has_fallback():
    backend, _detail = chat_backend_status()
    assert backend in ('pywebview', 'system_gtk', 'browser')


def test_system_python_with_gi_finds_ubuntu_python():
    py = system_python_with_gi()
    if py:
        assert py.endswith('python3') or 'python3' in py


def test_pywebview_gtk_ready_is_bool():
    assert isinstance(pywebview_gtk_ready(), bool)
