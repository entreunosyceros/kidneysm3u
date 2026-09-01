"""Cola de YouTube aparte de la lista IPTV: siguiente, quitar y reordenar."""

import tkinter as tk
from tkinter import ttk, messagebox

import app_config
from ui_theme import (
    center_window, get_colors, set_window_icon, style_window,
)
from ui_layout import bind_wraplength, bind_tree_stretch, setup_resizable_dialog


def show_youtube_queue(player):
    if not getattr(player, 'window', None):
        return None
    existing = getattr(player, '_youtube_queue_win', None)
    if existing is not None:
        try:
            if existing.window.winfo_exists():
                existing.window.deiconify()
                existing.window.lift()
                existing.refresh()
                return existing
        except tk.TclError:
            pass
    return YoutubeQueueWindow(player)


class YoutubeQueueWindow:
    def __init__(self, player):
        self.player = player
        player._youtube_queue_win = self
        colors = get_colors()
        window = tk.Toplevel(player.window)
        window.title('Cola de YouTube')
        setup_resizable_dialog(window, 560, 420, 420, 300)
        style_window(window)
        set_window_icon(window)
        window.transient(player.window)
        self.window = window

        top = ttk.Frame(window, padding=(12, 10, 12, 6))
        top.pack(fill=tk.X)
        ttk.Label(top, text='Cola de YouTube', style='PageTitle.TLabel').pack(side=tk.LEFT)
        ttk.Button(top, text='Cerrar', command=self.close).pack(side=tk.RIGHT)

        intro = ttk.Label(
            window,
            text='Lo que añadas aquí se reproduce al terminar el vídeo actual. No se mezcla con la lista IPTV.',
            style='Muted.TLabel',
            wraplength=520,
        )
        intro.pack(anchor=tk.W, padx=12, pady=(0, 8))
        bind_wraplength(window, padding=24)

        body = ttk.Frame(window, padding=(12, 0, 12, 12))
        body.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            body,
            columns=('order',),
            show='tree headings',
            selectmode='browse',
        )
        self.tree.heading('#0', text='Título', anchor=tk.W)
        self.tree.heading('order', text='#', anchor=tk.CENTER)
        self.tree.column('#0', width=420, stretch=True)
        self.tree.column('order', width=40, stretch=False, anchor=tk.CENTER)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bind_tree_stretch(self.tree, stretch_columns=('#0',))
        self.tree.tag_configure('empty', foreground=colors['text_muted'])
        self.tree.bind('<Double-Button-1>', self._play_selected)
        self.tree.bind('<Return>', self._play_selected)
        self.tree.bind('<Delete>', lambda e: self._remove_selected())

        buttons = ttk.Frame(window, padding=(12, 0, 12, 12))
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text='Siguiente', style='Accent.TButton', command=self._play_next).pack(side=tk.LEFT)
        ttk.Button(buttons, text='Reproducir', command=self._play_selected).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text='Quitar', command=self._remove_selected).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text='Subir', command=lambda: self._move(-1)).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text='Bajar', command=lambda: self._move(1)).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text='Vaciar', command=self._clear).pack(side=tk.RIGHT)

        window.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()

    def close(self):
        if getattr(self.player, '_youtube_queue_win', None) is self:
            self.player._youtube_queue_win = None
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def refresh(self):
        if not self.player._widget_exists(self.window):
            return
        try:
            selected = self.tree.selection()
            selected_iid = selected[0] if selected else ''
            self.tree.delete(*self.tree.get_children())
        except tk.TclError:
            return
        queue = app_config.youtube_queue()
        if not queue:
            self.tree.insert('', 'end', iid='empty', text='La cola está vacía', values=('',), tags=('empty',))
            return
        for index, item in enumerate(queue, start=1):
            iid = str(index - 1)
            self.tree.insert('', 'end', iid=iid, text=item.get('name') or 'YouTube', values=(str(index),))
        if selected_iid and self.tree.exists(selected_iid):
            self.tree.selection_set(selected_iid)
            self.tree.see(selected_iid)

    def _selected_index(self):
        try:
            selection = self.tree.selection()
        except tk.TclError:
            return None
        if not selection or selection[0] == 'empty':
            return None
        try:
            return int(selection[0])
        except (TypeError, ValueError):
            return None

    def _play_next(self):
        play = getattr(self.player, 'play_youtube_queue_next', None)
        if play:
            play()

    def _play_selected(self, event=None):
        index = self._selected_index()
        if index is None:
            return
        play = getattr(self.player, 'play_youtube_queue_index', None)
        if play:
            play(index)

    def _remove_selected(self):
        index = self._selected_index()
        if index is None:
            return
        app_config.remove_youtube_queue(index)
        self.refresh()

    def _move(self, delta):
        index = self._selected_index()
        if index is None:
            return
        if not app_config.move_youtube_queue(index, delta):
            return
        self.refresh()
        dest = index + int(delta)
        if self.tree.exists(str(dest)):
            self.tree.selection_set(str(dest))
            self.tree.see(str(dest))

    def _clear(self):
        if not app_config.youtube_queue():
            return
        if not messagebox.askyesno(
            'Vaciar cola',
            '¿Quitar todos los vídeos de la cola?',
            parent=self.window,
        ):
            return
        app_config.clear_youtube_queue()
        self.refresh()
