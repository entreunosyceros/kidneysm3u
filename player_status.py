"""Barra de estado del reproductor: mensajes y contexto (canal / EPG / fuente)."""

import tkinter as tk
from tkinter import ttk

from display_text import plain_ui_line, plain_display_text


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
        frame = ttk.Frame(self.player_frame, style='Status.TFrame', padding=(10, 4))
        frame.pack(side=tk.BOTTOM, fill=tk.X)
        self._player_status_var = tk.StringVar(value='')
        self._player_context_var = tk.StringVar(value='')
        ttk.Label(
            frame,
            textvariable=self._player_context_var,
            style='Status.TLabel',
        ).pack(anchor=tk.W, fill=tk.X)
        ttk.Label(
            frame,
            textvariable=self._player_status_var,
            style='Status.TLabel',
        ).pack(anchor=tk.W, fill=tk.X)
        self._player_status_frame = frame
        self._player_status_sticky = False
        self._player_status_clear_job = None
        self._source_accent_bar = None

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

    def _playback_source_label(self):
        """Etiqueta corta de la fuente en reproducción."""
        if getattr(self, '_playing_youtube', False):
            return 'YouTube'
        if getattr(self, '_playing_twitch', False):
            return 'Twitch'
        if getattr(self, '_playing_kick', False):
            return 'Kick'
        return 'IPTV'

    def _playback_source_accent(self):
        """Color de acento según fuente."""
        from ui_theme import get_colors
        colors = get_colors()
        if getattr(self, '_playing_youtube', False):
            return '#ef4444'
        if getattr(self, '_playing_twitch', False):
            return '#9146ff'
        if getattr(self, '_playing_kick', False):
            return '#53fc18'
        return colors['accent']

    def refresh_player_context_bar(self):
        """Actualiza la línea canal · EPG · calidad/buffer."""
        if not self._widget_exists(getattr(self, 'window', None)):
            return
        self._ensure_player_status_bar()
        var = getattr(self, '_player_context_var', None)
        if var is None:
            return
        parts = [self._playback_source_label()]
        index = getattr(self, 'current_channel', None)
        name = ''
        if index is not None and 0 <= index < len(getattr(self, 'channels', []) or []):
            try:
                name = plain_display_text(self.channels[index][0])
            except Exception:
                name = ''
        if not name:
            title_fn = getattr(self, '_video_overlay_title', None)
            if callable(title_fn):
                try:
                    name = plain_display_text(title_fn() or '')
                except Exception:
                    name = ''
        if name:
            parts.append(name)
        epg = ''
        if index is not None:
            getter = getattr(self, '_epg_now_title', None)
            if callable(getter):
                try:
                    epg = plain_display_text(getter(index) or '')
                except Exception:
                    epg = ''
        if epg:
            parts.append(epg)
        detail = ''
        if getattr(self, '_playing_youtube', False):
            import app_config
            q = app_config.youtube_quality_label()
            detail = f'Calidad {q}'
        elif getattr(self, '_playing_twitch', False):
            import app_config
            detail = f'Calidad {app_config.twitch_quality_label()}'
        elif getattr(self, '_playing_kick', False):
            import app_config
            detail = f'Calidad {app_config.kick_quality_label()}'
        else:
            import app_config
            buf = app_config.get_iptv_buffer()
            labels = {'fast': 'Rápido', 'balanced': 'Equilibrado', 'stable': 'Estable'}
            detail = f'Buffer {labels.get(buf, buf)}'
            cache_ms = getattr(self, '_iptv_cache_ms', None)
            if cache_ms:
                detail += f' · {int(cache_ms)} ms'
        if detail:
            parts.append(detail)
        var.set(plain_ui_line('  ·  '.join(p for p in parts if p)))
        self._sync_source_accent_bar()

    def _sync_source_accent_bar(self):
        """Franja de color bajo el vídeo según IPTV/YouTube/Twitch/Kick."""
        # En player_frame, no en video_frame: al reproducir se vacían los hijos del vídeo.
        parent = getattr(self, 'player_frame', None)
        video = getattr(self, 'video_frame', None)
        if not self._widget_exists(parent) or not self._widget_exists(video):
            return
        bar = getattr(self, '_source_accent_bar', None)
        color = self._playback_source_accent()
        if not self._widget_exists(bar):
            bar = tk.Frame(parent, height=3, bg=color, highlightthickness=0, bd=0)
            self._source_accent_bar = bar
        else:
            try:
                bar.configure(bg=color)
            except tk.TclError:
                pass
        try:
            bar.place(in_=video, relx=0, rely=0, relwidth=1, height=3)
            bar.lift()
        except tk.TclError:
            pass
