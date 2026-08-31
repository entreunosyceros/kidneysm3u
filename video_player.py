import os
import pathlib
import time
import shutil
import psutil
from display_text import plain_display_text, plain_ui_line, busy_status_text
from channel_zap import (
    ZAP_TIMEOUT_MS,
    zap_buffer_append,
    zap_buffer_backspace,
    zap_event_digit,
    zap_number,
    zap_visible_index,
)
from favorites_manager import (
    FavoritesManager,
    add_favorite,
    favorite_name,
    favorite_url,
    favorites_contain,
    merge_favorites,
    normalize_favorites,
    read_favorites_file,
    remove_favorite,
    write_favorites_file,
)
import vlc
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import sys
import re
import threading
import yt_dlp
import traceback
from youtube_player import YouTubeHandler, youtube_ydl_opts
from twitch_player import TwitchHandler, is_twitch_url, is_twitch_vod_url, twitch_default_title
from youtube_search import (
    YouTubeSearchDialog,
    fetch_youtube_channel_videos,
    is_youtube_channel_url,
    is_youtube_playlist_url,
)
from ui_theme import (
    get_colors, get_font, style_window, style_menu_tree,
    set_window_icon, make_control_icons,
)
from ui_clipboard import ask_string
import app_config
from iptv_buffer import vlc_aout_instance_args, vlc_aout_option
from subtitle_style import apply_spu_delay, fingerprint, vlc_instance_args, vlc_media_options
from m3u_parse import (
    parse_m3u_channels, parse_m3u_epg_urls, decode_m3u_bytes,
    IPTV_USER_AGENT,
)
from channel_sidebar import ChannelSidebar
import epg
import logo_cache
from epg_grid import show_epg_grid
from iptv_history import show_iptv_history
from youtube_queue import show_youtube_queue
from player_controls import PlayerControlsMixin
from player_iptv import IptvPlaybackMixin
from player_overlay import ChannelNoticeMixin
from player_pip import PlayerPipMixin
from iptv_record import StreamRecorder, default_recording_path, show_recordings


def popup_menu_origin(btn_x, btn_y, btn_h, menu_w, menu_h, area_x, area_y, area_w, area_h, pad=4):
    """Esquina superior izquierda del menú para que quepa en el área. Prefiere debajo del botón."""
    below = btn_y + btn_h
    if below + menu_h + pad <= area_y + area_h:
        y = below
    else:
        y = btn_y - menu_h
        if y < area_y + pad:
            y = area_y + pad
    x = btn_x
    if x + menu_w + pad > area_x + area_w:
        x = area_x + area_w - menu_w - pad
    if x < area_x + pad:
        x = area_x + pad
    return int(x), int(y)


# Clase Tooltip para mostrar información al pasar el ratón
class Tooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self._text = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text, x=None, y=None, wraplength=0):
        """Muestra el tooltip con el texto dado, cerca del puntero del ratón."""
        text = plain_display_text(text)
        if not text:
            self.hidetip()
            return
        if self.tipwindow and self._text == text:
            return
        self.hidetip()
        if x is None or y is None:
            x = self.widget.winfo_pointerx() + 16
            y = self.widget.winfo_pointery() + 12
        self._text = text
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{int(x)}+{int(y)}")
        try:
            tw.attributes('-topmost', True)
        except tk.TclError:
            pass
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
            wraplength=wraplength,
        )
        label.pack()

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        self._text = None
        if tw:
            try:
                tw.destroy()
            except tk.TclError:
                pass


def _make_vlc_instance():
    """Instancia VLC; en modo normal sin VA-API (NVIDIA). Opcional GPU en modo ligero."""
    os.environ['LIBVA_MESSAGING_LEVEL'] = '0'
    use_hw = app_config.iptv_use_hw_decode()
    core = [
        "--quiet",
        "--verbose=0",
        "--audio-resampler=soxr",
        "--network-caching=3000",
        "--live-caching=3000",
        "--file-caching=3000",
        "--sout-mux-caching=3000",
        f"--http-user-agent={IPTV_USER_AGENT}",
    ]
    if not use_hw:
        core.insert(2, "--avcodec-hw=none")
    core.extend(vlc_aout_instance_args())
    attempts = (
        core + vlc_instance_args(),
        list(core),
    )
    if not use_hw:
        attempts = attempts + (["--quiet", "--avcodec-hw=none"],)
    else:
        attempts = attempts + (["--quiet"],)
    last_error = None
    for args in attempts:
        try:
            instance = vlc.Instance(*args)
        except Exception as exc:
            last_error = exc
            continue
        if instance is not None:
            return instance
    detail = f' ({last_error})' if last_error else ''
    raise RuntimeError(
        'VLC no pudo crear el reproductor. Comprueba que libvlc está instalado.'
        + detail
    )


def should_offer_youtube_replay(playing_youtube, standalone, sequential, queue_pending):
    """True solo si acaba un vídeo de YouTube suelto, no una cola, playlist o secuencia."""
    return bool(playing_youtube and standalone and not sequential and not queue_pending)


class VideoPlayer(PlayerControlsMixin, IptvPlaybackMixin, ChannelNoticeMixin, PlayerPipMixin):
    def __init__(self):
        self.window = None
        self.instance = _make_vlc_instance()
        self.player = self.instance.media_player_new()
        self._vlc_style_key = fingerprint()
        self._vlc_hw_decode_key = app_config.iptv_use_hw_decode()
        self.channels = []
        self.current_channel = None
        self.channels_listbox = None
        self.sidebar = None
        self._groups = []
        self._groups_all = []
        self._tvg_ids = []
        self._tvg_ids_all = []
        self._logos = []
        self._logos_all = []
        self._logo_photos = {}
        self._show_logos = app_config.effective_show_channel_logos()
        self._previous_channel_index = None
        self._logos_var = None
        self._epg = None
        self._epg_urls = []
        self._epg_urls_list = []
        self._epg_url_manual = ''
        self._epg_gen = 0
        self._epg_grid = None
        self._iptv_history = None
        self._history_menu = None
        self._iptv_resume_s = 0
        self._last_iptv_resume_save = 0
        self._epg_reload_job = None
        self._epg_tick_job = None
        self._logo_refresh_job = None
        self._filter_job = None
        self._filter_gen = 0
        self._load_gen = 0
        self.channels_frame_visible = True
        self.is_fullscreen = False
        self.controls_visible = True
        self.hide_controls_timer = None
        self.empty_menu = None  # Menú vacío para ocultar en fullscreen
        self.volume = app_config.get_volume()
        self.favorites = []
        self._showing_favorites = False
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
        self._last_twitch_resume_save = 0
        self._tw_end_handled = False
        self._playing_youtube = False
        self._playing_twitch = False
        self._pipe_ready = False
        self._playlist_source = ''
        self._playlist_kind = ''
        self._geometry_save_job = None
        self._volume_save_job = None
        self._media_started = False
        self._yt_standalone = True
        self._yt_end_handled = False
        self._media_end_gen = 0
        self._yt_replay_frame = None
        self._iptv_relay_procs = []
        self._iptv_relay_server = None
        self._iptv_relay_tmpdir = None
        self._iptv_attempts = []
        self._iptv_source_url = ''
        self._iptv_retry_name = ''
        self._stream_recorder = StreamRecorder(self)
        self._recordings = []
        self._recordings_win = None
        self._record_watch_job = None
        self._pip_window = None
        self._pip_frame = None
        self._topmost_var = None
        self._iptv_check_gen = 0
        self._iptv_status_frame = None
        self._iptv_notice_top = None
        self._iptv_banner = None
        self._iptv_failed = False
        self._iptv_ok_ticks = 0
        self._audio_tracks = []
        self._spu_tracks = []
        self._yt_subtitles = []
        self._active_audio_id = None
        self._active_spu_id = -1
        self._active_yt_sub = None
        self._track_poll_gen = 0
        self._last_video_click_at = 0
        self._zap_digits = ''
        self._zap_job = None
        self._zap_top = None
        self._zap_side_label = None
        self._yt_sub_dir = None
        self._audio_choice = None
        self._subs_choice = None

        # Inicializar el manejador de YouTube
        self.youtube_handler = YouTubeHandler(self)
        self.twitch_handler = TwitchHandler(self)

        # Inicializar el manejador de favoritos
        self.favorites_manager = FavoritesManager(self)

        self.create_window()
        self.load_favorites()
        self.setup_mouse_tracking()

        # Nuevas variables para reproducción secuencial
        self.is_sequential_playback = False
        self.current_playlist_index = None

    def create_window(self):
        self.window = tk.Toplevel(class_='Kidneysm3u')
        self.window._video_player = self
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

        # Lista a la izquierda: botones en cuadrícula 2×2 para que no se desborden
        self.channels_frame = ttk.Frame(self.main_frame, width=300)
        self.channels_frame.pack_propagate(False)
        self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Frame separador (sizer)
        self.sizer = ttk.Frame(self.main_frame, width=5, cursor='sb_h_double_arrow', style='Sizer.TFrame')
        self.sizer.pack(side=tk.LEFT, fill=tk.Y)

        toolbar = ttk.Frame(self.channels_frame)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 4))
        toolbar.columnconfigure(0, weight=1, uniform='sidebar_btn')
        toolbar.columnconfigure(1, weight=1, uniform='sidebar_btn')
        ttk.Button(
            toolbar, text="★ Favoritos", style='Compact.TButton', command=self.show_favorites,
        ).grid(row=0, column=0, sticky='ew', padx=(0, 4), pady=(0, 4))
        ttk.Button(
            toolbar, text="Todos", style='Compact.TButton', command=self.restore_all_channels,
        ).grid(row=0, column=1, sticky='ew', pady=(0, 4))
        ttk.Button(
            toolbar, text="Limpiar", style='Compact.TButton', command=self.clear_channel_list,
        ).grid(row=1, column=0, sticky='ew', padx=(0, 4), pady=(0, 4))
        ttk.Button(
            toolbar, text="Guía", style='Compact.TButton', command=self.open_epg_grid,
        ).grid(row=1, column=1, sticky='ew', pady=(0, 4))

        search_row = ttk.Frame(self.channels_frame)
        search_row.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', self.filter_channels)
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            search_row, text='★ Añadir', style='Compact.TButton', command=self.add_to_favorites,
        ).pack(side=tk.LEFT, padx=(6, 0))
        self._zap_side_label = ttk.Label(self.channels_frame, text='', style='PageTitle.TLabel')

        self._epg_label = ttk.Label(
            self.channels_frame,
            text='',
            style='Muted.TLabel',
            wraplength=260,
            justify=tk.LEFT,
        )

        self.sidebar = ChannelSidebar(self.channels_frame)
        self.sidebar.now_text = self._epg_now_title
        self.sidebar.row_image = self._logo_photo
        self.sidebar.is_favorite = self._channel_is_favorite
        self.sidebar.on_view_change = self._on_sidebar_view_change
        self.channels_listbox = self.sidebar.tree
        self.channels_listbox.bind('<Double-Button-1>', self.play_selected)
        self.channels_listbox.bind('<Button-3>', self.show_channel_context_menu)
        self.channels_listbox.bind('<<TreeviewSelect>>', self._on_sidebar_select_epg, add='+')

        self.listbox_tooltip = Tooltip(self.channels_listbox)
        self._listbox_tip_index = None
        self.channels_listbox.bind('<Motion>', self.on_listbox_motion)
        self.channels_listbox.bind('<Leave>', self.on_listbox_leave)
        self.channels_listbox.bind('<Button-4>', self._hide_listbox_tooltip, add='+')
        self.channels_listbox.bind('<Button-5>', self._hide_listbox_tooltip, add='+')
        self.channels_listbox.bind('<MouseWheel>', self._hide_listbox_tooltip, add='+')

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
        colors = get_colors()
        self._control_icons = make_control_icons(colors['text'], record_color=colors['danger'])
        buttons_info = [
            ('skip_back', 'Retroceder 10 segundos', lambda: self.seek_relative(-10)),
            ('rewind', 'Retroceder 2 segundos', lambda: self.seek_relative(-2)),
            ('play_pause', 'Reproducir / Pausar', self.toggle_play),
            ('forward', 'Avanzar 2 segundos', lambda: self.seek_relative(2)),
            ('skip_forward', 'Avanzar 10 segundos', lambda: self.seek_relative(10)),
            ('stop', 'Detener reproducción', self.stop),
            ('record', 'Grabar', self.toggle_stream_recording),
            ('quality', 'Calidad / audio', self._popup_audio_menu),
            ('subtitles', 'Subtítulos', self._popup_subs_menu),
            ('volume', 'Silenciar / Activar sonido', self.toggle_mute),
            ('pip', 'Ventana PiP', self.toggle_pip),
            ('fullscreen', 'Pantalla completa', self.toggle_fullscreen),
            ('playlist', 'Mostrar / Ocultar lista', self.toggle_playlist),
        ]
        self._audio_btn = None
        self._subs_btn = None
        self._record_btn = None
        self._control_buttons = {}
        self._posted_popup = None
        self._channel_menu = None
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
            if key == 'record':
                self._record_btn = btn
                btn.bind('<Enter>', lambda e, t=tip: t.showtip(self._record_tip_text()))
            else:
                btn.bind('<Enter>', lambda e, t=tip, txt=tip_text: t.showtip(txt))
            btn.bind('<Leave>', lambda e, t=tip: t.hidetip())
            self._control_buttons[key] = btn
            if key == 'quality':
                self._audio_btn = btn
            elif key == 'subtitles':
                self._subs_btn = btn
        self.add_volume_control()
        self._refresh_record_button()
        self.setup_performance_monitoring()
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.youtube_handler.notify_session()
        self.twitch_handler.notify_session()
        self.setup_keyboard_shortcuts()

    def setup_performance_monitoring(self):
        """Monitor de CPU opcional (muestreo cada ~8 s)."""
        label = getattr(self, 'cpu_label', None)
        if not app_config.get_show_cpu_monitor():
            if label is not None and self._widget_exists(label):
                try:
                    label.destroy()
                except tk.TclError:
                    pass
                self.cpu_label = None
            return
        if label is None or not self._widget_exists(label):
            self.cpu_label = ttk.Label(self.controls_frame, text=plain_ui_line('CPU: …'))
            self.cpu_label.pack(side=tk.RIGHT, padx=5)
        self.update_performance_stats()

    def update_performance_stats(self):
        """Actualiza las estadísticas de rendimiento."""
        label = getattr(self, 'cpu_label', None)
        if not app_config.get_show_cpu_monitor() or not self._widget_exists(label):
            return
        try:
            cpu_percent = psutil.cpu_percent()
            label.config(text=f'CPU: {cpu_percent:.0f} %')
        except Exception:
            pass
        if self._widget_exists(self.window):
            self.window.after(
                app_config.CPU_MONITOR_INTERVAL_MS,
                self.update_performance_stats,
            )
        
    def create_menu(self):
        self.menubar = tk.Menu(self.window)

        reproducir_menu = tk.Menu(self.menubar, tearoff=0)
        reproducir_menu.add_command(label="Cargar URL", command=self.prompt_url)
        reproducir_menu.add_command(label="Cargar Archivo Local", command=self.prompt_file)
        epg_menu = tk.Menu(reproducir_menu, tearoff=0)
        epg_menu.add_command(label=plain_ui_line("Parrilla…"), command=self.open_epg_grid)
        epg_menu.add_separator()
        epg_menu.add_command(label=plain_ui_line("Desde URL…"), command=self.prompt_epg_url)
        epg_menu.add_command(label=plain_ui_line("Desde archivo…"), command=self.prompt_epg_file)
        epg_menu.add_separator()
        epg_menu.add_command(label="Quitar guía", command=self.clear_manual_epg)
        self._logos_var = tk.BooleanVar(value=self.channel_logos_enabled())
        epg_menu.add_separator()
        epg_menu.add_checkbutton(
            label="Mostrar logos de canal",
            variable=self._logos_var,
            command=self._on_logos_menu_toggle,
        )
        reproducir_menu.add_cascade(label="Guía EPG", menu=epg_menu)
        self._history_menu = tk.Menu(reproducir_menu, tearoff=0)
        self._history_menu.configure(postcommand=self._fill_history_menu)
        reproducir_menu.add_cascade(label="Historial", menu=self._history_menu)
        reproducir_menu.add_separator()
        reproducir_menu.add_command(label="Grabar / detener", command=self.toggle_stream_recording)
        reproducir_menu.add_command(
            label=plain_ui_line("Grabar en…"),
            command=lambda: self.start_stream_recording(ask_path=True),
        )
        reproducir_menu.add_command(
            label=plain_ui_line("Grabaciones…"),
            command=lambda: show_recordings(self),
        )
        reproducir_menu.add_separator()
        self._topmost_var = tk.BooleanVar(value=False)
        reproducir_menu.add_checkbutton(
            label="Siempre encima",
            variable=self._topmost_var,
            command=self.toggle_always_on_top,
        )
        reproducir_menu.add_command(label="Ventana PiP", command=self.toggle_pip)
        reproducir_menu.add_separator()
        reproducir_menu.add_command(label="Limpiar lista lateral", command=self.clear_channel_list)
        reproducir_menu.add_separator()
        reproducir_menu.add_command(label="Preferencias", command=self.open_preferences)
        reproducir_menu.add_command(label="Cerrar Reproductor", command=self.close)

        youtube_menu = tk.Menu(self.menubar, tearoff=0)
        youtube_menu.add_command(label="Cargar URL de YouTube", command=self.youtube_handler.prompt_youtube_url)
        youtube_menu.add_command(label="Descargar vídeo de YouTube", command=self.youtube_handler.download_youtube_video)
        youtube_menu.add_command(label="Buscar en YouTube", command=self.open_youtube_search)
        youtube_menu.add_command(label="Cola de YouTube", command=self.open_youtube_queue)
        # NUEVO: Añadir opción para cargar playlist
        youtube_menu.add_command(label="Cargar Playlist de YouTube", command=self.prompt_youtube_playlist)
        youtube_menu.add_separator()
        youtube_menu.add_command(label=plain_ui_line("Sesión YouTube: …"), state='disabled')
        self._yt_session_menu_index = youtube_menu.index('end')
        youtube_menu.add_command(label="Reexportar cookies", command=self.reexport_youtube_cookies)
        youtube_menu.add_command(label="Actualizar yt-dlp", command=self.update_yt_dlp)
        self._youtube_menu = youtube_menu
        twitch_menu = tk.Menu(self.menubar, tearoff=0)
        twitch_menu.add_command(label="Cargar URL de Twitch", command=self.twitch_handler.prompt_twitch_url)
        twitch_menu.add_command(
            label=plain_ui_line("VODs del canal…"),
            command=self.open_twitch_channel_browser,
        )
        twitch_menu.add_command(
            label=plain_ui_line("Buscar…"),
            command=self.open_twitch_search,
        )
        twitch_menu.add_command(
            label=plain_ui_line("Añadir a favoritos"),
            command=self.add_twitch_to_favorites,
        )
        twitch_menu.add_command(
            label=plain_ui_line("Ver chat…"),
            command=self.toggle_twitch_chat,
            state='disabled',
        )
        self._tw_chat_menu_index = twitch_menu.index('end')
        self._twitch_recent_menu = tk.Menu(twitch_menu, tearoff=0)
        self._twitch_recent_menu.configure(postcommand=self._fill_twitch_recent_menu)
        twitch_menu.add_cascade(label=plain_ui_line("Recientes"), menu=self._twitch_recent_menu)
        twitch_menu.add_separator()
        twitch_menu.add_command(label=plain_ui_line("Sesión Twitch: …"), state='disabled')
        self._tw_session_menu_index = twitch_menu.index('end')
        twitch_menu.add_command(label="Reexportar cookies", command=self.reexport_twitch_cookies)
        self._twitch_menu = twitch_menu
        favoritos_menu = tk.Menu(self.menubar, tearoff=0)
        favoritos_menu.add_command(label="Mostrar Favoritos", command=self.show_favorites)
        favoritos_menu.add_command(label="Añadir a Favoritos", command=self.add_to_favorites)
        favoritos_menu.add_command(label="Eliminar de Favoritos", command=self.remove_from_favorites)
        favoritos_menu.add_separator()
        favoritos_menu.add_command(label=plain_ui_line('Exportar favoritos…'), command=self.export_favorites)
        favoritos_menu.add_command(label=plain_ui_line('Importar favoritos…'), command=self.import_favorites)

        self.audio_menu = tk.Menu(self.menubar, tearoff=0)
        self.subs_menu = tk.Menu(self.menubar, tearoff=0)
        self.audio_popup = tk.Menu(self.window, tearoff=0)
        self.subs_popup = tk.Menu(self.window, tearoff=0)
        self._audio_choice = tk.StringVar(value='')
        self._subs_choice = tk.StringVar(value='off')
        self._quality_choice = tk.StringVar(value=str(app_config.get_youtube_quality()))
        self.menubar.add_cascade(label="Reproducir", menu=reproducir_menu)
        self.menubar.add_cascade(label="Youtube", menu=youtube_menu)
        self.menubar.add_cascade(label="Twitch", menu=twitch_menu)
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
        self.window.bind('<space>', self._on_space_toggle_play)
        self.window.bind('<F1>', lambda e: self.toggle_fullscreen())
        self.window.bind('<m>', lambda e: self.toggle_mute())
        self.window.bind('<Left>', lambda e: self.seek_relative(-2))
        self.window.bind('<Right>', lambda e: self.seek_relative(2))
        self.window.bind('<Escape>', self._on_escape_key)
        
        # Atajos para favoritos
        self.window.bind('<Control-s>', self.handle_add_favorite)
        self.window.bind('<Control-d>', self.handle_remove_favorite)
        self.window.bind('<g>', self._on_epg_grid_key)
        self.window.bind('<G>', self._on_epg_grid_key)
        self.window.bind('<c>', self._on_twitch_chat_key)
        self.window.bind('<C>', self._on_twitch_chat_key)
        self.window.bind('<Prior>', self._on_channel_prev_key)
        self.window.bind('<Next>', self._on_channel_next_key)
        self.window.bind('<plus>', self._on_channel_next_key)
        self.window.bind('<minus>', self._on_channel_prev_key)
        self.window.bind('<KP_Add>', self._on_channel_next_key)
        self.window.bind('<KP_Subtract>', self._on_channel_prev_key)
        self.window.bind('<b>', self._on_last_channel_key)
        self.window.bind('<B>', self._on_last_channel_key)
        self.window.bind('<Return>', self._on_zap_confirm)
        self.window.bind('<KP_Enter>', self._on_zap_confirm)
        self.window.bind('<BackSpace>', self._on_zap_backspace)
        for digit in '0123456789':
            self.window.bind(digit, self._on_zap_digit)
            self.window.bind(f'<KP_{digit}>', self._on_zap_digit)
        
        # Asegurarse de que el listbox también recibe los eventos
        self.channels_listbox.bind('<Control-s>', self.handle_add_favorite)
        self.channels_listbox.bind('<Control-d>', self.handle_remove_favorite)
        self.channels_listbox.bind('<Return>', self._on_zap_confirm)
        self.channels_listbox.bind('<KP_Enter>', self._on_zap_confirm)
        self.channels_listbox.bind('<BackSpace>', self._on_zap_backspace)
        self.search_entry.bind('<Control-s>', self.handle_add_favorite)
        self.search_entry.bind('<Control-d>', self.handle_remove_favorite)
        for digit in '0123456789':
            self.channels_listbox.bind(digit, self._on_zap_digit)
            self.channels_listbox.bind(f'<KP_{digit}>', self._on_zap_digit)
        for sequence, handler in (
            ('<Prior>', self._on_channel_prev_key),
            ('<Next>', self._on_channel_next_key),
            ('<plus>', self._on_channel_next_key),
            ('<minus>', self._on_channel_prev_key),
            ('<KP_Add>', self._on_channel_next_key),
            ('<KP_Subtract>', self._on_channel_prev_key),
            ('<b>', self._on_last_channel_key),
            ('<B>', self._on_last_channel_key),
        ):
            self.channels_listbox.bind(sequence, handler)
            self.search_entry.bind(sequence, handler)
        video = getattr(self, 'video_frame', None)
        if video is not None:
            video.bind('<Key>', self._on_zap_digit, add='+')
            video.bind('<Return>', self._on_zap_confirm, add='+')
            video.bind('<KP_Enter>', self._on_zap_confirm, add='+')
            video.bind('<BackSpace>', self._on_zap_backspace, add='+')
            video.bind('<Escape>', self._on_escape_key, add='+')
            for sequence, handler in (
                ('<Prior>', self._on_channel_prev_key),
                ('<Next>', self._on_channel_next_key),
                ('<plus>', self._on_channel_next_key),
                ('<minus>', self._on_channel_prev_key),
                ('<KP_Add>', self._on_channel_next_key),
                ('<KP_Subtract>', self._on_channel_prev_key),
                ('<b>', self._on_last_channel_key),
                ('<B>', self._on_last_channel_key),
            ):
                video.bind(sequence, handler, add='+')

    def _on_channel_prev_key(self, event=None):
        if self._event_in_text_field(event):
            return
        self._play_relative_channel(-1)
        return 'break'

    def _on_channel_next_key(self, event=None):
        if self._event_in_text_field(event):
            return
        self._play_relative_channel(1)
        return 'break'

    def _on_last_channel_key(self, event=None):
        if self._event_in_text_field(event):
            return
        self._play_last_channel()
        return 'break'

    def _play_relative_channel(self, delta):
        visible = self._zap_visible_indices()
        if not visible:
            return
        current = self.current_channel
        if current in visible:
            position = visible.index(current) + int(delta)
        else:
            position = 0 if delta >= 0 else len(visible) - 1
        if position < 0 or position >= len(visible):
            return
        index = visible[position]
        sidebar = getattr(self, 'sidebar', None)
        if sidebar:
            sidebar.select(index)
            sidebar.see(index)
        self.play_channel(index)

    def _play_last_channel(self):
        previous = getattr(self, '_previous_channel_index', None)
        current = self.current_channel
        if previous is None or previous == current:
            return
        if not (0 <= previous < len(self.channels)):
            return
        sidebar = getattr(self, 'sidebar', None)
        if sidebar:
            sidebar.select(previous)
            sidebar.see(previous)
        self.play_channel(previous)

    def _event_in_text_field(self, event):
        widget = getattr(event, 'widget', None) if event is not None else None
        try:
            if widget and widget.winfo_class() in ('Entry', 'TEntry', 'Text', 'TCombobox'):
                return True
        except tk.TclError:
            pass
        return False

    def _on_escape_key(self, event=None):
        if self._zap_digits:
            self._clear_zap()
            return 'break'
        self.exit_fullscreen()
        return 'break'

    def _zap_visible_indices(self):
        sidebar = getattr(self, 'sidebar', None)
        if sidebar:
            indices = sidebar.current_indices()
            if indices:
                return indices
        return list(range(len(self.channels)))

    def _cancel_zap_timer(self):
        job = getattr(self, '_zap_job', None)
        self._zap_job = None
        if job is None or not self._widget_exists(self.window):
            return
        try:
            self.window.after_cancel(job)
        except (tk.TclError, ValueError):
            pass

    def _schedule_zap(self):
        self._cancel_zap_timer()
        if not self._zap_digits or not self._widget_exists(self.window):
            return
        try:
            self._zap_job = self.window.after(ZAP_TIMEOUT_MS, self._commit_zap)
        except tk.TclError:
            self._zap_job = None

    def _on_zap_digit(self, event=None):
        if self._event_in_text_field(event):
            return
        if event is not None and getattr(event, 'state', 0) & 0x4:
            return
        digit = zap_event_digit(event) if event is not None else ''
        if not digit:
            return
        count = len(self._zap_visible_indices())
        if count <= 0:
            return 'break'
        self._zap_digits = zap_buffer_append(self._zap_digits, digit, count)
        self._show_zap_osd()
        self._schedule_zap()
        return 'break'

    def _on_zap_backspace(self, event=None):
        if self._event_in_text_field(event):
            return
        if not self._zap_digits:
            return
        self._zap_digits = zap_buffer_backspace(self._zap_digits)
        if self._zap_digits:
            self._show_zap_osd()
            self._schedule_zap()
        else:
            self._clear_zap()
        return 'break'

    def _on_zap_confirm(self, event=None):
        if self._event_in_text_field(event):
            return
        if not self._zap_digits:
            return
        self._commit_zap()
        return 'break'

    def _commit_zap(self):
        self._cancel_zap_timer()
        visible = self._zap_visible_indices()
        number = zap_number(self._zap_digits)
        position = zap_visible_index(number, len(visible))
        if position is None:
            self._show_zap_osd(miss=True)
            self._zap_digits = ''
            if self._widget_exists(self.window):
                try:
                    self._zap_job = self.window.after(800, self._clear_zap)
                except tk.TclError:
                    self._clear_zap()
            return
        index = visible[position]
        self._clear_zap()
        sidebar = getattr(self, 'sidebar', None)
        if sidebar:
            sidebar.select(index)
            sidebar.see(index)
        self.play_channel(index)

    def _zap_preview_name(self):
        visible = self._zap_visible_indices()
        position = zap_visible_index(zap_number(self._zap_digits), len(visible))
        if position is None:
            return ''
        index = visible[position]
        if 0 <= index < len(self.channels):
            return plain_display_text(self.channels[index][0])
        return ''

    def _show_zap_osd(self, miss=False):
        colors = get_colors()
        number = self._zap_digits or '—'
        name = '' if miss else plain_display_text(self._zap_preview_name())
        if miss:
            text = f'{number}\nno hay canal'
        elif name:
            text = f'{number}\n{name}'
        else:
            text = number
        side = getattr(self, '_zap_side_label', None)
        if self._widget_exists(side):
            try:
                side.configure(text=text.replace('\n', '  ·  '))
                sidebar = getattr(self, 'sidebar', None)
                before = getattr(sidebar, 'outer', None) if sidebar else None
                if before and self._widget_exists(before):
                    side.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6), before=before)
                else:
                    side.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6))
            except tk.TclError:
                pass
        top = getattr(self, '_zap_top', None)
        if not self._widget_exists(top):
            if not self._widget_exists(self.window):
                return
            top = tk.Toplevel(self.window)
            try:
                top.overrideredirect(True)
            except tk.TclError:
                pass
            try:
                top.attributes('-topmost', True)
            except tk.TclError:
                pass
            try:
                top.wm_attributes('-type', 'splash')
            except tk.TclError:
                pass
            top.configure(bg=colors['surface'])
            label = tk.Label(
                top,
                text=text,
                font=get_font(22, 'bold'),
                bg=colors['surface'],
                fg=colors['text'],
                padx=16,
                pady=10,
                justify='right',
                wraplength=280,
            )
            label.pack()
            self._zap_top = top
            self._zap_osd_label = label
        else:
            label = getattr(self, '_zap_osd_label', None)
            if self._widget_exists(label):
                try:
                    label.configure(text=text)
                except tk.TclError:
                    pass
        self._position_zap_osd()
        try:
            top.deiconify()
            top.lift()
        except tk.TclError:
            pass

    def _position_zap_osd(self, event=None):
        top = getattr(self, '_zap_top', None)
        if not self._widget_exists(top) or not self._widget_exists(self.window):
            return
        area = getattr(self, 'player_frame', None)
        if not self._widget_exists(area):
            area = getattr(self, 'video_frame', None)
        if not self._widget_exists(area):
            return
        try:
            area.update_idletasks()
            top.update_idletasks()
            width = max(120, top.winfo_reqwidth())
            height = max(48, top.winfo_reqheight())
            x = area.winfo_rootx() + max(12, area.winfo_width() - width - 16)
            y = area.winfo_rooty() + 12
            top.geometry(f'{int(width)}x{int(height)}+{int(x)}+{int(y)}')
        except tk.TclError:
            pass

    def _clear_zap(self):
        self._cancel_zap_timer()
        self._zap_digits = ''
        side = getattr(self, '_zap_side_label', None)
        if self._widget_exists(side):
            try:
                side.configure(text='')
                side.pack_forget()
            except tk.TclError:
                pass
        top = getattr(self, '_zap_top', None)
        self._zap_top = None
        self._zap_osd_label = None
        if top is not None:
            try:
                top.destroy()
            except tk.TclError:
                pass

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
        channel_menu = getattr(self, '_channel_menu', None)
        self._posted_popup = None
        self._channel_menu = None
        for menu in (
            posted,
            channel_menu,
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
        if channel_menu is not None:
            try:
                channel_menu.destroy()
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
        posted = getattr(self, '_posted_popup', None)
        if self._event_on_menu(event, posted):
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

    def _track_menu_size(self, menu):
        try:
            menu.update_idletasks()
            width = int(menu.winfo_reqwidth() or 0)
            height = int(menu.winfo_reqheight() or 0)
        except tk.TclError:
            width, height = 0, 0
        try:
            last = menu.index('end')
            count = 0 if last is None else last + 1
        except tk.TclError:
            count = 4
        if width < 80:
            width = 220
        if height < 24:
            height = max(count, 1) * 28 + 8
        return width, height

    def _popup_origin_for_button(self, button, menu):
        menu_w, menu_h = self._track_menu_size(menu)
        win = self.window
        return popup_menu_origin(
            button.winfo_rootx(),
            button.winfo_rooty(),
            button.winfo_height(),
            menu_w,
            menu_h,
            win.winfo_rootx(),
            win.winfo_rooty(),
            win.winfo_width(),
            win.winfo_height(),
        )

    def _popup_track_menu(self, button, menu):
        if not button or not self._widget_exists(button) or menu is None:
            return
        if self._posted_popup is menu and self._menu_is_mapped(menu):
            self._dismiss_track_menus()
            return
        self._dismiss_track_menus()
        self._rebuild_track_menus()
        try:
            x, y = self._popup_origin_for_button(button, menu)
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
        menu.add_radiobutton(
            label='1080p',
            variable=self._quality_choice,
            value='1080',
            command=lambda: self._choose_from_menu(lambda: self._apply_youtube_quality(1080)),
        )
        menu.add_radiobutton(
            label='Mejor disponible',
            variable=self._quality_choice,
            value='0',
            command=lambda: self._choose_from_menu(lambda: self._apply_youtube_quality(0)),
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

    def _apply_youtube_quality(self, height, force=False):
        height = app_config.normalize_youtube_quality(height)
        previous = app_config.get_youtube_quality()
        app_config.set_youtube_quality(height)
        if getattr(self, '_quality_choice', None) is not None:
            self._quality_choice.set(str(height))
        if (not force and previous == height) or not getattr(self, '_playing_youtube', False):
            return
        handler = getattr(self, 'youtube_handler', None)
        url = getattr(handler, '_current_url', '') or ''
        if not handler or not url:
            return
        elapsed_s = self._playback_elapsed_ms() / 1000.0
        kwargs = dict(getattr(handler, '_play_kwargs', {}) or {})
        print(
            f"[YouTube] Calidad {app_config.youtube_quality_label(previous)} → "
            f"{app_config.youtube_quality_label(height)}"
        )
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
                vtt_url=item.get('vtt_url'),
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
            keep_ms = self._playback_elapsed_ms()
            handler = self.youtube_handler
            direct = getattr(handler, '_direct_url', '') or ''
            if not direct:
                print('[YouTube] No hay URL de stream para recargar con subtítulos')
                return
            self._ensure_vlc_style_instance()
            self.play_video_url(
                direct,
                force_pulse=True,
                show_progress=True,
                http_headers=getattr(handler, '_direct_headers', None),
                duration_s=(self._known_duration_ms / 1000.0) if self._known_duration_ms else None,
                subtitle_path=path,
                start_s=keep_ms / 1000.0,
                fail_after_s=20,
            )
            self._hold_progress_ms = keep_ms
            self._hold_progress_until = time.time() + 2.5
            return
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

        # Clic en el vídeo: pausa/reanuda. VLC no debe tragarse el ratón (si no, el clic no llega a Tk).
        self.video_frame.bind('<Button-1>', self._on_video_click)

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

    def _on_space_toggle_play(self, event=None):
        if self._event_in_text_field(event):
            return
        self.toggle_play()
        return 'break'

    def _on_video_click(self, event=None):
        """Un clic en el vídeo pausa o reanuda, como Espacio. Sin redibujar el frame."""
        widget = getattr(event, 'widget', None) if event is not None else None
        if widget is not None and widget is not self.video_frame:
            return
        if self._posted_popup or self._any_track_menu_mapped():
            self._dismiss_track_menus()
            return 'break'
        now = time.time()
        if now - getattr(self, '_last_video_click_at', 0) < 0.28:
            return 'break'
        self._last_video_click_at = now
        self.toggle_play()
        if self.is_fullscreen:
            self.show_controls_and_menu()
        try:
            self.window.focus_set()
        except tk.TclError:
            pass
        return 'break'

    def toggle_stream_recording(self):
        recorder = getattr(self, '_stream_recorder', None)
        if recorder and recorder.is_recording():
            self.stop_stream_recording(notify=True)
        else:
            self.start_stream_recording(ask_path=False)

    def start_stream_recording(self, ask_path=False):
        recorder = getattr(self, '_stream_recorder', None)
        if recorder is None:
            return
        if recorder.is_recording():
            messagebox.showinfo(
                "Grabar",
                f"Ya se está grabando:\n{recorder.path}",
                parent=self.window,
            )
            return
        source, _headers, name = recorder.current_source()
        if not source:
            messagebox.showinfo(
                "Grabar",
                "No hay un stream que se pueda copiar ahora.",
                parent=self.window,
            )
            return
        dest = default_recording_path(name)
        if ask_path:
            dest = filedialog.asksaveasfilename(
                parent=self.window,
                title=plain_ui_line('Grabar en…'),
                initialfile=os.path.basename(dest),
                initialdir=os.path.dirname(dest),
                defaultextension='.ts',
                filetypes=[('MPEG-TS', '*.ts'), ('Matroska', '*.mkv'), ('Todos', '*.*')],
            )
            if not dest:
                return
        ok, detail = recorder.start(dest)
        if not ok:
            messagebox.showerror("Grabar", detail, parent=self.window)
            return
        self._refresh_record_button()
        self._watch_recording()
        win = getattr(self, '_recordings_win', None)
        if win is not None:
            try:
                win.refresh()
            except tk.TclError:
                pass

    def stop_stream_recording(self, notify=False):
        self._cancel_record_watch()
        recorder = getattr(self, '_stream_recorder', None)
        if recorder is None:
            return
        was = recorder.is_recording() or bool(recorder.proc)
        path = recorder.stop()
        if path and was:
            name = os.path.basename(path)
            items = [
                item for item in (getattr(self, '_recordings', None) or [])
                if item.get('path') != path
            ]
            items.insert(0, {'name': name, 'path': path})
            self._recordings = items[:30]
        self._refresh_record_button()
        win = getattr(self, '_recordings_win', None)
        if win is not None:
            try:
                win.refresh()
            except tk.TclError:
                pass
        if notify and path:
            messagebox.showinfo("Grabar", f"Guardado:\n{path}", parent=self.window)

    def _record_tip_text(self):
        recorder = getattr(self, '_stream_recorder', None)
        if recorder and recorder.is_recording():
            return 'Detener grabación'
        return 'Grabar'

    def _refresh_record_button(self):
        btn = getattr(self, '_record_btn', None)
        icons = getattr(self, '_control_icons', None) or {}
        if not btn:
            return
        recorder = getattr(self, '_stream_recorder', None)
        live = bool(recorder and recorder.is_recording())
        key = 'record_on' if live else 'record'
        style = 'IconRecord.TButton' if live else 'Icon.TButton'
        try:
            btn.configure(image=icons.get(key) or icons.get('record'), style=style)
        except tk.TclError:
            pass

    def _cancel_record_watch(self):
        job = getattr(self, '_record_watch_job', None)
        if job is None:
            return
        try:
            self.window.after_cancel(job)
        except (tk.TclError, ValueError, AttributeError):
            pass
        self._record_watch_job = None

    def _watch_recording(self):
        self._cancel_record_watch()
        recorder = getattr(self, '_stream_recorder', None)
        if recorder and recorder.proc is not None and recorder.proc.poll() is not None:
            self.stop_stream_recording(notify=False)
            return
        if recorder and recorder.is_recording() and self._widget_exists(self.window):
            try:
                self._record_watch_job = self.window.after(2000, self._watch_recording)
            except tk.TclError:
                self._record_watch_job = None

    def close(self):
        """Cierra la ventana y libera recursos."""
        self._clear_zap()
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
            self.save_iptv_resume()
            self.save_twitch_resume()
            self._save_window_geometry()
            app_config.set_volume(self.volume)
            self.save_favorites()
            self.stop_update_time()
            self._cancel_epg_jobs()
            self.stop_stream_recording(notify=False)
            close_pip = getattr(self, 'close_pip', None)
            if close_pip:
                close_pip()
            twitch = getattr(self, 'twitch_handler', None)
            if twitch:
                twitch.close_chat(notify_ui=False)
            self._load_gen = getattr(self, '_load_gen', 0) + 1
            self._clear_busy()

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

    def _embed_vlc_in_frame(self):
        """Enchufa VLC al frame y deja el clic para Tk (pausa sin OSD ni parpadeo)."""
        target = self._video_target_frame() if hasattr(self, '_video_target_frame') else self.video_frame
        if not self.player or not self._widget_exists(target):
            return
        try:
            self.player.video_set_mouse_input(False)
            self.player.video_set_key_input(False)
        except Exception:
            pass
        try:
            top = target.winfo_toplevel()
            if self._widget_exists(top):
                top.update_idletasks()
            elif self._widget_exists(self.window):
                self.window.update_idletasks()
            target.update_idletasks()
            wid = int(target.winfo_id())
        except (tk.TclError, TypeError, ValueError):
            return
        if not wid:
            return
        if sys.platform.startswith('win'):
            self.player.set_hwnd(wid)
        elif sys.platform == 'darwin':
            self.player.set_nsobject(wid)
        else:
            self.player.set_xwindow(wid)

    def _ensure_vlc_style_instance(self):
        """Recrea la instancia de VLC si cambió el estilo de subtítulos (freetype es de instancia)."""
        key = fingerprint()
        if (
            self.instance is not None
            and self.player is not None
            and getattr(self, '_vlc_style_key', None) == key
            and getattr(self, '_vlc_hw_decode_key', None) == app_config.iptv_use_hw_decode()
        ):
            return False
        self._cleanup_vlc_player()
        self.instance = _make_vlc_instance()
        self.player = self.instance.media_player_new()
        try:
            self.player.audio_set_volume(getattr(self, 'volume', 50))
        except Exception:
            pass
        self._vlc_style_key = key
        self._vlc_hw_decode_key = app_config.iptv_use_hw_decode()
        return True

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
        self._position_zap_osd()
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
        if not app_config.get_remember_last_list():
            return
        session = app_config.load().get('session') or {}
        if app_config.should_skip_session_restore(session):
            return
        playlist = session.get('playlist') or ''
        kind = session.get('playlist_kind') or ''
        sidebar = session.get('sidebar') or []
        items = []
        groups = []
        tvg_ids = []
        logos = []
        for entry in sidebar:
            if isinstance(entry, dict) and entry.get('url'):
                items.append((entry.get('name') or entry.get('url'), entry['url']))
                groups.append(entry.get('group') or '')
                tvg_ids.append(entry.get('tvg_id') or '')
                logos.append(entry.get('tvg_logo') or '')
        if kind == 'items' or (items and kind not in ('file', 'url')):
            self._apply_sidebar_items(items, groups, tvg_ids, logos)
            self._playlist_source = playlist
            self._playlist_kind = kind or 'items'
            self.restore_last_channel()
            self._start_epg(session.get('epg_urls') or [])
            return
        if not playlist:
            return
        if kind == 'youtube_playlist':
            if items:
                self._apply_sidebar_items(items, groups, tvg_ids, logos)
                self._playlist_source = playlist
                self._playlist_kind = 'youtube_playlist'
                self.restore_last_channel()
            else:
                self.load_youtube_playlist(playlist, notify=False, on_done=self.restore_last_channel)
            return
        if kind == 'url' or playlist.lower().startswith('http'):
            self.load_m3u_url(playlist, notify=False, on_done=self.restore_last_channel)
        elif os.path.isfile(playlist):
            self.load_m3u_file(playlist, notify=False, on_done=self.restore_last_channel)
        else:
            self.restore_last_channel()

    def _apply_sidebar_items(self, items, groups=None, tvg_ids=None, logos=None):
        self.channels = list(items)
        self.all_channels = list(items)
        if groups is None or len(groups) != len(items):
            self._groups = [''] * len(items)
        else:
            self._groups = list(groups)
        self._groups_all = list(self._groups)
        if tvg_ids is None or len(tvg_ids) != len(items):
            self._tvg_ids = [''] * len(items)
        else:
            self._tvg_ids = list(tvg_ids)
        self._tvg_ids_all = list(self._tvg_ids)
        if logos is None or len(logos) != len(items):
            self._logos = [''] * len(items)
        else:
            self._logos = list(logos)
        self._logos_all = list(self._logos)
        self._rebuild_sidebar()

    def _persist_sidebar(self):
        if not app_config.get_remember_last_list():
            return
        items = list(self.all_channels)
        source = self._playlist_source or ''
        kind = self._playlist_kind or ''
        if not items:
            app_config.clear_session_list()
            return
        if kind in ('file', 'url') and source:
            app_config.remember_playlist(source, kind)
            return
        session_max = app_config.light_mode_session_max() if app_config.get_light_mode() else 1500
        if len(items) > session_max:
            if source:
                app_config.remember_playlist(source, kind or 'file')
            return
        app_config.remember_sidebar(
            items, source, kind or 'items', self._groups_all, self._tvg_ids_all,
            epg_urls=self._epg_urls, logos=self._logos_all,
        )

    def restore_last_channel(self):
        if not app_config.get_remember_last_list():
            return
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
            self.sidebar.select(chosen)
            self.sidebar.see(chosen)
            self.current_channel = chosen
        except tk.TclError:
            pass

    def save_favorites(self):
        try:
            self.favorites = normalize_favorites(self.favorites)
            with open('favoritos.json', 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron guardar los favoritos: {e}")

    def load_favorites(self):
        try:
            with open('favoritos.json', 'r', encoding='utf-8') as f:
                self.favorites = normalize_favorites(json.load(f))
        except FileNotFoundError:
            self.favorites = []
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los favoritos: {e}")

    def _favorite_rows(self):
        rows = []
        groups = []
        tvg_ids = []
        logos = []
        for item in normalize_favorites(self.favorites):
            name, url = favorite_name(item), favorite_url(item)
            rows.append((name, url))
            groups.append('')
            tvg_ids.append(self._tvg_id_for_url(url) if hasattr(self, '_tvg_id_for_url') else '')
            logos.append(self._logo_for_url(url) if hasattr(self, '_logo_for_url') else '')
        return rows, groups, tvg_ids, logos

    def _refresh_favorite_marks(self):
        sidebar = getattr(self, 'sidebar', None)
        if sidebar:
            sidebar.refresh_rows()

    def _channel_is_favorite(self, index):
        if index is None or not (0 <= index < len(self.channels)):
            return False
        name, url = self.channels[index]
        return favorites_contain(self.favorites, name, url)

    def show_favorites(self):
        if not self.favorites:
            messagebox.showinfo("Favoritos", "Por el momento no hay favoritos añadidos.")
            return
        self._showing_favorites = True
        if getattr(self, 'search_var', None):
            try:
                if (self.search_var.get() or '').strip():
                    self._apply_channel_filter()
                    return
            except tk.TclError:
                pass
        self.channels, self._groups, self._tvg_ids, self._logos = self._favorite_rows()
        self._rebuild_sidebar()
        self._set_epg_label('')

    def restore_all_channels(self):
        self._showing_favorites = False
        self.channels = self.all_channels.copy()
        self._groups = list(self._groups_all)
        self._tvg_ids = list(self._tvg_ids_all) if len(self._tvg_ids_all) == len(self.all_channels) else [''] * len(self.all_channels)
        self._logos = list(self._logos_all) if len(getattr(self, '_logos_all', [])) == len(self.all_channels) else [''] * len(self.all_channels)
        if getattr(self, 'search_var', None):
            try:
                if (self.search_var.get() or '').strip():
                    self._apply_channel_filter()
                    return
            except tk.TclError:
                pass
        self._rebuild_sidebar()

    def prompt_url(self):
        self.ensure_window()
        url = ask_string(
            self.window,
            "Cargar URL",
            "Introduce la URL (lista M3U, YouTube o Twitch):",
        )
        if not url:
            return
        url = url.strip()
        if is_twitch_url(url):
            self.play_twitch_url(url)
            return
        if app_config._is_youtube_url(url):
            self.youtube_handler.prompt_youtube_url(url)
            return
        self.load_m3u_url(url)

    def prompt_file(self):
        filename = filedialog.askopenfilename(
            title="Selecciona un archivo M3U o M3U8",
            filetypes=[("Archivos M3U/M3U8", "*.m3u *.m3u8"), ("Todos los archivos", "*")],
            parent=self.window
        )
        if filename:
            self.load_m3u_file(filename)

    def prompt_epg_url(self):
        """Pide la URL HTTP de una guía XMLTV."""
        self.ensure_window()
        current = (self._epg_url_manual or app_config.get_epg_url() or '').strip()
        if current and not current.lower().startswith(('http://', 'https://')):
            current = ''
        url = ask_string(
            self.window,
            "Guía EPG",
            "URL de la guía XMLTV (http o https):",
            initialvalue=current,
        )
        if url is None:
            return
        url = (url or '').strip()
        if not url:
            return
        self._apply_manual_epg(url)

    def prompt_epg_file(self):
        """Elige un archivo XMLTV local como guía."""
        self.ensure_window()
        filename = filedialog.askopenfilename(
            title="Selecciona una guía XMLTV",
            filetypes=[
                ("XMLTV", "*.xml *.xml.gz *.gz"),
                ("Todos los archivos", "*"),
            ],
            parent=self.window,
        )
        if filename:
            self._apply_manual_epg(filename)

    def clear_manual_epg(self):
        self._apply_manual_epg('', notify=False)

    def _apply_manual_epg(self, value, notify=True):
        text = epg.normalize_epg_source(value)
        if text and not text.lower().startswith(('http://', 'https://', 'file://')) and not os.path.isfile(text):
            messagebox.showerror(
                "Guía EPG",
                "Indica una URL http(s) o un archivo XMLTV que exista.",
                parent=self.window,
            )
            return
        self._epg_url_manual = text
        app_config.set_epg_url(text)
        self._start_epg(notify=notify and bool(text))
        self._persist_sidebar()

    def _set_busy(self, text=None, percent=None):
        if not self._widget_exists(self.window):
            return
        caption = busy_status_text(text, percent)
        try:
            self.window.config(cursor='watch')
            self.window.title(f'Reproductor de vídeo - {caption}')
        except tk.TclError:
            pass
        self._show_busy_overlay(caption, percent)

    def _clear_busy(self):
        if not self._widget_exists(self.window):
            return
        try:
            self.window.config(cursor='')
            self.window.title('Reproductor de vídeo')
        except tk.TclError:
            pass
        self._hide_busy_overlay()

    def _hide_busy_overlay(self):
        bar = getattr(self, '_busy_bar', None)
        if bar is not None:
            try:
                bar.stop()
            except tk.TclError:
                pass
        self._busy_bar = None
        self._busy_label = None
        frame = getattr(self, '_busy_frame', None)
        self._busy_frame = None
        if frame is not None:
            try:
                frame.destroy()
            except tk.TclError:
                pass

    def _show_busy_overlay(self, text, percent=None):
        if not self._widget_exists(self.window):
            return
        parent = getattr(self, 'player_frame', None) or getattr(self, 'video_frame', None)
        video = getattr(self, 'video_frame', None)
        if not self._widget_exists(parent):
            return
        frame = getattr(self, '_busy_frame', None)
        if not self._widget_exists(frame):
            colors = get_colors()
            overlay = tk.Frame(parent, bg='#000000', highlightthickness=0)
            try:
                if self._widget_exists(video):
                    overlay.place(in_=video, relx=0, rely=0, relwidth=1, relheight=1)
                    overlay.lift(video)
                else:
                    overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            except tk.TclError:
                overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            card = tk.Frame(
                overlay,
                bg=colors['surface'],
                highlightbackground=colors['border'],
                highlightthickness=1,
                padx=22,
                pady=16,
            )
            card.place(relx=0.5, rely=0.5, anchor='center')
            label = tk.Label(
                card,
                text=text,
                font=get_font(12, 'bold'),
                bg=colors['surface'],
                fg=colors['text'],
            )
            label.pack(anchor=tk.W)
            hint = tk.Label(
                card,
                text='La lista se lee en segundo plano; la ventana no se ha colgado.',
                font=get_font(9),
                bg=colors['surface'],
                fg=colors['text_muted'],
            )
            hint.pack(anchor=tk.W, pady=(4, 10))
            bar = ttk.Progressbar(card, length=360, mode='indeterminate')
            bar.pack(fill=tk.X)
            self._busy_frame = overlay
            self._busy_label = label
            self._busy_bar = bar
            self._busy_indeterminate = True
            try:
                bar.start(12)
            except tk.TclError:
                pass
        else:
            label = getattr(self, '_busy_label', None)
            bar = getattr(self, '_busy_bar', None)
            if label is not None:
                try:
                    label.configure(text=text)
                except tk.TclError:
                    pass
        bar = getattr(self, '_busy_bar', None)
        if bar is None:
            return
        if percent is None:
            if not getattr(self, '_busy_indeterminate', False):
                try:
                    bar.stop()
                    bar.configure(mode='indeterminate')
                    bar.start(12)
                except tk.TclError:
                    pass
                self._busy_indeterminate = True
            return
        try:
            value = max(0.0, min(100.0, float(percent)))
        except (TypeError, ValueError):
            value = 0.0
        try:
            if getattr(self, '_busy_indeterminate', False):
                bar.stop()
                bar.configure(mode='determinate', maximum=100)
                self._busy_indeterminate = False
            bar['value'] = value
        except tk.TclError:
            pass

    def _report_load_progress(self, window, gen, text, percent=None):
        if gen != getattr(self, '_load_gen', 0):
            return

        def apply():
            if gen != getattr(self, '_load_gen', 0):
                return
            self._set_busy(text, percent=percent)

        self._after_window(window, apply)

    def _after_window(self, window, callback):
        try:
            window.after(0, callback)
        except tk.TclError:
            pass

    def load_m3u_file(self, filename, notify=True, on_done=None):
        """Carga un archivo M3U local en segundo plano y procesa sus canales."""
        self.ensure_window()
        gen = self._load_gen + 1
        self._load_gen = gen
        self._set_busy('Cargando lista…', percent=0)
        window = self.window

        def work():
            err = None
            parsed = None
            epg_urls = []
            try:
                with open(filename, 'rb') as f:
                    content = decode_m3u_bytes(f.read())
                self._report_load_progress(window, gen, 'Leyendo canales…', 8)

                def on_progress(frac):
                    self._report_load_progress(
                        window, gen, 'Leyendo canales…', 8 + frac * 82,
                    )

                parsed = parse_m3u_channels(content, on_progress=on_progress)
                epg_urls = parse_m3u_epg_urls(content)
            except Exception as exc:
                err = exc

            def apply():
                if gen != self._load_gen:
                    return
                if err:
                    self._clear_busy()
                    messagebox.showerror("Error", f"No se pudo cargar el archivo M3U: {err}")
                    return
                self._set_busy('Mostrando canales…', percent=95)
                try:
                    self.window.update_idletasks()
                except tk.TclError:
                    pass
                self._apply_parsed_channels(parsed, filename, 'file', notify, epg_urls=epg_urls)
                self._clear_busy()
                if on_done:
                    on_done()

            self._after_window(window, apply)

        threading.Thread(target=work, daemon=True).start()

    def load_m3u_url(self, url, notify=True, on_done=None):
        """Carga una lista M3U desde una URL en segundo plano."""
        self.ensure_window()
        gen = self._load_gen + 1
        self._load_gen = gen
        self._set_busy('Descargando lista…')
        window = self.window

        def work():
            err = None
            parsed = None
            epg_urls = []
            try:
                import urllib.request
                with urllib.request.urlopen(url) as response:
                    total = 0
                    try:
                        total = int(response.headers.get('Content-Length') or 0)
                    except (TypeError, ValueError):
                        total = 0
                    chunks = []
                    read = 0
                    last_pct = -1
                    while True:
                        if gen != getattr(self, '_load_gen', 0):
                            return
                        block = response.read(256 * 1024)
                        if not block:
                            break
                        chunks.append(block)
                        read += len(block)
                        if total > 0:
                            pct = min(40.0, (read / total) * 40.0)
                            if pct - last_pct >= 1:
                                last_pct = pct
                                self._report_load_progress(
                                    window, gen, 'Descargando lista…', pct,
                                )
                content = decode_m3u_bytes(b''.join(chunks))
                self._report_load_progress(window, gen, 'Leyendo canales…', 42)

                def on_progress(frac):
                    self._report_load_progress(
                        window, gen, 'Leyendo canales…', 42 + frac * 48,
                    )

                parsed = parse_m3u_channels(content, on_progress=on_progress)
                epg_urls = parse_m3u_epg_urls(content)
            except Exception as exc:
                err = exc

            def apply():
                if gen != self._load_gen:
                    return
                if err:
                    self._clear_busy()
                    messagebox.showerror("Error", f"No se pudo cargar la URL M3U: {err}")
                    return
                self._set_busy('Mostrando canales…', percent=95)
                try:
                    self.window.update_idletasks()
                except tk.TclError:
                    pass
                self._apply_parsed_channels(parsed, url, 'url', notify, epg_urls=epg_urls)
                self._clear_busy()
                if on_done:
                    on_done()

            self._after_window(window, apply)

        threading.Thread(target=work, daemon=True).start()

    def update_sidebar_title(self, url, title):
        updated = False
        for i, (name, item_url) in enumerate(self.channels):
            if item_url != url or name == title:
                continue
            self.channels[i] = (title, url)
            updated = True
            if getattr(self, 'sidebar', None):
                self.sidebar.set_item_name(i, title)
        for i, (name, item_url) in enumerate(self.all_channels):
            if item_url != url or name == title:
                continue
            self.all_channels[i] = (title, url)
            updated = True
        return updated

    def _rebuild_sidebar(self):
        sidebar = getattr(self, 'sidebar', None)
        if not sidebar or not self._widget_exists(self.channels_listbox):
            return
        if len(self._groups) != len(self.channels):
            self._groups = [''] * len(self.channels)
        sidebar.rebuild(self.channels, self._groups)

    def _fill_channel_listbox(self, names=None):
        self._rebuild_sidebar()

    def _process_m3u_content(self, content):
        """Procesa el contenido de un archivo M3U y carga los canales."""
        self._apply_parsed_channels(
            parse_m3u_channels(content),
            '',
            'file',
            notify=False,
            epg_urls=parse_m3u_epg_urls(content),
        )

    def _unpack_parsed_channels(self, parsed):
        channels = []
        groups = []
        tvg_ids = []
        logos = []
        for row in parsed or []:
            name = row[0] if row else ''
            url = row[1] if len(row) > 1 else ''
            group = row[2] if len(row) > 2 else ''
            tvg_id = row[3] if len(row) > 3 else ''
            logo = row[4] if len(row) > 4 else ''
            channels.append((name, url))
            groups.append(group or '')
            tvg_ids.append(tvg_id or '')
            logos.append(logo or '')
        return channels, groups, tvg_ids, logos

    def _apply_parsed_channels(self, parsed, source, kind, notify=True, epg_urls=None):
        self.ensure_window()
        channels, groups, tvg_ids, logos = self._unpack_parsed_channels(parsed)
        self.channels = channels
        self._groups = groups
        self._tvg_ids = tvg_ids
        self._logos = logos
        self.all_channels = list(self.channels)
        self._groups_all = list(self._groups)
        self._tvg_ids_all = list(self._tvg_ids)
        self._logos_all = list(self._logos)
        self._showing_favorites = False
        self._playlist_source = source
        self._playlist_kind = kind
        self._rebuild_sidebar()
        self._start_epg(epg_urls)
        self._persist_sidebar()
        self._clear_busy()
        if notify:
            messagebox.showinfo("Éxito", f"Lista M3U cargada correctamente: {len(self.channels)} canales encontrados")

    def _merged_epg_urls(self):
        urls = []
        seen = set()
        manual = (self._epg_url_manual or app_config.get_epg_url() or '').strip()
        self._epg_url_manual = manual
        for item in (manual, *(self._epg_urls_list or [])):
            item = (item or '').strip()
            if not item or item in seen:
                continue
            seen.add(item)
            urls.append(item)
        return urls[:3]

    def _start_epg(self, urls=None, notify=False):
        if urls is not None:
            self._epg_urls_list = [item for item in urls if item]
        self._epg_urls = self._merged_epg_urls()
        wanted_ids = [item for item in (self._tvg_ids_all or []) if item]
        wanted_names = [name for name, _url in (self.all_channels or self.channels or [])]
        if app_config.get_light_mode():
            sidebar = getattr(self, 'sidebar', None)
            visible = sidebar.current_indices() if sidebar else []
            if visible:
                wanted_ids = [
                    self._tvg_ids_all[i]
                    for i in visible
                    if 0 <= i < len(self._tvg_ids_all) and self._tvg_ids_all[i]
                ]
                wanted_names = [
                    self.channels[i][0]
                    for i in visible
                    if 0 <= i < len(self.channels)
                ]
        if not wanted_ids:
            wanted_ids = list(wanted_names)
        if not self._epg_urls or not (wanted_ids or wanted_names):
            self._epg = None
            self._set_epg_label('')
            self._refresh_sidebar_now()
            if notify and not (self.all_channels or self.channels):
                messagebox.showinfo(
                    "Guía EPG",
                    "No hay canales en la lista ahora. La URL se ha guardado y se aplicará al cargar un M3U.",
                    parent=self.window,
                )
            return
        self._epg_gen += 1
        gen = self._epg_gen
        window = self.window
        sources = list(self._epg_urls)
        self._set_epg_label(plain_ui_line('Cargando guía...'))

        def work():
            try:
                guide = epg.load_guide(sources, wanted_ids, wanted_names=wanted_names)
            except Exception:
                guide = epg.Guide()

            def apply():
                if gen != self._epg_gen:
                    return
                self._epg = guide
                self._listbox_tip_index = None
                index = self._selected_channel_index()
                if index is None:
                    index = self.current_channel
                if index is not None:
                    self._refresh_epg_label(index)
                else:
                    self._set_epg_label('')
                self._refresh_sidebar_now()
                self._prefetch_visible_logos()
                grid = getattr(self, '_epg_grid', None)
                if grid is not None:
                    grid.refresh()
                self._schedule_epg_reload()
                self._schedule_epg_tick()
                if notify and not guide.channel_count():
                    messagebox.showinfo(
                        "Guía EPG",
                        "Se guardó la guía, pero no coincidió con esta lista. Se prueba tvg-id, tvg-name y el nombre del canal frente al XMLTV.",
                        parent=self.window,
                    )

            self._after_window(window, apply)

        threading.Thread(target=work, daemon=True).start()

    def _epg_text_for_index(self, index):
        if not self._epg:
            return ''
        current, nxt = self._epg.now_next(self._epg_key(index))
        return epg.format_now_next(current, nxt)

    def _set_epg_label(self, text):
        label = getattr(self, '_epg_label', None)
        if not self._widget_exists(label):
            return
        if app_config.get_light_mode():
            try:
                label.pack_forget()
            except tk.TclError:
                pass
            return
        text = (text or '').strip()
        try:
            label.configure(text=text)
        except tk.TclError:
            return
        sidebar = getattr(self, 'sidebar', None)
        before = getattr(sidebar, 'outer', None) if sidebar else None
        if text:
            try:
                if before and self._widget_exists(before):
                    label.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6), before=before)
                elif not label.winfo_ismapped():
                    label.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 6))
            except tk.TclError:
                pass
        else:
            try:
                label.pack_forget()
            except tk.TclError:
                pass

    def _refresh_epg_label(self, index):
        self._set_epg_label(self._epg_text_for_index(index))

    def _on_sidebar_select_epg(self, event=None):
        sidebar = getattr(self, 'sidebar', None)
        if sidebar and sidebar.ignore_play():
            return
        index = self._selected_channel_index()
        self._refresh_epg_label(index)

    def _tvg_id_for_url(self, url):
        for i, (_name, item_url) in enumerate(self.all_channels):
            if item_url != url:
                continue
            if i < len(self._tvg_ids_all):
                return self._tvg_ids_all[i]
            return ''
        return ''

    def _logo_for_url(self, url):
        for i, (_name, item_url) in enumerate(self.all_channels):
            if item_url != url:
                continue
            if i < len(getattr(self, '_logos_all', [])):
                return self._logos_all[i]
            return ''
        return ''

    def _epg_key(self, index):
        if index is None:
            return ''
        if 0 <= index < len(getattr(self, '_tvg_ids', [])):
            tvg = (self._tvg_ids[index] or '').strip()
            if tvg:
                return tvg
        if 0 <= index < len(self.channels):
            return (self.channels[index][0] or '').strip()
        return ''

    def _epg_now_title(self, index):
        guide = getattr(self, '_epg', None)
        if not guide:
            return ''
        return guide.now_title(self._epg_key(index))

    def _logo_url(self, index):
        if index is None:
            return ''
        if 0 <= index < len(self._logos) and self._logos[index]:
            return self._logos[index]
        if self._epg:
            return self._epg.icon(self._epg_key(index))
        return ''

    def _logo_photo(self, index):
        if not self.channel_logos_enabled():
            return None
        url = self._logo_url(index)
        if not url:
            return None
        photos = getattr(self, '_logo_photos', None)
        if photos is None:
            photos = {}
            self._logo_photos = photos
        return logo_cache.load_photo(url, photos)

    def channel_logos_enabled(self):
        if app_config.get_light_mode():
            return False
        return bool(getattr(self, '_show_logos', True))

    def _on_logos_menu_toggle(self):
        var = getattr(self, '_logos_var', None)
        enabled = bool(var.get()) if var is not None else True
        app_config.set_show_channel_logos(enabled)
        self._apply_logo_pref(enabled)

    def _apply_logo_pref(self, enabled=None):
        if enabled is None:
            enabled = app_config.effective_show_channel_logos()
        else:
            enabled = bool(enabled) and not app_config.get_light_mode()
        self._show_logos = bool(enabled)
        var = getattr(self, '_logos_var', None)
        if var is not None:
            try:
                var.set(self._show_logos)
            except tk.TclError:
                pass
        if self._show_logos:
            self._prefetch_visible_logos()
        self._refresh_sidebar_now()

    def _on_sidebar_view_change(self):
        self._prefetch_visible_logos()
        if app_config.get_light_mode() and self._epg_urls:
            self._start_epg(notify=False)

    def _prefetch_visible_logos(self):
        if not self.channel_logos_enabled():
            return
        sidebar = getattr(self, 'sidebar', None)
        indices = sidebar.current_indices() if sidebar else list(range(min(80, len(self.channels))))
        urls = []
        for index in indices[:80]:
            url = self._logo_url(index)
            if url:
                urls.append(url)
        if not urls:
            return
        window = self.window

        def done():
            if not self.channel_logos_enabled():
                return
            if self._widget_exists(window):
                window.after(0, self._schedule_logo_refresh)

        logo_cache.fetch_many(urls, on_done=done)

    def _schedule_logo_refresh(self):
        job = getattr(self, '_logo_refresh_job', None)
        if job and self._widget_exists(self.window):
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass
        if not self._widget_exists(self.window):
            return
        self._logo_refresh_job = self.window.after(120, self._flush_logo_refresh)

    def _flush_logo_refresh(self):
        self._logo_refresh_job = None
        self._refresh_sidebar_now()

    def _refresh_sidebar_now(self):
        sidebar = getattr(self, 'sidebar', None)
        if sidebar:
            sidebar.refresh_rows()
        grid = getattr(self, '_epg_grid', None)
        if grid is not None:
            try:
                grid.refresh()
            except tk.TclError:
                pass

    def _cancel_epg_jobs(self):
        for attr in ('_epg_reload_job', '_epg_tick_job', '_logo_refresh_job'):
            job = getattr(self, attr, None)
            setattr(self, attr, None)
            if job and self._widget_exists(self.window):
                try:
                    self.window.after_cancel(job)
                except tk.TclError:
                    pass

    def _schedule_epg_reload(self):
        job = getattr(self, '_epg_reload_job', None)
        if job and self._widget_exists(self.window):
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass
        if not self._widget_exists(self.window):
            return
        interval = app_config.epg_reload_interval_ms()
        if interval <= 0:
            self._epg_reload_job = None
            return
        self._epg_reload_job = self.window.after(interval, lambda: self._start_epg(notify=False))

    def _schedule_epg_tick(self):
        job = getattr(self, '_epg_tick_job', None)
        if job and self._widget_exists(self.window):
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass
        if not self._widget_exists(self.window):
            return
        self._epg_tick_job = self.window.after(
            app_config.epg_tick_interval_ms(),
            self._tick_epg,
        )

    def _tick_epg(self):
        self._epg_tick_job = None
        if not self._widget_exists(self.window):
            return
        index = self._selected_channel_index()
        if index is None:
            index = self.current_channel
        if index is not None:
            self._refresh_epg_label(index)
        self._refresh_sidebar_now()
        self._schedule_epg_tick()

    def open_epg_grid(self):
        show_epg_grid(self)
        self._prefetch_visible_logos()

    def open_iptv_history(self):
        show_iptv_history(self)

    def _refresh_history_ui(self):
        win = getattr(self, '_iptv_history', None)
        if win is not None:
            try:
                win.refresh()
            except tk.TclError:
                pass
        self._fill_twitch_recent_menu()

    def _fill_twitch_recent_menu(self):
        menu = getattr(self, '_twitch_recent_menu', None)
        if menu is None:
            return
        try:
            menu.delete(0, 'end')
        except tk.TclError:
            return
        items = app_config.twitch_history()
        if not items:
            menu.add_command(label="Sin recientes", state='disabled')
            return
        for item in items[:12]:
            url = item['url']
            name = item.get('name') or 'Twitch'
            menu.add_command(
                label=app_config.twitch_history_label(
                    item,
                    with_time=bool(item.get('s') and item.get('kind') == 'vod'),
                ),
                command=lambda u=url, n=name: self.play_twitch_url(u, title=n, add_to_list=False),
            )
        menu.add_separator()
        menu.add_command(
            label=plain_ui_line("Vaciar recientes de Twitch"),
            command=self.clear_twitch_history_prompt,
        )

    def clear_twitch_history_prompt(self):
        if not app_config.twitch_history():
            return
        if not messagebox.askyesno(
            'Twitch',
            '¿Quitar el historial reciente de Twitch?',
            parent=self.window,
        ):
            return
        app_config.clear_twitch_history()
        self._refresh_history_ui()

    def _fill_history_menu(self):
        menu = getattr(self, '_history_menu', None)
        if menu is None:
            return
        try:
            menu.delete(0, 'end')
        except tk.TclError:
            return
        watching = app_config.iptv_continue_watching()
        recent = app_config.iptv_history()
        yt_watching = app_config.youtube_continue_watching()
        yt_recent = app_config.youtube_history()
        tw_watching = app_config.twitch_continue_watching()
        tw_recent = app_config.twitch_history()
        menu.add_command(label=plain_ui_line("Ver historial…"), command=self.open_iptv_history)
        if watching:
            menu.add_separator()
            menu.add_command(label="Seguir viendo", state='disabled')
            for item in watching[:8]:
                url = item['url']
                menu.add_command(
                    label=app_config.iptv_history_label(item, with_time=True),
                    command=lambda u=url: self.play_history_url(u),
                )
        if yt_watching:
            menu.add_separator()
            menu.add_command(label="YouTube a medio ver", state='disabled')
            for item in yt_watching[:8]:
                url = item['url']
                name = item.get('name') or 'YouTube'
                menu.add_command(
                    label=app_config.youtube_history_label(item, with_time=True),
                    command=lambda u=url, n=name: self.play_youtube_url(u, title=n, add_to_list=False),
                )
        if tw_watching:
            menu.add_separator()
            menu.add_command(label="Twitch a medio ver", state='disabled')
            for item in tw_watching[:8]:
                url = item['url']
                name = item.get('name') or 'Twitch'
                menu.add_command(
                    label=app_config.twitch_history_label(item, with_time=True),
                    command=lambda u=url, n=name: self.play_twitch_url(u, title=n, add_to_list=False),
                )
        menu.add_separator()
        if not recent and not yt_recent and not tw_recent:
            menu.add_command(label="Sin recientes", state='disabled')
        else:
            for item in recent[:10]:
                url = item['url']
                vod = item.get('kind') == 'vod'
                menu.add_command(
                    label=app_config.iptv_history_label(item, with_time=vod),
                    command=lambda u=url: self.play_history_url(u),
                )
            if recent and yt_recent:
                menu.add_separator()
            if yt_recent:
                menu.add_command(label="YouTube recientes", state='disabled')
            for item in yt_recent[:10]:
                url = item['url']
                name = item.get('name') or 'YouTube'
                menu.add_command(
                    label=app_config.youtube_history_label(item, with_time=True),
                    command=lambda u=url, n=name: self.play_youtube_url(u, title=n, add_to_list=False),
                )
            if tw_recent:
                menu.add_separator()
                menu.add_command(label="Twitch recientes", state='disabled')
            for item in tw_recent[:10]:
                url = item['url']
                name = item.get('name') or 'Twitch'
                menu.add_command(
                    label=app_config.twitch_history_label(
                        item,
                        with_time=bool(item.get('s') and item.get('kind') == 'vod'),
                    ),
                    command=lambda u=url, n=name: self.play_twitch_url(u, title=n, add_to_list=False),
                )
        menu.add_separator()
        menu.add_command(label="Vaciar historial", command=self.clear_iptv_history_prompt)

    def clear_iptv_history_prompt(self):
        if not app_config.iptv_history() and not app_config.youtube_history() and not app_config.twitch_history():
            return
        if not messagebox.askyesno(
            'Vaciar historial',
            '¿Quitar el historial de IPTV, YouTube y Twitch?',
            parent=self.window,
        ):
            return
        app_config.clear_iptv_history()
        app_config.clear_youtube_history()
        app_config.clear_twitch_history()
        self._refresh_history_ui()

    def play_history_url(self, url):
        url = (url or '').strip()
        if not url:
            return
        if app_config._is_youtube_url(url):
            item = app_config.youtube_history_item_by_url(url) or {}
            self.play_youtube_url(url, title=item.get('name') or 'YouTube', add_to_list=False)
            self._refresh_history_ui()
            return
        if is_twitch_url(url):
            item = app_config.twitch_history_item_by_url(url) or {}
            self.play_twitch_url(url, title=item.get('name') or 'Twitch', add_to_list=False)
            self._refresh_history_ui()
            return
        for index, (_name, item_url) in enumerate(self.channels):
            if item_url != url:
                continue
            sidebar = getattr(self, 'sidebar', None)
            if sidebar:
                try:
                    sidebar.select(index)
                    sidebar.see(index)
                except tk.TclError:
                    pass
            self.play_channel(index)
            return
        item = app_config.iptv_history_item(url) or {}
        name = item.get('name') or 'Historial'
        self.save_youtube_resume()
        self.save_iptv_resume()
        self.save_twitch_resume()
        self.current_channel = None
        app_config.remember_iptv_history(name, url, group=item.get('group') or '')
        self._ensure_vlc_style_instance()
        if self.instance is None:
            self.instance = _make_vlc_instance()
            self._vlc_style_key = fingerprint()
        self.clear_youtube_subtitles()
        self._reset_vlc_tracks()
        self._hide_channel_status()
        self._cleanup_vlc_player()
        self.player = self.instance.media_player_new()
        try:
            self.player.audio_set_volume(self.volume)
        except Exception:
            pass
        self.show_controls_and_menu()
        self._iptv_resume_s = app_config.iptv_resume_seconds(url)
        try:
            self._play_iptv_url(name, url)
        except Exception:
            self._show_channel_unavailable(name)
        self._refresh_history_ui()

    def _on_epg_grid_key(self, event=None):
        if self._event_in_text_field(event):
            return
        self.open_epg_grid()
        return 'break'

    def _epg_grid_rows(self):
        sidebar = getattr(self, 'sidebar', None)
        if sidebar and getattr(sidebar, 'mode', '') == 'catalog':
            return []
        indices = sidebar.current_indices() if sidebar else []
        if not indices:
            indices = list(range(min(80, len(self.channels))))
        rows = []
        for index in indices[:80]:
            if not (0 <= index < len(self.channels)):
                continue
            name = self.channels[index][0]
            tvg_id = self._epg_key(index)
            rows.append((index, name, tvg_id, self._logo_url(index)))
        return rows

    def prompt_youtube_playlist(self):
        """Solicita URL de playlist de YouTube y la carga."""
        playlist_url = ask_string(
            self.window,
            "Cargar Playlist de YouTube",
            "Introduce la URL de la playlist de YouTube:",
        )
        if playlist_url:
            self.load_youtube_playlist(playlist_url)

    def load_youtube_playlist(self, playlist_url, notify=True, on_done=None):
        """Extrae la playlist de YouTube en segundo plano y la muestra en la lista."""
        self.ensure_window()
        gen = self._load_gen + 1
        self._load_gen = gen
        self._set_busy('Extrayendo playlist…')
        window = self.window

        def work():
            err = None
            parsed = []
            try:
                ydl_opts = youtube_ydl_opts(
                    extract_flat=True,
                    skip_download=True,
                    force_generic_extractor=False,
                    noplaylist=False,
                )
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(playlist_url, download=False)
                    videos = info.get('entries', []) or []
                for video in videos:
                    if not video or not video.get('id'):
                        continue
                    title = video.get('title', 'Sin título')
                    parsed.append((title, f"https://www.youtube.com/watch?v={video.get('id')}"))
            except Exception as exc:
                err = exc

            def apply():
                if gen != self._load_gen:
                    return
                if err:
                    self._clear_busy()
                    messagebox.showerror("Error", f"No se pudo cargar la playlist: {err}")
                    return
                if not parsed:
                    self._clear_busy()
                    messagebox.showinfo("Info", "No se encontraron vídeos en la playlist.")
                    return
                self._set_busy('Mostrando lista…')
                try:
                    self.window.update_idletasks()
                except tk.TclError:
                    pass
                self.channels = parsed
                self.all_channels = list(parsed)
                self._showing_favorites = False
                self._groups = [''] * len(parsed)
                self._groups_all = list(self._groups)
                self._tvg_ids = [''] * len(parsed)
                self._tvg_ids_all = list(self._tvg_ids)
                self._logos = [''] * len(parsed)
                self._logos_all = list(self._logos)
                self._epg = None
                self._epg_urls = []
                self._epg_urls_list = []
                self._set_epg_label('')
                self._playlist_source = playlist_url
                self._playlist_kind = 'youtube_playlist'
                self._rebuild_sidebar()
                self._persist_sidebar()
                self._clear_busy()
                if notify:
                    messagebox.showinfo("Éxito", f"Playlist cargada: {len(parsed)} vídeos")
                if on_done:
                    on_done()

            self._after_window(window, apply)

        threading.Thread(target=work, daemon=True).start()

    def play_selected(self, event=None):
        """Reproduce el canal seleccionado de la lista al hacer doble clic."""
        index = None
        if event is not None and getattr(self, 'sidebar', None):
            if self.sidebar.ignore_play():
                return
            if self.sidebar.group_at(event):
                return
            index = self.sidebar.index_at(event)
        if index is None and getattr(self, 'sidebar', None):
            index = self.sidebar.selected_index()
        if index is not None:
            self._refresh_epg_label(index)
            self.play_channel(index)
            
    def play_channel(self, index):
        if 0 <= index < len(self.channels):
            if (
                self.current_channel is not None
                and self.current_channel != index
                and 0 <= self.current_channel < len(self.channels)
            ):
                self._previous_channel_index = self.current_channel
            name, url = self.channels[index]
            if is_youtube_channel_url(url):
                self.current_channel = index
                app_config.remember_channel(index, name, url)
                self.play_youtube_channel(url, title=name)
                return
            if is_youtube_playlist_url(url):
                self.current_channel = index
                app_config.remember_channel(index, name, url)
                self.load_youtube_playlist(url, notify=False, on_done=lambda: self.play_channel(0))
                return
            self.save_youtube_resume()
            self.save_iptv_resume()
            self.save_twitch_resume()
            self.current_channel = index
            self._refresh_epg_label(index)
            app_config.remember_channel(index, name, url)
            group = self._groups[index] if index < len(getattr(self, '_groups', [])) else ''
            app_config.remember_iptv_history(name, url, group=group)
            self._refresh_history_ui()
            self._ensure_vlc_style_instance()
            if self.instance is None:
                self.instance = _make_vlc_instance()
                self._vlc_style_key = fingerprint()
            self.clear_youtube_subtitles()
            self._reset_vlc_tracks()
            self._hide_channel_status()
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
            self._iptv_resume_s = 0
            if "youtube.com" in url or "youtu.be" in url:
                self._playing_youtube = True
                self._playing_twitch = False
                kind = getattr(self, '_playlist_kind', '') or ''
                self._yt_standalone = not (
                    self.is_sequential_playback
                    or kind in ('youtube_playlist', 'youtube_channel')
                )
                self.youtube_handler.play_youtube_url(
                    url, 
                    force_pulse=True, 
                    show_progress=True,
                    is_sequential=self.is_sequential_playback,
                    title=name,
                )
                return
            if is_twitch_url(url):
                self.current_channel = index
                self._refresh_epg_label(index)
                app_config.remember_channel(index, name, url)
                self.play_twitch_url(url, title=name, add_to_list=False)
                return
            self._iptv_resume_s = app_config.iptv_resume_seconds(url)
            try:
                self._play_iptv_url(name, url)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                self._show_channel_unavailable(name)

    def play_video_url(self, url, force_pulse=False, show_progress=False, is_sequential=False, http_headers=None, on_fail=None, fail_after_s=8, local_file=False, duration_s=None, subtitle_path=None, start_s=0):
        try:
            self._hide_channel_status()
            self._media_started = False
            self._yt_end_handled = True
            self._ensure_vlc_style_instance()
            for widget in self.video_frame.winfo_children():
                widget.destroy()
            if self.player is None:
                self.player = self.instance.media_player_new()
            if self.player.is_playing():
                self.player.stop()
            self._media_end_gen = getattr(self, '_media_end_gen', 0) + 1
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
            self._yt_resume_s = start_s if start_s >= 0.5 else 0
            if local_file and '127.0.0.1' in str(url):
                self._yt_resume_s = 0
            if self._yt_resume_s:
                self._set_progress_ui(int(self._yt_resume_s * 1000))
            elif local_file:
                offset = int(getattr(self, '_yt_start_offset_ms', 0) or 0)
                if offset:
                    self._set_progress_ui(offset)
            
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
                ':audio-resampler=soxr',
                ':codec=avcodec',
            ]
            if not app_config.iptv_use_hw_decode():
                options.insert(5, ':avcodec-hw=none')
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
            aout = vlc_aout_option(force_pulse=force_pulse)
            if aout:
                options.append(aout)
                print(f"[AUDIO] Salida de audio: {aout}")
            if subtitle_path and os.path.isfile(subtitle_path):
                options.append(f':sub-file={subtitle_path}')
                print(f"[VLC] sub-file={subtitle_path}")
            if self._yt_resume_s:
                options.append(f':start-time={self._yt_resume_s:.1f}')
                print(f"[VLC] start-time={self._yt_resume_s:.1f}s")
            options.extend(vlc_media_options())
            for option in options:
                media.add_option(option)
            self.player.set_media(media)
            self._embed_vlc_in_frame()
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

    def save_twitch_resume(self):
        if not getattr(self, '_playing_twitch', False):
            return
        handler = getattr(self, 'twitch_handler', None)
        url = getattr(handler, '_current_url', '') if handler else ''
        if not url or not is_twitch_vod_url(url):
            return
        stream = getattr(handler, '_current_stream', None) or {}
        if stream.get('is_live'):
            return
        elapsed_ms = self._playback_elapsed_ms()
        duration_ms = self._media_length_ms()
        duration_s = (duration_ms / 1000.0) if duration_ms else stream.get('duration')
        app_config.update_twitch_position(url, elapsed_ms / 1000.0, duration_s)
        self._last_twitch_resume_save = time.time()

    def clear_twitch_resume(self):
        handler = getattr(self, 'twitch_handler', None)
        url = getattr(handler, '_current_url', '') if handler else ''
        if url and is_twitch_vod_url(url):
            app_config.clear_twitch_position(url)

    def _on_twitch_vod_ended(self):
        if getattr(self, '_tw_end_handled', False):
            return
        self._tw_end_handled = True
        self.clear_twitch_resume()

    def save_youtube_resume(self):
        if not getattr(self, '_playing_youtube', False):
            return
        video_id = self._current_youtube_id()
        if not video_id:
            return
        handler = getattr(self, 'youtube_handler', None)
        elapsed_ms = self._playback_elapsed_ms()
        duration_ms = self._media_length_ms()
        app_config.remember_youtube_position(
            video_id,
            elapsed_ms / 1000.0,
            (duration_ms / 1000.0) if duration_ms else None,
            title=getattr(handler, '_loading_title_text', None) if handler else None,
            url=getattr(handler, '_current_url', None) if handler else None,
        )
        self._last_yt_resume_save = time.time()

    def save_iptv_resume(self):
        if getattr(self, '_playing_youtube', False):
            return
        url = (getattr(self, '_iptv_source_url', '') or '').strip()
        if not url:
            return
        pending = float(getattr(self, '_iptv_resume_s', 0) or 0)
        elapsed_ms = self._playback_elapsed_ms()
        if pending and elapsed_ms < pending * 1000 - 2000:
            return
        duration_ms = self._media_length_ms()
        app_config.update_iptv_position(
            url,
            elapsed_ms / 1000.0,
            (duration_ms / 1000.0) if duration_ms else None,
        )
        self._last_iptv_resume_save = time.time()

    def _apply_pending_iptv_resume(self, tries=0):
        pending = float(getattr(self, '_iptv_resume_s', 0) or 0)
        if pending < 0.5 or getattr(self, '_playing_youtube', False):
            return
        if not self._widget_exists(self.window):
            return
        if not self._iptv_has_real_media() and tries < 20:
            self.window.after(400, lambda: self._apply_pending_iptv_resume(tries + 1))
            return
        self._iptv_resume_s = 0
        self._apply_seek(int(pending * 1000))

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
                if getattr(self, '_iptv_failed', False):
                    pass
                elif (
                    state == vlc.State.Error
                    and not getattr(self, '_playing_youtube', False)
                    and not self._widget_exists(getattr(self, '_iptv_notice_top', None))
                    and not self._widget_exists(getattr(self, '_iptv_status_frame', None))
                ):
                    name = ''
                    if self.current_channel is not None and 0 <= self.current_channel < len(self.channels):
                        name = self.channels[self.current_channel][0]
                    self._show_channel_unavailable(name)
                elif state == vlc.State.Playing:
                    if (
                        getattr(self, '_playing_youtube', False)
                        or getattr(self, '_playing_twitch', False)
                        or self._iptv_has_real_media()
                    ):
                        started = getattr(self, '_media_started', False)
                        self._media_started = True
                        if started is False:
                            self._yt_end_handled = False
                            self._tw_end_handled = False
                        if not started and not getattr(self, '_playing_youtube', False):
                            self._apply_pending_iptv_resume()
                elif (
                    state == vlc.State.Ended
                    and getattr(self, '_playing_youtube', False)
                    and getattr(self, '_media_started', False)
                    and not getattr(self, '_yt_end_handled', False)
                ):
                    self._on_media_ended(getattr(self, '_media_end_gen', 0))
                elif (
                    state == vlc.State.Ended
                    and getattr(self, '_playing_twitch', False)
                    and self.progress_frame.winfo_ismapped()
                    and not getattr(self, '_tw_end_handled', False)
                ):
                    self._on_twitch_vod_ended()
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
                    now = time.time()
                    if active and now - getattr(self, '_last_yt_resume_save', 0) >= 20:
                        self.save_youtube_resume()
                    if active and now - getattr(self, '_last_iptv_resume_save', 0) >= 20:
                        self.save_iptv_resume()
                    if active and now - getattr(self, '_last_twitch_resume_save', 0) >= 20:
                        self.save_twitch_resume()
        except Exception as e:
            print(f"Error actualizando tiempo: {e}")
        self.update_time_job = self.window.after(250, self.update_time)

    def adjust_video_settings(self):
        """Ajusta la configuración del video para optimizar la reproducción"""
        if self.player:
            # Cambiamos True por una cadena vacía "" para desactivar o "yadif" para activar
            self.player.video_set_deinterlace("") 
            self.player.audio_set_volume(self.volume)
            apply_spu_delay(self.player)

    def filter_channels(self, *args):
        if not self._widget_exists(getattr(self, 'channels_listbox', None)):
            return
        job = getattr(self, '_filter_job', None)
        if job:
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass
        self._filter_job = self.window.after(80, self._apply_channel_filter)

    def _apply_channel_filter(self):
        self._filter_job = None
        if not self._widget_exists(getattr(self, 'channels_listbox', None)):
            return
        search_term = ''
        if getattr(self, 'search_var', None):
            try:
                search_term = (self.search_var.get() or '').strip().lower()
            except tk.TclError:
                search_term = ''
        gen = self._filter_gen + 1
        self._filter_gen = gen
        if getattr(self, '_showing_favorites', False):
            snapshot, groups_all, tvg_all, logos_all = self._favorite_rows()
        else:
            snapshot = list(self.all_channels)
            groups_all = self._groups_all if len(self._groups_all) == len(self.all_channels) else [''] * len(self.all_channels)
            tvg_all = self._tvg_ids_all if len(self._tvg_ids_all) == len(self.all_channels) else [''] * len(self.all_channels)
            logos_all = self._logos_all if len(getattr(self, '_logos_all', [])) == len(self.all_channels) else [''] * len(self.all_channels)
        if not search_term:
            self.channels = list(snapshot)
            self._groups = list(groups_all)
            self._tvg_ids = list(tvg_all)
            self._logos = list(logos_all)
            self._rebuild_sidebar()
            return
        groups_snap = groups_all
        tvg_snap = tvg_all
        logos_snap = logos_all

        def finish(filtered, filtered_groups, filtered_tvg, filtered_logos):
            if gen != self._filter_gen:
                return
            if not self._widget_exists(getattr(self, 'channels_listbox', None)):
                return
            self.channels = filtered
            self._groups = filtered_groups
            self._tvg_ids = filtered_tvg
            self._logos = filtered_logos
            self._rebuild_sidebar()

        def scan():
            filtered = []
            filtered_groups = []
            filtered_tvg = []
            filtered_logos = []
            for (name, url), group, tvg_id, logo in zip(snapshot, groups_snap, tvg_snap, logos_snap):
                if search_term in (name or '').lower() or search_term in (group or '').lower():
                    filtered.append((name, url))
                    filtered_groups.append(group)
                    filtered_tvg.append(tvg_id)
                    filtered_logos.append(logo)
            return filtered, filtered_groups, filtered_tvg, filtered_logos

        if len(snapshot) < 800:
            finish(*scan())
            return

        window = self.window

        def work():
            result = scan()
            self._after_window(window, lambda: finish(*result))

        threading.Thread(target=work, daemon=True).start()

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
        if not self.is_alive():
            self.ensure_window()
        url = (url or '').strip()
        if not url:
            return 0
        existing = {item_url for _name, item_url in self.all_channels}
        if url in existing:
            return 0
        if is_twitch_url(url):
            group = 'Twitch'
            title = twitch_default_title(url, name)
        else:
            group = 'YouTube'
            title = (name or '').strip() or 'YouTube'
        self.all_channels.append((title, url))
        self._groups_all.append(group)
        self._tvg_ids_all.append('')
        self._logos_all.append('')
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
            self.channels.append((title, url))
            self._groups.append(group)
            self._tvg_ids.append('')
            self._logos.append('')
            self._rebuild_sidebar()
            if getattr(self, 'sidebar', None):
                self.sidebar.see(len(self.channels) - 1)
        self._persist_sidebar()
        return 1

    def enqueue_youtube_items(self, items):
        """Añade vídeos a la cola de YouTube, no a la lista IPTV."""
        return self.enqueue_youtube_queue(items)

    def enqueue_youtube_queue(self, items):
        added = app_config.enqueue_youtube_queue(items)
        if not added:
            return added
        existing = getattr(self, '_youtube_queue_win', None)
        if existing is not None:
            try:
                if existing.window.winfo_exists():
                    existing.refresh()
                    return added
            except tk.TclError:
                pass
        self.open_youtube_queue()
        return added

    def open_youtube_queue(self):
        if not self.is_alive():
            self.ensure_window()
        show_youtube_queue(self)

    def _refresh_queue_ui(self):
        win = getattr(self, '_youtube_queue_win', None)
        if win is not None:
            try:
                win.refresh()
            except tk.TclError:
                pass

    def play_youtube_queue_index(self, index):
        item = app_config.pop_youtube_queue(index)
        self._refresh_queue_ui()
        if not item:
            return
        self.play_youtube_url(
            item.get('url') or '',
            title=item.get('name'),
            add_to_list=False,
            standalone=False,
        )

    def play_youtube_queue_next(self):
        self.play_youtube_queue_index(0)

    def play_youtube_channel(self, url, title=None):
        """Un favorito de canal no es un vídeo: carga las subidas recientes y reproduce la primera."""
        if getattr(self, '_loading_yt_channel', False):
            return
        self.ensure_window()
        self._loading_yt_channel = True
        label = (title or '').strip() or 'canal'
        self._set_busy(f'Cargando vídeos de {plain_ui_line(label, "canal")}...')
        window = self.window

        def work():
            err = None
            videos = []
            channel_name = label
            try:
                videos, channel_name = fetch_youtube_channel_videos(url, limit=30)
                channel_name = channel_name or label
            except Exception as exc:
                err = exc

            def apply():
                self._loading_yt_channel = False
                if err:
                    self._clear_busy()
                    messagebox.showerror(
                        "YouTube",
                        f"No se pudieron leer los vídeos recientes de {label}.",
                    )
                    return
                if not videos:
                    self._clear_busy()
                    messagebox.showinfo(
                        "YouTube",
                        f"No se encontraron vídeos recientes de {label}.",
                    )
                    return
                self._set_busy('Mostrando lista…')
                try:
                    self.window.update_idletasks()
                except tk.TclError:
                    pass
                items = [(item['title'], item['url']) for item in videos]
                self._playlist_source = url
                self._playlist_kind = 'youtube_channel'
                self.cargar_videos_playlist(items)
                self._clear_busy()
                if items:
                    self.play_channel(0)

            self._after_window(window, apply)

        threading.Thread(target=work, daemon=True).start()

    def play_youtube_url(self, url, title=None, add_to_list=True, standalone=True):
        """Delega la reproducción de YouTube al manejador y añade el vídeo a la lista si falta."""
        if is_youtube_channel_url(url):
            self.play_youtube_channel(url, title=title)
            return
        if is_youtube_playlist_url(url):
            self.load_youtube_playlist(url, notify=False, on_done=lambda: self.play_channel(0))
            return
        if add_to_list:
            existing = next((name for name, item_url in self.all_channels if item_url == url), None)
            if existing and existing not in ('YouTube', url):
                title = title or existing
            elif not existing:
                self.add_channel_to_list(title or 'YouTube', url)
        self._playing_youtube = True
        self._yt_standalone = bool(standalone) and not self.is_sequential_playback
        self.youtube_handler.play_youtube_url(
            url,
            force_pulse=True,
            show_progress=True,
            title=title,
        )
        self._refresh_history_ui()

    def _prepare_web_stream_player(self):
        self._ensure_vlc_style_instance()
        if self.instance is None:
            self.instance = _make_vlc_instance()
            self._vlc_style_key = fingerprint()
        self._cleanup_vlc_player()
        self.player = self.instance.media_player_new()
        try:
            self.player.audio_set_volume(self.volume)
        except Exception:
            pass
        self.show_controls_and_menu()

    def play_twitch_url(self, url, title=None, add_to_list=True):
        """Reproduce una emisión de Twitch (directo, VOD o clip)."""
        self.ensure_window()
        url = (url or '').strip()
        if not is_twitch_url(url):
            messagebox.showerror('Twitch', 'La URL no parece ser de Twitch.', parent=self.window)
            return
        if add_to_list:
            label = twitch_default_title(url, title)
            existing = next((name for name, item_url in self.all_channels if item_url == url), None)
            if existing and existing not in ('Twitch', url):
                label = title or existing
            elif not existing:
                self.add_channel_to_list(label, url)
        self._playing_youtube = False
        self._playing_twitch = True
        self._yt_standalone = True
        self.twitch_handler.play_twitch_url(url, title=twitch_default_title(url, title))
        self._refresh_history_ui()

    def add_twitch_to_favorites(self):
        handler = getattr(self, 'twitch_handler', None)
        if handler:
            handler.add_current_to_favorites()

    def toggle_twitch_chat(self):
        handler = getattr(self, 'twitch_handler', None)
        if handler:
            handler.toggle_chat()

    def update_twitch_chat_ui(self):
        from twitch_chat import can_show_twitch_chat

        menu = getattr(self, '_twitch_menu', None)
        index = getattr(self, '_tw_chat_menu_index', None)
        handler = getattr(self, 'twitch_handler', None)
        chat = getattr(handler, '_chat', None) if handler else None
        available = can_show_twitch_chat(handler) if handler else False
        open_ = chat.is_open() if chat else False
        if menu is not None and index is not None:
            label = plain_ui_line('Ocultar chat') if open_ else plain_ui_line('Ver chat…')
            try:
                menu.entryconfigure(
                    index,
                    label=label,
                    state='normal' if available or open_ else 'disabled',
                )
            except tk.TclError:
                pass

    def _on_twitch_chat_key(self, event=None):
        if not getattr(self, '_playing_twitch', False):
            return 'break'
        handler = getattr(self, 'twitch_handler', None)
        if handler and getattr(handler, '_chat', None):
            from twitch_chat import can_show_twitch_chat
            if can_show_twitch_chat(handler) or handler._chat.is_open():
                handler.toggle_chat()
        return 'break'

    def open_twitch_channel_browser(self):
        from twitch_browse import open_twitch_channel_browser
        self.ensure_window()
        open_twitch_channel_browser(self)

    def open_twitch_search(self):
        from twitch_search import open_twitch_search
        self.ensure_window()
        open_twitch_search(self)

    def cargar_videos_playlist(self, canales):
        """Carga los vídeos de una playlist de YouTube como canales en el listado."""
        self.channels = canales
        self.all_channels = canales.copy()
        self._showing_favorites = False
        self._groups = [''] * len(canales)
        self._groups_all = list(self._groups)
        self._tvg_ids = [''] * len(canales)
        self._tvg_ids_all = list(self._tvg_ids)
        self._logos = [''] * len(canales)
        self._logos_all = list(self._logos)
        self._epg = None
        self._epg_urls = []
        self._epg_urls_list = []
        self._set_epg_label('')
        self._playlist_kind = self._playlist_kind or 'items'
        self._rebuild_sidebar()
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
                initialdir=app_config.get_download_dir(),
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

    def update_youtube_session_ui(self, info=None):
        info = info or self.youtube_handler.session_view()
        ok = bool(info.get('ok'))
        text = f"Sesión YouTube: {'OK' if ok else 'caducada'}"
        menu = getattr(self, '_youtube_menu', None)
        index = getattr(self, '_yt_session_menu_index', None)
        if menu is not None and index is not None:
            try:
                menu.entryconfigure(index, label=text)
            except tk.TclError:
                pass
        from preferences import refresh_preferences_session_ui
        refresh_preferences_session_ui(youtube_info=info)

    def update_twitch_session_ui(self, info=None):
        info = info or self.twitch_handler.session_view()
        ok = bool(info.get('ok'))
        text = f"Sesión Twitch: {'OK' if ok else 'caducada'}"
        menu = getattr(self, '_twitch_menu', None)
        index = getattr(self, '_tw_session_menu_index', None)
        if menu is not None and index is not None:
            try:
                menu.entryconfigure(index, label=text)
            except tk.TclError:
                pass
        from preferences import refresh_preferences_session_ui
        refresh_preferences_session_ui(twitch_info=info)

    def open_preferences(self):
        from preferences import show_preferences
        callback = getattr(self, '_prefs_apply', self.apply_preferences)
        show_preferences(self.window, on_apply=callback, video_player=self)

    def apply_preferences(self):
        if not self._widget_exists(self.window):
            return
        self.refresh_theme()
        volume = app_config.get_volume()
        self.volume = volume
        scale = getattr(self, 'volume_scale', None)
        if scale:
            try:
                scale.set(volume)
            except tk.TclError:
                pass
        try:
            if self.player:
                self.player.audio_set_volume(volume)
        except Exception:
            pass
        try:
            if self.player:
                apply_spu_delay(self.player)
        except Exception:
            pass
        height = app_config.effective_youtube_quality()
        previous = None
        choice = getattr(self, '_quality_choice', None)
        if choice is not None:
            try:
                previous = int(choice.get())
            except (TypeError, ValueError, tk.TclError):
                previous = None
            try:
                choice.set(str(height))
            except tk.TclError:
                pass
        if previous is not None and previous != height and getattr(self, '_playing_youtube', False):
            self._apply_youtube_quality(height, force=True)
        tw_height = app_config.effective_twitch_quality()
        prev_tw = getattr(self, '_twitch_quality_applied', None)
        if prev_tw is None:
            self._twitch_quality_applied = tw_height
        elif prev_tw != tw_height and getattr(self, '_playing_twitch', False):
            self._twitch_quality_applied = tw_height
            tw_url = getattr(getattr(self, 'twitch_handler', None), '_current_url', '')
            if tw_url:
                self.twitch_handler.play_twitch_url(tw_url)
        else:
            self._twitch_quality_applied = tw_height
        self._logo_photos = {}
        style_changed = fingerprint() != getattr(self, '_vlc_style_key', None)
        self._ensure_vlc_style_instance()
        if style_changed:
            self._reload_current_subtitle_style()
        elif hasattr(self, '_rebuild_track_menus'):
            self._rebuild_track_menus()
        self._apply_logo_pref()
        self._apply_light_mode_runtime()
        self.setup_performance_monitoring()
        try:
            from youtube_player import enforce_youtube_cache_limit
            enforce_youtube_cache_limit(max_bytes=app_config.effective_yt_cache_max_bytes())
        except Exception:
            pass

    def _apply_light_mode_runtime(self):
        if app_config.get_light_mode():
            self._set_epg_label('')
            job = getattr(self, '_epg_reload_job', None)
            if job and self._widget_exists(self.window):
                try:
                    self.window.after_cancel(job)
                except tk.TclError:
                    pass
            self._epg_reload_job = None
        else:
            if self._epg_urls and self._widget_exists(self.window):
                self._schedule_epg_reload()
        index = self._selected_channel_index()
        if index is None:
            index = self.current_channel
        if index is not None and not app_config.get_light_mode():
            self._refresh_epg_label(index)

    def _reload_current_subtitle_style(self):
        """Reabre el vídeo en curso para que VLC aplique el estilo freetype nuevo."""
        if getattr(self, '_playing_youtube', False):
            self._reload_youtube_with_subtitle_style()
            return
        index = self.current_channel
        if index is None or not self.channels:
            return
        if not (0 <= index < len(self.channels)):
            return
        name, url = self.channels[index]
        if is_youtube_channel_url(url) or is_youtube_playlist_url(url):
            return
        if 'youtube.com' in url or 'youtu.be' in url:
            return
        self.play_channel(index)

    def _reload_youtube_with_subtitle_style(self):
        """Vuelve a abrir el stream de YouTube con la instancia VLC del estilo actual."""
        handler = getattr(self, 'youtube_handler', None)
        direct = getattr(handler, '_direct_url', '') or '' if handler else ''
        if not handler or not direct:
            self._ensure_vlc_style_instance()
            return
        keep_ms = self._playback_elapsed_ms()
        sub_path = None
        active = getattr(self, '_active_yt_sub', None)
        for item in getattr(self, '_yt_subtitles', []) or []:
            if active and (item.get('kind'), item.get('lang')) == active:
                sub_path = item.get('path')
                break
        if sub_path and os.path.isfile(sub_path):
            from youtube_subs import prepare_subtitle_for_vlc
            ready = prepare_subtitle_for_vlc(sub_path)
            if ready:
                sub_path = ready
                for item in getattr(self, '_yt_subtitles', []) or []:
                    if active and (item.get('kind'), item.get('lang')) == active:
                        item['path'] = ready
                        break
        kwargs = dict(getattr(handler, '_play_kwargs', {}) or {})
        self._ensure_vlc_style_instance()
        self.play_video_url(
            direct,
            force_pulse=kwargs.get('force_pulse', True),
            show_progress=kwargs.get('show_progress', True),
            is_sequential=kwargs.get('is_sequential', False),
            http_headers=getattr(handler, '_direct_headers', None),
            duration_s=(self._known_duration_ms / 1000.0) if self._known_duration_ms else None,
            subtitle_path=sub_path if sub_path and os.path.isfile(sub_path) else None,
            start_s=keep_ms / 1000.0,
            fail_after_s=20,
        )

    def refresh_theme(self):
        if not self._widget_exists(self.window):
            return
        style_window(self.window)
        if self._widget_exists(self.channels_listbox):
            sidebar = getattr(self, 'sidebar', None)
            if sidebar:
                sidebar.refresh_theme()
        style_menu_tree(getattr(self, 'menubar', None))
        for menu in (
            getattr(self, 'audio_menu', None),
            getattr(self, 'subs_menu', None),
            getattr(self, 'audio_popup', None),
            getattr(self, 'subs_popup', None),
            getattr(self, '_youtube_menu', None),
        ):
            if menu is not None:
                style_menu_tree(menu)
        colors = get_colors()
        self._control_icons = make_control_icons(colors['text'], record_color=colors['danger'])
        for key, btn in getattr(self, '_control_buttons', {}).items():
            if key == 'record':
                continue
            try:
                btn.configure(image=self._control_icons[key])
            except tk.TclError:
                pass
        self._refresh_record_button()
        handler = getattr(self, 'youtube_handler', None)
        if handler:
            handler.notify_session()
        twitch = getattr(self, 'twitch_handler', None)
        if twitch:
            twitch.notify_session()

    def reexport_youtube_cookies(self):
        self.youtube_handler.reexport_youtube_cookies()

    def reexport_twitch_cookies(self):
        self.twitch_handler.reexport_twitch_cookies()

    def update_yt_dlp(self):
        from preferences import start_yt_dlp_upgrade
        start_yt_dlp_upgrade(self.window)

    def open_youtube_search(self):
        """Abre la ventana de búsqueda de YouTube."""
        # Asegúrate de que load_playlist_callback se pasa correctamente
        search_dialog = YouTubeSearchDialog(
            self.window,
            self.play_youtube_url,
            self.load_playlist_callback,
            self.enqueue_youtube_queue,
            youtube_handler=self.youtube_handler,
            favorite_callback=self.add_favorite_entry,
            unfavorite_callback=self.remove_favorite_entry,
            is_favorite_callback=lambda url: favorites_contain(self.favorites, '', url),
        )

    def load_playlist_callback(self, channels_list):
         """Callback para cargar vídeos de una playlist en la lista principal."""
         if channels_list:
             self.ensure_window()
             self.channels = list(channels_list)
             self.all_channels = list(channels_list)
             self._showing_favorites = False
             self._groups = [''] * len(channels_list)
             self._groups_all = list(self._groups)
             self._tvg_ids = [''] * len(channels_list)
             self._tvg_ids_all = list(self._tvg_ids)
             self._logos = [''] * len(channels_list)
             self._logos_all = list(self._logos)
             self._epg = None
             self._epg_urls = []
             self._epg_urls_list = []
             self._set_epg_label('')
             self._playlist_kind = self._playlist_kind or 'youtube_playlist'
             self._rebuild_sidebar()
             self._persist_sidebar()
             messagebox.showinfo("Playlist cargada", f"Se cargaron {len(channels_list)} vídeos de la playlist.")

    def _listbox_index_at(self, event):
        """Índice de la fila bajo el puntero, o None si no hay título debajo."""
        sidebar = getattr(self, 'sidebar', None)
        if not sidebar:
            return None
        return sidebar.index_at(event)

    def _hide_listbox_tooltip(self, event=None):
        self._listbox_tip_index = None
        tip = getattr(self, 'listbox_tooltip', None)
        if tip:
            tip.hidetip()

    def on_listbox_motion(self, event):
        """Muestra el título completo solo al pasar el ratón por esa fila."""
        if getattr(self, '_posted_popup', None):
            self._hide_listbox_tooltip()
            return
        sidebar = getattr(self, 'sidebar', None)
        name = sidebar.name_at(event) if sidebar else None
        if not name:
            self._hide_listbox_tooltip()
            return
        index = sidebar.index_at(event) if sidebar else None
        extra = self._epg_text_for_index(index) if index is not None else ''
        text = f'{name}\n{extra}' if extra else name
        tip_key = (index if index is not None else name, extra)
        if tip_key == self._listbox_tip_index and self.listbox_tooltip.tipwindow:
            return
        self._listbox_tip_index = tip_key
        self.listbox_tooltip.showtip(
            text,
            event.x_root + 14,
            event.y_root + 12,
            wraplength=360,
        )

    def on_listbox_leave(self, event):
        box = self.channels_listbox
        try:
            px = box.winfo_pointerx() - box.winfo_rootx()
            py = box.winfo_pointery() - box.winfo_rooty()
            if 0 <= px < box.winfo_width() and 0 <= py < box.winfo_height():
                return
        except tk.TclError:
            pass
        self._hide_listbox_tooltip()

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
                if getattr(self, 'sidebar', None):
                    self.sidebar.select(index)
                    self.sidebar.see(index)
                
                # Crear nuevo reproductor y reproducir
                print("Iniciando reproducción")
                self.play_channel(index)
            else:
                print(f"Índice {index} fuera de rango (max: {len(self.channels)-1})")
        except Exception as e:
            print(f"Error en select_and_play_channel: {e}")
            import traceback
            print(traceback.format_exc())

    def _hide_youtube_replay_prompt(self):
        frame = getattr(self, '_yt_replay_frame', None)
        self._yt_replay_frame = None
        if self._widget_exists(frame):
            try:
                frame.destroy()
            except tk.TclError:
                pass

    def _show_youtube_replay_prompt(self):
        """Ofrece repetir un vídeo de YouTube suelto. VLC tapa el Tk embebido: se suelta el vídeo."""
        if self._widget_exists(getattr(self, '_yt_replay_frame', None)):
            return
        if not self._widget_exists(self.window):
            return
        handler = getattr(self, 'youtube_handler', None)
        title = ''
        if handler:
            title = (getattr(handler, '_loading_title_text', None) or '').strip()
        if not title and self.current_channel is not None:
            try:
                title = self.channels[self.current_channel][0]
            except (IndexError, TypeError):
                title = ''
        title = title or 'YouTube'
        self.show_controls_and_menu()
        release = getattr(self, '_release_vlc_video_window', None)
        if release:
            release()
        colors = get_colors()
        target = getattr(self, '_video_target_frame', None)
        parent = target() if callable(target) else None
        if not self._widget_exists(parent):
            parent = getattr(self, 'video_frame', None)
        if not self._widget_exists(parent):
            parent = getattr(self, 'player_frame', None)
        if not self._widget_exists(parent):
            return
        panel = tk.Frame(parent, bg='#000000', highlightthickness=0)
        try:
            panel.place(relx=0, rely=0, relwidth=1, relheight=1)
            panel.lift()
        except tk.TclError:
            panel.pack(fill=tk.BOTH, expand=True)
        card = tk.Frame(
            panel,
            bg=colors['surface'],
            highlightbackground=colors['border'],
            highlightthickness=1,
            padx=28,
            pady=22,
        )
        card.place(relx=0.5, rely=0.5, anchor='center')
        tk.Label(
            card,
            text=title,
            font=get_font(16, 'bold'),
            bg=colors['surface'],
            fg=colors['text'],
            wraplength=460,
            justify='center',
        ).pack()
        tk.Label(
            card,
            text='¿Volver a ver este vídeo?',
            font=get_font(12),
            bg=colors['surface'],
            fg=colors['text_muted'],
            wraplength=460,
            justify='center',
        ).pack(pady=(12, 16))
        buttons = ttk.Frame(card, style='Card.TFrame')
        buttons.pack()
        ttk.Button(
            buttons,
            text='Volver a ver',
            style='Accent.TButton',
            command=self._replay_current_youtube,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            buttons,
            text='No, gracias',
            style='Ghost.TButton',
            command=self._hide_youtube_replay_prompt,
        ).pack(side=tk.LEFT)
        self._yt_replay_frame = panel

    def _replay_current_youtube(self):
        self._hide_youtube_replay_prompt()
        handler = getattr(self, 'youtube_handler', None)
        url = getattr(handler, '_current_url', '') or '' if handler else ''
        if not handler or not url:
            return
        self._yt_standalone = True
        handler.play_youtube_url(
            url,
            force_pulse=True,
            show_progress=True,
            title=getattr(handler, '_loading_title_text', None),
            resume_s=0,
        )

    def _safe_on_media_end(self, event):
        """VLC llama esto fuera del hilo de Tk."""
        gen = getattr(self, '_media_end_gen', 0)
        window = getattr(self, 'window', None)
        if window is None:
            return
        try:
            window.after(0, lambda g=gen: self._on_media_ended(g))
        except tk.TclError:
            pass

    def _on_media_ended(self, gen=None):
        """Cuando termina un vídeo, sigue la cola o la secuencia; si es YouTube suelto, ofrece repetir."""
        try:
            if gen is not None and gen != getattr(self, '_media_end_gen', 0):
                return
            if getattr(self, '_yt_end_handled', False):
                return
            if not self.player:
                return
            if not getattr(self, '_media_started', False):
                return
            try:
                state = self.player.get_state()
            except Exception:
                return
            if state != vlc.State.Ended:
                return
            self._yt_end_handled = True
            self.clear_youtube_resume()

            if getattr(self, '_playing_youtube', False) and app_config.youtube_queue():
                def play_queue_next():
                    try:
                        if self.player and self.player.is_playing():
                            self.player.stop()
                        if hasattr(self, '_current_event_manager') and self._current_event_manager:
                            try:
                                self._current_event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                                self._current_event_manager = None
                            except Exception:
                                pass
                        self.play_youtube_queue_next()
                    except Exception as exc:
                        print(f"Error al reproducir el siguiente de la cola: {exc}")

                self.window.after(500, play_queue_next)
                return

            if self.is_sequential_playback:
                if self.current_playlist_index is None:
                    return
                current_index = self.current_playlist_index
                next_index = current_index + 1
                if next_index < len(self.channels):
                    def play_next():
                        try:
                            if self.player and self.player.is_playing():
                                self.player.stop()
                            if hasattr(self, '_current_event_manager') and self._current_event_manager:
                                try:
                                    self._current_event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                                    self._current_event_manager = None
                                except Exception:
                                    pass
                            self.current_playlist_index = next_index
                            self.select_and_play_channel(next_index)
                        except Exception as exc:
                            print(f"Error al reproducir siguiente vídeo: {exc}")

                    self.window.after(500, play_next)
                    return
                self.is_sequential_playback = False
                self.current_playlist_index = None
                self._current_event_manager = None
                return

            if should_offer_youtube_replay(
                getattr(self, '_playing_youtube', False),
                getattr(self, '_yt_standalone', False),
                False,
                bool(app_config.youtube_queue()),
            ):
                self._show_youtube_replay_prompt()
        except Exception as exc:
            print(f"Error en _on_media_ended: {exc}")
            traceback.print_exc()

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
            if not (0 <= index < len(self.channels)):
                return
            _name, url = self.channels[index]
            del self.channels[index]
            if index < len(self._groups):
                del self._groups[index]
            if index < len(self._tvg_ids):
                del self._tvg_ids[index]
            if index < len(getattr(self, '_logos', [])):
                del self._logos[index]
            for i, (_n, item_url) in enumerate(list(self.all_channels)):
                if item_url != url:
                    continue
                del self.all_channels[i]
                if i < len(self._groups_all):
                    del self._groups_all[i]
                if i < len(self._tvg_ids_all):
                    del self._tvg_ids_all[i]
                if i < len(getattr(self, '_logos_all', [])):
                    del self._logos_all[i]
                break
            self._rebuild_sidebar()
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
            self._showing_favorites = False
            self._groups.clear()
            self._groups_all.clear()
            self._tvg_ids.clear()
            self._tvg_ids_all.clear()
            self._logos.clear()
            self._logos_all.clear()
            self._epg = None
            self._epg_urls = []
            self._epg_urls_list = []
            self.current_channel = None
            self._set_epg_label('')
            if self._widget_exists(self.search_entry):
                self.search_var.set('')
            if getattr(self, 'sidebar', None):
                self.sidebar.clear()
        except Exception as e:
            print(f"Error al limpiar la lista: {e}")

    def _selected_channel_index(self, event=None):
        sidebar = getattr(self, 'sidebar', None)
        if event is not None and sidebar:
            index = sidebar.index_at(event)
            if index is not None:
                return index
        if sidebar:
            return sidebar.selected_index()
        return None

    def add_favorite_entry(self, name, url, notify=False):
        """Guarda un canal (de la lista o de una búsqueda) en favoritos.json."""
        title = (name or '').strip() or 'Canal'
        self.favorites, added = add_favorite(self.favorites, title, url)
        if added:
            self.save_favorites()
            self._refresh_favorite_marks()
            if notify:
                messagebox.showinfo(
                    "Favoritos",
                    f"«{title}» está en favoritos. Pulsa ★ Favoritos para verlos.",
                )
        elif notify:
            if not str(url or '').strip():
                messagebox.showinfo("Información", "Por favor, selecciona un canal primero")
            else:
                messagebox.showinfo("Información", f"«{title}» ya está en favoritos")
        return added

    def remove_favorite_entry(self, name, url, notify=False):
        title = (name or '').strip() or 'Canal'
        self.favorites, removed = remove_favorite(self.favorites, title, url)
        if removed:
            self.save_favorites()
            if getattr(self, '_showing_favorites', False):
                self._apply_channel_filter()
            else:
                self._refresh_favorite_marks()
            if notify:
                messagebox.showinfo("Favoritos", f"«{title}» se quitó de favoritos")
        elif notify:
            messagebox.showinfo("Información", f"«{title}» no estaba en favoritos")
        return removed

    def add_to_favorites(self):
        """Añade el canal seleccionado a favoritos (también desde una búsqueda)."""
        selected_index = self._selected_channel_index()
        if selected_index is None:
            messagebox.showinfo("Información", "Selecciona un canal de la búsqueda o de la lista.")
            return
        name, url = self.channels[selected_index]
        self.add_favorite_entry(name, url, notify=True)

    def remove_from_favorites(self):
        """Elimina el canal seleccionado de favoritos"""
        selected_index = self._selected_channel_index()
        if selected_index is None:
            messagebox.showinfo("Información", "Por favor, selecciona un canal primero")
            return
        name, url = self.channels[selected_index]
        self.remove_favorite_entry(name, url, notify=True)

    def _favorites_dialog_dir(self):
        return app_config.get_download_dir() or app_config.suggested_download_dir()

    def _apply_imported_favorites(self, items, replace):
        incoming = normalize_favorites(items)
        if replace:
            self.favorites = incoming
            added, skipped = len(incoming), 0
        else:
            self.favorites, added, skipped = merge_favorites(self.favorites, incoming)
        self.save_favorites()
        manager = getattr(self, 'favorites_manager', None)
        if manager is not None:
            manager.favorites = self.favorites
        if getattr(self, '_showing_favorites', False):
            if self.favorites:
                self.show_favorites()
            else:
                self.restore_all_channels()
        else:
            self._refresh_favorite_marks()
        return added, skipped

    def export_favorites(self):
        items = normalize_favorites(self.favorites)
        if not items:
            messagebox.showinfo(
                "Favoritos",
                "Por el momento no hay favoritos que exportar.",
                parent=self.window,
            )
            return
        path = filedialog.asksaveasfilename(
            parent=self.window,
            title='Exportar favoritos',
            initialdir=self._favorites_dialog_dir(),
            initialfile='kidneysm3u-favoritos.json',
            defaultextension='.json',
            filetypes=[
                ('Favoritos JSON', '*.json'),
                ('Lista M3U', '*.m3u'),
                ('Todos', '*.*'),
            ],
        )
        if not path:
            return
        try:
            written = write_favorites_file(path, items)
        except Exception:
            messagebox.showerror(
                "Favoritos",
                "No se pudieron exportar los favoritos.",
                parent=self.window,
            )
            return
        messagebox.showinfo(
            "Favoritos",
            f"Se exportaron {len(items)} favoritos.\n\n"
            f"{written}\n\n"
            "Ese archivo puede contener las mismas URLs que favoritos.json "
            "(a veces con usuario y contraseña). No lo subas a internet.",
            parent=self.window,
        )

    def import_favorites(self):
        path = filedialog.askopenfilename(
            parent=self.window,
            title='Importar favoritos',
            initialdir=self._favorites_dialog_dir(),
            filetypes=[
                ('Favoritos JSON o M3U', '*.json *.m3u *.m3u8'),
                ('JSON', '*.json'),
                ('Lista M3U', '*.m3u *.m3u8'),
                ('Todos', '*.*'),
            ],
        )
        if not path:
            return
        try:
            incoming = read_favorites_file(path)
        except ValueError as exc:
            messagebox.showerror("Favoritos", str(exc), parent=self.window)
            return
        except Exception:
            messagebox.showerror(
                "Favoritos",
                "No se pudieron leer los favoritos.",
                parent=self.window,
            )
            return
        if not incoming:
            messagebox.showinfo(
                "Favoritos",
                "El archivo no contiene favoritos.",
                parent=self.window,
            )
            return
        replace = False
        current = len(normalize_favorites(self.favorites))
        if current:
            choice = messagebox.askyesnocancel(
                "Importar favoritos",
                f"Ya hay {current} favoritos en este equipo.\n\n"
                "Sí: añadir los del archivo (los que ya existan se ignoran).\n"
                "No: sustituir todos por los del archivo.\n"
                "Cancelar: no cambiar nada.",
                parent=self.window,
            )
            if choice is None:
                return
            replace = not choice
        added, skipped = self._apply_imported_favorites(incoming, replace)
        if replace:
            detail = f"Se sustituyeron los favoritos ({len(self.favorites)})."
        elif added:
            extra = f" {skipped} ya estaban." if skipped else ''
            detail = f"Se añadieron {added} favoritos.{extra}"
        else:
            detail = "No se añadió ninguno: ya estaban todos."
        messagebox.showinfo("Favoritos", detail, parent=self.window)

    def show_channel_context_menu(self, event):
        selection = self._selected_channel_index(event)
        self._hide_listbox_tooltip()
        if selection is None:
            self._dismiss_track_menus()
            return
        if getattr(self, 'sidebar', None):
            self.sidebar.select(selection)
        self._dismiss_track_menus()
        menu = tk.Menu(self.window, tearoff=0)
        style_menu_tree(menu)
        menu.add_command(
            label="Reproducir desde aquí",
            command=lambda: self._choose_from_menu(lambda: self.play_from_here(selection)),
        )
        menu.add_separator()
        menu.add_command(
            label="Añadir a Favoritos",
            command=lambda: self._choose_from_menu(self.add_to_favorites),
        )
        menu.add_command(
            label="Eliminar de Favoritos",
            command=lambda: self._choose_from_menu(self.remove_from_favorites),
        )
        menu.add_separator()
        menu.add_command(
            label="Descargar",
            command=lambda: self._choose_from_menu(lambda: self.download_channel(selection)),
        )
        menu.add_command(
            label="Eliminar canal",
            command=lambda: self._choose_from_menu(lambda: self.remove_channel(selection)),
        )
        menu.add_separator()
        menu.add_command(
            label="Limpiar lista",
            command=lambda: self._choose_from_menu(self.clear_channel_list),
        )
        try:
            menu.post(event.x_root, event.y_root)
            self._channel_menu = menu
            self._posted_popup = menu
        except tk.TclError:
            try:
                menu.destroy()
            except tk.TclError:
                pass
            self._channel_menu = None
            self._posted_popup = None

    def toggle_playlist(self):
        """Muestra u oculta la lista de canales y el sizer"""
        self._hide_listbox_tooltip()
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

