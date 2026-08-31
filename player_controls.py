"""Barra de controles, volumen, pantalla completa y play/pausa."""

import tkinter as tk
from tkinter import ttk


class PlayerControlsMixin:
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
        if getattr(self, 'pip_is_open', lambda: False)():
            self.close_pip()
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

    def reset_hide_controls_timer(self):
        """
        Reinicia el temporizador para ocultar controles y menú en pantalla completa.

        SOLUCIÓN AL TIMEOUT: Este método implementa el timeout de 3 segundos que
        oculta automáticamente el menú y controles en fullscreen. Solo se activa
        con interacciones intencionales (clics), no con movimientos de mouse.
        """
        if self.hide_controls_timer:
            self.window.after_cancel(self.hide_controls_timer)
            self.hide_controls_timer = None
        if self.is_fullscreen and not getattr(self, '_iptv_failed', False):
            self.hide_controls_timer = self.window.after(3000, self.hide_controls_and_menu)

    def on_control_interact(self, event=None):
        """
        Manejador para cualquier interacción con los controles en fullscreen.

        SOLUCIÓN AL TIMEOUT: Solo se activa con clics intencionales, no con
        movimientos de mouse, permitiendo que el timeout de 3 segundos funcione.
        """
        widget = getattr(event, 'widget', None) if event is not None else None
        if widget not in (getattr(self, '_audio_btn', None), getattr(self, '_subs_btn', None)):
            self._dismiss_track_menus()
        if self.is_fullscreen:
            self.reset_hide_controls_timer()

    def add_volume_control(self):
        self.volume_scale = ttk.Scale(
            self.controls_frame, from_=0, to=100,
            orient='horizontal', command=self.set_volume
        )
        self.volume_scale.set(self.volume)
        self.volume_scale.pack(side=tk.LEFT, padx=5)

        # SOLUCIÓN TIMEOUT: Solo clics en control de volumen, no <Motion>
        # que causaba reinicio constante del timer
        self.volume_scale.bind('<Button-1>', self.on_control_interact)
        self.volume_scale.bind('<ButtonRelease-1>', self.on_control_interact)

    def set_volume(self, value):
        """Establece el volumen del reproductor"""
        try:
            if self.player:
                self.volume = int(float(value))
                self.player.audio_set_volume(self.volume)
                self._schedule_volume_save()
            # Reiniciar timer si estamos en fullscreen
            if self.is_fullscreen:
                self.reset_hide_controls_timer()
        except Exception as e:
            print(f"Error al ajustar el volumen: {e}")

    def toggle_mute(self):
        self.player.audio_toggle_mute()

    def toggle_fullscreen(self, event=None):
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
            self._hide_channel_status()
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
        self.progress_frame.pack_forget()
