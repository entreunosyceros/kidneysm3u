"""Ventana de historial IPTV y YouTube. No registra URLs."""

import tkinter as tk
from tkinter import ttk, messagebox

import app_config
from ui_theme import (
    center_window, get_colors, set_window_icon, style_window,
)
from ui_layout import bind_wraplength, bind_tree_stretch, setup_resizable_dialog


def show_iptv_history(player):
    if not getattr(player, 'window', None):
        return None
    existing = getattr(player, '_iptv_history', None)
    if existing is not None:
        try:
            if existing.window.winfo_exists():
                existing.window.deiconify()
                existing.window.lift()
                existing.refresh()
                return existing
        except tk.TclError:
            pass
    return HistoryWindow(player)


class HistoryWindow:
    def __init__(self, player):
        self.player = player
        player._iptv_history = self
        colors = get_colors()
        window = tk.Toplevel(player.window)
        window.title('Historial')
        setup_resizable_dialog(window, 720, 520, 520, 360)
        style_window(window)
        set_window_icon(window)
        window.transient(player.window)
        self.window = window
        self._entries = {}

        top = ttk.Frame(window, padding=(12, 10, 12, 6))
        top.pack(fill=tk.X)
        ttk.Label(top, text='Historial', style='PageTitle.TLabel').pack(side=tk.LEFT)
        ttk.Button(top, text='Cerrar', command=self.close).pack(side=tk.RIGHT)
        ttk.Button(top, text='Vaciar', command=self._clear).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Label(
            window,
            text='IPTV (canales y películas) y YouTube (últimos vídeos). El segundo se guarda en VOD y en YouTube; los directos solo quedan en recientes.',
            style='Muted.TLabel',
            wraplength=680,
        ).pack(anchor=tk.W, padx=12, pady=(0, 8))
        bind_wraplength(window, padding=24)

        body = ttk.Frame(window, padding=(12, 0, 12, 12))
        body.pack(fill=tk.BOTH, expand=True)
        columns = ('when', 'progress')
        self.tree = ttk.Treeview(
            body,
            columns=columns,
            show='tree headings',
            selectmode='browse',
        )
        self.tree.heading('#0', text='Título', anchor=tk.W)
        self.tree.heading('when', text='Tipo', anchor=tk.W)
        self.tree.heading('progress', text='Posición', anchor=tk.W)
        self.tree.column('#0', width=340, stretch=True)
        self.tree.column('when', width=120, stretch=False)
        self.tree.column('progress', width=140, stretch=False)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bind_tree_stretch(self.tree, stretch_columns=('#0',))
        self.tree.tag_configure('section', foreground=colors['text_muted'])
        self.tree.bind('<Double-Button-1>', self._play_selected)
        self.tree.bind('<Return>', self._play_selected)

        buttons = ttk.Frame(window, padding=(12, 0, 12, 12))
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text='Reproducir', style='Accent.TButton', command=self._play_selected).pack(side=tk.LEFT)
        ttk.Button(buttons, text='Quitar', command=self._remove_selected).pack(side=tk.LEFT, padx=(8, 0))

        window.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()

    def close(self):
        if getattr(self.player, '_iptv_history', None) is self:
            self.player._iptv_history = None
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def refresh(self):
        if not self.player._widget_exists(self.window):
            return
        try:
            self.tree.delete(*self.tree.get_children())
        except tk.TclError:
            return
        self._entries = {}
        watching = app_config.iptv_continue_watching()
        recent = app_config.iptv_history()
        yt_watching = app_config.youtube_continue_watching()
        yt_recent = app_config.youtube_history()
        if watching:
            self.tree.insert('', 'end', iid='sec:watch', text='Seguir viendo', values=('', ''), tags=('section',))
            for index, item in enumerate(watching):
                self._insert_iptv(f'w:{index}', item, watching=True)
        self.tree.insert('', 'end', iid='sec:recent', text='Recientes IPTV', values=('', ''), tags=('section',))
        if recent:
            for index, item in enumerate(recent):
                self._insert_iptv(f'r:{index}', item, watching=False)
        else:
            self.tree.insert('', 'end', iid='empty-iptv', text='Aún no hay historial IPTV', values=('', ''))
        if yt_watching:
            self.tree.insert('', 'end', iid='sec:ytwatch', text='Seguir viendo YouTube', values=('', ''), tags=('section',))
            for index, item in enumerate(yt_watching):
                self._insert_youtube(f'ytw:{index}', item, watching=True)
        self.tree.insert('', 'end', iid='sec:ytrecent', text='Recientes YouTube', values=('', ''), tags=('section',))
        if yt_recent:
            for index, item in enumerate(yt_recent):
                self._insert_youtube(f'ytr:{index}', item, watching=False)
        else:
            self.tree.insert('', 'end', iid='empty-yt', text='Aún no hay vídeos de YouTube', values=('', ''))

    def _insert_iptv(self, iid, item, watching):
        url = item.get('url') or ''
        self._entries[iid] = {'kind': 'iptv', 'url': url}
        kind = 'Película / VOD' if item.get('kind') == 'vod' else 'Directo'
        if watching:
            kind = 'Seguir viendo'
        progress = ''
        seconds = int(item.get('s') or 0)
        if item.get('kind') == 'vod' and seconds >= app_config.IPTV_RESUME_MIN_S:
            stamp = app_config.format_iptv_clock(seconds)
            duration = int(item.get('duration') or 0)
            progress = f'{stamp} / {app_config.format_iptv_clock(duration)}' if duration else stamp
        self.tree.insert(
            '',
            'end',
            iid=iid,
            text=item.get('name') or 'Sin nombre',
            values=(kind, progress),
        )

    def _insert_youtube(self, iid, item, watching):
        self._entries[iid] = {
            'kind': 'youtube',
            'url': item.get('url') or '',
            'id': item.get('id') or '',
            'name': item.get('name') or 'YouTube',
        }
        kind = 'Seguir viendo' if watching else 'YouTube'
        progress = ''
        seconds = int(item.get('s') or 0)
        if seconds >= app_config.YT_RESUME_MIN_S:
            stamp = app_config.format_iptv_clock(seconds)
            duration = int(item.get('duration') or 0)
            progress = f'{stamp} / {app_config.format_iptv_clock(duration)}' if duration else stamp
        self.tree.insert(
            '',
            'end',
            iid=iid,
            text=item.get('name') or 'YouTube',
            values=(kind, progress),
        )

    def _selected_entry(self):
        try:
            selection = self.tree.selection()
        except tk.TclError:
            return None
        if not selection:
            return None
        return self._entries.get(selection[0])

    def _play_selected(self, event=None):
        entry = self._selected_entry()
        if not entry:
            return
        url = entry.get('url') or ''
        if not url:
            return
        if entry.get('kind') == 'youtube':
            play = getattr(self.player, 'play_youtube_url', None)
            if play:
                play(url, title=entry.get('name'), add_to_list=False)
            return
        play = getattr(self.player, 'play_history_url', None)
        if play:
            play(url)

    def _remove_selected(self):
        entry = self._selected_entry()
        if not entry:
            return
        if entry.get('kind') == 'youtube':
            app_config.remove_youtube_history(entry.get('id') or '')
        else:
            app_config.remove_iptv_history(entry.get('url') or '')
        self.refresh()
        fill = getattr(self.player, '_fill_history_menu', None)
        if fill:
            fill()

    def _clear(self):
        if not app_config.iptv_history() and not app_config.youtube_history():
            return
        if not messagebox.askyesno(
            'Vaciar historial',
            '¿Quitar el historial de IPTV y de YouTube?',
            parent=self.window,
        ):
            return
        app_config.clear_iptv_history()
        app_config.clear_youtube_history()
        self.refresh()
        fill = getattr(self.player, '_fill_history_menu', None)
        if fill:
            fill()
