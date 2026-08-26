import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog, font as tkfont
import yt_dlp
import requests
import webbrowser
import threading
import os
import re
import subprocess
from datetime import datetime, timedelta
from urllib.parse import quote, quote_plus
from youtube_player import (
    youtube_ydl_opts, youtube_auth_blocked, youtube_auth_help, slim_youtube_cookies_file,
)
from ui_theme import style_window, style_listbox, style_menu_tree, set_window_icon, center_window
import app_config


STAR_ON = '★'
STAR_OFF = '☆'


def youtube_result_line(kind, title, duration_str='', favorite=False):
    """Texto de una fila de búsqueda, con estrella clicable al inicio."""
    mark = STAR_ON if favorite else STAR_OFF
    name = (title or '').strip() or 'YouTube'
    if kind == 'channel':
        body = f'[Canal] {name}'
    elif kind == 'playlist':
        body = f'[Lista] {name}'
    elif kind in ('short', 'shorts'):
        body = f'[Short] {name}'
    else:
        body = f'[Vídeo] {name}'
    extra = (duration_str or '').strip()
    if extra:
        body += f' [{extra}]'
    return f'{mark} {body}'


def youtube_star_hit(x, star_width=16):
    """True si el clic cae sobre la estrella de la fila."""
    try:
        pos = int(x)
        width = int(star_width)
    except (TypeError, ValueError):
        return False
    return pos <= max(22, width + 10)


def _hashtag_slug(query):
    text = (query or '').strip().lstrip('#')
    return re.sub(r'[^\w]+', '', text, flags=re.UNICODE)


def _is_youtube_short(entry):
    if not entry:
        return False
    for key in ('url', 'original_url', 'webpage_url'):
        if '/shorts/' in str(entry.get(key) or ''):
            return True
    return False


def _fill_short_titles(entries):
    missing = [entry for entry in entries if not (entry.get('title') or '').strip()]
    if not missing:
        return

    def fetch(entry):
        video_id = entry.get('id')
        try:
            response = requests.get(
                'https://www.youtube.com/oembed',
                params={'url': f'https://www.youtube.com/watch?v={video_id}', 'format': 'json'},
                timeout=6,
            )
            if response.ok:
                entry['title'] = (response.json().get('title') or '').strip() or video_id
                return
        except Exception:
            pass
        entry['title'] = video_id

    workers = [threading.Thread(target=fetch, args=(entry,), daemon=True) for entry in missing]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=8)


def _search_youtube_shorts(query, max_results, extra_query=''):
    """Busca Shorts reales: pestaña /hashtag/.../shorts y filtro de búsqueda."""
    seen = set()
    found = []
    fetch_limit = max(max_results + 10, 20)
    sources = []
    slugs = []
    full_slug = _hashtag_slug(query)
    if full_slug:
        slugs.append(full_slug)
    for word in re.findall(r'\w+', (query or '').lstrip('#'), flags=re.UNICODE):
        word_slug = _hashtag_slug(word)
        if word_slug and word_slug not in slugs:
            slugs.append(word_slug)
    for slug in slugs:
        sources.append((f'https://www.youtube.com/hashtag/{quote(slug)}/shorts', True))
    search_text = (query + extra_query).strip()
    sources.append((
        f'https://www.youtube.com/results?search_query={quote_plus(search_text)}&sp=EgIQCQ%3D%3D',
        False,
    ))

    for url, from_shorts_tab in sources:
        if len(found) >= max_results:
            break
        ydl_opts = youtube_ydl_opts(
            extract_flat='in_playlist',
            skip_download=True,
            force_generic_extractor=False,
            noplaylist=False,
            playlistend=fetch_limit,
            use_cookiefile=False,
        )
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as err:
            print(f"[Shorts] No se pudo leer una fuente ({err})")
            continue
        for entry in info.get('entries') or []:
            if not entry or not entry.get('id'):
                continue
            if not from_shorts_tab and not _is_youtube_short(entry):
                continue
            video_id = entry['id']
            if video_id in seen:
                continue
            seen.add(video_id)
            found.append(entry)
            if len(found) >= max_results:
                break

    print(f"[Shorts] {len(found)}/{max_results} resultados")
    _fill_short_titles(found)
    return found


def youtube_channel_tab_url(url):
    text = (url or '').strip().rstrip('/')
    if not text:
        return text
    lower = text.lower()
    if any(lower.endswith(suffix) for suffix in ('/videos', '/streams', '/shorts', '/releases')):
        return text
    return f'{text}/videos'


_YT_VIDEO_ID_RE = re.compile(r'(?:v=|/v/|/shorts/|youtu\.be/)([^"&?/\s]{11})')
_YT_CHANNEL_RE = re.compile(
    r'youtube\.com/(?:channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+|@[^/?#]+)',
    re.I,
)


def youtube_video_id(url):
    match = _YT_VIDEO_ID_RE.search(url or '')
    return match.group(1) if match else None


def is_youtube_playlist_url(url):
    lower = (url or '').lower()
    if 'list=' not in lower:
        return False
    return youtube_video_id(url) is None


def is_youtube_channel_url(url):
    text = url or ''
    if youtube_video_id(text) or is_youtube_playlist_url(text):
        return False
    return bool(_YT_CHANNEL_RE.search(text))


def fetch_youtube_channel_videos(channel_url, limit=30):
    """Vídeos recientes de un canal. No registra la URL."""
    limit = max(5, min(int(limit or 30), 50))
    tab_url = youtube_channel_tab_url(channel_url)
    ydl_opts = youtube_ydl_opts(
        extract_flat='in_playlist',
        skip_download=True,
        force_generic_extractor=False,
        noplaylist=False,
        playlistend=limit,
    )
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(tab_url, download=False)
    videos = []
    seen = set()
    for entry in info.get('entries') or []:
        if not entry or not entry.get('id'):
            continue
        video_id = str(entry.get('id'))
        if len(video_id) != 11 or video_id in seen:
            continue
        seen.add(video_id)
        videos.append({
            'title': (entry.get('title') or '').strip() or 'YouTube',
            'id': video_id,
            'url': f'https://www.youtube.com/watch?v={video_id}',
            'duration': entry.get('duration'),
        })
        if len(videos) >= limit:
            break
    channel_name = (info.get('channel') or info.get('uploader') or info.get('title') or '').strip()
    return videos, channel_name


class YouTubeSearchDialog:
    def __init__(
        self,
        parent,
        play_callback,
        load_playlist_callback=None,
        enqueue_callback=None,
        youtube_handler=None,
        favorite_callback=None,
        unfavorite_callback=None,
        is_favorite_callback=None,
    ):
        self.parent = parent
        self.play_callback = play_callback
        self.load_playlist_callback = load_playlist_callback
        self.enqueue_callback = enqueue_callback
        self.youtube_handler = youtube_handler
        self.favorite_callback = favorite_callback
        self.unfavorite_callback = unfavorite_callback
        self.is_favorite_callback = is_favorite_callback
        self._posted_menu = None
        self.window = tk.Toplevel(parent)
        self.window.title("Buscar en YouTube")
        self.window.geometry("780x560")
        self.window.minsize(640, 420)
        style_window(self.window)
        set_window_icon(self.window)
        center_window(self.window, 780, 560)
        self.create_widgets()
        if self.youtube_handler:
            self.youtube_handler.add_session_listener(self.update_youtube_session_ui)
            self.update_youtube_session_ui(self.youtube_handler.session_view())
        self.window.protocol('WM_DELETE_WINDOW', self._on_close)

    def create_widgets(self):
        main_frame = ttk.Frame(self.window, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text='Buscar en YouTube', style='PageTitle.TLabel').pack(anchor=tk.W)
        ttk.Label(
            main_frame,
            text='Vídeos, Shorts, listas y canales. Pulsa ☆ junto al nombre para guardarlo en favoritos.',
            style='Muted.TLabel',
        ).pack(anchor=tk.W, pady=(0, 8))

        session_frame = ttk.Frame(main_frame)
        session_frame.pack(fill=tk.X, pady=(0, 12))
        self._yt_session_label = ttk.Label(session_frame, text='Sesión YouTube: …', style='Muted.TLabel')
        self._yt_session_label.pack(side=tk.LEFT)
        ttk.Button(
            session_frame,
            text="Reexportar cookies",
            command=self.reexport_youtube_cookies,
        ).pack(side=tk.LEFT, padx=(10, 0))
        
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.bind('<Return>', lambda e: self.search())
        search_entry.focus_set()

        ttk.Button(search_frame, text="Buscar", style='Accent.TButton', command=self.search).pack(side=tk.LEFT, padx=(8, 0))

        # Frame de filtros
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Filtro por tipo de contenido
        ttk.Label(filter_frame, text="Tipo:").pack(side=tk.LEFT, padx=(0, 2))
        self.type_var = tk.StringVar(value="Vídeos")
        type_combobox = ttk.Combobox(
            filter_frame, textvariable=self.type_var,
            values=["Vídeos", "Shorts", "Listas de reproducción", "Canales"],
            width=15, state="readonly"
        )
        type_combobox.pack(side=tk.LEFT, padx=(0, 10))
        type_combobox.bind('<<ComboboxSelected>>', self._on_type_change)
        
        # Filtro por fecha
        ttk.Label(filter_frame, text="Fecha:").pack(side=tk.LEFT, padx=(0, 2))
        self.date_var = tk.StringVar(value="Cualquier fecha")
        date_combobox = ttk.Combobox(
            filter_frame, textvariable=self.date_var,
            values=["Cualquier fecha", "Hoy", "Esta semana", "Este mes", "Este año"],
            width=15, state="readonly"
        )
        date_combobox.pack(side=tk.LEFT, padx=(0, 10))
        
        # Filtro por duración
        ttk.Label(filter_frame, text="Duración:").pack(side=tk.LEFT, padx=(0, 2))
        self.duration_var = tk.StringVar(value="Cualquier duración")
        self.duration_combobox = ttk.Combobox(
            filter_frame, textvariable=self.duration_var,
            values=["Cualquier duración", "Corto (<4 min)", "Medio (4-20 min)", "Largo (>20 min)"],
            width=15, state="readonly"
        )
        self.duration_combobox.pack(side=tk.LEFT, padx=(0, 10))
        
        # Filtro por orden
        ttk.Label(filter_frame, text="Ordenar por:").pack(side=tk.LEFT, padx=(0, 2))
        self.sort_var = tk.StringVar(value="Relevancia")
        sort_combobox = ttk.Combobox(
            filter_frame, textvariable=self.sort_var,
            values=["Relevancia", "Fecha", "Vistas", "Valoración"],
            width=15, state="readonly"
        )
        sort_combobox.pack(side=tk.LEFT)

        # Frame para la lista de resultados
        results_frame = ttk.Frame(main_frame)
        results_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(results_frame, text="Número de resultados:").pack(side=tk.LEFT, padx=(0, 2))
        self.results_count = tk.IntVar(value=10)
        results_spinbox = ttk.Spinbox(
            results_frame, from_=1, to=100, textvariable=self.results_count, width=4
        )
        results_spinbox.pack(side=tk.LEFT)
        
        # Frame para la lista de resultados y barra de desplazamiento
        results_list_frame = ttk.Frame(main_frame)
        results_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(results_list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.results_listbox = tk.Listbox(
            results_list_frame,
            yscrollcommand=scrollbar.set,
            selectmode=tk.EXTENDED,
        )
        self.results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        style_listbox(self.results_listbox)
        scrollbar.config(command=self.results_listbox.yview)
        
        # Configurar el menú contextual
        self.results_listbox.bind('<Double-Button-1>', self.play_selected)
        self.results_listbox.bind('<Button-1>', self._on_result_click, add='+')
        self.results_listbox.bind('<Motion>', self._on_result_motion)
        self.results_listbox.bind('<Leave>', lambda e: self._set_list_cursor(''))
        self.results_listbox.bind('<Button-3>', self.show_context_menu)
        self.results_listbox.bind('<Control-Return>', lambda e: self.enqueue_selected() or 'break')
        self.results_listbox.bind('<Control-s>', lambda e: self.add_selected_to_favorites() or 'break')
        self.window.bind_all('<ButtonPress-1>', self._on_press_dismiss_menu, add='+')
        self.window.bind_all('<Escape>', self._on_escape_dismiss_menu, add='+')

        # Barra de progreso
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.pack(fill=tk.X, pady=(5, 10))
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='indeterminate')
        
        # Frame de botones
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        play_btn = ttk.Button(button_frame, text="Reproducir", style='Accent.TButton', command=self.play_selected)
        play_btn.pack(side=tk.LEFT, padx=(0, 5))

        queue_btn = ttk.Button(button_frame, text="Añadir a la cola", command=self.enqueue_selected)
        queue_btn.pack(side=tk.LEFT, padx=(0, 5))
        if not self.enqueue_callback:
            queue_btn.configure(state='disabled')

        fav_btn = ttk.Button(button_frame, text="Añadir a favoritos", command=self.add_selected_to_favorites)
        fav_btn.pack(side=tk.LEFT, padx=(0, 5))
        if not self.favorite_callback:
            fav_btn.configure(state='disabled')
        
        download_video_btn = ttk.Button(button_frame, text="Descargar Vídeo+Audio", 
                                      command=lambda: self.download_selected(False))
        download_video_btn.pack(side=tk.LEFT, padx=5)
        
        download_audio_btn = ttk.Button(button_frame, text="Descargar SOLO Audio", 
                                      command=lambda: self.download_selected(True))
        download_audio_btn.pack(side=tk.LEFT, padx=5)
        
        close_btn = ttk.Button(button_frame, text="Cerrar", command=self._on_close)
        close_btn.pack(side=tk.RIGHT)

        self.queue_status = ttk.Label(main_frame, text='', style='Muted.TLabel')
        self.queue_status.pack(anchor=tk.W, pady=(8, 0))
        
        self.results = []
        self.result_types = []
        self.result_details = []

    def _on_close(self):
        self._dismiss_context_menu()
        if self.youtube_handler:
            self.youtube_handler.remove_session_listener(self.update_youtube_session_ui)
        self.window.destroy()

    def update_youtube_session_ui(self, info=None):
        if not getattr(self, '_yt_session_label', None):
            return
        if info is None and self.youtube_handler:
            info = self.youtube_handler.session_view()
        info = info or {'ok': False, 'label': 'caducada'}
        ok = bool(info.get('ok'))
        text = f"Sesión YouTube: {'OK' if ok else 'caducada'}"
        style = 'SessionOk.TLabel' if ok else 'SessionBad.TLabel'
        try:
            self._yt_session_label.configure(text=text, style=style)
        except tk.TclError:
            pass

    def reexport_youtube_cookies(self):
        if self.youtube_handler:
            self.youtube_handler.reexport_youtube_cookies()
            return
        messagebox.showinfo(
            'Cookies de YouTube',
            'Abre el reproductor para exportar cookies.txt desde el navegador.',
        )

    def _on_type_change(self, event=None):
        shorts = self.type_var.get() == "Shorts"
        self.duration_combobox.configure(state='disabled' if shorts else 'readonly')
        if shorts:
            self.duration_var.set("Cualquier duración")

    def format_duration(self, seconds):
        """Formatea la duración en segundos a formato HH:MM:SS o MM:SS"""
        if not seconds:
            return ""
        
        try:
            seconds = int(seconds)
            if seconds < 3600:  # Menos de una hora
                return f"{seconds // 60}:{seconds % 60:02d}"
            else:
                return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
        except:
            return ""

    def check_ffmpeg(self):
        """Verifica si FFmpeg está instalado en el sistema."""
        try:
            result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def search(self):
        query = self.search_var.get().strip()
        if not query:
            messagebox.showinfo("Info", "Introduce un término de búsqueda.")
            return
        
        self.results_listbox.delete(0, tk.END)
        self.results = []
        self.result_types = []
        self.result_details = []
        
        self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_bar.start(10)
        
        search_query = query
        
        # Filtro de fecha
        date_filter = self.date_var.get()
        date_query = ""
        if date_filter == "Hoy":
            date_query = " after:today"
        elif date_filter == "Esta semana":
            date_query = f" after:{(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')}"
        elif date_filter == "Este mes":
            date_query = f" after:{(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')}"
        elif date_filter == "Este año":
            date_query = f" after:{(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')}"
        
        # Filtro de duración
        duration_filter = self.duration_var.get()
        duration_query = ""
        if duration_filter == "Corto (<4 min)":
            duration_query = " short"
        elif duration_filter == "Medio (4-20 min)":
            duration_query = " medium"
        elif duration_filter == "Largo (>20 min)":
            duration_query = " long"
        
        # Aplicar filtros según el tipo
        tipo = self.type_var.get()
        if tipo == "Vídeos":
            search_query += date_query + duration_query
        elif tipo == "Shorts":
            search_query += date_query
        elif tipo == "Listas de reproducción":
            search_query += " playlist" + date_query

        def perform_search():
            try:
                try:
                    max_results = int(self.results_count.get())
                except (tk.TclError, TypeError, ValueError):
                    max_results = 10
                max_results = min(max(max_results, 1), 100)
                if tipo == "Shorts":
                    shorts = _search_youtube_shorts(query, max_results, extra_query=date_query)

                    def update_shorts_ui():
                        if not shorts:
                            messagebox.showinfo("Info", "No se encontraron Shorts con esa búsqueda.")
                            self.progress_bar.stop()
                            self.progress_bar.pack_forget()
                            return
                        for entry in shorts:
                            title = (entry.get('title') or '').strip() or entry.get('id')
                            duration = entry.get('duration')
                            duration_str = self.format_duration(duration) if duration else ""
                            self.result_types.append("video")
                            self.results.append(f"https://www.youtube.com/shorts/{entry.get('id')}")
                            self.result_details.append({
                                'title': title,
                                'id': entry.get('id'),
                                'duration': duration,
                            })
                            display_text = youtube_result_line(
                                'short',
                                title,
                                duration_str,
                                favorite=self._url_is_favorite(
                                    f"https://www.youtube.com/shorts/{entry.get('id')}"
                                ),
                            )
                            self.results_listbox.insert(tk.END, display_text)
                        self.progress_bar.stop()
                        self.progress_bar.pack_forget()

                    self.window.after(0, update_shorts_ui)
                    return

                ydl_opts = youtube_ydl_opts(
                    extract_flat=True,
                    skip_download=True,
                    force_generic_extractor=False,
                    noplaylist=False,
                    playlistend=max_results + 5,
                )

                query_q = quote_plus(search_query)
                if tipo == "Listas de reproducción":
                    sp = "EgIQAw%3D%3D"
                elif tipo == "Canales":
                    sp = "EgIQAg%3D%3D"
                else:
                    sp = "EgIQAQ%3D%3D"
                search_url = (
                    f"https://www.youtube.com/results?search_query={query_q}"
                    f"&hl=es&gl=ES&sp={sp}"
                )

                def extract_search(opts):
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(search_url, download=False)

                try:
                    info = extract_search(ydl_opts)
                except Exception as err:
                    if '413' not in str(err):
                        raise
                    slim_youtube_cookies_file()
                    retry_opts = youtube_ydl_opts(
                        extract_flat=True,
                        skip_download=True,
                        force_generic_extractor=False,
                        noplaylist=False,
                        playlistend=max_results + 5,
                    )
                    try:
                        info = extract_search(retry_opts)
                    except Exception as err2:
                        if '413' not in str(err2):
                            raise
                        print('[YouTube] Búsqueda 413: reintentando sin cookies.txt hinchado')
                        info = extract_search(youtube_ydl_opts(
                            extract_flat=True,
                            skip_download=True,
                            force_generic_extractor=False,
                            noplaylist=False,
                            playlistend=max_results + 5,
                            use_cookiefile=False,
                        ))

                results_count = 0
                found_playlist = False

                def update_ui():
                    nonlocal results_count, found_playlist
                    for entry in info.get('entries') or []:
                        if not entry or results_count >= max_results:
                            break

                        title = entry.get('title', 'Sin título')
                        duration = entry.get('duration')
                        duration_str = self.format_duration(duration) if duration else ""

                        if tipo == "Listas de reproducción":
                            playlist_id = None
                            if entry.get('url') and 'list=' in entry.get('url'):
                                playlist_id = re.search(r'list=([^&]+)', entry.get('url'))
                                if playlist_id:
                                    playlist_id = playlist_id.group(1)
                                    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                                    self.result_types.append("playlist")
                                    self.results.append(playlist_url)
                                    self.result_details.append({
                                        'title': title,
                                        'id': playlist_id,
                                        'duration': duration
                                    })
                                    self.results_listbox.insert(
                                        tk.END,
                                        youtube_result_line(
                                            'playlist',
                                            title,
                                            favorite=self._url_is_favorite(playlist_url),
                                        ),
                                    )
                                    found_playlist = True
                                    results_count += 1
                        elif tipo == "Vídeos":
                            if entry.get('id'):
                                url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                                self.result_types.append("video")
                                self.results.append(url)
                                self.result_details.append({
                                    'title': title,
                                    'id': entry.get('id'),
                                    'duration': duration
                                })
                                display_text = youtube_result_line(
                                    'video',
                                    title,
                                    duration_str,
                                    favorite=self._url_is_favorite(url),
                                )
                                self.results_listbox.insert(tk.END, display_text)
                                results_count += 1

                        elif tipo == "Canales":
                            channel_id = entry.get('channel_id') or entry.get('uploader_id') or entry.get('id')
                            if channel_id:
                                url = f"https://www.youtube.com/channel/{channel_id}"
                                self.result_types.append("channel")
                                self.results.append(url)
                                self.result_details.append({
                                    'title': title,
                                    'id': channel_id
                                })
                                self.results_listbox.insert(
                                    tk.END,
                                    youtube_result_line(
                                        'channel',
                                        title,
                                        favorite=self._url_is_favorite(url),
                                    ),
                                )
                                results_count += 1

                    if tipo == "Listas de reproducción" and not found_playlist:
                        messagebox.showinfo("Info", "No se encontraron listas de reproducción con ese nombre.")

                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()

                self.window.after(0, update_ui)
                    
            except Exception as e:
                err = e

                def show_error(exc=err):
                    if self.youtube_handler:
                        self.youtube_handler.mark_session_from_error(exc)
                    if youtube_auth_blocked(exc):
                        messagebox.showerror("Sesión YouTube", youtube_auth_help())
                    elif '413' in str(exc):
                        messagebox.showerror(
                            "Error",
                            "YouTube rechazó la búsqueda (petición demasiado grande).\n"
                            "Suele ser cookies.txt hinchado. Pulsa «Reexportar cookies» e inténtalo de nuevo.",
                        )
                    else:
                        messagebox.showerror("Error", f"No se pudo realizar la búsqueda: {exc}")
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()

                self.window.after(0, show_error)

        threading.Thread(target=perform_search, daemon=True).start()

    def _window_alive(self):
        window = getattr(self, 'window', None)
        if window is None:
            return False
        try:
            return bool(window.winfo_exists())
        except tk.TclError:
            return False

    def _url_is_favorite(self, url):
        checker = self.is_favorite_callback
        if not checker or not url:
            return False
        try:
            return bool(checker(url))
        except Exception:
            return False

    def _star_hit_width(self):
        try:
            face = tkfont.nametofont(self.results_listbox.cget('font'))
            return face.measure(f'{STAR_ON} ')
        except Exception:
            return 16

    def _set_list_cursor(self, name):
        try:
            self.results_listbox.configure(cursor=name)
        except tk.TclError:
            pass

    def _on_result_motion(self, event):
        if not self.favorite_callback:
            return
        index = self.results_listbox.nearest(event.y)
        if 0 <= index < len(self.results) and youtube_star_hit(event.x, self._star_hit_width()):
            self._set_list_cursor('hand2')
        else:
            self._set_list_cursor('')

    def _on_result_click(self, event):
        self._dismiss_context_menu()
        if not self.favorite_callback:
            return
        index = self.results_listbox.nearest(event.y)
        if not (0 <= index < len(self.results)):
            return
        if not youtube_star_hit(event.x, self._star_hit_width()):
            return
        self.results_listbox.selection_clear(0, tk.END)
        self.results_listbox.selection_set(index)
        self.results_listbox.activate(index)
        self._toggle_favorite_at(index)
        return 'break'

    def _result_kind_label(self, index):
        tipo = self.result_types[index] if index < len(self.result_types) else 'video'
        url = self.results[index] if index < len(self.results) else ''
        if tipo == 'channel':
            return 'channel'
        if tipo == 'playlist':
            return 'playlist'
        if '/shorts/' in (url or ''):
            return 'short'
        return 'video'

    def _refresh_result_row(self, index, keep_select=True):
        if not (0 <= index < len(self.results)):
            return
        duration = ''
        if index < len(self.result_details):
            duration = self.format_duration(self.result_details[index].get('duration'))
        line = youtube_result_line(
            self._result_kind_label(index),
            self._result_title(index),
            duration,
            favorite=self._url_is_favorite(self.results[index]),
        )
        try:
            self.results_listbox.delete(index)
            self.results_listbox.insert(index, line)
            if keep_select:
                self.results_listbox.selection_set(index)
        except tk.TclError:
            pass

    def _toggle_favorite_at(self, index):
        if not (0 <= index < len(self.results)):
            return
        url = self.results[index]
        title = self._result_title(index)
        if self._url_is_favorite(url):
            removed = False
            if self.unfavorite_callback:
                try:
                    removed = bool(self.unfavorite_callback(title, url))
                except Exception:
                    removed = False
            if removed:
                self._set_queue_status(f'Se quitó de favoritos: {title}')
            else:
                self._set_queue_status(f'«{title}» no se pudo quitar de favoritos.')
        else:
            added = False
            if self.favorite_callback:
                try:
                    added = bool(self.favorite_callback(title, url))
                except Exception:
                    added = False
            if added:
                self._set_queue_status(f'En favoritos: {title}. Ábrelos con ★ Favoritos.')
            else:
                self._set_queue_status(f'«{title}» ya estaba en favoritos.')
        self._refresh_result_row(index)

    def _menu_is_mapped(self, menu):
        try:
            return bool(menu) and menu.winfo_ismapped()
        except tk.TclError:
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

    def _dismiss_context_menu(self):
        menu = getattr(self, '_posted_menu', None)
        self._posted_menu = None
        if menu is None:
            return
        try:
            menu.unpost()
        except tk.TclError:
            pass
        try:
            menu.grab_release()
        except tk.TclError:
            pass
        try:
            menu.destroy()
        except tk.TclError:
            pass

    def _on_press_dismiss_menu(self, event):
        if not self._window_alive():
            return
        menu = getattr(self, '_posted_menu', None)
        if not menu:
            return
        if self._event_on_menu(event, menu):
            return
        self._dismiss_context_menu()

    def _on_escape_dismiss_menu(self, event=None):
        if not self._window_alive():
            return
        if getattr(self, '_posted_menu', None):
            self._dismiss_context_menu()
            return 'break'

    def _choose_from_menu(self, action):
        def run():
            self._dismiss_context_menu()
            action()
        if self._window_alive():
            self.window.after_idle(run)
        else:
            action()

    def show_context_menu(self, event):
        """Muestra el menú contextual al hacer clic derecho en un elemento"""
        selection = self.results_listbox.nearest(event.y)
        if not (0 <= selection < len(self.results)):
            return
        self._dismiss_context_menu()
        self.results_listbox.selection_clear(0, tk.END)
        self.results_listbox.selection_set(selection)
        self.results_listbox.activate(selection)

        context_menu = tk.Menu(self.window, tearoff=0)
        style_menu_tree(context_menu)
        tipo = self.result_types[selection]
        choose = self._choose_from_menu

        if tipo == "video":
            context_menu.add_command(label="Reproducir", command=lambda: choose(self.play_selected))
            context_menu.add_command(label="Añadir a la cola", command=lambda: choose(self.enqueue_selected))
            if self.favorite_callback:
                context_menu.add_command(
                    label="Añadir a favoritos",
                    command=lambda: choose(self.add_selected_to_favorites),
                )
            context_menu.add_command(
                label="Descargar vídeo",
                command=lambda: choose(lambda: self.download_selected(False)),
            )
            context_menu.add_command(
                label="Descargar audio",
                command=lambda: choose(lambda: self.download_selected(True)),
            )
            context_menu.add_separator()
            context_menu.add_command(
                label="Abrir en navegador",
                command=lambda: choose(lambda: webbrowser.open_new(self.results[selection])),
            )
        elif tipo == "playlist":
            context_menu.add_command(label="Cargar lista", command=lambda: choose(self.play_selected))
            context_menu.add_command(
                label="Añadir lista a la cola",
                command=lambda: choose(self.enqueue_selected),
            )
            if self.favorite_callback:
                context_menu.add_command(
                    label="Añadir a favoritos",
                    command=lambda: choose(self.add_selected_to_favorites),
                )
            context_menu.add_separator()
            context_menu.add_command(
                label="Abrir en navegador",
                command=lambda: choose(lambda: webbrowser.open_new(self.results[selection])),
            )
        elif tipo == "channel":
            context_menu.add_command(
                label="Ver vídeos recientes",
                command=lambda: choose(self.play_selected),
            )
            context_menu.add_command(
                label="Añadir recientes a la cola",
                command=lambda: choose(self.enqueue_selected),
            )
            if self.favorite_callback:
                context_menu.add_command(
                    label="Añadir canal a favoritos",
                    command=lambda: choose(self.add_selected_to_favorites),
                )
            context_menu.add_separator()
            context_menu.add_command(
                label="Abrir en navegador",
                command=lambda: choose(lambda: webbrowser.open_new(self.results[selection])),
            )
        else:
            try:
                context_menu.destroy()
            except tk.TclError:
                pass
            return

        try:
            context_menu.post(event.x_root, event.y_root)
            context_menu.update_idletasks()
            self._posted_menu = context_menu
        except tk.TclError:
            try:
                context_menu.destroy()
            except tk.TclError:
                pass
            self._posted_menu = None

    def play_selected(self, event=None):
        selection = self.results_listbox.curselection()
        if selection:
            index = selection[0]
            url = self.results[index]
            tipo = self.result_types[index] if hasattr(self, 'result_types') else "video"
            if tipo == "video":
                label = self._result_title(index)
                self.play_callback(url, title=label)
                self.window.destroy()
            elif tipo == "playlist":
                self.load_playlist_videos(url, close_after=True)
            elif tipo == "channel":
                self.open_channel_videos(url, title=self._result_title(index))

    def _result_title(self, index):
        details = None
        if 0 <= index < len(self.result_details):
            details = self.result_details[index]
        if details and details.get('title'):
            return details['title']
        try:
            text = self.results_listbox.get(index)
        except tk.TclError:
            return 'YouTube'
        if text.startswith(STAR_ON) or text.startswith(STAR_OFF):
            text = text[1:].lstrip()
        return text or 'YouTube'

    def add_selected_to_favorites(self, event=None):
        if not self.favorite_callback:
            self._set_queue_status('Abre la búsqueda desde el reproductor para guardar favoritos.')
            return
        selection = self.results_listbox.curselection()
        if not selection:
            self._set_queue_status('Selecciona un resultado para guardarlo en favoritos.')
            return
        added = 0
        skipped = 0
        last_title = ''
        for index in selection:
            url = self.results[index] if index < len(self.results) else ''
            title = self._result_title(index)
            last_title = title
            if not url:
                skipped += 1
                continue
            try:
                if self.favorite_callback(title, url):
                    added += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        if added == 1 and skipped == 0:
            self._set_queue_status(f'En favoritos: {last_title}. Ábrelos con ★ Favoritos.')
        elif added:
            extra = f' ({skipped} ya estaban o no se pudieron guardar)' if skipped else ''
            self._set_queue_status(f'{added} resultados en favoritos.{extra}')
        else:
            self._set_queue_status('Esos resultados ya estaban en favoritos.')
        for index in selection:
            self._refresh_result_row(index, keep_select=False)
        for index in selection:
            try:
                self.results_listbox.selection_set(index)
            except tk.TclError:
                pass

    def _set_queue_status(self, text):
        label = getattr(self, 'queue_status', None)
        if label:
            try:
                label.configure(text=text)
            except tk.TclError:
                pass

    def enqueue_selected(self, event=None):
        if not self.enqueue_callback:
            return
        selection = self.results_listbox.curselection()
        if not selection:
            self._set_queue_status('Selecciona uno o más resultados para la cola.')
            return
        videos = []
        playlists = []
        channels = []
        skipped = 0
        for index in selection:
            tipo = self.result_types[index] if index < len(self.result_types) else 'video'
            url = self.results[index] if index < len(self.results) else ''
            if tipo == 'video' and url:
                videos.append((self._result_title(index), url))
            elif tipo == 'playlist' and url:
                playlists.append((self._result_title(index), url))
            elif tipo == 'channel' and url:
                channels.append((self._result_title(index), url))
            else:
                skipped += 1
        if videos:
            added = self.enqueue_callback(videos)
            if added:
                if added == 1:
                    self._set_queue_status(f'Añadido a la cola: {videos[0][0]}')
                else:
                    self._set_queue_status(f'{added} vídeos añadidos a la cola.')
            else:
                self._set_queue_status('Esos vídeos ya estaban en la cola.')
        if playlists:
            self._enqueue_playlists(playlists, skipped)
            return
        if channels:
            title, url = channels[0]
            self.open_channel_videos(url, title=title, enqueue=True)
            return
        if skipped and not videos:
            self._set_queue_status('Selecciona un vídeo, una lista o un canal.')

    def _enqueue_playlists(self, playlists, skipped=0):
        self._set_queue_status('Añadiendo lista a la cola…')
        self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_bar.start(10)

        def work():
            collected = []
            errors = []
            for title, url in playlists:
                try:
                    videos = self._fetch_playlist_videos(url)
                    if videos:
                        collected.extend(videos)
                    else:
                        errors.append(title)
                except Exception as exc:
                    errors.append(f'{title}: {exc}')

            def done():
                self.progress_bar.stop()
                self.progress_bar.pack_forget()
                added = self.enqueue_callback(collected) if collected else 0
                if added:
                    self._set_queue_status(f'{added} vídeos de lista añadidos a la cola.')
                elif errors:
                    self._set_queue_status('No se pudo añadir la lista a la cola.')
                else:
                    self._set_queue_status('Esos vídeos ya estaban en la cola.')
                if skipped and not added:
                    self._set_queue_status('Selecciona un vídeo, una lista o un canal.')

            self.window.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def download_selected(self, audio_only=False):
        """Descarga el vídeo seleccionado o solo su audio"""
        if audio_only and not self.check_ffmpeg():
            messagebox.showerror("Error", "FFmpeg no está instalado. Para descargar audio necesitas instalar FFmpeg:\n\nEn Ubuntu/Debian: sudo apt install ffmpeg\nEn Fedora: sudo dnf install ffmpeg")
            return

        selection = self.results_listbox.curselection()
        if not selection:
            messagebox.showinfo("Info", "Selecciona un vídeo para descargar.")
            return
        
        index = selection[0]
        tipo = self.result_types[index]
        url = self.results[index]
        
        if tipo != "video":
            messagebox.showinfo("Info", "Solo se pueden descargar vídeos individuales.")
            return
        
        try:
            title = self.result_details[index]['title']
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            
            file_types = [("Archivos MP3", "*.mp3")] if audio_only else [("Archivos MP4", "*.mp4")]
            default_ext = ".mp3" if audio_only else ".mp4"
            
            filepath = filedialog.asksaveasfilename(
                title="Guardar " + ("audio" if audio_only else "vídeo"),
                initialdir=app_config.get_download_dir(),
                initialfile=safe_title + default_ext,
                defaultextension=default_ext,
                filetypes=file_types + [("Todos los archivos", "*.*")]
            )
            
            if not filepath:
                return
                
            download_thread = threading.Thread(
                target=self._execute_download, 
                args=(url, filepath, title, audio_only)
            )
            download_thread.start()
            
            tipo_descarga = "audio" if audio_only else "vídeo"
            messagebox.showinfo("Descarga iniciada", 
                              f"Iniciando descarga del {tipo_descarga} de '{title}'. Se te notificará cuando termine.")
                
        except Exception as e:
            if self.youtube_handler:
                self.youtube_handler.mark_session_from_error(e)
            if youtube_auth_blocked(e):
                messagebox.showerror("Sesión YouTube", youtube_auth_help())
            else:
                messagebox.showerror("Error", f"No se pudo iniciar la descarga: {str(e)}")

    def _execute_download(self, url, filepath, title, audio_only=False):
        """Ejecuta la descarga del vídeo de YouTube."""
        try:
            ydl_opts = youtube_ydl_opts(
                format='bestaudio/best' if audio_only else 'best',
                outtmpl=filepath,
                quiet=False,
                noprogress=False,
            )
            
            if audio_only:
                ydl_opts.update({
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            self.window.after(0, lambda: messagebox.showinfo(
                "Descarga completada", 
                f"'{title}' descargado en:\n{filepath}"
            ))
            
        except Exception as e:
            if self.youtube_handler:
                self.youtube_handler.mark_session_from_error(e)
            if youtube_auth_blocked(e):
                self.window.after(0, lambda: messagebox.showerror(
                    "Sesión YouTube",
                    youtube_auth_help(),
                ))
            else:
                error_message = str(e)
                self.window.after(0, lambda msg=error_message: messagebox.showerror(
                    "Error de descarga",
                    f"No se pudo descargar '{title}':\n{msg}\n\nPosibles soluciones:\n"
                    f"1. Verifica que el enlace sea accesible\n"
                    f"2. Prueba con otro vídeo\n"
                    f"3. Comprueba tu conexión a internet"
                ))
            
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass

    def load_playlist_videos(self, playlist_url, close_after=False):
        if getattr(self, '_loading_playlist', False):
            return
        self._loading_playlist = True
        self._set_queue_status('Cargando lista…')
        self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_bar.start(10)
        window = self.window

        def work():
            err = None
            channels = None
            try:
                channels = self._fetch_playlist_videos(playlist_url)
            except Exception as exc:
                err = exc

            def done():
                self._loading_playlist = False
                try:
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
                except tk.TclError:
                    pass
                if err:
                    if self.youtube_handler:
                        self.youtube_handler.mark_session_from_error(err)
                    if youtube_auth_blocked(err):
                        messagebox.showerror("Sesión YouTube", youtube_auth_help())
                    else:
                        messagebox.showerror("Error", f"No se pudo obtener la playlist: {err}")
                    return
                if not channels:
                    messagebox.showinfo("Info", "No se encontraron vídeos en la playlist.")
                    return
                if self.load_playlist_callback:
                    self.load_playlist_callback(channels)
                if close_after:
                    try:
                        self.window.destroy()
                    except tk.TclError:
                        pass

            try:
                window.after(0, done)
            except tk.TclError:
                self._loading_playlist = False
                if channels and self.load_playlist_callback:
                    try:
                        self.parent.after(0, lambda: self.load_playlist_callback(channels))
                    except tk.TclError:
                        pass

        threading.Thread(target=work, daemon=True).start()

    def open_channel_videos(self, channel_url, title='', enqueue=False):
        if getattr(self, '_loading_playlist', False):
            return
        self._loading_playlist = True
        label = title or 'canal'
        if enqueue:
            self._set_queue_status(f'Añadiendo vídeos recientes de {label}…')
        else:
            self._set_queue_status(f'Cargando vídeos recientes de {label}…')
        self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_bar.start(10)
        window = self.window
        try:
            limit = max(10, min(int(self.results_count.get() or 20), 50))
        except (TypeError, ValueError, tk.TclError):
            limit = 20

        def work():
            err = None
            videos = []
            channel_name = label
            try:
                videos, channel_name = self._fetch_channel_videos(channel_url, limit=limit)
                channel_name = channel_name or label
            except Exception as exc:
                err = exc

            def done():
                self._loading_playlist = False
                try:
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
                except tk.TclError:
                    pass
                if err:
                    if self.youtube_handler:
                        self.youtube_handler.mark_session_from_error(err)
                    if youtube_auth_blocked(err):
                        messagebox.showerror("Sesión YouTube", youtube_auth_help())
                    else:
                        messagebox.showerror("Error", f"No se pudieron leer los vídeos del canal: {err}")
                    return
                if not videos:
                    messagebox.showinfo("Info", "No se encontraron vídeos recientes en ese canal.")
                    return
                if enqueue:
                    items = [(item['title'], item['url']) for item in videos]
                    added = self.enqueue_callback(items) if self.enqueue_callback else 0
                    if added:
                        self._set_queue_status(
                            f'{added} vídeos de {channel_name} añadidos a la cola.'
                        )
                    else:
                        self._set_queue_status('Esos vídeos ya estaban en la cola.')
                    return
                self._replace_results_with_videos(
                    videos,
                    f'Vídeos recientes de {channel_name} ({len(videos)}).',
                )

            try:
                window.after(0, done)
            except tk.TclError:
                self._loading_playlist = False

        threading.Thread(target=work, daemon=True).start()

    def _replace_results_with_videos(self, videos, status=''):
        try:
            self.results_listbox.delete(0, tk.END)
        except tk.TclError:
            return
        self.results = []
        self.result_types = []
        self.result_details = []
        for item in videos:
            duration = item.get('duration')
            duration_str = self.format_duration(duration) if duration else ''
            self.result_types.append('video')
            self.results.append(item['url'])
            self.result_details.append({
                'title': item.get('title') or 'YouTube',
                'id': item.get('id'),
                'duration': duration,
            })
            display = youtube_result_line(
                'video',
                item.get('title') or 'YouTube',
                duration_str,
                favorite=self._url_is_favorite(item['url']),
            )
            self.results_listbox.insert(tk.END, display)
        self._set_queue_status(status)

    def _fetch_channel_videos(self, channel_url, limit=30):
        return fetch_youtube_channel_videos(channel_url, limit=limit)

    def _fetch_playlist_videos(self, playlist_url):
        ydl_opts = youtube_ydl_opts(
            extract_flat=True,
            skip_download=True,
            force_generic_extractor=False,
            noplaylist=False,
        )
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            videos = info.get('entries', []) or []
            channels = []
            for video in videos:
                if not video or not video.get('id'):
                    continue
                title = video.get('title', 'Sin título')
                video_url = f"https://www.youtube.com/watch?v={video.get('id')}"
                channels.append((title, video_url))
            return channels


