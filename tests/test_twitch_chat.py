"""Módulo de test twitch chat."""

import os
import sys
import urllib.request

import pytest

from twitch_chat import (
    _ChatServer,
    _browser_fallback_reason,
    can_show_twitch_chat,
    chat_backend_status,
    chat_embed_html,
    linux_ci_runner,
    pywebview_gtk_ready,
    pywebview_integrated_ready,
    resolve_twitch_channel,
    system_python_with_gi,
    twitch_chat_window_url,
    twitch_popout_chat_url,
)

_LINUX_CI = linux_ci_runner()
_WINDOWS_CI = (
    sys.platform == 'win32'
    and os.environ.get('CI', '').lower() in ('1', 'true', 'yes')
)

skip_linux_ci_native_gui = pytest.mark.skipif(
    _LINUX_CI,
    reason='Imports GTK/WebKit nativos no fiables en el runner CI de Linux',
)


def test_linux_ci_runner_detects_github_actions(monkeypatch):
    """Prueba linux ci runner detects github actions."""
    monkeypatch.setattr('twitch_chat.sys.platform', 'linux')
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.delenv('CI', raising=False)
    assert linux_ci_runner() is False
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    assert linux_ci_runner() is True


class _FakeHandler:
    """Clase que representa fakehandler."""
    def __init__(self, stream=None, url=''):
        """Inicializa _FakeHandler."""
        self._current_stream = stream or {}
        self._current_url = url


def test_chat_embed_html_uses_matching_parent():
    """Prueba chat embed html uses matching parent."""
    html = chat_embed_html('DemoChannel', '127.0.0.1')
    assert 'embed/demochannel/chat?parent=127.0.0.1' in html.lower()
    assert 'darkpopout' in html
    assert 'allow-scripts' in html


def test_twitch_chat_window_url_uses_popout():
    """Prueba twitch chat ventana URL uses popout."""
    assert twitch_chat_window_url('DemoChannel') == (
        'https://www.twitch.tv/popout/demochannel/chat?popout='
    )


def test_twitch_popout_chat_url():
    """Prueba twitch popout chat URL."""
    assert twitch_popout_chat_url('DemoChannel') == (
        'https://www.twitch.tv/popout/demochannel/chat?popout='
    )


def test_can_show_twitch_chat_only_for_live():
    """Prueba can show twitch chat only for live."""
    live = _FakeHandler({'is_live': True, 'channel': 'demo'}, 'https://www.twitch.tv/demo')
    vod = _FakeHandler({'is_live': False, 'channel': 'demo'}, 'https://www.twitch.tv/videos/1')
    assert can_show_twitch_chat(live) is True
    assert can_show_twitch_chat(vod) is False


def test_resolve_twitch_channel_prefers_stream_name():
    """Prueba resolve twitch canal prefers stream name."""
    handler = _FakeHandler({'is_live': True, 'channel': 'DemoChannel'}, 'https://www.twitch.tv/other')
    assert resolve_twitch_channel(handler) == 'demochannel'


def test_resolve_twitch_channel_from_url():
    """Prueba resolve twitch canal from URL."""
    handler = _FakeHandler({'is_live': True, 'channel': ''}, 'https://www.twitch.tv/livechannel')
    assert resolve_twitch_channel(handler) == 'livechannel'


@pytest.mark.skipif(
    _WINDOWS_CI,
    reason='ThreadingHTTPServer.shutdown provoca fatal exception en Windows CI',
)
def test_chat_server_serves_embed_page():
    """Prueba chat server serves embed page."""
    server = _ChatServer()
    port = server.start('demo')
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=2) as response:
            body = response.read().decode('utf-8')
        assert 'embed/demo/chat?parent=127.0.0.1' in body
    finally:
        server.stop()


def test_chat_embed_html_matches_server_content():
    """El HTML del embed (sin servidor HTTP) incluye el chat de Twitch."""
    html = chat_embed_html('demo', '127.0.0.1')
    assert 'embed/demo/chat?parent=127.0.0.1' in html.lower()


@skip_linux_ci_native_gui
def test_chat_backend_status_has_fallback():
    """Prueba chat backend status has fallback."""
    backend, _detail = chat_backend_status()
    assert backend in ('pywebview', 'system_gtk', 'browser')


@skip_linux_ci_native_gui
def test_system_python_with_gi_finds_ubuntu_python():
    """Prueba system python with gi finds ubuntu python."""
    py = system_python_with_gi()
    if py:
        assert py.endswith('python3') or 'python3' in py


@skip_linux_ci_native_gui
def test_pywebview_gtk_ready_is_bool():
    """Prueba pywebview gtk ready is bool."""
    assert isinstance(pywebview_gtk_ready(), bool)


@skip_linux_ci_native_gui
def test_pywebview_integrated_ready_is_bool():
    """Prueba pywebview integrated ready is bool."""
    assert isinstance(pywebview_integrated_ready(), bool)


def test_browser_fallback_reason_platform_specific(monkeypatch):
    """El aviso de respaldo no menciona paquetes de Linux en Windows."""
    monkeypatch.setattr('twitch_chat.sys.platform', 'win32')
    monkeypatch.setattr('twitch_chat.webview', object())
    text = _browser_fallback_reason()
    assert 'pythonnet' in text.lower()
    assert 'ubuntu' not in text.lower()
    assert 'python3-gi' not in text.lower()


def test_system_python_with_gi_skips_non_linux(monkeypatch):
    """En Windows no busca python3 del sistema con gi."""
    monkeypatch.setattr('twitch_chat.sys.platform', 'win32')
    assert system_python_with_gi() == ''
