import os
import pathlib
import time
import shutil
import psutil
from favorites_manager import FavoritesManager
import vlc
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import sys
import re
import threading
import yt_dlp
import traceback
from youtube_player import YouTubeHandler, youtube_ydl_opts
from youtube_search import YouTubeSearchDialog
from ui_theme import (
    get_colors, get_font, style_window, style_menu_tree,
    set_window_icon, make_control_icons,
)
import app_config
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
        """Muestra el tooltip con el texto dado, cerca del puntero del ratón"""
        text = (text or '').strip()
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


class VideoPlayer(PlayerControlsMixin, IptvPlaybackMixin, ChannelNoticeMixin, PlayerPipMixin):
    def __init__(self):
        self.window = None
        self.instance = _make_vlc_instance()
        self.player = self.instance.media_player_new()
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
        self._show_logos = app_config.get_show_channel_logos()
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
        self.window = tk.Toplevel(className='Kidneysm3u')
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
        ttk.Button(favorites_buttons_frame, text="Guía", command=self.open_epg_grid).pack(side=tk.LEFT, padx=(6, 0))

        # Búsqueda
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_channels)
        self.search_entry = ttk.Entry(self.channels_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 8))

        self._epg_label = ttk.Label(
            self.channels_frame,
            text='',
            style='Muted.TLabel',
            wraplength=260,
            justify=tk.LEFT,
        )

        session_frame = ttk.Frame(self.channels_frame)
        session_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 8))
        self._yt_session_label = ttk.Label(session_frame, text='Sesión YouTube: …', style='Muted.TLabel')
        self._yt_session_label.pack(anchor=tk.W)
        ttk.Button(
            session_frame,
            text="Reexportar cookies",
            command=self.reexport_youtube_cookies,
        ).pack(anchor=tk.W, pady=(4, 0))

        self.sidebar = ChannelSidebar(self.channels_frame)
        self.sidebar.now_text = self._epg_now_title
        self.sidebar.row_image = self._logo_photo
        self.sidebar.on_view_change = self._prefetch_visible_logos
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
        #self.setup_performance_monitoring()
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind('<Escape>', lambda e: self.exit_fullscreen())
        self.youtube_handler.notify_session()

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
        epg_menu = tk.Menu(reproducir_menu, tearoff=0)
        epg_menu.add_command(label="Parrilla…", command=self.open_epg_grid)
        epg_menu.add_separator()
        epg_menu.add_command(label="Desde URL…", command=self.prompt_epg_url)
        epg_menu.add_command(label="Desde archivo…", command=self.prompt_epg_file)
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
        reproducir_menu.add_command(label="Grabar en…", command=lambda: self.start_stream_recording(ask_path=True))
        reproducir_menu.add_command(label="Grabaciones…", command=lambda: show_recordings(self))
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
        youtube_menu.add_command(label="Sesión YouTube: …", state='disabled')
        self._yt_session_menu_index = youtube_menu.index('end')
        youtube_menu.add_command(label="Reexportar cookies", command=self.reexport_youtube_cookies)
        youtube_menu.add_command(label="Actualizar yt-dlp", command=self.update_yt_dlp)
        self._youtube_menu = youtube_menu
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
        self.window.bind('<space>', self._on_space_toggle_play)
        self.window.bind('<F1>', lambda e: self.toggle_fullscreen())
        self.window.bind('<m>', lambda e: self.toggle_mute())
        self.window.bind('<Left>', lambda e: self.seek_relative(-2))
        self.window.bind('<Right>', lambda e: self.seek_relative(2))
        
        # Atajos para favoritos
        self.window.bind('<Control-s>', self.handle_add_favorite)
        self.window.bind('<Control-d>', self.handle_remove_favorite)
        self.window.bind('<g>', self._on_epg_grid_key)
        self.window.bind('<G>', self._on_epg_grid_key)
        
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
                    start_s=keep_ms / 1000.0,
                    fail_after_s=20,
                )
                self._hold_progress_ms = keep_ms
                self._hold_progress_until = time.time() + 2.5
                return
            keep_ms = self._playback_elapsed_ms()
            try:
                uri = pathlib.Path(path).resolve().as_uri()
                loaded = self.player.add_slave(vlc.MediaSlaveType.subtitle, uri, True)
                print(f"[VLC] Subtítulo esclavo ({loaded})")
            except Exception as exc:
                print(f"[VLC] No se pudo añadir el subtítulo: {exc}")
                return
            self._hold_progress_ms = keep_ms
            self._hold_progress_until = time.time() + 2.5
            if self._widget_exists(self.window):
                self.window.after(400, self._select_external_spu)
                self.window.after(550, lambda ms=keep_ms: self._restore_after_subtitle(ms))
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
        widget = getattr(event, 'widget', None) if event is not None else None
        try:
            if widget and widget.winfo_class() in ('Entry', 'TEntry', 'Text'):
                return
        except tk.TclError:
            pass
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
                title='Grabar en…',
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
            self._save_window_geometry()
            app_config.set_volume(self.volume)
            self.save_favorites()
            self.stop_update_time()
            self._cancel_epg_jobs()
            self.stop_stream_recording(notify=False)
            close_pip = getattr(self, 'close_pip', None)
            if close_pip:
                close_pip()

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
            self.window.update_idletasks()
            target.update_idletasks()
            wid = target.winfo_id()
        except tk.TclError:
            return
        if sys.platform.startswith('win'):
            self.player.set_hwnd(wid)
        elif sys.platform == 'darwin':
            self.player.set_nsobject(wid)
        else:
            self.player.set_xwindow(wid)

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
        if not app_config.get_remember_last_list():
            return
        session = app_config.load().get('session') or {}
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
        if len(items) > 1500:
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
        self._groups = [''] * len(self.channels)
        self._tvg_ids = [self._tvg_id_for_url(url) for _name, url in self.channels]
        self._logos = [self._logo_for_url(url) for _name, url in self.channels]
        self._rebuild_sidebar()
        self._set_epg_label('')

    
    def restore_all_channels(self):
        self.channels = self.all_channels.copy()
        self._groups = list(self._groups_all)
        self._tvg_ids = list(self._tvg_ids_all) if len(self._tvg_ids_all) == len(self.all_channels) else [''] * len(self.all_channels)
        self._logos = list(self._logos_all) if len(getattr(self, '_logos_all', [])) == len(self.all_channels) else [''] * len(self.all_channels)
        self._rebuild_sidebar()

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

    def prompt_epg_url(self):
        """Pide la URL HTTP de una guía XMLTV."""
        self.ensure_window()
        current = (self._epg_url_manual or app_config.get_epg_url() or '').strip()
        if current and not current.lower().startswith(('http://', 'https://')):
            current = ''
        url = simpledialog.askstring(
            "Guía EPG",
            "URL de la guía XMLTV (http o https):",
            parent=self.window,
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

    def _set_busy(self, text=None):
        if not self._widget_exists(self.window):
            return
        try:
            self.window.config(cursor='watch')
            if text:
                self.window.title(f'Reproductor de vídeo · {text}')
        except tk.TclError:
            pass

    def _clear_busy(self):
        if not self._widget_exists(self.window):
            return
        try:
            self.window.config(cursor='')
            self.window.title('Reproductor de vídeo')
        except tk.TclError:
            pass

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
        self._set_busy('Cargando lista…')
        window = self.window

        def work():
            err = None
            parsed = None
            try:
                with open(filename, 'rb') as f:
                    content = decode_m3u_bytes(f.read())
                parsed = parse_m3u_channels(content)
                epg_urls = parse_m3u_epg_urls(content)
            except Exception as exc:
                err = exc
                epg_urls = []

            def apply():
                if gen != self._load_gen:
                    return
                self._clear_busy()
                if err:
                    messagebox.showerror("Error", f"No se pudo cargar el archivo M3U: {err}")
                    return
                self._apply_parsed_channels(parsed, filename, 'file', notify, epg_urls=epg_urls)
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
            try:
                import urllib.request
                with urllib.request.urlopen(url) as response:
                    content = decode_m3u_bytes(response.read())
                parsed = parse_m3u_channels(content)
                epg_urls = parse_m3u_epg_urls(content)
            except Exception as exc:
                err = exc
                epg_urls = []

            def apply():
                if gen != self._load_gen:
                    return
                self._clear_busy()
                if err:
                    messagebox.showerror("Error", f"No se pudo cargar la URL M3U: {err}")
                    return
                self._apply_parsed_channels(parsed, url, 'url', notify, epg_urls=epg_urls)
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
        self._playlist_source = source
        self._playlist_kind = kind
        self._rebuild_sidebar()
        self._start_epg(epg_urls)
        self._persist_sidebar()
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
        self._set_epg_label('Cargando guía…')

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
        return bool(getattr(self, '_show_logos', True))

    def _on_logos_menu_toggle(self):
        var = getattr(self, '_logos_var', None)
        enabled = bool(var.get()) if var is not None else True
        app_config.set_show_channel_logos(enabled)
        self._apply_logo_pref(enabled)

    def _apply_logo_pref(self, enabled=None):
        if enabled is None:
            enabled = app_config.get_show_channel_logos()
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
        self._epg_reload_job = self.window.after(30 * 60 * 1000, lambda: self._start_epg(notify=False))

    def _schedule_epg_tick(self):
        job = getattr(self, '_epg_tick_job', None)
        if job and self._widget_exists(self.window):
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass
        if not self._widget_exists(self.window):
            return
        self._epg_tick_job = self.window.after(60 * 1000, self._tick_epg)

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
        menu.add_command(label="Ver historial…", command=self.open_iptv_history)
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
        menu.add_separator()
        if not recent and not yt_recent:
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
        menu.add_separator()
        menu.add_command(label="Vaciar historial", command=self.clear_iptv_history_prompt)

    def clear_iptv_history_prompt(self):
        if not app_config.iptv_history() and not app_config.youtube_history():
            return
        if not messagebox.askyesno(
            'Vaciar historial',
            '¿Quitar el historial de IPTV y de YouTube?',
            parent=self.window,
        ):
            return
        app_config.clear_iptv_history()
        app_config.clear_youtube_history()
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
        self.current_channel = None
        app_config.remember_iptv_history(name, url, group=item.get('group') or '')
        if self.instance is None:
            self.instance = _make_vlc_instance()
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
        widget = getattr(event, 'widget', None) if event is not None else None
        try:
            if widget and widget.winfo_class() in ('Entry', 'TEntry', 'Text'):
                return
        except tk.TclError:
            pass
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
        playlist_url = simpledialog.askstring("Cargar Playlist de YouTube", "Introduce la URL de la playlist de YouTube:")
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
                self._clear_busy()
                if err:
                    messagebox.showerror("Error", f"No se pudo cargar la playlist: {err}")
                    return
                if not parsed:
                    messagebox.showinfo("Info", "No se encontraron vídeos en la playlist.")
                    return
                self.channels = parsed
                self.all_channels = list(parsed)
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
            self.save_youtube_resume()
            self.save_iptv_resume()
            name, url = self.channels[index]
            self.current_channel = index
            self._refresh_epg_label(index)
            app_config.remember_channel(index, name, url)
            group = self._groups[index] if index < len(getattr(self, '_groups', [])) else ''
            app_config.remember_iptv_history(name, url, group=group)
            self._refresh_history_ui()
            if self.instance is None:
                self.instance = _make_vlc_instance()
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
                self.youtube_handler.play_youtube_url(
                    url, 
                    force_pulse=True, 
                    show_progress=True,
                    is_sequential=self.is_sequential_playback,
                    title=name,
                )
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
            self._yt_resume_s = start_s if start_s >= 0.5 else 0
            if local_file and '127.0.0.1' in str(url):
                self._yt_resume_s = 0
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
                    if getattr(self, '_playing_youtube', False) or self._iptv_has_real_media():
                        started = getattr(self, '_media_started', False)
                        self._media_started = True
                        if not started and not getattr(self, '_playing_youtube', False):
                            self._apply_pending_iptv_resume()
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
        if not search_term:
            self.channels = list(self.all_channels)
            self._groups = list(self._groups_all) if len(self._groups_all) == len(self.all_channels) else [''] * len(self.all_channels)
            self._tvg_ids = list(self._tvg_ids_all) if len(self._tvg_ids_all) == len(self.all_channels) else [''] * len(self.all_channels)
            self._logos = list(self._logos_all) if len(self._logos_all) == len(self.all_channels) else [''] * len(self.all_channels)
            self._rebuild_sidebar()
            return
        groups_all = self._groups_all if len(self._groups_all) == len(self.all_channels) else [''] * len(self.all_channels)
        tvg_all = self._tvg_ids_all if len(self._tvg_ids_all) == len(self.all_channels) else [''] * len(self.all_channels)
        logos_all = self._logos_all if len(getattr(self, '_logos_all', [])) == len(self.all_channels) else [''] * len(self.all_channels)
        snapshot = self.all_channels
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
        title = (name or '').strip() or 'YouTube'
        self.all_channels.append((title, url))
        self._groups_all.append('YouTube')
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
            self._groups.append('YouTube')
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
        self.play_youtube_url(item.get('url') or '', title=item.get('name'), add_to_list=False)

    def play_youtube_queue_next(self):
        self.play_youtube_queue_index(0)

    def play_youtube_url(self, url, title=None, add_to_list=True):
        """Delega la reproducción de YouTube al manejador y añade el vídeo a la lista si falta."""
        if add_to_list:
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
        self._refresh_history_ui()

    def cargar_videos_playlist(self, canales):
        """Carga los vídeos de una playlist de YouTube como canales en el listado."""
        self.channels = canales
        self.all_channels = canales.copy()
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
        style = 'SessionOk.TLabel' if ok else 'SessionBad.TLabel'
        label = getattr(self, '_yt_session_label', None)
        if label:
            try:
                label.configure(text=text, style=style)
            except tk.TclError:
                pass
        menu = getattr(self, '_youtube_menu', None)
        index = getattr(self, '_yt_session_menu_index', None)
        if menu is not None and index is not None:
            try:
                menu.entryconfigure(index, label=text)
            except tk.TclError:
                pass

    def open_preferences(self):
        from preferences import show_preferences
        callback = getattr(self, '_prefs_apply', self.apply_preferences)
        show_preferences(self.window, on_apply=callback)

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
        height = app_config.get_youtube_quality()
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
        elif hasattr(self, '_rebuild_track_menus'):
            self._rebuild_track_menus()
        self._apply_logo_pref()

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

    def reexport_youtube_cookies(self):
        self.youtube_handler.reexport_youtube_cookies()

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
        )

    def load_playlist_callback(self, channels_list):
         """Callback para cargar vídeos de una playlist en la lista principal."""
         if channels_list:
             self.ensure_window()
             self.channels = list(channels_list)
             self.all_channels = list(channels_list)
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

    def _safe_on_media_end(self, event):
        """Cuando termina un vídeo, sigue la cola de YouTube o el modo secuencial de la lista."""
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

    def add_to_favorites(self):
        """Añade el canal seleccionado a favoritos"""
        selected_index = self._selected_channel_index()
        if selected_index is None:
            messagebox.showinfo("Información", "Por favor, selecciona un canal primero")
            return
        channel = self.channels[selected_index]
        if channel not in self.favorites:
            self.favorites.append(channel)
            self.save_favorites()
            messagebox.showinfo("Éxito", f"Canal '{channel[0]}' añadido a favoritos")
        else:
            messagebox.showinfo("Información", f"El canal '{channel[0]}' ya está en favoritos")

    def remove_from_favorites(self):
        """Elimina el canal seleccionado de favoritos"""
        selected_index = self._selected_channel_index()
        if selected_index is None:
            messagebox.showinfo("Información", "Por favor, selecciona un canal primero")
            return
        channel = self.channels[selected_index]
        if channel in self.favorites:
            self.favorites.remove(channel)
            self.save_favorites()
            messagebox.showinfo("Éxito", f"Canal '{channel[0]}' eliminado de favoritos")
        else:
            messagebox.showinfo("Información", f"El canal '{channel[0]}' no estaba en favoritos")

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

