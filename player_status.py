"""Barra de estado del reproductor: mensajes visibles en lugar de solo consola."""

import tkinter as tk
from tkinter import ttk

from display_text import plain_ui_line


class PlayerStatusMixin:
    """Mensajes transientes o persistentes bajo los controles del reproductor."""

    def _ensure_player_status_bar(self):
        """Crea la barra de estado si aún no existe."""
        if getattr(self, '_player_status_frame', None) is not None:
            try:
                if self._player_status_frame.winfo_exists():
                    return
            except tk.TclError:
                pass
        if not self._widget_exists(getattr(self, 'player_frame', None)):
            return
        frame = ttk.Frame(self.player_frame, style='Status.TFrame', padding=(10, 6))
        frame.pack(side=tk.BOTTOM, fill=tk.X)
        self._player_status_var = tk.StringVar(value='')
        ttk.Label(
            frame,
            textvariable=self._player_status_var,
            style='Status.TLabel',
        ).pack(anchor=tk.W, fill=tk.X)
        self._player_status_frame = frame
        self._player_status_sticky = False
        self._player_status_clear_job = None

    def set_player_status(self, text, *, sticky=False, timeout_ms=0):
        """Muestra un mensaje en la barra de estado del reproductor."""
        if not self._widget_exists(getattr(self, 'window', None)):
            return
        self._ensure_player_status_bar()
        label_var = getattr(self, '_player_status_var', None)
        if label_var is None:
            return
        label_var.set(plain_ui_line(text))
        self._player_status_sticky = bool(sticky)
        job = getattr(self, '_player_status_clear_job', None)
        self._player_status_clear_job = None
        if job is not None:
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass
        if timeout_ms > 0 and not sticky:
            expected = label_var.get()
            self._player_status_clear_job = self.window.after(
                timeout_ms,
                lambda msg=expected: self._clear_player_status_timeout(msg),
            )

    def clear_player_status(self, match=None):
        """Quita el mensaje de estado (opcionalmente solo si contiene match)."""
        label_var = getattr(self, '_player_status_var', None)
        if label_var is None:
            return
        current = label_var.get()
        if match and match not in current:
            return
        if getattr(self, '_player_status_sticky', False) and not match:
            return
        if match:
            self._player_status_sticky = False
        label_var.set('')
        job = getattr(self, '_player_status_clear_job', None)
        self._player_status_clear_job = None
        if job is not None:
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass

    def _clear_player_status_timeout(self, expected):
        """Uso interno: limpia mensajes temporales caducados."""
        if getattr(self, '_player_status_sticky', False):
            return
        label_var = getattr(self, '_player_status_var', None)
        if label_var is None:
            return
        if label_var.get() == expected:
            label_var.set('')

    def refresh_ffmpeg_status_hint(self):
        """Aviso persistente si falta ffmpeg."""
        try:
            from onboarding import find_executable
            has_ffmpeg = bool(find_executable('ffmpeg'))
        except Exception:
            has_ffmpeg = False
        if has_ffmpeg:
            self.clear_player_status('Sin ffmpeg')
            return
        self.set_player_status(
            'Sin ffmpeg · grabación IPTV y audio YouTube limitados',
            sticky=True,
        )
