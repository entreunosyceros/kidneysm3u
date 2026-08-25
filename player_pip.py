"""Ventana PiP y siempre encima. El vídeo sigue en VLC, solo cambia el recuadro."""

import tkinter as tk

from ui_theme import set_window_icon, style_window


class PlayerPipMixin:
    def _video_target_frame(self):
        frame = getattr(self, '_pip_frame', None)
        if self._widget_exists(frame):
            return frame
        return getattr(self, 'video_frame', None)

    def _apply_topmost(self):
        on = bool(getattr(self, '_topmost_var', None) and self._topmost_var.get())
        for window in (getattr(self, 'window', None), getattr(self, '_pip_window', None)):
            if not self._widget_exists(window):
                continue
            try:
                window.attributes('-topmost', on or window is getattr(self, '_pip_window', None))
            except tk.TclError:
                pass

    def toggle_always_on_top(self):
        self._apply_topmost()

    def pip_is_open(self):
        return self._widget_exists(getattr(self, '_pip_window', None))

    def toggle_pip(self):
        if self.pip_is_open():
            self.close_pip()
        else:
            self.open_pip()

    def open_pip(self):
        if not self._widget_exists(self.window) or self.pip_is_open():
            return
        if getattr(self, 'is_fullscreen', False):
            self.exit_fullscreen()
        pip = tk.Toplevel(self.window)
        pip.title('PiP')
        pip.geometry('480x270')
        pip.minsize(280, 160)
        style_window(pip)
        set_window_icon(pip)
        pip.configure(bg='#000000')
        try:
            pip.attributes('-topmost', True)
        except tk.TclError:
            pass
        frame = tk.Frame(pip, bg='#000000', highlightthickness=0, bd=0)
        frame.pack(fill=tk.BOTH, expand=True)
        self._pip_window = pip
        self._pip_frame = frame
        pip.protocol('WM_DELETE_WINDOW', self.close_pip)
        pip.bind('<Escape>', lambda e: self.close_pip())
        pip.bind('<Double-Button-1>', lambda e: self.close_pip())
        click = getattr(self, '_on_video_click', None)
        if click:
            frame.bind('<Button-1>', click)
        self._reembed_vlc()
        self._apply_topmost()

    def close_pip(self):
        pip = getattr(self, '_pip_window', None)
        self._pip_window = None
        self._pip_frame = None
        if pip is not None:
            try:
                pip.destroy()
            except tk.TclError:
                pass
        self._reembed_vlc()
        self._apply_topmost()

    def _reembed_vlc(self):
        ready = getattr(self, '_vlc_is_ready', None)
        if callable(ready) and not ready():
            return
        embed = getattr(self, '_embed_vlc_in_frame', None)
        if embed and self.player:
            try:
                embed()
            except Exception:
                pass
