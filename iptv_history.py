"""Ventana de historial IPTV / seguir viendo. No registra URLs."""

import tkinter as tk
from tkinter import ttk, messagebox

import app_config
from ui_theme import (
    center_window, get_colors, set_window_icon, style_window,
)


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
        window.geometry('720x480')
        window.minsize(520, 360)
        style_window(window)
        set_window_icon(window)
        center_window(window, 720, 480)
        window.transient(player.window)
        self.window = window
        self._urls = {}

        top = ttk.Frame(window, padding=(12, 10, 12, 6))
        top.pack(fill=tk.X)
        ttk.Label(top, text='Historial', style='PageTitle.TLabel').pack(side=tk.LEFT)
        ttk.Button(top, text='Cerrar', command=self.close).pack(side=tk.RIGHT)
        ttk.Button(top, text='Vaciar', command=self._clear).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Label(
            window,
            text='Últimos canales y películas a medio ver. El segundo se guarda en VOD; los directos solo quedan en recientes.',
            style='Muted.TLabel',
            wraplength=680,
        ).pack(anchor=tk.W, padx=12, pady=(0, 8))

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
        self._urls = {}
        watching = app_config.iptv_continue_watching()
        recent = app_config.iptv_history()
        if watching:
            self.tree.insert('', 'end', iid='sec:watch', text='Seguir viendo', values=('', ''), tags=('section',))
            for index, item in enumerate(watching):
                self._insert_row(f'w:{index}', item, watching=True)
        self.tree.insert('', 'end', iid='sec:recent', text='Recientes', values=('', ''), tags=('section',))
        if not recent:
            self.tree.insert('', 'end', iid='empty', text='Aún no hay historial', values=('', ''))
            return
        for index, item in enumerate(recent):
            self._insert_row(f'r:{index}', item, watching=False)

    def _insert_row(self, iid, item, watching):
        url = item.get('url') or ''
        self._urls[iid] = url
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

    def _selected_url(self):
        try:
            selection = self.tree.selection()
        except tk.TclError:
            return ''
        if not selection:
            return ''
        return self._urls.get(selection[0], '')

    def _play_selected(self, event=None):
        url = self._selected_url()
        if not url:
            return
        play = getattr(self.player, 'play_history_url', None)
        if play:
            play(url)

    def _remove_selected(self):
        url = self._selected_url()
        if not url:
            return
        app_config.remove_iptv_history(url)
        self.refresh()
        fill = getattr(self.player, '_fill_history_menu', None)
        if fill:
            fill()

    def _clear(self):
        if not app_config.iptv_history():
            return
        if not messagebox.askyesno(
            'Vaciar historial',
            '¿Quitar todos los canales y películas del historial?',
            parent=self.window,
        ):
            return
        app_config.clear_iptv_history()
        self.refresh()
