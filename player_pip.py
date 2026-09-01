"""Ventana PiP y siempre encima. El vídeo sigue en VLC, solo cambia el recuadro."""

import tkinter as tk

from ui_theme import set_window_icon, style_window


def pip_surface_ready(width, height, viewable):
    """VLC en X11 necesita un recuadro ya mapeado y con tamaño real."""
    try:
        w = int(width)
        h = int(height)
    except (TypeError, ValueError):
        return False
    return bool(viewable) and w >= 16 and h >= 16


class PlayerPipMixin:
    """Clase que representa playerpipmixin."""
    def _video_target_frame(self):
        """Uso interno: video target marco."""
        frame = getattr(self, '_pip_frame', None)
        if self._widget_exists(frame):
            return frame
        return getattr(self, 'video_frame', None)

    def _apply_topmost(self):
        """Uso interno: apply topmost."""
        on = bool(getattr(self, '_topmost_var', None) and self._topmost_var.get())
        for window in (getattr(self, 'window', None), getattr(self, '_pip_window', None)):
            if not self._widget_exists(window):
                continue
            try:
                window.attributes('-topmost', on or window is getattr(self, '_pip_window', None))
            except tk.TclError:
                pass

    def toggle_always_on_top(self):
        """Alterna always on top."""
        self._apply_topmost()

    def pip_is_open(self):
        """Pip is open."""
        return self._widget_exists(getattr(self, '_pip_window', None))

    def toggle_pip(self):
        """Alterna PiP."""
        if self.pip_is_open():
            self.close_pip()
        else:
            self.open_pip()

    def open_pip(self):
        """Abre PiP."""
        if not self._widget_exists(self.window) or self.pip_is_open():
            return
        if getattr(self, 'is_fullscreen', False):
            self.exit_fullscreen()
        try:
            pip = tk.Toplevel(self.window, class_='Kidneysm3u')
        except tk.TclError:
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
        frame.bind('<Double-Button-1>', lambda e: self.close_pip())
        self._bind_youtube_title_motion(frame)
        click = getattr(self, '_on_video_click', None)
        if click:
            frame.bind('<Button-1>', click)
        frame.bind('<Map>', lambda e: self._schedule_pip_embed(20))
        try:
            pip.update_idletasks()
            pip.update()
        except tk.TclError:
            pass
        self._apply_topmost()
        self._schedule_pip_embed(30)
        try:
            pip.after(120, lambda: self._schedule_pip_embed(0))
            pip.after(350, lambda: self._schedule_pip_embed(0))
        except tk.TclError:
            pass

    def close_pip(self):
        """Cierra PiP."""
        self._cancel_pip_embed()
        pip = getattr(self, '_pip_window', None)
        self._pip_window = None
        self._pip_frame = None
        self._reembed_vlc()
        if pip is not None:
            try:
                pip.destroy()
            except tk.TclError:
                pass
        self._apply_topmost()

    def _cancel_pip_embed(self):
        """Uso interno: cancel PiP embed."""
        job = getattr(self, '_pip_embed_job', None)
        self._pip_embed_job = None
        if not job:
            return
        host = getattr(self, '_pip_window', None) or getattr(self, 'window', None)
        if not self._widget_exists(host):
            return
        try:
            host.after_cancel(job)
        except tk.TclError:
            pass

    def _schedule_pip_embed(self, delay_ms=50):
        """Uso interno: schedule PiP embed."""
        self._cancel_pip_embed()
        host = getattr(self, '_pip_window', None) or getattr(self, 'window', None)
        if not self._widget_exists(host):
            return
        wait = max(0, int(delay_ms or 0))
        if wait == 0:
            self._reembed_vlc()
            return
        try:
            self._pip_embed_job = host.after(wait, self._reembed_vlc)
        except tk.TclError:
            self._pip_embed_job = None

    def _pip_target_ready(self, target):
        """Uso interno: PiP target ready."""
        if not self._widget_exists(target):
            return False
        if not self.pip_is_open():
            return True
        try:
            return pip_surface_ready(
                target.winfo_width(),
                target.winfo_height(),
                target.winfo_viewable(),
            )
        except tk.TclError:
            return False

    def _player_state_name(self):
        """Uso interno: player state name."""
        try:
            state = self.player.get_state()
        except Exception:
            return ''
        name = getattr(state, 'name', None)
        if name:
            return str(name)
        text = str(state)
        return text.rsplit('.', 1)[-1]

    def _reembed_vlc(self):
        """Uso interno: reembed VLC."""
        self._pip_embed_job = None
        target = self._video_target_frame()
        if not self.player or not self._widget_exists(target):
            return
        if not self._pip_target_ready(target):
            self._schedule_pip_embed(80)
            return
        name = self._player_state_name()
        active = name in ('Playing', 'Paused', 'Buffering', 'Opening')
        paused = name == 'Paused'
        elapsed = 0
        if active:
            try:
                elapsed = int(self.player.get_time() or 0)
            except Exception:
                elapsed = 0
            try:
                self.player.stop()
            except Exception:
                pass
        embed = getattr(self, '_embed_vlc_in_frame', None)
        if not embed:
            return
        try:
            embed()
        except Exception as err:
            print(f'[PiP] No se pudo enganchar VLC: {err}')
            return
        if not active:
            return
        try:
            self.player.play()
        except Exception as err:
            print(f'[PiP] No se pudo reanudar el vídeo: {err}')
            return
        if paused:
            try:
                self.player.pause()
            except Exception:
                pass
        can_seek = elapsed >= 500 and (
            getattr(self, '_playing_youtube', False)
            or int(getattr(self, '_known_duration_ms', 0) or 0) > 0
        )
        apply = getattr(self, '_apply_seek', None)
        if can_seek and callable(apply):
            host = getattr(self, '_pip_window', None) or getattr(self, 'window', None)
            if self._widget_exists(host):
                host.after(280, lambda ms=elapsed: apply(ms))
