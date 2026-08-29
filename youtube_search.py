import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog, font as tkfont
import yt_dlp
import requests
import webbrowser
import threading
import os
import re
import subprocess
import base64
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, quote_plus
from youtube_player import (
    youtube_ydl_opts, youtube_auth_blocked, youtube_auth_help, slim_youtube_cookies_file,
)
from ui_theme import style_window, style_listbox, style_menu_tree, set_window_icon, center_window, get_colors
import app_config
from display_text import plain_display_text


STAR_ON = '★'
STAR_OFF = '☆'

_YT_SORT = {'relevance': 0, 'rating': 1, 'date': 2, 'views': 3}
_YT_TYPE = {'video': 1, 'channel': 2, 'playlist': 3, 'movie': 4, 'shorts': 9}
_YT_UPLOADED = {'hour': 1, 'today': 2, 'week': 3, 'month': 4, 'year': 5}
_YT_DURATION = {'short': 1, 'long': 2, 'medium': 3}
_UI_SORT = {
    'Relevancia': 'relevance',
    'Fecha': 'date',
    'Vistas': 'views',
    'Valoración': 'rating',
}
_UI_TYPE = {
    'Vídeos': 'video',
    'Shorts': 'shorts',
    'Listas de reproducción': 'playlist',
    'Canales': 'channel',
}
_UI_DATE = {
    'Hoy': 'today',
    'Esta semana': 'week',
    'Este mes': 'month',
    'Este año': 'year',
}
_UI_DURATION = {
    'Corto (<4 min)': 'short',
    'Medio (4-20 min)': 'medium',
    'Largo (>20 min)': 'long',
}


def _pb_varint(value):
    value = int(value)
    chunks = []
    while value > 0x7F:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    chunks.append(value & 0x7F)
    return bytes(chunks)


def _pb_key(field, wire=0):
    return _pb_varint((field << 3) | wire)


def youtube_search_sp(sort='relevance', result_type='video', uploaded=None, duration=None):
    """Protobuf `sp` de YouTube: tipo + orden + filtros. Fecha = más recientes primero."""
    filters = b''
    if uploaded in _YT_UPLOADED:
        filters += _pb_key(1) + _pb_varint(_YT_UPLOADED[uploaded])
    if result_type in _YT_TYPE:
        filters += _pb_key(2) + _pb_varint(_YT_TYPE[result_type])
    if duration in _YT_DURATION:
        filters += _pb_key(3) + _pb_varint(_YT_DURATION[duration])
    params = b''
    sort_n = _YT_SORT.get(sort, 0)
    if sort_n:
        params += _pb_key(1) + _pb_varint(sort_n)
    if filters:
        params += _pb_key(2, 2) + _pb_varint(len(filters)) + filters
    # El extra de yt-dlp (campo 30) rompe el orden por fecha; solo en vídeos por relevancia.
    if result_type == 'video' and not sort_n and uploaded is None and duration is None:
        params += b'\xf0\x01\x01'
    if not params:
        return None
    return base64.urlsafe_b64encode(params).decode()


_ES_RELATIVE_UNITS = {
    'segundo': 'seconds',
    'segundos': 'seconds',
    'minuto': 'minutes',
    'minutos': 'minutes',
    'hora': 'hours',
    'horas': 'hours',
    'dia': 'days',
    'dias': 'days',
    'día': 'days',
    'días': 'days',
    'semana': 'weeks',
    'semanas': 'weeks',
    'mes': 'days',
    'meses': 'days',
    'año': 'days',
    'años': 'days',
}
_ES_RELATIVE_MULTIPLIER = {
    'mes': 30,
    'meses': 30,
    'año': 365,
    'años': 365,
}
_YT_RELATIVE_TIME_PATCHED = False


def parse_relative_upload_text(text):
    """Convierte «hace 3 días» / «ayer» en datetime UTC (naive), como yt-dlp."""
    raw = (text or '').strip().lower()
    if not raw:
        return None
    if re.search(r'\bhoy\b|\bahora\b|un momento', raw):
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if re.search(r'\bayer\b', raw):
        return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    match = re.search(
        r'hace\s+(?:un[a]?\s+)?(\d+)?\s*'
        r'(segundos?|minutos?|horas?|días?|dias?|semanas?|meses?|años?)\b',
        raw,
    )
    if not match:
        return None
    amount = int(match.group(1) or 1)
    unit = match.group(2)
    amount *= _ES_RELATIVE_MULTIPLIER.get(unit, 1)
    field = _ES_RELATIVE_UNITS.get(unit)
    if not field:
        return None
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(**{field: amount})


def _ensure_spanish_relative_time():
    """yt-dlp solo entiende «3 days ago»; con el idioma en español las fechas son «hace 3 días»."""
    global _YT_RELATIVE_TIME_PATCHED
    if _YT_RELATIVE_TIME_PATCHED:
        return
    from yt_dlp.extractor.youtube._base import YoutubeBaseInfoExtractor

    original = YoutubeBaseInfoExtractor.extract_relative_time

    @classmethod
    def extract_relative_time(cls, relative_time_text):
        parsed = original(relative_time_text)
        if parsed is not None:
            return parsed
        return parse_relative_upload_text(relative_time_text)

    YoutubeBaseInfoExtractor.extract_relative_time = extract_relative_time
    _YT_RELATIVE_TIME_PATCHED = True


def _search_ydl_opts(**extra):
    """Fechas aproximadas sin traducir los títulos al inglés."""
    _ensure_spanish_relative_time()
    return youtube_ydl_opts(
        extractor_args={
            'youtubetab': {'approximate_date': ['']},
        },
        **extra,
    )


def youtube_search_sp_from_ui(tipo, sort_label, date_label=None, duration_label=None):
    result_type = _UI_TYPE.get(tipo, 'video')
    duration = None if result_type == 'shorts' else _UI_DURATION.get(duration_label)
    return youtube_search_sp(
        sort=_UI_SORT.get(sort_label, 'relevance'),
        result_type=result_type,
        uploaded=_UI_DATE.get(date_label),
        duration=duration,
    )


def _entry_recency(entry):
    if not isinstance(entry, dict):
        return 0
    for key in ('timestamp', 'release_timestamp'):
        try:
            value = int(entry.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    raw = str(entry.get('upload_date') or entry.get('release_date') or '').strip()
    digits = ''.join(ch for ch in raw if ch.isdigit())[:8]
    if len(digits) == 8:
        try:
            return int(
                datetime.strptime(digits, '%Y%m%d').replace(tzinfo=timezone.utc).timestamp()
            )
        except ValueError:
            return 0
    return 0


def sort_search_entries(entries, sort_label):
    """Si hay fechas, deja los más recientes primero al ordenar por Fecha."""
    items = [entry for entry in (entries or []) if entry]
    if _UI_SORT.get(sort_label) != 'date' or len(items) < 2:
        return items
    keyed = [(_entry_recency(entry), index, entry) for index, entry in enumerate(items)]
    if not any(recency for recency, _index, _entry in keyed):
        return items
    keyed.sort(key=lambda item: (-item[0], item[1]))
    return [entry for _recency, _index, entry in keyed]


def youtube_result_line(kind, title, duration_str='', favorite=False):
    """Texto de una fila de búsqueda, con estrella clicable al inicio."""
    mark = STAR_ON if favorite else STAR_OFF
    name = plain_display_text(title, 'YouTube')
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


def _search_youtube_shorts(query, max_results, extra_query='', search_sp=None, channel_url=None):
    """Busca Shorts: pestaña del canal, búsqueda y hashtag.

    Devuelve (entradas, keep_order). keep_order es True si ya vienen del canal
    (más recientes primero) y no hay que reordenar por fechas aproximadas.
    """
    fetch_limit = max(max_results + 10, 20)
    if channel_url:
        try:
            entries, _name = fetch_youtube_channel_tab_entries(
                channel_url, 'shorts', fetch_limit,
            )
            found = [entry for entry in entries if entry and entry.get('id')]
            if found:
                print(f"[Shorts] {len(found)}/{max_results} del canal")
                _fill_short_titles(found)
                return found[:max_results], True
        except Exception as err:
            print(f"[Shorts] No se pudo leer el canal ({err})")

    seen = set()
    found = []
    sources = []
    slugs = []
    full_slug = _hashtag_slug(query)
    if full_slug:
        slugs.append(full_slug)
    for word in re.findall(r'\w+', (query or '').lstrip('#'), flags=re.UNICODE):
        word_slug = _hashtag_slug(word)
        if word_slug and word_slug not in slugs:
            slugs.append(word_slug)
    search_text = (query + extra_query).strip()
    sp = search_sp or 'EgIQCQ=='
    search_url = (
        f'https://www.youtube.com/results?search_query={quote_plus(search_text)}'
        f'&sp={quote(sp, safe="")}'
    )
    sources.append((search_url, False))
    for slug in slugs:
        sources.append((f'https://www.youtube.com/hashtag/{quote(slug)}/shorts', True))

    for url, _from_shorts_tab in sources:
        if len(found) >= max_results:
            break
        ydl_opts = _search_ydl_opts(
            extract_flat='in_playlist',
            skip_download=True,
            force_generic_extractor=False,
            noplaylist=False,
            playlistend=fetch_limit,
            use_cookiefile=False,
            silent=True,
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
            video_id = str(entry['id'])
            if len(video_id) != 11 or video_id in seen:
                continue
            seen.add(video_id)
            found.append(entry)
            if len(found) >= max_results:
                break

    print(f"[Shorts] {len(found)}/{max_results} resultados")
    _fill_short_titles(found)
    return found, False


_CHANNEL_TABS = ('videos', 'streams', 'shorts', 'releases', 'playlists')
_YT_HANDLE_RE = re.compile(r'^@[\w.-]{2,32}$', re.I)


def youtube_channel_tab_url(url, tab='videos'):
    text = (url or '').strip().rstrip('/')
    if not text:
        return text
    if tab not in _CHANNEL_TABS:
        tab = 'videos'
    lower = text.lower()
    for suffix in _CHANNEL_TABS:
        token = '/' + suffix
        if lower.endswith(token):
            text = text[: -len(token)].rstrip('/')
            break
    return f'{text}/{tab}'


def channel_url_from_query(query):
    """URL de canal si la búsqueda es un @handle o un enlace de canal."""
    text = (query or '').strip()
    if not text:
        return None
    if _YT_HANDLE_RE.match(text):
        return f'https://www.youtube.com/{text}'
    if not re.match(r'^https?://', text, re.I):
        if re.match(r'^(www\.)?youtube\.com/', text, re.I):
            text = 'https://' + text
    if is_youtube_channel_url(text):
        return text.split('#')[0].split('?')[0].rstrip('/')
    return None


def channel_name_matches_query(query, *names):
    key = re.sub(r'[^a-z0-9]+', '', (query or '').strip().lower().lstrip('@'))
    if len(key) < 3:
        return False
    for name in names:
        other = re.sub(r'[^a-z0-9]+', '', str(name or '').strip().lower().lstrip('@'))
        if other and other == key:
            return True
    return False


def _search_matching_channel(query):
    """Canal cuyo nombre o handle coincide con la búsqueda (para ordenar por fecha)."""
    direct = channel_url_from_query(query)
    if direct:
        return direct
    sp = youtube_search_sp(result_type='channel') or 'EgIQAg=='
    search_url = (
        f'https://www.youtube.com/results?search_query={quote_plus(query)}'
        f'&sp={quote(sp, safe="")}'
    )
    ydl_opts = _search_ydl_opts(
        extract_flat=True,
        skip_download=True,
        force_generic_extractor=False,
        noplaylist=False,
        playlistend=5,
        use_cookiefile=False,
        silent=True,
    )
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
    except Exception as err:
        print(f'[YouTube] No se pudo resolver el canal ({err})')
        return None
    for entry in info.get('entries') or []:
        if not entry:
            continue
        if not channel_name_matches_query(
            query,
            entry.get('channel'),
            entry.get('title'),
            entry.get('uploader'),
            entry.get('uploader_id'),
        ):
            continue
        channel_url = entry.get('channel_url') or entry.get('url')
        if channel_url and is_youtube_channel_url(str(channel_url)):
            return str(channel_url).split('#')[0].split('?')[0].rstrip('/')
        channel_id = entry.get('channel_id') or entry.get('id')
        if channel_id and str(channel_id).startswith('UC'):
            return f'https://www.youtube.com/channel/{channel_id}'
        handle = str(entry.get('uploader_id') or '')
        if handle.startswith('@'):
            return f'https://www.youtube.com/{handle}'
    return None


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


def fetch_youtube_channel_tab_entries(channel_url, tab='videos', limit=30):
    """Entradas de una pestaña del canal (vídeos o Shorts). No registra la URL."""
    limit = max(5, min(int(limit or 30), 50))
    tab_url = youtube_channel_tab_url(channel_url, tab)
    ydl_opts = _search_ydl_opts(
        extract_flat='in_playlist',
        skip_download=True,
        force_generic_extractor=False,
        noplaylist=False,
        playlistend=limit,
        silent=True,
    )
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(tab_url, download=False)
    entries = []
    seen = set()
    for entry in info.get('entries') or []:
        if not entry or not entry.get('id'):
            continue
        video_id = str(entry.get('id'))
        if len(video_id) != 11 or video_id in seen:
            continue
        seen.add(video_id)
        entries.append(entry)
        if len(entries) >= limit:
            break
    channel_name = (info.get('channel') or info.get('uploader') or info.get('title') or '').strip()
    return entries, channel_name


def fetch_youtube_channel_videos(channel_url, limit=30):
    """Vídeos recientes de un canal. No registra la URL."""
    entries, channel_name = fetch_youtube_channel_tab_entries(channel_url, 'videos', limit)
    videos = []
    for entry in entries:
        video_id = str(entry.get('id'))
        videos.append({
            'title': plain_display_text(entry.get('title') or '', 'YouTube'),
            'id': video_id,
            'url': f'https://www.youtube.com/watch?v={video_id}',
            'duration': entry.get('duration'),
        })
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
        self.window.geometry("820x760")
        self.window.minsize(680, 580)
        style_window(self.window)
        set_window_icon(self.window)
        center_window(self.window, 820, 760)
        self.create_widgets()
        if self.youtube_handler:
            self.youtube_handler.add_session_listener(self.update_youtube_session_ui)
            self.update_youtube_session_ui(self.youtube_handler.session_view())
        self.window.protocol('WM_DELETE_WINDOW', self._on_close)

    def create_widgets(self):
        colors = get_colors()
        shell = ttk.Frame(self.window, padding=(16, 16, 12, 12))
        shell.pack(fill=tk.BOTH, expand=True)

        body = ttk.Frame(shell)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        canvas = tk.Canvas(body, bg=colors['bg'], highlightthickness=0, bd=0)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns', padx=(4, 0))
        self._search_canvas = canvas

        main_frame = ttk.Frame(canvas, padding=(0, 0, 8, 4))
        self._search_main_id = canvas.create_window((0, 0), window=main_frame, anchor='nw')
        self._search_scroll_syncing = False

        ttk.Label(main_frame, text='Buscar en YouTube', style='PageTitle.TLabel').pack(anchor=tk.W)
        ttk.Label(
            main_frame,
            text='Vídeos, Shorts, listas y canales. Las 5 últimas búsquedas están debajo: un clic las vuelve a lanzar. Pulsa ☆ junto al nombre para guardarlo en favoritos.',
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
        self.search_combo = ttk.Combobox(search_frame, textvariable=self.search_var)
        self.search_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_combo.bind('<Return>', lambda e: self.search())
        self.search_combo.bind('<<ComboboxSelected>>', self._on_recent_search)
        self.search_combo.focus_set()

        ttk.Button(search_frame, text="Buscar", style='Accent.TButton', command=self.search).pack(side=tk.LEFT, padx=(8, 0))

        recent_frame = ttk.LabelFrame(main_frame, text=" ÚLTIMAS BÚSQUEDAS ", padding=8)
        recent_frame.pack(fill=tk.X, pady=(0, 10))
        self._recent_empty = ttk.Label(
            recent_frame,
            text='Aún no hay búsquedas. Las 5 últimas se pueden repetir desde aquí.',
            style='Muted.TLabel',
        )
        list_row = ttk.Frame(recent_frame, style='Card.TFrame')
        self._recent_list_row = list_row
        self.recent_list = tk.Listbox(
            list_row,
            height=5,
            activestyle='dotbox',
            exportselection=False,
        )
        self.recent_list.pack(side=tk.LEFT, fill=tk.X, expand=True)
        style_listbox(self.recent_list)
        self.recent_list.bind('<ButtonRelease-1>', self._on_recent_list_click)
        self.recent_list.bind('<Return>', self._on_recent_list_select)
        self._refresh_search_history()

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
        results_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(results_list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.results_listbox = tk.Listbox(
            results_list_frame,
            height=14,
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

        main_frame.bind('<Configure>', self._sync_search_scroll)
        canvas.bind('<Configure>', self._sync_search_scroll)
        self._bind_search_wheel(self.window)
        self.window.after_idle(self._sync_search_scroll)

    def _sync_search_scroll(self, event=None):
        canvas = getattr(self, '_search_canvas', None)
        main_id = getattr(self, '_search_main_id', None)
        if canvas is None or main_id is None:
            return
        if getattr(self, '_search_scroll_syncing', False):
            return
        self._search_scroll_syncing = True
        try:
            width = max(1, int(canvas.winfo_width()))
            canvas.itemconfigure(main_id, width=width)
            canvas.configure(scrollregion=canvas.bbox('all') or (0, 0, 0, 0))
        except tk.TclError:
            pass
        finally:
            self._search_scroll_syncing = False

    def _on_search_wheel(self, event):
        canvas = getattr(self, '_search_canvas', None)
        if canvas is None:
            return
        if getattr(event, 'num', None) == 5:
            steps = 1
        elif getattr(event, 'num', None) == 4:
            steps = -1
        else:
            delta = getattr(event, 'delta', 0) or 0
            if not delta:
                return
            steps = int(-delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        widget = getattr(event, 'widget', None)
        if isinstance(widget, tk.Listbox):
            widget.yview_scroll(steps, 'units')
            return 'break'
        canvas.yview_scroll(steps, 'units')
        return 'break'

    def _bind_search_wheel(self, widget):
        widget.bind('<MouseWheel>', self._on_search_wheel)
        widget.bind('<Button-4>', self._on_search_wheel)
        widget.bind('<Button-5>', self._on_search_wheel)
        try:
            children = widget.winfo_children()
        except tk.TclError:
            return
        for child in children:
            self._bind_search_wheel(child)

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

    def _refresh_search_history(self):
        self._search_history = app_config.youtube_search_history()
        labels = [app_config.youtube_search_label(item) for item in self._search_history]
        combo = getattr(self, 'search_combo', None)
        if combo is not None:
            current = self.search_var.get()
            combo.configure(values=labels)
            if current:
                self.search_var.set(current)
        listing = getattr(self, 'recent_list', None)
        empty = getattr(self, '_recent_empty', None)
        row = getattr(self, '_recent_list_row', None)
        if listing is None:
            return
        applying = getattr(self, '_applying_recent', False)
        self._applying_recent = True
        try:
            listing.delete(0, tk.END)
            for label in labels:
                listing.insert(tk.END, label)
        finally:
            self._applying_recent = applying
        if labels:
            if empty is not None:
                empty.pack_forget()
            if row is not None and not row.winfo_ismapped():
                row.pack(fill=tk.X)
        else:
            if row is not None:
                row.pack_forget()
            if empty is not None:
                empty.pack(anchor=tk.W)
        self.window.after_idle(self._sync_search_scroll)

    def _reuse_search_at(self, index):
        history = getattr(self, '_search_history', None) or []
        if not (0 <= index < len(history)):
            return
        item = history[index]
        self._applying_recent = True
        try:
            self.search_var.set(item['query'])
            self.type_var.set(item['type'])
            self.date_var.set(item['date'])
            self.duration_var.set(item['duration'])
            self.sort_var.set(item['sort'])
            self._on_type_change()
        finally:
            self._applying_recent = False
        self.search()

    def _on_recent_list_click(self, event=None):
        if getattr(self, '_applying_recent', False):
            return
        listing = getattr(self, 'recent_list', None)
        if listing is None or event is None:
            return
        try:
            index = listing.nearest(event.y)
        except tk.TclError:
            return
        self._reuse_search_at(index)

    def _on_recent_list_select(self, event=None):
        if getattr(self, '_applying_recent', False):
            return
        listing = getattr(self, 'recent_list', None)
        if listing is None:
            return
        selection = listing.curselection()
        if not selection:
            return
        self._reuse_search_at(selection[0])

    def _on_recent_search(self, event=None):
        if getattr(self, '_applying_recent', False):
            return
        combo = getattr(self, 'search_combo', None)
        history = getattr(self, '_search_history', None) or []
        if combo is None or not history:
            return
        index = -1
        try:
            index = int(combo.current())
        except (TypeError, ValueError, tk.TclError):
            index = -1
        if not (0 <= index < len(history)):
            label = (self.search_var.get() or '').strip()
            index = next(
                (
                    item_index
                    for item_index, item in enumerate(history)
                    if app_config.youtube_search_label(item) == label
                ),
                -1,
            )
        self._reuse_search_at(index)

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

        app_config.remember_youtube_search(
            query,
            type_name=self.type_var.get(),
            date=self.date_var.get(),
            duration=self.duration_var.get(),
            sort=self.sort_var.get(),
        )
        self._refresh_search_history()
        
        self.results_listbox.delete(0, tk.END)
        self.results = []
        self.result_types = []
        self.result_details = []
        
        self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_bar.start(10)

        tipo = self.type_var.get()
        sort_label = self.sort_var.get()
        search_sp = youtube_search_sp_from_ui(
            tipo,
            sort_label,
            self.date_var.get(),
            self.duration_var.get(),
        )
        search_query = query

        def perform_search():
            try:
                try:
                    max_results = int(self.results_count.get())
                except (tk.TclError, TypeError, ValueError):
                    max_results = 10
                max_results = min(max(max_results, 1), 100)
                if tipo == "Shorts":
                    channel_url = None
                    if _UI_SORT.get(sort_label) == 'date':
                        channel_url = _search_matching_channel(query)
                    shorts, keep_order = _search_youtube_shorts(
                        query,
                        max_results,
                        search_sp=search_sp,
                        channel_url=channel_url,
                    )
                    if not keep_order:
                        shorts = sort_search_entries(shorts, sort_label)

                    def update_shorts_ui():
                        if not shorts:
                            messagebox.showinfo("Info", "No se encontraron Shorts con esa búsqueda.")
                            self.progress_bar.stop()
                            self.progress_bar.pack_forget()
                            return
                        for entry in shorts:
                            title = plain_display_text(entry.get('title', 'Sin título'), 'Sin título')
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

                fetch_end = max_results + 5
                if _UI_SORT.get(sort_label) == 'date':
                    fetch_end = max(max_results + 15, 25)

                from_channel_tab = False
                info = None
                if _UI_SORT.get(sort_label) == 'date' and tipo == 'Vídeos':
                    channel_url = _search_matching_channel(query)
                    if channel_url:
                        try:
                            entries, _name = fetch_youtube_channel_tab_entries(
                                channel_url, 'videos', max_results,
                            )
                            if entries:
                                info = {'entries': entries}
                                from_channel_tab = True
                        except Exception as err:
                            print(f'[YouTube] No se pudo leer el canal ({err})')

                if info is None:
                    ydl_opts = _search_ydl_opts(
                        extract_flat=True,
                        skip_download=True,
                        force_generic_extractor=False,
                        noplaylist=False,
                        playlistend=fetch_end,
                    )

                    query_q = quote_plus(search_query)
                    sp = search_sp or 'EgIQAQ=='
                    search_url = (
                        f"https://www.youtube.com/results?search_query={query_q}"
                        f"&sp={quote(sp, safe='')}"
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
                        retry_opts = _search_ydl_opts(
                            extract_flat=True,
                            skip_download=True,
                            force_generic_extractor=False,
                            noplaylist=False,
                            playlistend=fetch_end,
                        )
                        try:
                            info = extract_search(retry_opts)
                        except Exception as err2:
                            if '413' not in str(err2):
                                raise
                            print('[YouTube] Búsqueda 413: reintentando sin cookies.txt hinchado')
                            info = extract_search(_search_ydl_opts(
                                extract_flat=True,
                                skip_download=True,
                                force_generic_extractor=False,
                                noplaylist=False,
                                playlistend=fetch_end,
                                use_cookiefile=False,
                            ))

                results_count = 0
                found_playlist = False
                ordered_entries = list(info.get('entries') or [])
                if not from_channel_tab:
                    ordered_entries = sort_search_entries(ordered_entries, sort_label)

                def update_ui():
                    nonlocal results_count, found_playlist
                    for entry in ordered_entries:
                        if not entry or results_count >= max_results:
                            break

                        title = plain_display_text(entry.get('title', 'Sin título'), 'Sin título')
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
            return plain_display_text(details['title'], 'YouTube')
        try:
            text = self.results_listbox.get(index)
        except tk.TclError:
            return 'YouTube'
        if text.startswith(STAR_ON) or text.startswith(STAR_OFF):
            text = text[1:].lstrip()
        return plain_display_text(text, 'YouTube')

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
                title = plain_display_text(video.get('title', 'Sin título'), 'Sin título')
                video_url = f"https://www.youtube.com/watch?v={video.get('id')}"
                channels.append((title, video_url))
            return channels


