"""Pruebas de búsqueda lateral y barra de estado del reproductor."""

import tkinter as tk
from tkinter import ttk

import pytest

from channel_sidebar import ChannelSidebar
from player_status import PlayerStatusMixin


class _StatusHost(PlayerStatusMixin):
    def __init__(self, root):
        self.window = root
        self.player_frame = ttk.Frame(root)
        self.player_frame.pack(fill=tk.BOTH, expand=True)
        self.video_frame = ttk.Frame(self.player_frame)
        self.video_frame.pack(fill=tk.BOTH, expand=True)
        self.channels = [('Canal Demo', 'http://x')]
        self.current_channel = 0
        self._playing_youtube = False
        self._playing_twitch = False
        self._playing_kick = False
        self._iptv_cache_ms = 3000

    def _widget_exists(self, widget):
        if widget is None:
            return False
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def _epg_now_title(self, index):
        return 'Noticias 20:00' if index == 0 else ''


@pytest.mark.gui
def test_sidebar_search_filters_active_group():
    """La búsqueda solo afecta al grupo activo."""
    root = tk.Tk()
    root.withdraw()
    host = ttk.Frame(root)
    host.pack(fill=tk.BOTH, expand=True)
    sidebar = ChannelSidebar(host)
    channels = [('BBC One', 'http://a'), ('BBC Two', 'http://b'), ('CNN', 'http://c')]
    groups = ['UK', 'UK', 'News']
    sidebar.rebuild(channels, groups)
    sidebar.set_active_group('UK')
    count = sidebar.set_search_term('bbc')
    root.update_idletasks()
    assert count == 2
    assert sidebar.current_indices() == [0, 1]
    root.destroy()


@pytest.mark.gui
def test_sidebar_search_highlights_match_in_text():
    """Las coincidencias se marcan en el texto de la fila."""
    root = tk.Tk()
    root.withdraw()
    host = ttk.Frame(root)
    host.pack(fill=tk.BOTH, expand=True)
    sidebar = ChannelSidebar(host)
    sidebar.rebuild([('Canal Deportes HD', 'http://x')], ['Deportes'])
    sidebar.set_search_term('deportes')
    text = sidebar._row_text(0)
    assert '«' in text and '»' in text
    root.destroy()


@pytest.mark.gui
def test_player_status_bar_sets_and_clears():
    """La barra de estado muestra y limpia mensajes."""
    root = tk.Tk()
    root.withdraw()
    host = _StatusHost(root)
    host.set_player_status('Reconectando IPTV…', timeout_ms=0)
    assert 'Reconectando IPTV' in host._player_status_var.get()
    host.clear_player_status('Reconectando IPTV')
    assert host._player_status_var.get() == ''
    root.destroy()


@pytest.mark.gui
def test_player_context_bar_shows_channel_and_epg():
    """La línea de contexto incluye fuente, canal y EPG."""
    root = tk.Tk()
    root.withdraw()
    host = _StatusHost(root)
    host.refresh_player_context_bar()
    text = host._player_context_var.get()
    assert 'IPTV' in text
    assert 'Canal Demo' in text
    assert 'Noticias' in text
    root.destroy()
