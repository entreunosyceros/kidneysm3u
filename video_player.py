import os
import pathlib
import time
import shutil
import subprocess
import tempfile
import psutil
from http.server import ThreadingHTTPServer
from favorites_manager import FavoritesManager
import vlc
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import sys
import requests
import re
import threading
import yt_dlp
import traceback
from youtube_player import YouTubeHandler, youtube_ydl_opts, _GrowingTSHandler
from youtube_search import YouTubeSearchDialog
from ui_theme import (
    get_colors, get_font, style_window, style_listbox, style_menu_tree,
    set_window_icon, make_control_icons,
)
import app_config
from m3u_parse import (
    parse_m3u_entries, decode_m3u_bytes, describe_iptv_url,
    classify_iptv_url, iptv_upstream_candidates,
    IPTV_USER_AGENT,
)

# Clase Tooltip para mostrar información al pasar el ratón
class Tooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text, x=None, y=None):
        """Muestra el tooltip con el texto dado, cerca del puntero del ratón"""
        if self.tipwindow or not text:
            return
        # Si no se pasan coordenadas, usar la posición actual del puntero
        if x is None or y is None:
            x = self.widget.winfo_pointerx() + 20
            y = self.widget.winfo_pointery() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f"+{x}+{y}")
        colors = get_colors()
        label = tk.Label(
            tw,
            text=text,
            justify=tk.LEFT,
            background=colors['tooltip_bg'],
            foreground=colors['tooltip_fg'],
            relief=tk.FLAT,
            borderwidth=0,
            font=get_font(9),
            padx=8,
            pady=5,
        )
        label.pack()

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


def _make_vlc_instance():
    """Instancia VLC sin aceleración VA-API (ruidosa en NVIDIA) y con logs bajos."""
    os.environ['LIBVA_MESSAGING_LEVEL'] = '0'
    return vlc.Instance(
        "--quiet",
        "--verbose=0",
        "--avcodec-hw=none",
        "--aout=alsa",
        "--audio-resampler=soxr",
        "--network-caching=3000",
        "--live-caching=3000",
        "--file-caching=3000",
        "--sout-mux-caching=3000",
        f"--http-user-agent={IPTV_USER_AGENT}",
    )


class VideoPlayer:
    def __init__(self):
        self.window = None
        self.instance = _make_vlc_instance()
        self.player = self.instance.media_player_new()
        self.channels = []
        self.current_channel = None
        self.channels_listbox = None
        self.channels_frame_visible = True
        self.is_fullscreen = False
        self.controls_visible = True
        self.hide_controls_timer = None
        self.empty_menu = None  # Menú vacío para ocultar en fullscreen
        self.volume = app_config.get_volume()
        self.favorites = []
        self.all_channels = []
        self.is_seeking = False
        self._progress_internal = False
        self._seek_hint_ms = None
        self._seek_hint_until = 0
        self.update_time_job = None  # Inicializar para evitar errores al cerrar
        self._known_duration_ms = 0
        self._yt_via_pipe = False
        self._yt_start_offset_ms = 0
        self._yt_resume_s = 0
        self._last_yt_resume_save = 0
        self._playing_youtube = False
        self._pipe_ready = False
        self._playlist_source = ''
        self._playlist_kind = ''
        self._geometry_save_job = None
        self._volume_save_job = None
        self._media_started = False
        self._iptv_relay_procs = []
        self._iptv_relay_server = None
        self._iptv_relay_tmpdir = None
        self._iptv_attempts = []
        self._iptv_source_url = ''
        self._iptv_check_gen = 0
        self._audio_tracks = []
        self._spu_tracks = []
        self._yt_subtitles = []
        self._active_audio_id = None
        self._active_spu_id = -1
        self._active_yt_sub = None
        self._track_poll_gen = 0
        self._yt_sub_dir = None
        self._audio_choice = None
        self._subs_choice = None

        # Inicializar el manejador de YouTube
        self.youtube_handler = YouTubeHandler(self)

        # Inicializar el manejador de favoritos
        self.favorites_manager = FavoritesManager(self)

        self.create_window()
        self.load_favorites()
        self.setup_mouse_tracking()
        self.setup_keyboard_shortcuts()

        # Nuevas variables para reproducción secuencial
        self.is_sequential_playback = False
        self.current_playlist_index = None

    def create_window(self):
        self.window = tk.Toplevel()
        self.window.title('Reproductor de vídeo')
        self.window.geometry('1100x750')
        style_window(self.window)
        set_window_icon(self.window)
        if not app_config.apply_geometry(self.window, 'player', '1100x750'):
            self.window.geometry('1100x750')
        self.window.bind('<Configure>', self._on_window_configure)

        self.create_menu()

        # Frame principal
        self.main_frame = ttk.Frame(self.window)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame de canales con ancho inicial
        self.channels_frame = ttk.Frame(self.main_frame, width=300)  # Ancho inicial de 300 píxeles
        self.channels_frame.pack_propagate(False)  # Evita que el frame se ajuste automáticamente
        self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Frame separador (sizer)
        self.sizer = ttk.Frame(self.main_frame, width=5, cursor='sb_h_double_arrow', style='Sizer.TFrame')
        self.sizer.pack(side=tk.LEFT, fill=tk.Y)

        # Botones de favoritos
        favorites_buttons_frame = ttk.Frame(self.channels_frame)
        favorites_buttons_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)
        ttk.Button(favorites_buttons_frame, text="★ Favoritos", command=self.show_favorites).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(favorites_buttons_frame, text="Todos", command=self.restore_all_channels).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(favorites_buttons_frame, text="Limpiar", command=self.clear_channel_list).pack(side=tk.LEFT)

        # Búsqueda
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_channels)
        self.search_entry = ttk.Entry(self.channels_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 8))

        self.channels_listbox = tk.Listbox(self.channels_frame, width=30, yscrollcommand=None)
        self.channels_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        style_listbox(self.channels_listbox)
        self.channels_listbox.bind('<Double-Button-1>', self.play_selected)
        self.channels_listbox.bind('<Button-3>', self.show_channel_context_menu)

        # Tooltip para los elementos de la lista (solo al seleccionar)
        self.listbox_tooltip = Tooltip(self.channels_listbox)
        self.channels_listbox.bind('<<ListboxSelect>>', self.on_listbox_select)
        self.channels_listbox.bind('<FocusOut>', lambda e: self.listbox_tooltip.hidetip())
        # Ya no se usa el tooltip con el ratón

        scrollbar = ttk.Scrollbar(self.channels_frame, orient=tk.VERTICAL, command=self.channels_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.channels_listbox.config(yscrollcommand=scrollbar.set)

        # Frame de reproductor
        self.player_frame = ttk.Frame(self.main_frame)
        self.player_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Superficie negra nativa: ttk.Frame se redibuja al clic y hace parpadear VLC
        self.video_frame = tk.Frame(
            self.player_frame,
            bg='#000000',
            highlightthickness=0,
            bd=0,
            takefocus=0,
        )
        self.video_frame.pack(fill=tk.BOTH, expand=True)

        # Controles
        self.controls_frame = ttk.Frame(self.player_frame)
        self.controls_frame.pack(fill=tk.X, pady=5)
        
        # NO agregar eventos de movimiento de mouse que reinician constantemente el timer
        # Solo usar eventos de clic intencionales

        # Barra de progreso (solo visible para YouTube)
        self.progress_frame = ttk.Frame(self.controls_frame)
        self.progress_bar = ttk.Scale(
            self.progress_frame,
            from_=0,
            to=100,
            orient='horizontal',
            command=self._on_progress_scale,
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.progress_time_label = ttk.Label(self.progress_frame, text='00:00 / 00:00', style='Muted.TLabel')
        self.progress_time_label.pack(side=tk.RIGHT)
        self.progress_bar.bind('<Button-1>', self.start_seek)
        self.progress_bar.bind('<B1-Motion>', self._drag_seek)
        self.progress_bar.bind('<ButtonRelease-1>', self.end_seek)
        self.progress_frame.pack_forget()  # Oculta por defecto

        # Botones de control (iconos dibujados, no dependen de glifos Unicode de la fuente)
        self.controls_buttons_frame = ttk.Frame(self.controls_frame)
        self.controls_buttons_frame.pack(side=tk.TOP, fill=tk.X)
        self._control_icons = make_control_icons(get_colors()['text'])
        buttons_info = [
            ('skip_back', 'Retroceder 10 segundos', lambda: self.seek_relative(-10)),
            ('rewind', 'Retroceder 2 segundos', lambda: self.seek_relative(-2)),
            ('play_pause', 'Reproducir / Pausar', self.toggle_play),
            ('forward', 'Avanzar 2 segundos', lambda: self.seek_relative(2)),
            ('skip_forward', 'Avanzar 10 segundos', lambda: self.seek_relative(10)),
            ('stop', 'Detener reproducción', self.stop),
            ('quality', 'Calidad / audio', self._popup_audio_menu),
            ('subtitles', 'Subtítulos', self._popup_subs_menu),
            ('volume', 'Silenciar / Activar sonido', self.toggle_mute),
            ('fullscreen', 'Pantalla completa', self.toggle_fullscreen),
            ('playlist', 'Mostrar / Ocultar lista', self.toggle_playlist),
        ]
        self._audio_btn = None
        self._subs_btn = None
        self._posted_popup = None
        self._menu_rebuild_job = None
        for key, tip_text, command in buttons_info:
            btn = ttk.Button(
                self.controls_buttons_frame,
                image=self._control_icons[key],
                style='Icon.TButton',
                command=command,
            )
            btn.pack(side=tk.LEFT, padx=4)
            btn.bind('<Button-1>', self.on_control_interact)
            tip = Tooltip(btn)
            btn.bind('<Enter>', lambda e, t=tip, txt=tip_text: t.showtip(txt))
            btn.bind('<Leave>', lambda e, t=tip: t.hidetip())
            if key == 'quality':
                self._audio_btn = btn
            elif key == 'subtitles':
                self._subs_btn = btn
        self.add_volume_control()
        #self.setup_performance_monitoring()
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind('<Escape>', lambda e: self.exit_fullscreen())

    def setup_performance_monitoring(self):
        """Inicia el monitoreo de recursos"""
        self.cpu_label = ttk.Label(self.controls_frame, text="CPU: 0%")
        self.cpu_label.pack(side=tk.RIGHT, padx=5)
        self.update_performance_stats()

    def update_performance_stats(self):
        """Actualiza las estadísticas de rendimiento"""
        cpu_percent = psutil.cpu_percent()
        self.cpu_label.config(text=f"CPU: {cpu_percent}%")
        self.window.after(1000, self.update_performance_stats)
        
    def create_menu(self):
        self.menubar = tk.Menu(self.window)

        reproducir_menu = tk.Menu(self.menubar, tearoff=0)
        reproducir_menu.add_command(label="Cargar URL", command=self.prompt_url)
        reproducir_menu.add_command(label="Cargar Archivo Local", command=self.prompt_file)
        reproducir_menu.add_separator()
        reproducir_menu.add_command(label="Limpiar lista lateral", command=self.clear_channel_list)
        reproducir_menu.add_command(label="Cerrar Reproductor", command=self.close)

        youtube_menu = tk.Menu(self.menubar, tearoff=0)
        youtube_menu.add_command(label="Cargar URL de YouTube", command=self.youtube_handler.prompt_youtube_url)
        youtube_menu.add_command(label="Descargar vídeo de YouTube", command=self.youtube_handler.download_youtube_video)
        youtube_menu.add_command(label="Buscar en YouTube", command=self.open_youtube_search)
        # NUEVO: Añadir opción para cargar playlist
        youtube_menu.add_command(label="Cargar Playlist de YouTube", command=self.prompt_youtube_playlist)
        favoritos_menu = tk.Menu(self.menubar, tearoff=0)
        favoritos_menu.add_command(label="Mostrar Favoritos", command=self.show_favorites)
        favoritos_menu.add_command(label="Añadir a Favoritos", command=self.add_to_favorites)
        favoritos_menu.add_command(label="Eliminar de Favoritos", command=self.remove_from_favorites)

        self.audio_menu = tk.Menu(self.menubar, tearoff=0)
        self.subs_menu = tk.Menu(self.menubar, tearoff=0)
        self.audio_popup = tk.Menu(self.window, tearoff=0)
        self.subs_popup = tk.Menu(self.window, tearoff=0)
        self._audio_choice = tk.StringVar(value='')
        self._subs_choice = tk.StringVar(value='off')
        self._quality_choice = tk.StringVar(value=str(app_config.get_youtube_quality()))
        self.menubar.add_cascade(label="Reproducir", menu=reproducir_menu)
        self.menubar.add_cascade(label="Youtube", menu=youtube_menu)
        self.menubar.add_cascade(label="Favoritos", menu=favoritos_menu)
        self.menubar.add_cascade(label="Calidad / audio", menu=self.audio_menu)
        self.menubar.add_cascade(label="Subtítulos", menu=self.subs_menu)
        self.window.config(menu=self.menubar)
        style_menu_tree(self.menubar)
        self._rebuild_track_menus()
        self.window.bind_all('<ButtonPress-1>', self._on_press_dismiss_popup, add='+')
        self.window.bind_all('<Escape>', self._on_escape_dismiss_popup, add='+')

    def setup_keyboard_shortcuts(self):
        # Atajos generales
        self.window.bind('<space>', lambda e: self.toggle_play())
        self.window.bind('<F1>', lambda e: self.toggle_fullscreen())
        self.window.bind('<m>', lambda e: self.toggle_mute())
        self.window.bind('<Left>', lambda e: self.seek_relative(-2))
        self.window.bind('<Right>', lambda e: self.seek_relative(2))
        
        # Atajos para favoritos
        self.window.bind('<Control-s>', self.handle_add_favorite)
        self.window.bind('<Control-d>', self.handle_remove_favorite)
        
        # Asegurarse de que el listbox también recibe los eventos
        self.channels_listbox.bind('<Control-s>', self.handle_add_favorite)
        self.channels_listbox.bind('<Control-d>', self.handle_remove_favorite)

    def _menu_is_mapped(self, menu):
        try:
            return bool(menu) and menu.winfo_ismapped()
        except tk.TclError:
            return False

    def _any_track_menu_mapped(self):
        if getattr(self, '_posted_popup', None):
            return True
        for attr in ('audio_menu', 'subs_menu', 'audio_popup', 'subs_popup'):
            menu = getattr(self, attr, None)
            try:
                if menu and menu.winfo_ismapped() and menu.winfo_height() > 8:
                    return True
            except tk.TclError:
                continue
        return False

    def _event_on_menu(self, event, menu):
        if not self._menu_is_mapped(menu):
            return False
        try:
            x, y = menu.winfo_rootx(), menu.winfo_rooty()
            w, h = menu.winfo_width(), menu.winfo_height()
            return x <= event.x_root <= x + w and y <= event.y_root <= y + h
        except tk.TclError:
            return False

    def _dismiss_track_menus(self):
        posted = getattr(self, '_posted_popup', None)
        self._posted_popup = None
        for menu in (
            posted,
            getattr(self, 'audio_popup', None),
            getattr(self, 'subs_popup', None),
            getattr(self, 'audio_menu', None),
            getattr(self, 'subs_menu', None),
        ):
            if menu is None:
                continue
            try:
                menu.unpost()
            except tk.TclError:
                pass
            try:
                menu.grab_release()
            except tk.TclError:
                pass

    def _on_press_dismiss_popup(self, event):
        if not self._widget_exists(getattr(self, 'window', None)):
            return
        if not self._posted_popup and not self._any_track_menu_mapped():
            return
        widget = getattr(event, 'widget', None)
        if widget in (getattr(self, '_audio_btn', None), getattr(self, '_subs_btn', None)):
            return
        for attr in ('audio_menu', 'audio_popup', 'subs_menu', 'subs_popup'):
            if self._event_on_menu(event, getattr(self, attr, None)):
                return
        self._dismiss_track_menus()

    def _on_escape_dismiss_popup(self, event=None):
        if not self._widget_exists(getattr(self, 'window', None)):
            return
        if self._posted_popup or self._any_track_menu_mapped():
            self._dismiss_track_menus()
            return 'break'

    def _choose_from_menu(self, action):
        def run():
            self._dismiss_track_menus()
            action()
        if self._widget_exists(self.window):
            self.window.after_idle(run)
        else:
            action()

    def _popup_track_menu(self, button, menu):
        if not button or not self._widget_exists(button) or menu is None:
            return
        if self._posted_popup is menu and self._menu_is_mapped(menu):
            self._dismiss_track_menus()
            return
        self._dismiss_track_menus()
        self._rebuild_track_menus()
        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            menu.post(x, y)
            self._posted_popup = menu
        except tk.TclError:
            self._posted_popup = None
        if self.is_fullscreen:
            self.reset_hide_controls_timer()

    def _popup_audio_menu(self):
        self._popup_track_menu(self._audio_btn, self.audio_popup)

    def _popup_subs_menu(self):
        self._popup_track_menu(self._subs_btn, self.subs_popup)

    def _clear_menu_items(self, menu):
        if menu is None:
            return
        try:
            last = menu.index('end')
        except tk.TclError:
            return
        if last is not None:
            menu.delete(0, last)

    def _vlc_track_list(self, getter):
        try:
            desc = getter() if self.player else None
        except Exception:
            return []
        if not desc:
            return []
        items = []
        for item in desc:
            tid = getattr(item, 'id', None)
            name = getattr(item, 'name', None)
            if tid is None and isinstance(item, (tuple, list)) and len(item) >= 2:
                tid, name = item[0], item[1]
            if tid is None:
                continue
            try:
                tid = int(tid)
            except (TypeError, ValueError):
                continue
            if tid == -1:
                continue
            if isinstance(name, bytes):
                name = name.decode('utf-8', errors='replace')
            name = (name or '').strip() or f'Pista {tid}'
            items.append((tid, name))
        return items

    def _read_vlc_tracks(self):
        if not self.player:
            return
        self._audio_tracks = self._vlc_track_list(self.player.audio_get_track_description)
        if getattr(self, '_yt_via_pipe', False):
            self._spu_tracks = []
        else:
            self._spu_tracks = self._vlc_track_list(self.player.video_get_spu_description)
        try:
            self._active_audio_id = self.player.audio_get_track()
        except Exception:
            pass
        try:
            if self._active_yt_sub is None:
                self._active_spu_id = self.player.video_get_spu()
        except Exception:
            pass

    def _reset_vlc_tracks(self):
        self._audio_tracks = []
        self._spu_tracks = []
        self._active_audio_id = None
        self._active_spu_id = -1
        self._track_poll_gen = getattr(self, '_track_poll_gen', 0) + 1

    def clear_youtube_subtitles(self):
        self._yt_subtitles = []
        self._active_yt_sub = None
        self._clear_yt_sub_files()
        if getattr(self, '_subs_choice', None) is not None:
            self._subs_choice.set('off')
        self._rebuild_track_menus()

    def set_youtube_subtitles(self, items):
        self._yt_subtitles = list(items or [])
        self._rebuild_track_menus()

    def _clear_yt_sub_files(self):
        path = getattr(self, '_yt_sub_dir', None)
        self._yt_sub_dir = None
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)

    def _schedule_track_refresh(self):
        self._track_poll_gen = getattr(self, '_track_poll_gen', 0) + 1
        gen = self._track_poll_gen
        if self._widget_exists(self.window):
            self.window.after(700, lambda g=gen: self._poll_vlc_tracks(g, 0))

    def _poll_vlc_tracks(self, gen, attempt):
        if gen != getattr(self, '_track_poll_gen', 0):
            return
        if not self.player or not self._widget_exists(self.window):
            return
        self._read_vlc_tracks()
        self._rebuild_track_menus()
        has_choice = len(self._audio_tracks) > 1 or self._spu_tracks
        if has_choice and attempt >= 2:
            return
        if attempt >= 10:
            return
        self.window.after(900, lambda g=gen, a=attempt: self._poll_vlc_tracks(g, a + 1))

    def _rebuild_track_menus(self):
        if self._any_track_menu_mapped() or getattr(self, '_posted_popup', None):
            if not getattr(self, '_menu_rebuild_job', None) and self._widget_exists(self.window):
                self._menu_rebuild_job = self.window.after(200, self._rebuild_track_menus_later)
            return
        self._rebuild_track_menus_now()

    def _rebuild_track_menus_later(self):
        self._menu_rebuild_job = None
        if self._any_track_menu_mapped() or getattr(self, '_posted_popup', None):
            if self._widget_exists(self.window):
                self._menu_rebuild_job = self.window.after(200, self._rebuild_track_menus_later)
            return
        self._rebuild_track_menus_now()

    def _rebuild_track_menus_now(self):
        menus_audio = [getattr(self, 'audio_menu', None), getattr(self, 'audio_popup', None)]
        menus_subs = [getattr(self, 'subs_menu', None), getattr(self, 'subs_popup', None)]
        if not any(menus_audio) and not any(menus_subs):
            return
        if self._audio_choice is None:
            return
        if getattr(self, '_quality_choice', None) is None:
            self._quality_choice = tk.StringVar(value=str(app_config.get_youtube_quality()))
        self._quality_choice.set(str(app_config.get_youtube_quality()))
        current_audio = '' if self._active_audio_id is None else str(self._active_audio_id)
        if any(str(tid) == current_audio for tid, _name in self._audio_tracks):
            self._audio_choice.set(current_audio)
        elif self._audio_tracks:
            self._audio_choice.set(str(self._audio_tracks[0][0]))
        else:
            self._audio_choice.set('')
        if self._active_yt_sub:
            kind, lang = self._active_yt_sub
            self._subs_choice.set(f'{kind}:{lang}')
        elif self._active_spu_id not in (None, -1):
            self._subs_choice.set(f'vlc:{self._active_spu_id}')
        else:
            self._subs_choice.set('off')
        for menu in menus_audio:
            self._fill_audio_menu(menu)
        for menu in menus_subs:
            self._fill_subs_menu(menu)
        style_menu_tree(getattr(self, 'menubar', None))
        style_menu_tree(getattr(self, 'audio_popup', None))
        style_menu_tree(getattr(self, 'subs_popup', None))

    def _fill_audio_menu(self, menu):
        if menu is None:
            return
        self._clear_menu_items(menu)
        if getattr(self, '_quality_choice', None) is None:
            self._quality_choice = tk.StringVar(value=str(app_config.get_youtube_quality()))
        menu.add_radiobutton(
            label='360p',
            variable=self._quality_choice,
            value='360',
            command=lambda: self._choose_from_menu(lambda: self._apply_youtube_quality(360)),
        )
        menu.add_radiobutton(
            label='720p',
            variable=self._quality_choice,
            value='720',
            command=lambda: self._choose_from_menu(lambda: self._apply_youtube_quality(720)),
        )
        menu.add_separator()
        tracks = self._audio_tracks
        if len(tracks) <= 1:
            if getattr(self, '_playing_youtube', False):
                label = 'YouTube trae una sola pista de audio'
            else:
                label = 'Solo hay una pista de audio' if tracks else 'Sin pistas de audio'
            menu.add_command(label=label, state='disabled')
            return
        for tid, name in tracks:
            menu.add_radiobutton(
                label=name,
                variable=self._audio_choice,
                value=str(tid),
                command=lambda i=tid: self._choose_from_menu(lambda t=i: self._apply_audio_track(t)),
            )

    def _apply_youtube_quality(self, height):
        height = 360 if int(height) == 360 else 720
        previous = app_config.get_youtube_quality()
        app_config.set_youtube_quality(height)
        if getattr(self, '_quality_choice', None) is not None:
            self._quality_choice.set(str(height))
        if previous == height or not getattr(self, '_playing_youtube', False):
            return
        handler = getattr(self, 'youtube_handler', None)
        url = getattr(handler, '_current_url', '') or ''
        if not handler or not url:
            return
        elapsed_s = self._playback_elapsed_ms() / 1000.0
        kwargs = dict(getattr(handler, '_play_kwargs', {}) or {})
        print(f"[YouTube] Calidad {previous}p → {height}p")
        handler.play_youtube_url(
            url,
            force_pulse=kwargs.get('force_pulse', True),
            show_progress=kwargs.get('show_progress', True),
            is_sequential=kwargs.get('is_sequential', False),
            title=getattr(handler, '_loading_title_text', None),
            resume_s=elapsed_s,
        )

    def _fill_subs_menu(self, menu):
        if menu is None:
            return
        self._clear_menu_items(menu)
        has_vlc = bool(self._spu_tracks) and not getattr(self, '_yt_via_pipe', False)
        has_yt = bool(self._yt_subtitles)
        if not has_vlc and not has_yt:
            menu.add_command(label='Sin subtítulos', state='disabled')
            return
        menu.add_radiobutton(
            label='Desactivar',
            variable=self._subs_choice,
            value='off',
            command=lambda: self._choose_from_menu(self._disable_subtitles),
        )
        if has_vlc:
            if has_yt:
                menu.add_separator()
            for tid, name in self._spu_tracks:
                menu.add_radiobutton(
                    label=name,
                    variable=self._subs_choice,
                    value=f'vlc:{tid}',
                    command=lambda i=tid: self._choose_from_menu(lambda t=i: self._apply_spu_track(t)),
                )
        if has_yt:
            if has_vlc:
                menu.add_separator()
            for item in self._yt_subtitles:
                key = f"{item['kind']}:{item['lang']}"
                menu.add_radiobutton(
                    label=item['label'],
                    variable=self._subs_choice,
                    value=key,
                    command=lambda it=item: self._choose_from_menu(lambda s=it: self._apply_youtube_subtitle(s)),
                )

    def _apply_audio_track(self, track_id):
        if not self.player:
            return
        try:
            self.player.audio_set_track(int(track_id))
            self._active_audio_id = int(track_id)
        except Exception as exc:
            print(f"[VLC] No se pudo cambiar la pista de audio: {exc}")

    def _apply_spu_track(self, track_id):
        if not self.player or getattr(self, '_yt_via_pipe', False):
            return
        self._active_yt_sub = None
        try:
            self.player.video_set_spu(int(track_id))
            self._active_spu_id = int(track_id)
        except Exception as exc:
            print(f"[VLC] No se pudo cambiar el subtítulo: {exc}")

    def _disable_subtitles(self):
        self._active_yt_sub = None
        if self.player:
            try:
                self.player.video_set_spu(-1)
            except Exception:
                pass
        self._active_spu_id = -1

    def _apply_youtube_subtitle(self, item):
        self._active_yt_sub = (item.get('kind'), item.get('lang'))
        threading.Thread(
            target=self._download_and_load_youtube_sub,
            args=(item,),
            daemon=True,
        ).start()

    def _download_and_load_youtube_sub(self, item):
        try:
            path = self.youtube_handler.fetch_subtitle_file(
                item.get('lang'),
                auto=item.get('kind') == 'auto',
                url=item.get('url'),
                ext=item.get('ext') or 'vtt',
                path=item.get('path'),
            )
            if path:
                item['path'] = path
        except Exception as exc:
            print(f"[YouTube] Subtítulo no disponible: {exc}")
            path = None
        def apply():
            if not path or not os.path.isfile(path):
                print('[YouTube] No hay archivo de subtítulos para cargar')
                return
            handler = self.youtube_handler
            if getattr(self, '_yt_via_pipe', False) or not self.player:
                direct = getattr(handler, '_direct_url', '') or ''
                if not direct:
                    print('[YouTube] Los subtítulos no se pueden aplicar al relevo MPEG-TS')
                    return
                keep_ms = self._playback_elapsed_ms()
                self.play_video_url(
                    direct,
                    force_pulse=True,
                    show_progress=True,
                    http_headers=getattr(handler, '_direct_headers', None),
                    duration_s=(self._known_duration_ms / 1000.0) if self._known_duration_ms else None,
                    subtitle_path=path,
                    fail_after_s=20,
                )
                self._hold_progress_ms = keep_ms
                self._hold_progress_until = time.time() + 2.5
                return
            keep_ms = self._playback_elapsed_ms()
            try:
                uri = pathlib.Path(path).resolve().as_uri()
                loaded = self.player.add_slave(vlc.MediaSlaveType.subtitle, uri, True)
                print(f"[VLC] Subtítulo esclavo ({loaded}): {uri}")
            except Exception as exc:
                print(f"[VLC] No se pudo añadir el subtítulo: {exc}")
                return
            self._hold_progress_ms = keep_ms
            self._hold_progress_until = time.time() + 2.5
            self._restore_after_subtitle(keep_ms)
        if self._widget_exists(self.window):
            self.window.after(0, apply)

    def _restore_after_subtitle(self, keep_ms):
        if not self.player:
            return
        try:
            state = self.player.get_state()
            if state in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
                self.player.play()
            elapsed = self._playback_elapsed_ms()
            length = self._media_length_ms()
            jumped = length > 0 and elapsed >= max(0, length - 1200) and keep_ms < length - 1500
            if jumped or abs(elapsed - keep_ms) > 1500:
                offset = int(getattr(self, '_yt_start_offset_ms', 0) or 0)
                self.player.set_time(max(0, int(keep_ms) - offset))
        except Exception as exc:
            print(f"[VLC] No se pudo conservar la posición: {exc}")

    def _select_external_spu(self):
        if not self.player:
            return
        try:
            keep_ms = getattr(self, '_hold_progress_ms', None)
            self._read_vlc_tracks()
            if self._spu_tracks:
                track_id = self._spu_tracks[-1][0]
                self.player.video_set_spu(track_id)
                self._active_spu_id = track_id
            if keep_ms is not None:
                self._restore_after_subtitle(keep_ms)
            self._rebuild_track_menus()
        except Exception as exc:
            print(f"[VLC] No se pudo activar el subtítulo: {exc}")

    def setup_mouse_tracking(self):
        # Eliminar eventos de hover para mostrar/ocultar controles
        # self.video_frame.bind('<Enter>', self.on_mouse_enter)
        # self.video_frame.bind('<Leave>', self.on_mouse_leave)
        # self.controls_frame.bind('<Enter>', self.on_mouse_enter)
        # self.controls_frame.bind('<Leave>', self.on_mouse_leave)

        # Nuevo: mostrar controles solo al hacer clic en pantalla completa
        def on_video_click(event=None):
            self._dismiss_track_menus()
            if self.is_fullscreen:
                self.show_controls_and_menu()
            return 'break'

        self.video_frame.bind('<Button-1>', on_video_click)

        # Eventos para el sizer
        self.sizer.bind('<Button-1>', self.start_resize)
        self.sizer.bind('<B1-Motion>', self.do_resize)
        self.sizer.bind('<ButtonRelease-1>', self.stop_resize)
        self.resize_active = False
        self.last_x = 0

    # Eliminar la lógica de hover de controles
    def on_mouse_enter(self, event=None):
        pass  # Ya no se usa para mostrar controles

    def on_mouse_leave(self, event=None):
        pass  # Ya no se usa para ocultar controles

    def hide_controls_and_menu(self):
        """Oculta controles y menú superior juntos (solo en fullscreen el menú)."""
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
        if self.is_fullscreen:
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

    # Frame de configuración de audio
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

    def close(self):
        """Cierra la ventana y libera recursos."""
        try:
            # Desactivar los manejadores de eventos
            if hasattr(self, 'video_frame') and self.video_frame:
                try:
                    self.video_frame.unbind('<Enter>')
                    self.video_frame.unbind('<Leave>')
                except tk.TclError:
                    pass
                    
            if hasattr(self, 'controls_frame') and self.controls_frame:
                try:
                    self.controls_frame.unbind('<Enter>')
                    self.controls_frame.unbind('<Leave>')
                except tk.TclError:
                    pass

            # Guardar datos y limpiar temporizadores
            self._dismiss_track_menus()
            self.save_youtube_resume()
            self._save_window_geometry()
            app_config.set_volume(self.volume)
            self.save_favorites()
            self.stop_update_time()  # Detener temporizador de actualización

            if hasattr(self, 'youtube_handler') and self.youtube_handler:
                try:
                    self.youtube_handler.stop_pipeline()
                except Exception:
                    pass
            self._clear_yt_sub_files()

            # Liberar recursos de VLC
            self._cleanup_vlc_player()

            # Destruir la ventana y limpiar referencias
            if self.window:
                try:
                    self.window.destroy()
                except tk.TclError:
                    pass
                finally:
                    self.window = None
                    self.video_frame = None
                    self.controls_frame = None
                    self.channels_frame = None
                    self.channels_listbox = None
                    self.search_entry = None
                    self.sizer = None
                    
        except Exception as e:
            print(f"Error durante el cierre del reproductor: {e}")

    def _cleanup_vlc_player(self):
        """Limpia de forma segura el reproductor VLC y sus event managers."""
        self._stop_iptv_relay()
        try:
            # Limpiar event manager antes de liberar el reproductor
            if hasattr(self, '_current_event_manager') and self._current_event_manager:
                try:
                    self._current_event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                    self._current_event_manager = None
                except Exception as e:
                    print(f"Error al limpiar event manager: {e}")
            
            # Detener y liberar reproductor
            if self.player:
                try:
                    if self.player.is_playing():
                        self.player.stop()
                    # Esperar un poco para que VLC termine completamente
                    import time
                    time.sleep(0.1)
                    self.player.release()
                except Exception as e:
                    print(f"Error al liberar reproductor: {e}")
                finally:
                    self.player = None
        except Exception as e:
            print(f"Error en limpieza VLC: {e}")

    def _widget_exists(self, widget):
        if widget is None:
            return False
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def is_alive(self):
        return self._widget_exists(self.window) and self._widget_exists(self.channels_listbox)

    def ensure_window(self):
        """Recrea la ventana del reproductor si se cerró o sus widgets ya no existen."""
        if self.is_alive():
            try:
                self.window.deiconify()
                self.window.lift()
            except tk.TclError:
                pass
            return
        self.window = None
        self.channels_listbox = None
        if not self.player or not self.instance:
            self.instance = _make_vlc_instance()
            self.player = self.instance.media_player_new()
            self.volume = app_config.get_volume()
        self.create_window()

    def run(self):
        self.ensure_window()
        if self._widget_exists(self.window):
            try:
                self.window.deiconify()
                self.window.lift()
                self.window.focus_force()
            except tk.TclError:
                self.window = None
                self.channels_listbox = None
                self.ensure_window()

    def _on_window_configure(self, event=None):
        if event and event.widget is not self.window:
            return
        if self.is_fullscreen or not self._widget_exists(self.window):
            return
        if self._geometry_save_job:
            try:
                self.window.after_cancel(self._geometry_save_job)
            except Exception:
                pass
        self._geometry_save_job = self.window.after(500, self._save_window_geometry)

    def _save_window_geometry(self):
        self._geometry_save_job = None
        if not self._widget_exists(self.window) or self.is_fullscreen:
            return
        geometry = app_config.capture_geometry(self.window)
        if geometry:
            app_config.remember_window('player', geometry)

    def _schedule_volume_save(self):
        if not self._widget_exists(self.window):
            app_config.set_volume(self.volume)
            return
        if self._volume_save_job:
            try:
                self.window.after_cancel(self._volume_save_job)
            except Exception:
                pass
        self._volume_save_job = self.window.after(400, lambda: app_config.set_volume(self.volume))

    def restore_session(self):
        """Restaura la última lista lateral. Si se limpió, queda vacía. No reproduce."""
        session = app_config.load().get('session') or {}
        playlist = session.get('playlist') or ''
        kind = session.get('playlist_kind') or ''
        sidebar = session.get('sidebar') or []
        items = []
        for entry in sidebar:
            if isinstance(entry, dict) and entry.get('url'):
                items.append((entry.get('name') or entry.get('url'), entry['url']))
        if kind == 'items' or (items and kind not in ('file', 'url')):
            self._apply_sidebar_items(items)
            self._playlist_source = playlist
            self._playlist_kind = kind or 'items'
            self.restore_last_channel()
            return
        if not playlist:
            return
        if kind == 'youtube_playlist':
            if items:
                self._apply_sidebar_items(items)
                self._playlist_source = playlist
                self._playlist_kind = 'youtube_playlist'
            else:
                self.load_youtube_playlist(playlist, notify=False)
        elif kind == 'url' or playlist.lower().startswith('http'):
            self.load_m3u_url(playlist, notify=False)
        elif os.path.isfile(playlist):
            self.load_m3u_file(playlist, notify=False)
        self.restore_last_channel()

    def _apply_sidebar_items(self, items):
        self.channels = list(items)
        self.all_channels = list(items)
        self._fill_channel_listbox([name for name, _url in items])

    def _persist_sidebar(self):
        items = list(self.all_channels)
        source = self._playlist_source or ''
        kind = self._playlist_kind or ''
        if not items:
            app_config.clear_session_list()
            return
        if kind in ('file', 'url') and source:
            app_config.remember_playlist(source, kind)
            return
        if len(items) > 1500:
            if source:
                app_config.remember_playlist(source, kind or 'file')
            return
        app_config.remember_sidebar(items, source, kind or 'items')

    def restore_last_channel(self):
        if not self.channels or not self._widget_exists(self.channels_listbox):
            return
        session = app_config.load().get('session') or {}
        url = session.get('channel_url') or ''
        name = session.get('channel_name') or ''
        index = session.get('channel_index')
        chosen = None
        if url:
            for i, (_name, channel_url) in enumerate(self.channels):
                if channel_url == url:
                    chosen = i
                    break
        if chosen is None and name:
            for i, (channel_name, _url) in enumerate(self.channels):
                if channel_name == name:
                    chosen = i
                    break
        if chosen is None and isinstance(index, int) and 0 <= index < len(self.channels):
            chosen = index
        if chosen is None:
            return
        try:
            self.channels_listbox.selection_clear(0, tk.END)
            self.channels_listbox.selection_set(chosen)
            self.channels_listbox.activate(chosen)
            self.channels_listbox.see(chosen)
            self.current_channel = chosen
        except tk.TclError:
            pass

    def save_favorites(self):
        try:
            with open('favoritos.json', 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron guardar los favoritos: {e}")

    def load_favorites(self):
        try:
            with open('favoritos.json', 'r', encoding='utf-8') as f:
                self.favorites = json.load(f)
        except FileNotFoundError:
            self.favorites = []
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los favoritos: {e}")

    def show_favorites(self):
        if not self.favorites:
            messagebox.showinfo("Favoritos", "Por el momento no hay favoritos añadidos.")
            return
        self.temp_channels = self.channels.copy()
        self.channels = list(self.favorites)
        self._fill_channel_listbox([channel[0] for channel in self.channels])

    
    def restore_all_channels(self):
        self.channels = self.all_channels.copy()
        self._fill_channel_listbox([channel[0] for channel in self.channels])

    def prompt_url(self):
        url = simpledialog.askstring("Cargar URL", "Introduce la URL de la lista M3U:")
        if url:
            self.load_m3u_url(url)

    def prompt_file(self):
        filename = filedialog.askopenfilename(
            title="Selecciona un archivo M3U o M3U8",
            filetypes=[("Archivos M3U/M3U8", "*.m3u *.m3u8"), ("Todos los archivos", "*")],
            parent=self.window
        )
        if filename:
            self.load_m3u_file(filename)

    def load_m3u_file(self, filename, notify=True):
        """Carga un archivo M3U local y procesa sus canales."""
        try:
            self.ensure_window()
            with open(filename, 'rb') as f:
                content = decode_m3u_bytes(f.read())
            self._process_m3u_content(content)
            self._playlist_source = filename
            self._playlist_kind = 'file'
            self._persist_sidebar()
            if notify:
                messagebox.showinfo("Éxito", f"Lista M3U cargada correctamente: {len(self.channels)} canales encontrados")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el archivo M3U: {e}")

    def load_m3u_url(self, url, notify=True):
        """Carga una lista M3U desde una URL y procesa sus canales."""
        try:
            self.ensure_window()
            import urllib.request
            with urllib.request.urlopen(url) as response:
                content = decode_m3u_bytes(response.read())
            self._process_m3u_content(content)
            self._playlist_source = url
            self._playlist_kind = 'url'
            self._persist_sidebar()
            if notify:
                messagebox.showinfo("Éxito", f"Lista M3U cargada correctamente: {len(self.channels)} canales encontrados")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la URL M3U: {e}")

    def _fill_channel_listbox(self, names):
        if not self._widget_exists(self.channels_listbox):
            return
        try:
            self.channels_listbox.delete(0, tk.END)
            for start in range(0, len(names), 200):
                self.channels_listbox.insert(tk.END, *names[start:start + 200])
        except tk.TclError:
            return

    def _process_m3u_content(self, content):
        """Procesa el contenido de un archivo M3U y carga los canales."""
        self.ensure_window()
        parsed = parse_m3u_entries(content)
        self.channels = parsed
        self.all_channels = list(parsed)
        self._fill_channel_listbox([name for name, _ in parsed])

    def prompt_youtube_playlist(self):
        """Solicita URL de playlist de YouTube y la carga."""
        playlist_url = simpledialog.askstring("Cargar Playlist de YouTube", "Introduce la URL de la playlist de YouTube:")
        if playlist_url:
            self.load_youtube_playlist(playlist_url)

    def load_youtube_playlist(self, playlist_url, notify=True):
        """Carga todos los vídeos de una playlist de YouTube y los muestra en la lista de canales."""
        try:
            import yt_dlp
            ydl_opts = youtube_ydl_opts(
                extract_flat=True,
                skip_download=True,
                force_generic_extractor=False,
                noplaylist=False,
            )
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                videos = info.get('entries', [])
                if not videos:
                    messagebox.showinfo("Info", "No se encontraron vídeos en la playlist.")
                    return

                parsed = []
                for video in videos:
                    title = video.get('title', 'Sin título')
                    video_url = f"https://www.youtube.com/watch?v={video.get('id')}"
                    parsed.append((title, video_url))
                self.channels = parsed
                self.all_channels = list(parsed)
                self._playlist_source = playlist_url
                self._playlist_kind = 'youtube_playlist'
                self._fill_channel_listbox([title for title, _ in parsed])
                self._persist_sidebar()
                if notify:
                    messagebox.showinfo("Éxito", f"Playlist cargada: {len(videos)} vídeos")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la playlist: {e}")

    def play_selected(self, event=None):
        """Reproduce el canal seleccionado de la lista al hacer doble clic."""
        selection = self.channels_listbox.curselection()
        if selection:
            index = selection[0]
            self.play_channel(index)
            
    def play_channel(self, index):
        if 0 <= index < len(self.channels):
            self.save_youtube_resume()
            name, url = self.channels[index]
            self.current_channel = index
            app_config.remember_channel(index, name, url)
            if self.instance is None:
                self.instance = _make_vlc_instance()
            self.clear_youtube_subtitles()
            self._reset_vlc_tracks()
            # Limpiar reproductor anterior de forma segura
            self._cleanup_vlc_player()

            # Crear un nuevo reproductor
            self.player = self.instance.media_player_new()
            try:
                self.player.audio_set_volume(self.volume)
            except Exception:
                pass
            
            # Configurar el administrador de eventos si es una reproducción secuencial
            if self.is_sequential_playback:
                self.setup_event_manager()
                
            self.show_controls_and_menu()
            if "youtube.com" in url or "youtu.be" in url:
                self._playing_youtube = True
                self.youtube_handler.play_youtube_url(
                    url, 
                    force_pulse=True, 
                    show_progress=True,
                    is_sequential=self.is_sequential_playback,
                    title=name,
                )
                return
            try:
                self._play_iptv_url(name, url)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                messagebox.showerror("Error de reproducción", f"No se pudo reproducir el canal '{name}'.\n\nError: {e}")

    def _play_iptv_url(self, name, url):
        url = (url or '').strip()
        if not url:
            messagebox.showerror("Error de reproducción", f"No se pudo reproducir el canal '{name}'.")
            return
        self._media_started = False
        self._playing_youtube = False
        kind = classify_iptv_url(url)
        print(f"[IPTV] '{name}' → {describe_iptv_url(url)} tipo={kind}")
        if kind == 'container':
            self._known_duration_ms = 0
            self.show_youtube_progress_bar()
        else:
            self.hide_progress_bar()
        self._iptv_retry_name = name
        self._iptv_source_url = url
        self._iptv_did_ts_retry = False
        self._iptv_check_gen = getattr(self, '_iptv_check_gen', 0) + 1
        check_gen = self._iptv_check_gen
        self._start_vlc_remote(name, url, kind)
        self.window.after(2000, lambda: self._watch_iptv_start(check_gen, name, url, kind, 0))

    def _sanitize_iptv_log(self, text):
        return re.sub(r'https?://\S+', '[url]', text or '')

    def _iptv_report_unavailable(self, name):
        print(f"[IPTV] No se pudo abrir '{name}'")
        if not self._widget_exists(self.window):
            return
        messagebox.showerror(
            "No se pudo reproducir",
            f"No se pudo abrir «{name}».\n\n"
            "VLC no consiguió iniciar el vídeo.",
        )

    def _iptv_remote_options(self, kind, force_ts=False):
        options = [
            ':network-caching=3000',
            ':live-caching=3000',
            ':file-caching=3000',
            ':sout-mux-caching=3000',
            ':avcodec-hw=none',
            ':audio-resampler=soxr',
            ':codec=avcodec',
            f':http-user-agent={IPTV_USER_AGENT}',
            ':http-reconnect=true',
            ':aout=alsa',
        ]
        if force_ts:
            options.extend([':demux=ts', ':no-ts-trust-pcr'])
        elif kind == 'mpegts':
            options.append(':no-ts-trust-pcr')
        return options

    def _start_vlc_remote(self, name, url, kind, force_ts=False):
        if not self.instance:
            return
        if self.player is None:
            self.player = self.instance.media_player_new()
            try:
                self.player.audio_set_volume(self.volume)
            except Exception:
                pass
        try:
            self.player.stop()
        except Exception:
            pass
        how = 'mpegts forzado' if force_ts else kind
        print(f"[IPTV] Abriendo {describe_iptv_url(url)} ({how})")
        media = self.instance.media_new(url)
        for option in self._iptv_remote_options(kind, force_ts=force_ts):
            media.add_option(option)
        self.player.set_media(media)
        self.window.update_idletasks()
        self.video_frame.update_idletasks()
        if sys.platform.startswith('win'):
            self.player.set_hwnd(self.video_frame.winfo_id())
        elif sys.platform.startswith('linux'):
            self.player.set_xwindow(self.video_frame.winfo_id())
        elif sys.platform == 'darwin':
            self.player.set_nsobject(self.video_frame.winfo_id())
        self.player.play()
        self.adjust_video_settings()
        self.start_update_time()
        self._schedule_track_refresh()
        self._iptv_retry_name = name

    def _watch_iptv_start(self, check_gen, name, url, kind, ticks=0):
        if check_gen != getattr(self, '_iptv_check_gen', 0):
            return
        if not self.player:
            return
        try:
            state = self.player.get_state()
        except Exception:
            return
        if ticks < 6:
            print(f"[IPTV] VLC {state}")
        if state in (vlc.State.Playing, vlc.State.Buffering, vlc.State.Paused):
            self._media_started = True
            return
        if (
            state in (vlc.State.Ended, vlc.State.Error)
            and kind == 'container'
            and not getattr(self, '_iptv_did_ts_retry', False)
        ):
            self._iptv_did_ts_retry = True
            print("[IPTV] El contenedor cortó al abrir; reintento como MPEG-TS")
            self._iptv_check_gen = check_gen + 1
            retry_gen = self._iptv_check_gen
            self._start_vlc_remote(name, url, kind, force_ts=True)
            self.window.after(2500, lambda: self._watch_iptv_start(retry_gen, name, url, kind, 0))
            return
        if state == vlc.State.Opening:
            self.window.after(3000, lambda: self._watch_iptv_start(check_gen, name, url, kind, ticks + 1))
            return
        if kind == 'container' and getattr(self, '_iptv_did_ts_retry', False):
            self._iptv_report_unavailable(name)

    def _iptv_local_options(self):
        return [
            'network-caching=1500',
            'file-caching=1500',
            'avcodec-hw=none',
            'audio-resampler=soxr',
            'aout=alsa',
            'demux=ts',
            'no-ts-trust-pcr',
        ]

    def _start_vlc_local_ts(self, name, url):
        """VLC solo abre localhost; no usa el HTTP remoto que falla tras el 302."""
        if not self.instance:
            return
        if self.player is None:
            self.player = self.instance.media_player_new()
            try:
                self.player.audio_set_volume(self.volume)
            except Exception:
                pass
        try:
            if self.player.is_playing():
                self.player.stop()
        except Exception:
            pass
        media = self.instance.media_new(url)
        for option in self._iptv_local_options():
            media.add_option(option)
        self.player.set_media(media)
        self.window.update_idletasks()
        self.video_frame.update_idletasks()
        if sys.platform.startswith('win'):
            self.player.set_hwnd(self.video_frame.winfo_id())
        elif sys.platform.startswith('linux'):
            self.player.set_xwindow(self.video_frame.winfo_id())
        elif sys.platform == 'darwin':
            self.player.set_nsobject(self.video_frame.winfo_id())
        self.player.play()
        self.adjust_video_settings()
        self.start_update_time()
        self._schedule_track_refresh()
        self._iptv_retry_name = name

    def _check_iptv_stream(self, check_gen=None, waited=0):
        if check_gen is not None and check_gen != getattr(self, '_iptv_check_gen', 0):
            return
        if not self.player:
            return
        try:
            state = self.player.get_state()
        except Exception:
            return
        if state in (vlc.State.Playing, vlc.State.Buffering, vlc.State.Paused):
            self._media_started = True

    def _stop_iptv_relay(self):
        server = getattr(self, '_iptv_relay_server', None)
        self._iptv_relay_server = None
        if server:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
        for proc in getattr(self, '_iptv_relay_procs', []) or []:
            try:
                proc.terminate()
            except Exception:
                pass
        for proc in getattr(self, '_iptv_relay_procs', []) or []:
            try:
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._iptv_relay_procs = []
        tmpdir = getattr(self, '_iptv_relay_tmpdir', None)
        self._iptv_relay_tmpdir = None
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _ffmpeg_pull_cmd(self, ffmpeg, source, ts_path):
        return [
            ffmpeg, '-hide_banner', '-loglevel', 'error',
            '-user_agent', IPTV_USER_AGENT,
            '-reconnect', '1', '-reconnect_streamed', '1',
            '-reconnect_delay_max', '5',
            '-i', source,
            '-c', 'copy', '-f', 'mpegts', ts_path,
        ]

    def _start_iptv_ffmpeg_relay(self, name, url):
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            print("[IPTV] ffmpeg no está instalado")
            print(f"[IPTV] No se pudo abrir el canal '{name}'")
            return
        self._stop_iptv_relay()
        tmpdir = tempfile.mkdtemp(prefix='kidneys_iptv_')
        ts_path = os.path.join(tmpdir, 'stream.ts')
        self._iptv_relay_tmpdir = tmpdir
        check_gen = getattr(self, '_iptv_check_gen', 0) + 1
        self._iptv_check_gen = check_gen

        server = ThreadingHTTPServer(('127.0.0.1', 0), _GrowingTSHandler)
        server.ts_path = ts_path
        server.yt_procs = []
        self._iptv_relay_server = server
        threading.Thread(target=server.serve_forever, daemon=True).start()
        local_url = f'http://127.0.0.1:{server.server_address[1]}/stream.ts'

        def producer():
            try:
                sources = iptv_upstream_candidates(url)
            except Exception as err:
                print(f"[IPTV] No se pudieron preparar orígenes ({err})")
                sources = [url]
            if getattr(self, '_iptv_check_gen', 0) != check_gen:
                return
            print(f"[IPTV] Retransmitiendo por 127.0.0.1 ({len(sources)} origen(es))")
            for index, source in enumerate(sources, start=1):
                if getattr(self, '_iptv_check_gen', 0) != check_gen:
                    return
                try:
                    if os.path.exists(ts_path):
                        os.remove(ts_path)
                except OSError:
                    pass
                cmd = self._ffmpeg_pull_cmd(ffmpeg, source, ts_path)
                try:
                    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
                except Exception as exc:
                    print(f"[IPTV] ffmpeg no arrancó ({exc})")
                    continue
                self._iptv_relay_procs = [proc]
                if self._iptv_relay_server:
                    self._iptv_relay_server.yt_procs = self._iptv_relay_procs
                deadline = time.time() + 12
                got_data = False
                while time.time() < deadline:
                    if getattr(self, '_iptv_check_gen', 0) != check_gen:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        return
                    try:
                        if os.path.exists(ts_path) and os.path.getsize(ts_path) >= 32 * 1024:
                            got_data = True
                            break
                    except OSError:
                        pass
                    if proc.poll() is not None:
                        break
                    time.sleep(0.2)
                if got_data:
                    err = None
                    try:
                        err = proc.communicate()[1]
                    except Exception:
                        pass
                    if err:
                        text = err.decode('utf-8', errors='replace')[-400:]
                        if text.strip():
                            print(f"[IPTV ffmpeg] {self._sanitize_iptv_log(text)}")
                    return
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                err = b''
                try:
                    err = proc.stderr.read() if proc.stderr else b''
                except Exception:
                    pass
                if err:
                    print(f"[IPTV] origen {index}/{len(sources)} sin datos: {self._sanitize_iptv_log(err.decode('utf-8', errors='replace')[-200:])}")
                else:
                    print(f"[IPTV] origen {index}/{len(sources)} sin datos")
            if self._widget_exists(self.window):
                self.window.after(0, lambda: self._iptv_report_unavailable(name))

        def wait_and_play():
            deadline = time.time() + 45
            while time.time() < deadline:
                if getattr(self, '_iptv_check_gen', 0) != check_gen:
                    return
                try:
                    if os.path.exists(ts_path) and os.path.getsize(ts_path) >= 32 * 1024:
                        break
                except OSError:
                    pass
                time.sleep(0.2)
            else:
                return
            if not self._widget_exists(self.window):
                return
            self.window.after(0, lambda: self._start_vlc_local_ts(name, local_url))

        threading.Thread(target=producer, daemon=True).start()
        threading.Thread(target=wait_and_play, daemon=True).start()

    def play_video_url(self, url, force_pulse=False, show_progress=False, is_sequential=False, http_headers=None, on_fail=None, fail_after_s=8, local_file=False, duration_s=None, subtitle_path=None, start_s=0):
        try:
            for widget in self.video_frame.winfo_children():
                widget.destroy()
            if self.player is None:
                self.player = self.instance.media_player_new()
            if self.player.is_playing():
                self.player.stop()
            self.show_controls_and_menu()
            try:
                self._known_duration_ms = int(float(duration_s) * 1000) if duration_s else 0
            except (TypeError, ValueError):
                self._known_duration_ms = 0
            if show_progress:
                self.show_youtube_progress_bar()
            else:
                self.hide_progress_bar()
            try:
                start_s = float(start_s or 0)
            except (TypeError, ValueError):
                start_s = 0
            self._yt_resume_s = start_s if start_s >= 0.5 and not local_file else 0
            if self._yt_resume_s:
                self._set_progress_ui(int(self._yt_resume_s * 1000))
            elif local_file:
                offset = int(getattr(self, '_yt_start_offset_ms', 0) or 0)
                if offset:
                    self._set_progress_ui(offset)
            
            # Configurar event manager si es reproducción secuencial
            if is_sequential and not hasattr(self, '_current_event_manager'):
                self.setup_event_manager()
            
            if not (local_file and '127.0.0.1' in str(url)):
                self._yt_via_pipe = False
                self._yt_start_offset_ms = 0
                self._pipe_ready = False
            else:
                self._pipe_ready = False
                self._pipe_gen = getattr(self, '_pipe_gen', 0) + 1
                gen = self._pipe_gen
                self.window.after(
                    1500,
                    lambda g=gen: setattr(self, '_pipe_ready', True)
                    if getattr(self, '_pipe_gen', 0) == g else None,
                )
            media = self.instance.media_new(url)
            options = [
                ':network-caching=3000',
                ':live-caching=3000',
                ':file-caching=3000',
                ':sout-mux-caching=3000',
                ':no-ts-trust-pcr',
                ':avcodec-hw=none',
                ':audio-resampler=soxr',
                ':codec=avcodec',
            ]
            if local_file:
                if str(url).startswith('http'):
                    options.append(':http-reconnect=true')
                else:
                    options.append(':file-caching=1500')
            else:
                options.append(':http-reconnect=true')
                headers = http_headers or {}
                user_agent = headers.get('User-Agent') or headers.get('user-agent') or (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0'
                )
                referrer = headers.get('Referer') or headers.get('referer') or 'https://www.youtube.com/'
                options.append(f':http-user-agent={user_agent}')
                options.append(f':http-referrer={referrer}')
                cookie = headers.get('Cookie') or headers.get('cookie')
                if cookie:
                    options.append(f':http-cookie={cookie}')
            if force_pulse:
                options.append(':aout=pulse')
                print("[AUDIO] Forzando salida de audio: pulse (YouTube)")
            else:
                options.append(':aout=alsa')
                print("[AUDIO] Forzando salida de audio: alsa (M3U)")
            if subtitle_path and os.path.isfile(subtitle_path):
                options.append(f':sub-file={subtitle_path}')
                print(f"[VLC] sub-file={subtitle_path}")
            if self._yt_resume_s:
                options.append(f':start-time={self._yt_resume_s:.1f}')
                print(f"[VLC] start-time={self._yt_resume_s:.1f}s")
            for option in options:
                media.add_option(option)
            self.player.set_media(media)
            self.window.update_idletasks()
            self.video_frame.update_idletasks()
            import sys
            if sys.platform.startswith('win'):
                self.player.set_hwnd(self.video_frame.winfo_id())
            elif sys.platform.startswith('linux'):
                self.player.set_xwindow(self.video_frame.winfo_id())
            elif sys.platform == 'darwin':
                self.player.set_nsobject(self.video_frame.winfo_id())
            self.player.play()
            self.adjust_video_settings()
            self.start_update_time()
            self._schedule_track_refresh()
            self._youtube_fail_cb = on_fail
            self._youtube_fail_deadline = time.time() + max(8, int(fail_after_s))
            self._yt_check_gen = getattr(self, '_yt_check_gen', 0) + 1
            check_gen = self._yt_check_gen
            self.window.after(400, lambda g=check_gen: self._check_youtube_stream(g))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo reproducir el vídeo: {e}")
            if on_fail:
                on_fail()

    def _check_youtube_stream(self, gen=None):
        """Si VLC no consigue abrir el stream de YouTube, usa el plan B."""
        if gen is not None and gen != getattr(self, '_yt_check_gen', 0):
            return
        if not self.player:
            return
        try:
            state = self.player.get_state()
        except Exception:
            return
        playing = state in (vlc.State.Playing, vlc.State.Buffering, vlc.State.Paused)
        if playing:
            self._youtube_fail_cb = None
            self._apply_pending_youtube_resume()
            if hasattr(self, 'youtube_handler') and self.youtube_handler:
                self.youtube_handler.hide_loading()
            return
        callback = getattr(self, '_youtube_fail_cb', None)
        if not callback:
            return
        if state == vlc.State.Error:
            self._youtube_fail_cb = None
            callback()
            return
        if time.time() >= getattr(self, '_youtube_fail_deadline', 0):
            self._youtube_fail_cb = None
            print(f"[VLC] El stream de YouTube no arrancó (estado={state})")
            callback()
            return
        self.window.after(1500, lambda g=gen: self._check_youtube_stream(g))

    def start_update_time(self):
        """Inicia la actualización periódica de tiempo de reproducción (sin barra de progreso visible)."""
        self.stop_update_time()  # Detener cualquier temporizador previo
        self.update_time()  # Llamada inicial

    def stop_update_time(self):
        if self.update_time_job:
            try:
                self.window.after_cancel(self.update_time_job)
            except Exception:
                pass
            self.update_time_job = None

    def _media_length_ms(self):
        vlc_len = 0
        try:
            if self.player:
                vlc_len = int(self.player.get_length() or 0)
        except Exception:
            vlc_len = 0
        known = int(getattr(self, '_known_duration_ms', 0) or 0)
        # En YouTube por MPEG-TS local, VLC solo conoce lo ya descargado.
        if known > 0 and (vlc_len <= 0 or known > vlc_len + 1500):
            return known
        return vlc_len if vlc_len > 0 else known

    def _playback_elapsed_ms(self):
        raw = 0
        try:
            if self.player:
                raw = int(self.player.get_time() or 0)
        except Exception:
            raw = 0
        if raw < 0:
            raw = 0
        return raw + int(getattr(self, '_yt_start_offset_ms', 0) or 0)

    def _current_youtube_id(self):
        handler = getattr(self, 'youtube_handler', None)
        url = ''
        if handler:
            url = getattr(handler, '_current_url', '') or ''
        if not url and self.current_channel is not None:
            try:
                url = self.channels[self.current_channel][1]
            except (IndexError, TypeError):
                url = ''
        if 'youtube.com' not in url and 'youtu.be' not in url:
            return None
        if not handler:
            return None
        return handler.extract_youtube_id(url)

    def save_youtube_resume(self):
        if not getattr(self, '_playing_youtube', False):
            return
        video_id = self._current_youtube_id()
        if not video_id:
            return
        elapsed_ms = self._playback_elapsed_ms()
        duration_ms = self._media_length_ms()
        app_config.remember_youtube_position(
            video_id,
            elapsed_ms / 1000.0,
            (duration_ms / 1000.0) if duration_ms else None,
        )
        self._last_yt_resume_save = time.time()

    def clear_youtube_resume(self):
        video_id = self._current_youtube_id()
        if video_id:
            app_config.clear_youtube_position(video_id)

    def _apply_pending_youtube_resume(self):
        pending = float(getattr(self, '_yt_resume_s', 0) or 0)
        self._yt_resume_s = 0
        if pending < 0.5:
            return
        target_ms = int(pending * 1000)
        elapsed = self._playback_elapsed_ms()
        if elapsed < target_ms - 2500:
            self._apply_seek(target_ms)
        else:
            self._set_progress_ui(max(elapsed, target_ms))

    def _set_progress_ui(self, elapsed_ms, length_ms=None):
        if length_ms is None:
            length_ms = self._media_length_ms()
        elapsed_ms = max(0, int(elapsed_ms or 0))
        self._progress_internal = True
        try:
            if hasattr(self, 'progress_bar') and length_ms > 0:
                self.progress_bar.set(min(100.0, max(0.0, (elapsed_ms / length_ms) * 100)))
            if hasattr(self, 'progress_time_label'):
                total_txt = self._format_clock(length_ms) if length_ms > 0 else '--:--'
                self.progress_time_label.configure(
                    text=f'{self._format_clock(elapsed_ms)} / {total_txt}'
                )
        finally:
            self._progress_internal = False

    def _apply_seek(self, target_ms):
        length = self._media_length_ms()
        target_ms = max(0, int(target_ms))
        if length > 0:
            target_ms = min(target_ms, max(0, length - 250))
        if not self.player:
            return target_ms
        offset = int(getattr(self, '_yt_start_offset_ms', 0) or 0)
        local_ms = target_ms - offset
        vlc_len = 0
        try:
            vlc_len = int(self.player.get_length() or 0)
        except Exception:
            vlc_len = 0
        used_pipe = getattr(self, '_yt_via_pipe', False)
        beyond_buffer = used_pipe and vlc_len > 0 and local_ms > max(0, vlc_len - 400)
        can_restart = used_pipe and getattr(self, '_pipe_ready', False) and beyond_buffer
        if can_restart:
            last = getattr(self, '_pipe_seek_at', 0)
            if time.time() - last > 0.8:
                self._pipe_seek_at = time.time()
                self.youtube_handler.replay_from(target_ms / 1000.0)
        else:
            try:
                self.player.set_time(max(0, local_ms))
            except Exception:
                pass
        self._seek_hint_ms = target_ms
        self._seek_hint_until = time.time() + 1.2
        self._set_progress_ui(target_ms, length)
        return target_ms

    def _format_clock(self, milliseconds):
        total = max(0, int(milliseconds) // 1000)
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f'{hours}:{minutes:02d}:{seconds:02d}'
        return f'{minutes:02d}:{seconds:02d}'

    def update_time(self):
        """Actualiza el tiempo de reproducción y la barra de progreso."""
        try:
            if self.player:
                state = self.player.get_state()
                active = state in (vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering)
                hold = getattr(self, '_hold_progress_ms', None)
                hold_until = getattr(self, '_hold_progress_until', 0)
                holding = hold is not None and time.time() < hold_until
                if holding and state in (vlc.State.Ended, vlc.State.Stopped):
                    self._restore_after_subtitle(hold)
                    try:
                        state = self.player.get_state()
                    except Exception:
                        pass
                    active = state in (vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering)
                if active:
                    self._media_started = True
                if active and not self.is_seeking and self.progress_frame.winfo_ismapped():
                    elapsed = self._playback_elapsed_ms()
                    if holding:
                        length = self._media_length_ms()
                        if length > 0 and elapsed >= max(0, length - 1200) and hold < length - 1500:
                            self._restore_after_subtitle(hold)
                            elapsed = hold
                    hint = getattr(self, '_seek_hint_ms', None)
                    until = getattr(self, '_seek_hint_until', 0)
                    if hint is not None and time.time() < until:
                        if abs(elapsed - hint) > 1500:
                            elapsed = hint
                        else:
                            self._seek_hint_ms = None
                    elif hint is not None and time.time() >= until:
                        self._seek_hint_ms = None
                    self._set_progress_ui(elapsed)
                    if active and time.time() - getattr(self, '_last_yt_resume_save', 0) >= 20:
                        self.save_youtube_resume()
        except Exception as e:
            print(f"Error actualizando tiempo: {e}")
        self.update_time_job = self.window.after(250, self.update_time)

    def adjust_video_settings(self):
        """Ajusta la configuración del video para optimizar la reproducción"""
        if self.player:
            # Cambiamos True por una cadena vacía "" para desactivar o "yadif" para activar
            self.player.video_set_deinterlace("") 
            self.player.audio_set_volume(self.volume)

    def filter_channels(self, *args):
        if not self._widget_exists(getattr(self, 'channels_listbox', None)):
            return
        search_term = self.search_var.get().lower()
        filtered = [
            (name, url) for name, url in self.all_channels
            if search_term in name.lower()
        ]
        self.channels = filtered
        self._fill_channel_listbox([name for name, _ in filtered])

    def seek_relative(self, seconds):
        """Avanza o retrocede el video en segundos"""
        if not self.player:
            return
        now = time.time()
        last_at, last_delta = getattr(self, '_seek_relative_at', (0, None))
        if last_delta == seconds and (now - last_at) < 0.12:
            return
        self._seek_relative_at = (now, seconds)
        try:
            state = self.player.get_state()
        except Exception:
            return
        if state not in (vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering):
            return
        current = self._playback_elapsed_ms()
        hint = getattr(self, '_seek_hint_ms', None)
        if hint is not None and now < getattr(self, '_seek_hint_until', 0):
            current = hint
        self._apply_seek(current + int(seconds * 1000))

    def prompt_youtube_url(self):
        """Delega la solicitud de URL de YouTube al manejador centralizado"""
        self.youtube_handler.prompt_youtube_url()

    def add_channel_to_list(self, name, url):
        """Añade un canal o vídeo individual a la lista de la izquierda y a all_channels."""
        self.enqueue_youtube_items([(name, url)])

    def enqueue_youtube_items(self, items):
        """Añade vídeos a la lista lateral sin reproducirlos."""
        if not self.is_alive():
            self.ensure_window()
        existing = {url for _name, url in self.all_channels}
        added = []
        for name, url in items or []:
            url = (url or '').strip()
            if not url or url in existing:
                continue
            title = (name or '').strip() or 'YouTube'
            added.append((title, url))
            existing.add(url)
        if not added:
            return 0
        for entry in added:
            self.all_channels.append(entry)
        if self._playlist_kind in ('file', 'url') and len(self.all_channels) <= 1500:
            self._playlist_kind = 'items'
        elif not self._playlist_kind:
            self._playlist_kind = 'items'
        search = ''
        if getattr(self, 'search_var', None):
            try:
                search = (self.search_var.get() or '').strip()
            except tk.TclError:
                search = ''
        if search:
            self.filter_channels()
        else:
            for name, url in added:
                self.channels.append((name, url))
                if self._widget_exists(self.channels_listbox):
                    self.channels_listbox.insert(tk.END, name)
                    self.channels_listbox.see(tk.END)
        self._persist_sidebar()
        return len(added)

    def play_youtube_url(self, url, title=None):
        """Delega la reproducción de YouTube al manejador y añade el vídeo a la lista si falta."""
        existing = next((name for name, item_url in self.all_channels if item_url == url), None)
        if existing and existing not in ('YouTube', url):
            title = title or existing
        elif not existing:
            self.add_channel_to_list(title or 'YouTube', url)
        self._playing_youtube = True
        self.youtube_handler.play_youtube_url(
            url,
            force_pulse=True,
            show_progress=True,
            title=title,
        )

    def cargar_videos_playlist(self, canales):
        """Carga los vídeos de una playlist de YouTube como canales en el listado."""
        self.channels = canales
        self.all_channels = canales.copy()
        self._playlist_kind = self._playlist_kind or 'items'
        self._fill_channel_listbox([nombre for nombre, _url in canales])
        self._persist_sidebar()

    def download_channel(self, index):
        """Inicia la descarga del canal seleccionado en un hilo separado."""


        if 0 <= index < len(self.channels):
            name, url = self.channels[index]
            
            # Expresión regular simple para verificar extensiones de video comunes o URL de YouTube
            is_youtube = 'youtube.com' in url or 'youtu.be' in url
            is_direct_video = re.search(r'\.(mkv|mp4|avi|mov|flv|ogg|webm)$', url, re.IGNORECASE)

            if not is_youtube and not is_direct_video:
                messagebox.showinfo("Descarga no soportada", "La descarga solo está soportada para URLs de YouTube o enlaces directos a archivos de vídeo (mkv, mp4, etc.).")
                return

            # Pedir al usuario la ubicación de guardado
            # Sugerir nombre de archivo basado en el nombre del canal
            suggested_filename = re.sub(r'[\\/*?:"<>|]', "", name)  # Limpiar nombre de archivo
            filepath = filedialog.asksaveasfilename(
                title="Guardar vídeo",
                initialfile=suggested_filename,
                filetypes=[("Todos los archivos", "*.*")]
            )

            if not filepath:
                return 

            # Iniciar la descarga en un hilo para no bloquear la UI
            download_thread = threading.Thread(target=self._execute_download, args=(url, filepath, name))
            download_thread.start()
            messagebox.showinfo("Descarga iniciada", f"Iniciando descarga de '{name}'. Se te notificará cuando termine.")

    def _execute_download(self, url, filepath, name):
        """Ejecuta la descarga usando yt-dlp sin conversión a MP4."""
        try:
            # Opciones de yt-dlp simplificadas sin conversión
            ydl_opts = youtube_ydl_opts(
                format='best',
                outtmpl=filepath,
                quiet=False,
                noprogress=False,
            )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Mensaje de éxito en el hilo principal
            self.window.after(0, lambda: messagebox.showinfo("Descarga completada", f"'{name}' descargado en:\n{filepath}"))

        except Exception as e:
            # Capturar el mensaje de error
            error_message = str(e)
            # Usar el mensaje capturado en la lambda
            self.window.after(0, lambda msg=error_message: messagebox.showerror("Error de descarga", 
                f"No se pudo descargar '{name}':\n{msg}\n\nPosibles soluciones:\n"
                f"1. Verifica que el enlace sea accesible\n"
                f"2. Prueba con otro enlace de vídeo\n"
                f"3. Comprueba tu conexión a internet"))
            
            # Intentar eliminar archivo parcial si existe
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass # No hacer nada si no se puede borrar

    def open_youtube_search(self):
        """Abre la ventana de búsqueda de YouTube."""
        # Asegúrate de que load_playlist_callback se pasa correctamente
        search_dialog = YouTubeSearchDialog(
            self.window,
            self.play_youtube_url,
            self.load_playlist_callback,
            self.enqueue_youtube_items,
        )

    def load_playlist_callback(self, channels_list):
         """Callback para cargar vídeos de una playlist en la lista principal."""
         if channels_list:
             self.ensure_window()
             self.channels = list(channels_list)
             self.all_channels = list(channels_list)
             self._playlist_kind = self._playlist_kind or 'youtube_playlist'
             self._fill_channel_listbox([name for name, _url in channels_list])
             self._persist_sidebar()
             messagebox.showinfo("Playlist cargada", f"Se cargaron {len(channels_list)} vídeos de la playlist.")

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
            # Usar método de limpieza segura
            self._cleanup_vlc_player()
            # Ocultar la barra de progreso
            self.hide_progress_bar()
            if hasattr(self, 'youtube_handler') and self.youtube_handler:
                self.youtube_handler.cancel_pending_play()
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

    def on_listbox_motion(self, event):
        """Muestra un tooltip con el nombre del canal al pasar el ratón"""
        index = self.channels_listbox.nearest(event.y)
        if 0 <= index < len(self.channels):
            name = self.channels[index][0]
            # Usar coordenadas absolutas del puntero
            x = self.channels_listbox.winfo_pointerx() + 20
            y = self.channels_listbox.winfo_pointery() + 10
            self.listbox_tooltip.showtip(name, x, y)
        else:
            self.listbox_tooltip.hidetip()

    def on_listbox_select(self, event):
        """Muestra un tooltip con el nombre del canal seleccionado justo debajo del ítem seleccionado"""
        self.listbox_tooltip.hidetip()  # Oculta cualquier tooltip anterior
        selection = self.channels_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.channels):
                name = self.channels[index][0]
                bbox = self.channels_listbox.bbox(index)
                if bbox:
                    x, y, width, height = bbox
                    abs_x = self.channels_listbox.winfo_rootx() + x
                    abs_y = self.channels_listbox.winfo_rooty() + y + height
                    self.listbox_tooltip.showtip(name, abs_x, abs_y)
                else:
                    self.listbox_tooltip.showtip(name)
        else:
            self.listbox_tooltip.hidetip()

    def _progress_ms_from_x(self, x):
        width = max(1, self.progress_bar.winfo_width())
        percent = max(0.0, min(100.0, (float(x) / width) * 100.0))
        length = self._media_length_ms()
        target = int(percent / 100.0 * length) if length > 0 else 0
        self._progress_internal = True
        try:
            self.progress_bar.set(percent)
        finally:
            self._progress_internal = False
        if hasattr(self, 'progress_time_label'):
            total_txt = self._format_clock(length) if length > 0 else '--:--'
            self.progress_time_label.configure(
                text=f'{self._format_clock(target)} / {total_txt}'
            )
        self._seek_hint_ms = target
        self._seek_hint_until = time.time() + 1.2
        return target

    def start_seek(self, event):
        self.is_seeking = True
        self._progress_ms_from_x(event.x)
        if self.is_fullscreen:
            self.reset_hide_controls_timer()

    def _drag_seek(self, event):
        if self.is_seeking:
            self._progress_ms_from_x(event.x)

    def end_seek(self, event):
        if self.is_seeking:
            target = self._progress_ms_from_x(event.x)
            self._apply_seek(target)
        self.is_seeking = False
        if self.is_fullscreen:
            self.reset_hide_controls_timer()

    def _on_progress_scale(self, value):
        if getattr(self, '_progress_internal', False) or self.is_seeking or not self.player:
            return
        if getattr(self, '_yt_via_pipe', False) and not getattr(self, '_pipe_ready', False):
            return
        try:
            length = self._media_length_ms()
            if length <= 0:
                return
            self._apply_seek(int(float(value) / 100.0 * length))
        except Exception as e:
            print(f"Error en seek: {e}")

    def seek_to_position(self, value):
        self._on_progress_scale(value)

    def handle_add_favorite(self, event=None):
        """Manejador para el atajo de teclado Ctrl+S"""
        self.add_to_favorites()
        return "break"  # Evita que el evento se propague

    def handle_remove_favorite(self, event=None):
        """Manejador para el atajo de teclado Ctrl+D"""
        self.remove_from_favorites()
        return "break"  # Evita que el evento se propague

    def play_from_here(self, start_index):
        """Reproduce todos los videos de la lista desde el índice especificado."""
        print(f"Iniciando reproducción secuencial desde índice {start_index}")
        
        # Detener cualquier reproducción actual y limpiar el estado
        self.stop()
        
        # Esperar un momento antes de iniciar la nueva reproducción
        def start_playback():
            print("Configurando reproducción secuencial")
            self.is_sequential_playback = True
            self.current_playlist_index = start_index
            self.select_and_play_channel(start_index)
            
        # Usar delay para asegurar que todo se detuvo correctamente
        self.window.after(500, start_playback)

    def select_and_play_channel(self, index):
        """Selecciona y reproduce un canal del listado."""
        try:
            print(f"\n=== Seleccionando y reproduciendo canal {index} ===")
            if 0 <= index < len(self.channels):
                # Detener cualquier reproducción actual
                if self.player:
                    if self.player.is_playing():
                        print("Deteniendo reproducción actual")
                        self.player.stop()
                    print("Liberando reproductor actual")
                    self.player.release()
                    self.player = None
                
                # Actualizar selección visual
                print("Actualizando selección visual")
                self.channels_listbox.selection_clear(0, tk.END)
                self.channels_listbox.selection_set(index)
                self.channels_listbox.activate(index)
                self.channels_listbox.see(index)
                
                # Crear nuevo reproductor y reproducir
                print("Iniciando reproducción")
                self.play_channel(index)
            else:
                print(f"Índice {index} fuera de rango (max: {len(self.channels)-1})")
        except Exception as e:
            print(f"Error en select_and_play_channel: {e}")
            import traceback
            print(traceback.format_exc())

    def _safe_on_media_end(self, event):
        """Cuando termina un vídeo, reproduce el siguiente si estamos en modo secuencial."""
        try:
            print("\n=== MediaPlayerEndReached ===")
            print(f"Estado actual: {self.player.get_state() if self.player else 'No hay reproductor'}")
            print(f"Reproducción secuencial: {self.is_sequential_playback}")
            print(f"Índice actual: {self.current_playlist_index}")
            self.clear_youtube_resume()
            
            if not self.player:
                print("No hay reproductor activo")
                return
                
            if not getattr(self, '_media_started', False):
                print("Fin ignorado: el stream no llegó a reproducirse")
                return

            if not self.is_sequential_playback:
                print("Reproducción secuencial desactivada")
                return
                
            if self.current_playlist_index is None:
                print("Índice actual es None")
                return
                
            # Obtener el índice actual y el siguiente
            current_index = self.current_playlist_index
            next_index = current_index + 1
            
            print(f"\nProcesando transición de vídeo {current_index} -> {next_index}")
            
            # Verificar si hay más videos por reproducir
            if next_index < len(self.channels):
                print(f"Preparando reproducción del vídeo {next_index}")
                
                def play_next():
                    try:
                        print("\n=== Iniciando reproducción del siguiente vídeo ===")
                        # Detener reproducción actual
                        if self.player and self.player.is_playing():
                            self.player.stop()
                            print("Reproducción anterior detenida")
                            
                        # Limpiar event manager
                        if hasattr(self, '_current_event_manager') and self._current_event_manager:
                            try:
                                self._current_event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                                self._current_event_manager = None
                                print("Event manager limpiado")
                            except Exception as e:
                                print(f"Error al limpiar event manager: {e}")
                        
                        # Actualizar índice
                        self.current_playlist_index = next_index
                        print(f"Índice actualizado a {next_index}")
                        
                        # Reproducir siguiente vídeo
                        self.select_and_play_channel(next_index)
                        print("Reproducción iniciada")
                    except Exception as e:
                        print(f"Error al reproducir siguiente vídeo: {e}")
                
                # Usar delay más largo para asegurar que el vídeo anterior se ha detenido
                self.window.after(500, play_next)
                print("Reproducción programada con delay de 500ms")
            else:
                print("\nFin de la playlist alcanzado")
                self.is_sequential_playback = False
                self.current_playlist_index = None
                self._current_event_manager = None
                
        except Exception as e:
            print(f"Error en _safe_on_media_end: {e}")
            import traceback
            print(traceback.format_exc())

    def setup_event_manager(self):
        """Configura el event manager de VLC para manejar el fin de reproducción."""
        if not self.player:
            print("No hay reproductor disponible para configurar eventos")
            return

        print("Configurando event manager")

        # Limpiar cualquier event manager existente
        if hasattr(self, '_current_event_manager') and self._current_event_manager:
            try:
                self._current_event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                self._current_event_manager = None
                print("Event manager anterior limpiado")
            except Exception as e:
                print(f"Error al limpiar event manager anterior: {e}")

        try:
            # Verificar que el reproductor sigue válido
            if not self.player:
                print("No hay reproductor válido para configurar eventos")
                return
                
            # Crear un nuevo event manager
            event_manager = self.player.event_manager()
            
            # Configurar el callback para el fin de reproducción
            event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._safe_on_media_end)
            
            # Guardar la referencia al event manager actual
            self._current_event_manager = event_manager
            
            print(f"Event manager configurado exitosamente para índice {self.current_playlist_index}")

        except Exception as e:
            print(f"Error al configurar event manager: {e}")
            self.is_sequential_playback = False
            self.current_playlist_index = None
            self._current_event_manager = None

    def remove_channel(self, index):
        """Elimina un canal específico de la lista."""
        try:
            if 0 <= index < len(self.channels):
                del self.channels[index]
                if 0 <= index < len(self.all_channels):
                    del self.all_channels[index]
                self.channels_listbox.delete(index)
                self._persist_sidebar()
        except Exception as e:
            print(f"Error al eliminar canal: {e}")

    def clear_channel_list(self):
        """Vacía la lista de la barra lateral (no detiene el vídeo)."""
        if not self.all_channels and not self.channels:
            return
        player = self.window
        try:
            player.lift()
            player.focus_force()
        except tk.TclError:
            pass
        confirmed = messagebox.askyesno(
            "Limpiar lista",
            "¿Quitar todos los elementos de la lista lateral?",
            parent=player,
        )
        try:
            player.lift()
            player.focus_force()
        except tk.TclError:
            pass
        if not confirmed:
            return
        try:
            self.channels.clear()
            self.all_channels.clear()
            self.current_channel = None
            if self._widget_exists(self.search_entry):
                self.search_var.set('')
            if self._widget_exists(self.channels_listbox):
                self.channels_listbox.delete(0, tk.END)
        except Exception as e:
            print(f"Error al limpiar la lista: {e}")

    def add_to_favorites(self):
        """Añade el canal seleccionado a favoritos"""
        selection = self.channels_listbox.curselection()
        if not selection:
            messagebox.showinfo("Información", "Por favor, selecciona un canal primero")
            return
        selected_index = selection[0]
        channel = self.channels[selected_index]
        if channel not in self.favorites:
            self.favorites.append(channel)
            self.save_favorites()
            messagebox.showinfo("Éxito", f"Canal '{channel[0]}' añadido a favoritos")
        else:
            messagebox.showinfo("Información", f"El canal '{channel[0]}' ya está en favoritos")

    def remove_from_favorites(self):
        """Elimina el canal seleccionado de favoritos"""
        selection = self.channels_listbox.curselection()
        if not selection:
            messagebox.showinfo("Información", "Por favor, selecciona un canal primero")
            return
        selected_index = selection[0]
        channel = self.channels[selected_index]
        if channel in self.favorites:
            self.favorites.remove(channel)
            self.save_favorites()
            messagebox.showinfo("Éxito", f"Canal '{channel[0]}' eliminado de favoritos")
        else:
            messagebox.showinfo("Información", f"El canal '{channel[0]}' no estaba en favoritos")

    def show_channel_context_menu(self, event):
        selection = self.channels_listbox.nearest(event.y)
        if selection < 0 or selection >= len(self.channels):
            return
        self.channels_listbox.selection_clear(0, tk.END)
        self.channels_listbox.selection_set(selection)
        self.channels_listbox.activate(selection)
        menu = tk.Menu(self.window, tearoff=0)
        style_menu_tree(menu)
        menu.add_command(label="Reproducir desde aquí", command=lambda: self.play_from_here(selection))
        menu.add_separator()
        menu.add_command(label="Añadir a Favoritos", command=self.add_to_favorites)
        menu.add_command(label="Eliminar de Favoritos", command=self.remove_from_favorites)
        menu.add_separator()
        menu.add_command(label="Descargar", command=lambda: self.download_channel(selection))
        menu.add_command(label="Eliminar canal", command=lambda: self.remove_channel(selection))
        menu.add_separator()
        menu.add_command(label="Limpiar lista", command=self.clear_channel_list)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def toggle_playlist(self):
        """Muestra u oculta la lista de canales y el sizer"""
        if self.channels_frame_visible:
            self.channels_frame.pack_forget()
            self.sizer.pack_forget()
        else:
            self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)
            self.sizer.pack(side=tk.LEFT, fill=tk.Y)
        self.channels_frame_visible = not self.channels_frame_visible
        self.window.update_idletasks()

    def start_resize(self, event):
        self.resize_active = True
        self.last_x = event.x_root

    def do_resize(self, event):
        if not self.resize_active:
            return
        delta = event.x_root - self.last_x
        new_width = self.channels_frame.winfo_width() + delta
        # Limitar el ancho mínimo y máximo
        if 200 <= new_width <= 600:
            self.channels_frame.configure(width=new_width)
        self.last_x = event.x_root

    def stop_resize(self, event):
        self.resize_active = False

