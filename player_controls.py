"""Barra de controles, volumen, pantalla completa y play/pausa."""

import time
import tkinter as tk
from tkinter import ttk


class PlayerControlsMixin:
    """Clase que representa playercontrolsmixin."""

    def hide_controls_and_menu(self):
        """Oculta controles y menú superior juntos (solo en fullscreen el menú)."""
        if getattr(self, '_posted_popup', None) or (
            callable(getattr(self, '_any_track_menu_mapped', None))
            and self._any_track_menu_mapped()
        ):
            self.reset_hide_controls_timer()
            return
        self._dismiss_track_menus()
        if self.controls_visible:
            self.controls_frame.pack_forget()
            self.controls_visible = False
        # Ocultar menú superior solo si estamos en fullscreen
        if self.is_fullscreen:
            self.window.config(menu="")
        # Cancelar temporizador si existe
        if self.hide_controls_timer:
            self.window.after_cancel(self.hide_controls_timer)
            self.hide_controls_timer = None

    def show_controls_and_menu(self):
        """Muestra controles y menú superior juntos."""
        if not self.controls_visible:
            self.controls_frame.pack(fill=tk.X, pady=5)
            self.controls_visible = True

        # Mostrar menú solo si estamos en fullscreen
        if self.is_fullscreen:
            self.window.config(menu=self.menubar)
            # Siempre reiniciar el timeout cuando se muestran controles en fullscreen
            self.reset_hide_controls_timer()
        else:
            # Fuera de pantalla completa el menú ya está visible; no reaplicarlo (provoca parpadeo)
            pass

    def enter_fullscreen(self):
        """Enter fullscreen."""
        if getattr(self, 'pip_is_open', lambda: False)():
            self.close_pip()
        self._cinema_hid_sidebar = False
        self.window.attributes('-fullscreen', True)
        self.is_fullscreen = True
        self.window.config(menu="")  # Ocultar menú superior
        if self.channels_frame_visible:
            self.channels_frame.pack_forget()
            self.sizer.pack_forget()  # Ocultar también el sizer
        else:
            # Por si acaso el sizer quedó visible
            self.sizer.pack_forget()
        self.hide_controls_and_menu()  # Ocultar controles y menú al entrar en fullscreen

    def exit_fullscreen(self):
        """Exit fullscreen."""
        self.window.attributes('-fullscreen', False)
        self.is_fullscreen = False
        self.window.config(menu=self.menubar)
        if self.channels_frame_visible:
            self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)
            self.sizer.pack(side=tk.LEFT, fill=tk.Y)
        if self.hide_controls_timer:
            self.window.after_cancel(self.hide_controls_timer)
            self.hide_controls_timer = None
        self.show_controls_and_menu()
        apply = getattr(self, '_apply_topmost', None)
        if apply:
            apply()

    def _cinema_mode_enabled(self):
        """True si el modo solo vídeo por idle está activo."""
        try:
            import app_config
            return bool(app_config.get_cinema_mode_idle())
        except Exception:
            return False

    def _cinema_idle_ms(self):
        """Milisegundos de idle para modo solo vídeo."""
        try:
            import app_config
            return int(float(app_config.get_cinema_mode_idle_s()) * 1000)
        except Exception:
            return 4000

    def arm_cinema_mode(self, settle_s=6.0):
        """Tras iniciar reproducción: no ocultar chrome hasta settle_s (evita parpadeo)."""
        self._cinema_earliest_hide_at = time.time() + max(2.0, float(settle_s))
        if self.is_fullscreen or self._cinema_mode_enabled():
            self.reset_hide_controls_timer()

    def _reveal_cinema_chrome(self):
        """Restaura lista/controles ocultados por el modo solo vídeo."""
        if getattr(self, '_cinema_hid_sidebar', False):
            self._cinema_hid_sidebar = False
            if self.channels_frame_visible and not self.is_fullscreen:
                try:
                    self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)
                    self.sizer.pack(side=tk.LEFT, fill=tk.Y)
                except tk.TclError:
                    pass
        if not self.controls_visible:
            # Evitar bucle con show_controls → reset en fullscreen
            was_fs = self.is_fullscreen
            if not self.controls_visible:
                self.controls_frame.pack(fill=tk.X, pady=5)
                self.controls_visible = True
            if was_fs:
                try:
                    self.window.config(menu=self.menubar)
                except tk.TclError:
                    pass

    def _idle_hide_chrome(self):
        """Oculta chrome tras idle (fullscreen o modo solo vídeo)."""
        self.hide_controls_timer = None
        if getattr(self, '_posted_popup', None) or (
            callable(getattr(self, '_any_track_menu_mapped', None))
            and self._any_track_menu_mapped()
        ):
            self.reset_hide_controls_timer()
            return
        earliest = float(getattr(self, '_cinema_earliest_hide_at', 0) or 0)
        now = time.time()
        if not self.is_fullscreen and now < earliest:
            delay = max(200, int((earliest - now) * 1000))
            try:
                self.hide_controls_timer = self.window.after(delay, self._idle_hide_chrome)
            except tk.TclError:
                pass
            return
        if self.is_fullscreen:
            self.hide_controls_and_menu()
            return
        if not self._cinema_mode_enabled():
            return
        if self.channels_frame_visible and not getattr(self, '_cinema_hid_sidebar', False):
            try:
                self.channels_frame.pack_forget()
                self.sizer.pack_forget()
                self._cinema_hid_sidebar = True
            except tk.TclError:
                pass
        self.hide_controls_and_menu()

    def reset_hide_controls_timer(self):
        """
        Reinicia el temporizador para ocultar controles (fullscreen o modo solo vídeo).

        No usa <Motion>: con VLC embebido reinicia el timer sin parar y provoca parpadeo.
        """
        if self.hide_controls_timer:
            try:
                self.window.after_cancel(self.hide_controls_timer)
            except tk.TclError:
                pass
            self.hide_controls_timer = None
        if getattr(self, '_iptv_failed', False):
            return
        if self.is_fullscreen:
            idle_ms = 3000
        elif self._cinema_mode_enabled():
            idle_ms = self._cinema_idle_ms()
        else:
            return
        try:
            self.hide_controls_timer = self.window.after(idle_ms, self._idle_hide_chrome)
        except tk.TclError:
            self.hide_controls_timer = None

    def on_control_interact(self, event=None):
        """
        Manejador para cualquier interacción con los controles.
        """
        widget = getattr(event, 'widget', None) if event is not None else None
        if widget not in (getattr(self, '_audio_btn', None), getattr(self, '_subs_btn', None)):
            self._dismiss_track_menus()
        if getattr(self, '_cinema_hid_sidebar', False) or not self.controls_visible:
            self._reveal_cinema_chrome()
        if self.is_fullscreen or self._cinema_mode_enabled():
            self.reset_hide_controls_timer()

    def on_video_activity(self, event=None):
        """Clic/actividad intencional sobre el vídeo (no Motion)."""
        if getattr(self, '_cinema_hid_sidebar', False) or not self.controls_visible:
            self._reveal_cinema_chrome()
            if self.is_fullscreen or self._cinema_mode_enabled():
                self.reset_hide_controls_timer()
            return True
        if self.is_fullscreen:
            self.show_controls_and_menu()
            return True
        return False

    def add_volume_control(self):
        """Añade volume control."""
        host = getattr(self, 'controls_buttons_frame', None) or self.controls_frame
        wrap = ttk.Frame(host)
        wrap.pack(side=tk.LEFT, padx=(22, 10), pady=2)
        length = 96 if self._control_density_compact() else 118
        self.volume_scale = ttk.Scale(
            wrap,
            from_=0,
            to=100,
            orient='horizontal',
            length=length,
            command=self.set_volume,
        )
        self.volume_scale.set(self.volume)
        self.volume_scale.pack(side=tk.LEFT)

        # Solo clics en control de volumen, no <Motion>
        self.volume_scale.bind('<Button-1>', self.on_control_interact)
        self.volume_scale.bind('<ButtonRelease-1>', self.on_control_interact)

    def _control_density_compact(self):
        """True si los controles van en modo compacto."""
        try:
            import app_config
            return app_config.get_ui_control_density() == 'compact'
        except Exception:
            return False

    def set_volume(self, value):
        """Establece el volumen del reproductor"""
        try:
            if self.player:
                self.volume = int(float(value))
                self.player.audio_set_volume(self.volume)
                self._schedule_volume_save()
            if self.is_fullscreen or self._cinema_mode_enabled():
                self.reset_hide_controls_timer()
        except Exception as e:
            print(f"Error al ajustar el volumen: {e}")

    def toggle_mute(self):
        """Alterna mute."""
        self.player.audio_toggle_mute()

    def toggle_fullscreen(self, event=None):
        """Alterna fullscreen."""
        if not self.is_fullscreen:
            self.enter_fullscreen()
        else:
            self.exit_fullscreen()

    def toggle_play(self):
        """Alterna entre reproducir y pausar el vídeo actual."""
        if self.player:
            if self.player.is_playing():
                self.player.pause()
            else:
                self.player.play()

    def stop(self):
        """Detiene la reproducción del vídeo actual y reinicia el estado del reproductor."""
        try:
            self.save_youtube_resume()
            self.save_iptv_resume()
            self.save_twitch_resume()
            stop_rec = getattr(self, 'stop_stream_recording', None)
            if stop_rec:
                stop_rec(notify=False)
            # Usar método de limpieza segura
            self._cleanup_vlc_player()
            # Ocultar la barra de progreso
            self.hide_progress_bar()
            if hasattr(self, 'youtube_handler') and self.youtube_handler:
                self.youtube_handler.cancel_pending_play()
            twitch = getattr(self, 'twitch_handler', None)
            if twitch:
                twitch.cancel_pending_play()
                twitch.close_chat()
            kick = getattr(self, 'kick_handler', None)
            if kick:
                kick.cancel_pending_play()
            self._playing_twitch = False
            self._playing_kick = False
            self._hide_youtube_title_overlay()
            self._hide_channel_status()
            refresh = getattr(self, 'refresh_player_context_bar', None)
            if callable(refresh):
                refresh()
        except Exception as e:
            print(f"Error al detener la reproducción: {e}")

        self.stop_update_time()
        # Resetear el estado de reproducción secuencial
        self.is_sequential_playback = False
        self.current_playlist_index = None

    def show_youtube_progress_bar(self):
        """Muestra y configura la barra de progreso para videos de YouTube."""
        pack_opts = {'fill': tk.X, 'padx': 8, 'pady': (0, 6)}
        if getattr(self, 'controls_buttons_frame', None):
            self.progress_frame.pack(before=self.controls_buttons_frame, **pack_opts)
        else:
            self.progress_frame.pack(**pack_opts)
        self._progress_internal = True
        try:
            self.progress_bar.set(0)
        finally:
            self._progress_internal = False
        if hasattr(self, 'progress_time_label'):
            total = self._format_clock(self._known_duration_ms) if self._known_duration_ms else '--:--'
            self.progress_time_label.configure(text=f'00:00 / {total}')
        self.progress_bar.state(['!disabled'])

    def hide_progress_bar(self):
        """Hide progress bar."""
        self.progress_frame.pack_forget()
