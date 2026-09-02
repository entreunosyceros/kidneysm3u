"""Pruebas de búsqueda lateral y barra de estado del reproductor."""

import tkinter as tk
from tkinter import ttk

from channel_sidebar import ChannelSidebar
from player_status import PlayerStatusMixin


class _StatusHost(PlayerStatusMixin):
    def __init__(self, root):
        self.window = root
        self.player_frame = ttk.Frame(root)
        self.player_frame.pack(fill=tk.BOTH, expand=True)

    def _widget_exists(self, widget):
        if widget is None:
            return False
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False


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
