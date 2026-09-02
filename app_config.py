"""Configuración persistente: sesión, ventanas y archivos recientes."""

import json
import os
import time
import tkinter as tk
from urllib.parse import urlparse

from app_paths import data_dir
from display_text import truncate_ui_text
from iptv_buffer import normalize_iptv_buffer_profile
from m3u_parse import is_iptv_vod

CONFIG_PATH = os.path.join(data_dir(), 'config.json')
MAX_RECENT = 12
MAX_DOWNLOAD_URLS = 12
MAX_YT_RESUME = 80
MAX_YT_HISTORY = 40
MAX_TWITCH_HISTORY = 20
MAX_KICK_HISTORY = 20
MAX_YT_QUEUE = 80
MAX_YT_SEARCHES = 5
MAX_IPTV_HISTORY = 25
YT_RESUME_MIN_S = 15
YT_RESUME_END_S = 20
IPTV_RESUME_MIN_S = 15
YOUTUBE_QUALITIES = (0, 360, 720, 1080)
IPTV_BUFFER_PROFILES = ('fast', 'balanced', 'stable')

COOKIE_BROWSERS = ('auto', 'firefox')

_DEFAULTS = {
    'theme': 'dark',
    'recent_files': [],
    'recent_download_urls': [],
    'patterns': [
        'tvg-name="ES"',
        'group-title="',
        'tvg-logo="',
    ],
    'volume': 50,
    'download_dir': '',
    'open_folder_after_download': True,
    'cookie_browser': 'auto',
    'remember_last_list': True,
    'show_channel_logos': True,
    'epg_url': '',
    'windows': {
        'main': '',
        'player': '',
    },
    'session': {
        'playlist': '',
        'playlist_kind': '',
        'sidebar': [],
        'channel_index': None,
        'channel_name': '',
        'channel_url': '',
    },
    'youtube_resume': {},
    'youtube_history': [],
    'twitch_history': [],
    'kick_history': [],
    'youtube_queue': [],
    'youtube_searches': [],
    'iptv_history': [],
    'youtube_quality': 720,
    'youtube_auto_subtitles': True,
    'twitch_quality': 720,
    'kick_quality': 720,
    'twitch_chat_auto_open': False,
    'iptv_buffer': 'balanced',
    'subtitle_size': 0,
    'subtitle_color': '#FFFFFF',
    'subtitle_opacity': 255,
    'subtitle_outline': 1,
    'subtitle_outline_color': '#000000',
    'subtitle_bg_color': '#000000',
    'subtitle_bg_opacity': 0,
    'subtitle_margin': 0,
    'subtitle_delay_ds': 0,
    'check_app_updates': True,
    'app_update_checked_at': 0,
    'app_update_cache': {},
    'light_mode': False,
    'light_mode_hw_decode': True,
    'light_mode_auto': True,
    'light_mode_auto_channels': 1500,
    'light_mode_auto_cpu': True,
    'light_mode_auto_cpu_percent': 85,
    'show_cpu_monitor': False,
    'onboarding_completed': False,
    'player_shortcuts_hint_shown': False,
    'vlc_subtitle_style_warn_shown': False,
    'usage_profile': 'custom',
}

LIGHT_MODE_SESSION_MAX = 1500
LIGHT_MODE_YT_CACHE_BYTES = 150 * 1024 * 1024
LIGHT_MODE_YT_QUALITY_CAP = 720
LIGHT_MODE_EPG_TICK_MS = 5 * 60 * 1000
CPU_MONITOR_INTERVAL_MS = 8 * 1000

_cache = None


def _deep_merge(base, incoming):
    """Uso interno: deep merge."""
    merged = dict(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load():
    """Load."""
    global _cache
    if _cache is not None:
        return _cache
    data = dict(_DEFAULTS)
    exists = os.path.isfile(CONFIG_PATH)
    try:
        with open(CONFIG_PATH, encoding='utf-8') as handle:
            stored = json.load(handle)
        if isinstance(stored, dict):
            data = _deep_merge(_DEFAULTS, stored)
        else:
            exists = False
    except (OSError, json.JSONDecodeError):
        exists = False
    data.pop('language', None)
    _cache = data
    if not exists:
        save()
    return _cache


def save(updates=None):
    """Save."""
    data = load()
    if updates:
        data = _deep_merge(data, updates)
        global _cache
        _cache = data
    data.pop('language', None)
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
    except OSError:
        pass
    return data


def get_theme():
    """Obtiene theme."""
    theme = str(load().get('theme') or 'dark').strip().lower()
    return 'dark' if theme in ('dark', 'equilux') else 'light'


def set_theme(theme):
    """Establece theme."""
    save({'theme': 'dark' if theme in ('dark', 'equilux', True) else 'light'})


def get_volume():
    """Obtiene volume."""
    try:
        return max(0, min(100, int(load().get('volume', 50))))
    except (TypeError, ValueError):
        return 50


def set_volume(value):
    """Establece volume."""
    try:
        save({'volume': max(0, min(100, int(value)))})
    except (TypeError, ValueError):
        pass


def suggested_download_dir():
    """Suggested download dir."""
    candidates = [
        os.environ.get('XDG_DOWNLOAD_DIR'),
        os.path.expanduser('~/Descargas'),
        os.path.expanduser('~/Downloads'),
        os.path.expanduser('~'),
    ]
    for path in candidates:
        path = os.path.expanduser(path) if path else ''
        if path and os.path.isdir(path):
            return path
    return os.path.expanduser('~')


def get_download_dir():
    """Obtiene download dir."""
    stored = str(load().get('download_dir') or '').strip()
    if stored and os.path.isdir(stored):
        return stored
    return suggested_download_dir()


def set_download_dir(path):
    """Establece download dir."""
    save({'download_dir': str(path or '').strip()})


def get_open_folder_after_download():
    """Obtiene open folder after download."""
    return bool(load().get('open_folder_after_download', True))


def set_open_folder_after_download(value):
    """Establece open folder after download."""
    save({'open_folder_after_download': bool(value)})


def get_cookie_browser():
    """Obtiene cookie browser."""
    value = str(load().get('cookie_browser') or 'auto').strip().lower()
    return value if value in COOKIE_BROWSERS else 'auto'


def set_cookie_browser(name):
    """Establece cookie browser."""
    value = str(name or 'auto').strip().lower()
    save({'cookie_browser': value if value in COOKIE_BROWSERS else 'auto'})


def get_remember_last_list():
    """Obtiene remember last list."""
    return bool(load().get('remember_last_list', True))


def set_remember_last_list(value):
    """Establece remember last list."""
    save({'remember_last_list': bool(value)})


def get_show_channel_logos():
    """Obtiene show canal logos."""
    return bool(load().get('show_channel_logos', True))


def set_show_channel_logos(value):
    """Establece show canal logos."""
    save({'show_channel_logos': bool(value)})


def get_light_mode():
    """Obtiene light mode."""
    return bool(load().get('light_mode', False))


def set_light_mode(value):
    """Establece light mode."""
    save({'light_mode': bool(value)})


def get_light_mode_hw_decode():
    """Obtiene light mode hw decode."""
    return bool(load().get('light_mode_hw_decode', True))


def set_light_mode_hw_decode(value):
    """Establece light mode hw decode."""
    save({'light_mode_hw_decode': bool(value)})


def get_light_mode_auto():
    """Obtiene si el modo ligero automático está habilitado."""
    return bool(load().get('light_mode_auto', True))


def set_light_mode_auto(value):
    """Establece light mode auto."""
    save({'light_mode_auto': bool(value)})


def get_light_mode_auto_channels():
    """Umbral de canales para activar modo ligero automático."""
    try:
        value = int(load().get('light_mode_auto_channels', LIGHT_MODE_SESSION_MAX))
    except (TypeError, ValueError):
        value = LIGHT_MODE_SESSION_MAX
    return max(500, min(20000, value))


def set_light_mode_auto_channels(value):
    """Establece light mode auto channels."""
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = LIGHT_MODE_SESSION_MAX
    save({'light_mode_auto_channels': max(500, min(20000, count))})


def get_light_mode_auto_cpu():
    """True si la CPU alta puede activar modo ligero automático."""
    return bool(load().get('light_mode_auto_cpu', True))


def set_light_mode_auto_cpu(value):
    """Establece light mode auto cpu."""
    save({'light_mode_auto_cpu': bool(value)})


def get_light_mode_auto_cpu_percent():
    """Porcentaje de CPU que dispara el modo ligero automático."""
    try:
        value = int(load().get('light_mode_auto_cpu_percent', 85))
    except (TypeError, ValueError):
        value = 85
    return max(50, min(100, value))


def set_light_mode_auto_cpu_percent(value):
    """Establece light mode auto cpu percent."""
    try:
        percent = int(value)
    except (TypeError, ValueError):
        percent = 85
    save({'light_mode_auto_cpu_percent': max(50, min(100, percent))})


def effective_light_mode():
    """Modo ligero manual o automático activo en esta sesión."""
    if get_light_mode():
        return True
    if not get_light_mode_auto():
        return False
    from light_mode_auto import is_auto_light_mode_active
    return is_auto_light_mode_active()


def get_show_cpu_monitor():
    """Obtiene show cpu monitor."""
    return bool(load().get('show_cpu_monitor', False))


def set_show_cpu_monitor(value):
    """Establece show cpu monitor."""
    save({'show_cpu_monitor': bool(value)})


def light_mode_session_max():
    """Light mode session max."""
    return LIGHT_MODE_SESSION_MAX


def effective_show_channel_logos():
    """Effective show canal logos."""
    return get_show_channel_logos() and not effective_light_mode()


def iptv_use_hw_decode():
    """Iptv use hw decode."""
    return effective_light_mode() and get_light_mode_hw_decode()


def effective_youtube_quality(value=None):
    """Effective youtube quality."""
    height = normalize_youtube_quality(
        get_youtube_quality() if value is None else value
    )
    if not effective_light_mode():
        return height
    if height <= 0 or height > LIGHT_MODE_YT_QUALITY_CAP:
        return LIGHT_MODE_YT_QUALITY_CAP
    return height


def effective_twitch_quality(value=None):
    """Effective twitch quality."""
    height = normalize_twitch_quality(
        get_twitch_quality() if value is None else value
    )
    if not effective_light_mode():
        return height
    if height <= 0 or height > LIGHT_MODE_YT_QUALITY_CAP:
        return LIGHT_MODE_YT_QUALITY_CAP
    return height


def effective_kick_quality(value=None):
    """Effective kick quality."""
    height = normalize_kick_quality(
        get_kick_quality() if value is None else value
    )
    if not effective_light_mode():
        return height
    if height <= 0 or height > LIGHT_MODE_YT_QUALITY_CAP:
        return LIGHT_MODE_YT_QUALITY_CAP
    return height


def effective_yt_cache_max_bytes():
    """Effective youtube cache max bytes."""
    if effective_light_mode():
        return LIGHT_MODE_YT_CACHE_BYTES
    return 500 * 1024 * 1024


def epg_reload_interval_ms():
    """Guía epg reload interval ms."""
    if effective_light_mode():
        return 0
    return 30 * 60 * 1000


def epg_tick_interval_ms():
    """Guía epg tick interval ms."""
    if effective_light_mode():
        return LIGHT_MODE_EPG_TICK_MS
    return 60 * 1000


def should_skip_session_restore(session):
    """En modo ligero no se restaura una lista enorme al arrancar."""
    if not effective_light_mode():
        return False
    if not isinstance(session, dict):
        return False
    kind = str(session.get('playlist_kind') or '').strip()
    playlist = str(session.get('playlist') or '').strip()
    sidebar = session.get('sidebar') or []
    if kind in ('file', 'url') and playlist:
        return True
    if isinstance(sidebar, list) and len(sidebar) > LIGHT_MODE_SESSION_MAX:
        return True
    return False


def get_epg_url():
    """Obtiene guía EPG URL."""
    return str(load().get('epg_url') or '').strip()


def set_epg_url(url):
    """Establece guía EPG URL."""
    save({'epg_url': str(url or '').strip()})


def get_check_app_updates():
    """Obtiene check app updates."""
    return bool(load().get('check_app_updates', True))


def set_check_app_updates(value):
    """Establece check app updates."""
    save({'check_app_updates': bool(value)})


def get_app_update_checked_at():
    """Obtiene app update checked at."""
    try:
        return max(0, int(load().get('app_update_checked_at') or 0))
    except (TypeError, ValueError):
        return 0


def get_app_update_cache():
    """Obtiene app update cache."""
    cached = load().get('app_update_cache')
    if not isinstance(cached, dict):
        return None
    version = str(cached.get('version') or '').strip()
    if not version:
        return None
    return cached


def set_app_update_cache(payload):
    """Establece app update cache."""
    import time
    data = payload if isinstance(payload, dict) else {}
    save({
        'app_update_checked_at': int(time.time()),
        'app_update_cache': {
            'version': str(data.get('version') or '').strip(),
            'tag': str(data.get('tag') or '').strip(),
            'url': str(data.get('url') or '').strip(),
            'assets': data.get('assets') if isinstance(data.get('assets'), list) else [],
        },
    })


def normalize_youtube_quality(value):
    """0 = mejor disponible; el resto se ajusta a 360, 720 o 1080."""
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ('best', 'max', 'mejor', '0'):
            return 0
        try:
            value = int(text)
        except (TypeError, ValueError):
            return 720
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 720
    if value <= 0:
        return 0
    if value <= 360:
        return 360
    if value <= 720:
        return 720
    return 1080


def youtube_quality_label(value=None):
    """Youtube quality label."""
    height = normalize_youtube_quality(
        get_youtube_quality() if value is None else value
    )
    if height <= 0:
        return 'Mejor disponible'
    return f'{height}p'


def youtube_quality_cache_key(value=None):
    """Youtube quality cache key."""
    height = normalize_youtube_quality(
        get_youtube_quality() if value is None else value
    )
    return 'best' if height <= 0 else str(height)


def get_youtube_quality():
    """Obtiene youtube quality."""
    return normalize_youtube_quality(load().get('youtube_quality', 720))


def set_youtube_quality(height):
    """Establece youtube quality."""
    save({'youtube_quality': normalize_youtube_quality(height)})


def get_youtube_auto_subtitles():
    """Obtiene youtube auto subtitles."""
    return bool(load().get('youtube_auto_subtitles', True))


def set_youtube_auto_subtitles(enabled):
    """Establece youtube auto subtitles."""
    save({'youtube_auto_subtitles': bool(enabled)})


def normalize_twitch_quality(value):
    """Normaliza twitch quality."""
    return normalize_youtube_quality(value)


def twitch_quality_label(value=None):
    """Twitch quality label."""
    height = normalize_twitch_quality(
        get_twitch_quality() if value is None else value
    )
    if height <= 0:
        return 'Mejor disponible'
    return f'{height}p'


def get_twitch_quality():
    """Obtiene twitch quality."""
    return normalize_twitch_quality(load().get('twitch_quality', 720))


def set_twitch_quality(height):
    """Establece twitch quality."""
    save({'twitch_quality': normalize_twitch_quality(height)})


def normalize_kick_quality(value):
    """Normaliza kick quality."""
    return normalize_youtube_quality(value)


def kick_quality_label(value=None):
    """Etiqueta de calidad Kick."""
    height = normalize_kick_quality(
        get_kick_quality() if value is None else value
    )
    if height <= 0:
        return 'Mejor disponible'
    return f'{height}p'


def get_kick_quality():
    """Obtiene kick quality."""
    return normalize_kick_quality(load().get('kick_quality', 720))


def set_kick_quality(height):
    """Establece kick quality."""
    save({'kick_quality': normalize_kick_quality(height)})


def get_twitch_chat_auto_open():
    """Obtiene twitch chat auto open."""
    return bool(load().get('twitch_chat_auto_open', False))


def set_twitch_chat_auto_open(value):
    """Establece twitch chat auto open."""
    save({'twitch_chat_auto_open': bool(value)})


def get_iptv_buffer():
    """Obtiene IPTV buffer."""
    return normalize_iptv_buffer_profile(load().get('iptv_buffer', 'balanced'))


def set_iptv_buffer(value):
    """Establece IPTV buffer."""
    save({'iptv_buffer': normalize_iptv_buffer_profile(value)})


def get_subtitle_style():
    """Obtiene subtitle style."""
    from subtitle_style import normalize_subtitle_style
    return normalize_subtitle_style(load())


def set_subtitle_style(values):
    """Establece subtitle style."""
    from subtitle_style import normalize_subtitle_style
    save(normalize_subtitle_style(values))


def remember_playlist(path, kind='file'):
    """Remember lista de reproducción."""
    if not path:
        return
    path = str(path).strip()
    recent = [item for item in load().get('recent_files') or [] if item != path]
    recent.insert(0, path)
    updates = {'recent_files': recent[:MAX_RECENT]}
    if get_remember_last_list():
        updates['session'] = {
            'playlist': path,
            'playlist_kind': kind,
            'sidebar': [],
        }
    save(updates)


def _clean_download_url_entry(raw):
    """Uso interno: clean download URL entry."""
    if isinstance(raw, str):
        url = raw.strip()
        return {'url': url, 'name': ''} if url else None
    if not isinstance(raw, dict):
        return None
    url = str(raw.get('url') or '').strip()
    if not url:
        return None
    return {
        'url': url,
        'name': str(raw.get('name') or '').strip(),
    }


def download_url_history():
    """Descarga URL historial."""
    items = []
    seen = set()
    for raw in load().get('recent_download_urls') or []:
        entry = _clean_download_url_entry(raw)
        if not entry or entry['url'] in seen:
            continue
        seen.add(entry['url'])
        items.append(entry)
    return items[:MAX_DOWNLOAD_URLS]


def remember_download_url(url, name=''):
    """Remember download url."""
    url = str(url or '').strip()
    if not url:
        return
    name = str(name or '').strip()
    items = []
    previous = None
    for entry in download_url_history():
        if entry['url'] == url:
            previous = entry
            continue
        items.append(entry)
    items.insert(0, {
        'url': url,
        'name': name or (previous or {}).get('name') or '',
    })
    save({'recent_download_urls': items[:MAX_DOWNLOAD_URLS]})


YT_SEARCH_TYPES = ('Vídeos', 'Shorts', 'Listas de reproducción', 'Canales')
YT_SEARCH_DATES = ('Cualquier fecha', 'Hoy', 'Esta semana', 'Este mes', 'Este año')
YT_SEARCH_DURATIONS = (
    'Cualquier duración',
    'Corto (<4 min)',
    'Medio (4-20 min)',
    'Largo (>20 min)',
)
YT_SEARCH_SORTS = ('Relevancia', 'Fecha', 'Vistas', 'Valoración')


def _clean_youtube_search_entry(raw):
    """Uso interno: clean youtube search entry."""
    if isinstance(raw, str):
        query = raw.strip()
        raw = {'query': query} if query else None
    if not isinstance(raw, dict):
        return None
    query = str(raw.get('query') or '').strip()
    if not query:
        return None
    kind = raw.get('type') if raw.get('type') in YT_SEARCH_TYPES else 'Vídeos'
    date = raw.get('date') if raw.get('date') in YT_SEARCH_DATES else 'Cualquier fecha'
    duration = raw.get('duration') if raw.get('duration') in YT_SEARCH_DURATIONS else 'Cualquier duración'
    sort = raw.get('sort') if raw.get('sort') in YT_SEARCH_SORTS else 'Relevancia'
    return {
        'query': query[:120],
        'type': kind,
        'date': date,
        'duration': duration,
        'sort': sort,
    }


def youtube_search_key(entry):
    """Youtube search key."""
    item = _clean_youtube_search_entry(entry)
    if not item:
        return None
    return (
        item['query'].casefold(),
        item['type'],
        item['date'],
        item['duration'],
        item['sort'],
    )


def youtube_search_label(entry):
    """Youtube search label."""
    item = _clean_youtube_search_entry(entry)
    if not item:
        return ''
    extras = []
    if item['type'] != 'Vídeos':
        extras.append(item['type'])
    if item['date'] != 'Cualquier fecha':
        extras.append(item['date'])
    if item['duration'] != 'Cualquier duración':
        extras.append(item['duration'])
    if item['sort'] != 'Relevancia':
        extras.append(item['sort'])
    if extras:
        return f"{item['query']}  ·  {' · '.join(extras)}"
    return item['query']


def youtube_search_history():
    """Youtube search historial."""
    items = []
    seen = set()
    for raw in load().get('youtube_searches') or []:
        entry = _clean_youtube_search_entry(raw)
        key = youtube_search_key(entry)
        if not entry or key in seen:
            continue
        seen.add(key)
        items.append(entry)
    return items[:MAX_YT_SEARCHES]


def remember_youtube_search(query, type_name='Vídeos', date='Cualquier fecha', duration='Cualquier duración', sort='Relevancia'):
    """Remember youtube search."""
    entry = _clean_youtube_search_entry({
        'query': query,
        'type': type_name,
        'date': date,
        'duration': duration,
        'sort': sort,
    })
    key = youtube_search_key(entry)
    if not key:
        return
    items = [item for item in youtube_search_history() if youtube_search_key(item) != key]
    items.insert(0, entry)
    save({'youtube_searches': items[:MAX_YT_SEARCHES]})


def remember_sidebar(items, source='', kind='items', groups=None, tvg_ids=None, epg_urls=None, logos=None):
    """Remember barra lateral."""
    if not get_remember_last_list():
        return
    snapshot = []
    for index, entry in enumerate(items or []):
        group = ''
        tvg_id = ''
        logo = ''
        if groups is not None and index < len(groups):
            group = groups[index] or ''
        if tvg_ids is not None and index < len(tvg_ids):
            tvg_id = tvg_ids[index] or ''
        if logos is not None and index < len(logos):
            logo = logos[index] or ''
        if isinstance(entry, dict):
            name, url = entry.get('name'), entry.get('url')
            group = entry.get('group') or group
            tvg_id = entry.get('tvg_id') or tvg_id
            logo = entry.get('tvg_logo') or logo
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            name, url = entry[0], entry[1]
            if len(entry) >= 3:
                group = entry[2] or group
            if len(entry) >= 4:
                tvg_id = entry[3] or tvg_id
            if len(entry) >= 5:
                logo = entry[4] or logo
        else:
            continue
        if url:
            snapshot.append({
                'name': name or '',
                'url': url,
                'group': group or '',
                'tvg_id': tvg_id or '',
                'tvg_logo': logo or '',
            })
    urls = []
    seen = set()
    for item in epg_urls or []:
        item = (item or '').strip()
        if not item or item in seen:
            continue
        seen.add(item)
        urls.append(item)
    save({
        'session': {
            'playlist': source or '',
            'playlist_kind': kind or 'items',
            'sidebar': snapshot,
            'epg_urls': urls[:3],
        },
    })


def clear_session_list():
    """Limpia session list."""
    save({
        'session': {
            'playlist': '',
            'playlist_kind': '',
            'sidebar': [],
            'channel_index': None,
            'channel_name': '',
            'channel_url': '',
        },
    })


def remember_channel(index, name, url):
    """Remember canal."""
    if not get_remember_last_list():
        return
    save({
        'session': {
            'channel_index': index,
            'channel_name': name or '',
            'channel_url': url or '',
        },
    })


def _yt_resume_seconds_value(entry):
    """Uso interno: YouTube resume seconds value."""
    if isinstance(entry, (int, float)):
        return float(entry)
    if isinstance(entry, dict):
        try:
            return float(entry.get('s') or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _yt_resume_near_end(seconds, duration_s):
    """Uso interno: YouTube resume near end."""
    try:
        duration_s = float(duration_s or 0)
    except (TypeError, ValueError):
        duration_s = 0.0
    if duration_s <= 0 or seconds < 0:
        return False
    margin = min(YT_RESUME_END_S, max(5.0, duration_s * 0.05))
    return (duration_s - seconds) <= margin


def youtube_resume_seconds(video_id, duration_s=None):
    """Youtube resume seconds."""
    video_id = str(video_id or '').strip()
    if len(video_id) != 11:
        return 0.0
    seconds = _yt_resume_seconds_value((load().get('youtube_resume') or {}).get(video_id))
    if seconds < YT_RESUME_MIN_S:
        return 0.0
    if _yt_resume_near_end(seconds, duration_s):
        clear_youtube_position(video_id)
        return 0.0
    return seconds


def remember_youtube_position(video_id, seconds, duration_s=None, title=None, url=None):
    """Remember youtube position."""
    video_id = str(video_id or '').strip()
    if len(video_id) != 11:
        return
    try:
        seconds = float(seconds or 0)
    except (TypeError, ValueError):
        return
    if seconds < YT_RESUME_MIN_S:
        return
    data = load()
    resume = dict(data.get('youtube_resume') or {})
    if _yt_resume_near_end(seconds, duration_s):
        if video_id in resume:
            resume.pop(video_id, None)
            data['youtube_resume'] = resume
        _upsert_youtube_history(
            data, video_id, title=title, url=url,
            seconds=0, duration=duration_s,
        )
        save()
        return
    resume[video_id] = {'s': int(seconds), 'updated': int(time.time())}
    if len(resume) > MAX_YT_RESUME:
        ordered = sorted(
            resume.items(),
            key=lambda item: item[1].get('updated', 0) if isinstance(item[1], dict) else 0,
        )
        for key, _unused in ordered[: len(resume) - MAX_YT_RESUME]:
            resume.pop(key, None)
    data['youtube_resume'] = resume
    _upsert_youtube_history(
        data, video_id, title=title, url=url,
        seconds=int(seconds), duration=duration_s,
    )
    save()


def clear_youtube_position(video_id):
    """Limpia youtube position."""
    video_id = str(video_id or '').strip()
    if not video_id:
        return
    data = load()
    resume = dict(data.get('youtube_resume') or {})
    history_changed = False
    if video_id in resume:
        resume.pop(video_id, None)
        data['youtube_resume'] = resume
        history_changed = True
    items = []
    for raw in data.get('youtube_history') or []:
        entry = _clean_youtube_history_entry(raw)
        if not entry:
            continue
        if entry['id'] == video_id and entry.get('s'):
            entry['s'] = 0
            history_changed = True
        items.append(entry)
    if history_changed:
        data['youtube_history'] = items[:MAX_YT_HISTORY]
        save()


def _clean_youtube_history_entry(item):
    """Uso interno: clean youtube historial entry."""
    if not isinstance(item, dict):
        return None
    video_id = str(item.get('id') or '').strip()
    if len(video_id) != 11:
        return None
    url = str(item.get('url') or '').strip() or f'https://www.youtube.com/watch?v={video_id}'
    try:
        seconds = max(0, int(float(item.get('s') or 0)))
    except (TypeError, ValueError):
        seconds = 0
    try:
        duration = max(0, int(float(item.get('duration') or 0)))
    except (TypeError, ValueError):
        duration = 0
    try:
        updated = int(item.get('updated') or 0)
    except (TypeError, ValueError):
        updated = 0
    return {
        'id': video_id,
        'name': str(item.get('name') or '').strip() or 'YouTube',
        'url': url,
        's': seconds,
        'duration': duration,
        'updated': updated,
    }


def _upsert_youtube_history(data, video_id, title=None, url=None, seconds=None, duration=None):
    """Uso interno: upsert youtube historial."""
    video_id = str(video_id or '').strip()
    if len(video_id) != 11:
        return
    items = []
    previous = None
    for raw in data.get('youtube_history') or []:
        entry = _clean_youtube_history_entry(raw)
        if not entry:
            continue
        if entry['id'] == video_id:
            previous = entry
            continue
        items.append(entry)
    previous = previous or {}
    if seconds is None:
        stored_s = int(previous.get('s') or 0)
    else:
        try:
            stored_s = max(0, int(float(seconds)))
        except (TypeError, ValueError):
            stored_s = int(previous.get('s') or 0)
    if duration is None:
        stored_duration = int(previous.get('duration') or 0)
    else:
        try:
            stored_duration = max(0, int(float(duration or 0)))
        except (TypeError, ValueError):
            stored_duration = int(previous.get('duration') or 0)
    name = str(title or '').strip() or previous.get('name') or 'YouTube'
    stored_url = str(url or '').strip() or previous.get('url') or f'https://www.youtube.com/watch?v={video_id}'
    items.insert(0, {
        'id': video_id,
        'name': name,
        'url': stored_url,
        's': stored_s,
        'duration': stored_duration,
        'updated': int(time.time()),
    })
    data['youtube_history'] = items[:MAX_YT_HISTORY]


def remember_youtube_watch(video_id, title='', url=''):
    """Remember youtube watch."""
    video_id = str(video_id or '').strip()
    if len(video_id) != 11:
        return
    data = load()
    _upsert_youtube_history(data, video_id, title=title, url=url)
    save()


def youtube_history():
    """Youtube historial."""
    items = []
    seen = set()
    for raw in load().get('youtube_history') or []:
        entry = _clean_youtube_history_entry(raw)
        if not entry or entry['id'] in seen:
            continue
        seen.add(entry['id'])
        items.append(entry)
    return items[:MAX_YT_HISTORY]


def youtube_history_item(video_id):
    """Youtube historial item."""
    video_id = str(video_id or '').strip()
    if len(video_id) != 11:
        return None
    for item in youtube_history():
        if item['id'] == video_id:
            return item
    return None


def youtube_history_item_by_url(url):
    """Youtube historial item by url."""
    url = str(url or '').strip()
    if not url:
        return None
    for item in youtube_history():
        if item.get('url') == url:
            return item
    return None


def youtube_history_label(item, with_time=False, limit=46):
    """Youtube historial label."""
    name = str((item or {}).get('name') or 'YouTube').strip() or 'YouTube'
    name = truncate_ui_text(name, limit)
    if not with_time:
        return name
    try:
        seconds = int((item or {}).get('s') or 0)
    except (TypeError, ValueError):
        seconds = 0
    if seconds < YT_RESUME_MIN_S:
        return name
    stamp = format_iptv_clock(seconds)
    try:
        duration = int((item or {}).get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration > 0:
        return f'{name}  ·  {stamp} / {format_iptv_clock(duration)}'
    return f'{name}  ·  {stamp}'


def youtube_continue_watching():
    """Youtube continue watching."""
    found = []
    for item in youtube_history():
        seconds = int(item.get('s') or 0)
        if seconds < YT_RESUME_MIN_S:
            continue
        if _yt_resume_near_end(seconds, item.get('duration') or 0):
            continue
        found.append(item)
    return found


def remove_youtube_history(video_id):
    """Quita youtube historial."""
    video_id = str(video_id or '').strip()
    if not video_id:
        return
    data = load()
    items = [
        entry for entry in (_clean_youtube_history_entry(raw) for raw in data.get('youtube_history') or [])
        if entry and entry['id'] != video_id
    ]
    data['youtube_history'] = items
    resume = dict(data.get('youtube_resume') or {})
    resume.pop(video_id, None)
    data['youtube_resume'] = resume
    save()


def clear_youtube_history():
    """Limpia youtube historial."""
    data = load()
    changed = bool(data.get('youtube_history') or data.get('youtube_resume'))
    if not changed:
        return
    data['youtube_history'] = []
    data['youtube_resume'] = {}
    save()


def _is_twitch_url(url):
    """Uso interno: is twitch URL."""
    text = (url or '').lower()
    return 'twitch.tv' in text


def _clean_twitch_history_entry(item):
    """Uso interno: clean twitch historial entry."""
    if not isinstance(item, dict):
        return None
    url = str(item.get('url') or '').strip()
    if not url or not _is_twitch_url(url):
        return None
    name = str(item.get('name') or '').strip() or 'Twitch'
    try:
        seen_at = float(item.get('at') or 0)
    except (TypeError, ValueError):
        seen_at = 0
    try:
        updated = int(item.get('updated') or seen_at or 0)
    except (TypeError, ValueError):
        updated = int(seen_at or 0)
    kind = str(item.get('kind') or '').strip().lower()
    if not kind:
        kind = 'vod' if '/videos/' in url.lower() else 'live'
    try:
        seconds = int(item.get('s') or 0)
    except (TypeError, ValueError):
        seconds = 0
    try:
        duration = int(item.get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0
    if kind != 'vod':
        seconds = 0
        duration = 0
    return {
        'url': url,
        'name': name,
        'at': seen_at,
        'updated': updated,
        'kind': kind,
        's': seconds,
        'duration': duration,
    }


def _is_twitch_vod_url(url):
    """Uso interno: is twitch vod URL."""
    text = str(url or '').lower()
    return _is_twitch_url(text) and '/videos/' in text


def remember_twitch_watch(url, title=''):
    """Remember twitch watch."""
    url = str(url or '').strip()
    if not url or not _is_twitch_url(url):
        return
    data = load()
    items = []
    now = time.time()
    name = str(title or '').strip() or 'Twitch'
    previous = None
    for raw in data.get('twitch_history') or []:
        entry = _clean_twitch_history_entry(raw)
        if not entry:
            continue
        if entry['url'] == url:
            previous = entry
            continue
        items.append(entry)
    kind = 'vod' if _is_twitch_vod_url(url) else 'live'
    seconds = int((previous or {}).get('s') or 0) if kind == 'vod' else 0
    duration = int((previous or {}).get('duration') or 0) if kind == 'vod' else 0
    items.insert(0, {
        'url': url,
        'name': name,
        'at': now,
        'updated': int(now),
        'kind': kind,
        's': seconds,
        'duration': duration,
    })
    data['twitch_history'] = items[:MAX_TWITCH_HISTORY]
    save()


def update_twitch_position(url, seconds, duration_s=None):
    """Actualiza twitch position."""
    url = str(url or '').strip()
    if not url or not _is_twitch_vod_url(url):
        return
    try:
        seconds = float(seconds or 0)
    except (TypeError, ValueError):
        return
    data = load()
    items = []
    current = None
    for raw in data.get('twitch_history') or []:
        entry = _clean_twitch_history_entry(raw)
        if not entry:
            continue
        if entry['url'] == url:
            current = entry
            continue
        items.append(entry)
    if current is None:
        return
    if seconds < IPTV_RESUME_MIN_S or _yt_resume_near_end(seconds, duration_s):
        current['s'] = 0
        current['duration'] = 0
    else:
        current['s'] = int(seconds)
        try:
            current['duration'] = max(0, int(float(duration_s or 0)))
        except (TypeError, ValueError):
            current['duration'] = int(current.get('duration') or 0)
    current['updated'] = int(time.time())
    current['kind'] = 'vod'
    items.insert(0, current)
    data['twitch_history'] = items[:MAX_TWITCH_HISTORY]
    save()


def twitch_resume_seconds(url, duration_s=None):
    """Twitch resume seconds."""
    if not _is_twitch_vod_url(url):
        return 0.0
    item = twitch_history_item_by_url(url)
    if not item or item.get('kind') != 'vod':
        return 0.0
    seconds = float(item.get('s') or 0)
    if seconds < IPTV_RESUME_MIN_S:
        return 0.0
    if _yt_resume_near_end(seconds, duration_s if duration_s is not None else item.get('duration')):
        update_twitch_position(url, 0, 0)
        return 0.0
    return seconds


def twitch_continue_watching():
    """Twitch continue watching."""
    found = []
    for item in twitch_history():
        if item.get('kind') != 'vod':
            continue
        seconds = int(item.get('s') or 0)
        if seconds < IPTV_RESUME_MIN_S:
            continue
        if _yt_resume_near_end(seconds, item.get('duration') or 0):
            continue
        found.append(item)
    return found


def clear_twitch_position(url):
    """Limpia twitch position."""
    update_twitch_position(url, 0, 0)


def twitch_history():
    """Twitch historial."""
    items = []
    seen = set()
    for raw in load().get('twitch_history') or []:
        entry = _clean_twitch_history_entry(raw)
        if not entry or entry['url'] in seen:
            continue
        seen.add(entry['url'])
        items.append(entry)
    return items[:MAX_TWITCH_HISTORY]


def twitch_history_item_by_url(url):
    """Twitch historial item by url."""
    wanted = str(url or '').strip()
    if not wanted:
        return None
    for item in twitch_history():
        if item.get('url') == wanted:
            return item
    return None


def twitch_history_label(item, limit=46, with_time=False):
    """Twitch historial label."""
    name = str((item or {}).get('name') or 'Twitch').strip()
    name = truncate_ui_text(name, limit)
    base = f'Twitch · {name}'
    seconds = int((item or {}).get('s') or 0)
    if not with_time or seconds < IPTV_RESUME_MIN_S or (item or {}).get('kind') != 'vod':
        return base
    stamp = format_iptv_clock(seconds)
    try:
        duration = int((item or {}).get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration > 0:
        return f'{base}  ·  {stamp} / {format_iptv_clock(duration)}'
    return f'{base}  ·  {stamp}'


def clear_twitch_history():
    """Limpia twitch historial."""
    data = load()
    if not data.get('twitch_history'):
        return
    data['twitch_history'] = []
    save()


def _is_kick_url(url):
    """Uso interno: is kick URL."""
    text = (url or '').lower()
    return 'kick.com' in text


def _clean_kick_history_entry(item):
    """Uso interno: clean kick historial entry."""
    if not isinstance(item, dict):
        return None
    url = str(item.get('url') or '').strip()
    if not url or not _is_kick_url(url):
        return None
    name = str(item.get('name') or '').strip() or 'Kick'
    try:
        seen_at = float(item.get('at') or 0)
    except (TypeError, ValueError):
        seen_at = 0
    try:
        updated = int(item.get('updated') or seen_at or 0)
    except (TypeError, ValueError):
        updated = int(seen_at or 0)
    kind = str(item.get('kind') or '').strip().lower()
    if not kind:
        lower = url.lower()
        kind = 'vod' if '/videos/' in lower or '/video/' in lower else 'live'
    try:
        seconds = int(item.get('s') or 0)
    except (TypeError, ValueError):
        seconds = 0
    try:
        duration = int(item.get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0
    if kind != 'vod':
        seconds = 0
        duration = 0
    return {
        'url': url,
        'name': name,
        'at': seen_at,
        'updated': updated,
        'kind': kind,
        's': seconds,
        'duration': duration,
    }


def _is_kick_vod_url(url):
    """Uso interno: is kick vod URL."""
    text = str(url or '').lower()
    if not _is_kick_url(text):
        return False
    if '/videos/' in text:
        return True
    parsed = urlparse(text) if text else None
    parts = [segment for segment in ((parsed.path if parsed else '') or '').strip('/').split('/') if segment]
    return len(parts) >= 2 and parts[0] == 'video'


def remember_kick_watch(url, title=''):
    """Remember kick watch."""
    url = str(url or '').strip()
    if not url or not _is_kick_url(url):
        return
    data = load()
    items = []
    now = time.time()
    name = str(title or '').strip() or 'Kick'
    previous = None
    for raw in data.get('kick_history') or []:
        entry = _clean_kick_history_entry(raw)
        if not entry:
            continue
        if entry['url'] == url:
            previous = entry
            continue
        items.append(entry)
    kind = 'vod' if _is_kick_vod_url(url) else 'live'
    seconds = int((previous or {}).get('s') or 0) if kind == 'vod' else 0
    duration = int((previous or {}).get('duration') or 0) if kind == 'vod' else 0
    items.insert(0, {
        'url': url,
        'name': name,
        'at': now,
        'updated': int(now),
        'kind': kind,
        's': seconds,
        'duration': duration,
    })
    data['kick_history'] = items[:MAX_KICK_HISTORY]
    save()


def update_kick_position(url, seconds, duration_s=None):
    """Actualiza kick position."""
    url = str(url or '').strip()
    if not url or not _is_kick_vod_url(url):
        return
    try:
        seconds = float(seconds or 0)
    except (TypeError, ValueError):
        return
    data = load()
    items = []
    current = None
    for raw in data.get('kick_history') or []:
        entry = _clean_kick_history_entry(raw)
        if not entry:
            continue
        if entry['url'] == url:
            current = entry
            continue
        items.append(entry)
    if current is None:
        return
    if seconds < IPTV_RESUME_MIN_S or _yt_resume_near_end(seconds, duration_s):
        current['s'] = 0
        current['duration'] = 0
    else:
        current['s'] = int(seconds)
        try:
            current['duration'] = max(0, int(float(duration_s or 0)))
        except (TypeError, ValueError):
            current['duration'] = int(current.get('duration') or 0)
    current['updated'] = int(time.time())
    current['kind'] = 'vod'
    items.insert(0, current)
    data['kick_history'] = items[:MAX_KICK_HISTORY]
    save()


def kick_resume_seconds(url, duration_s=None):
    """Kick resume seconds."""
    if not _is_kick_vod_url(url):
        return 0.0
    item = kick_history_item_by_url(url)
    if not item or item.get('kind') != 'vod':
        return 0.0
    seconds = float(item.get('s') or 0)
    if seconds < IPTV_RESUME_MIN_S:
        return 0.0
    if _yt_resume_near_end(seconds, duration_s if duration_s is not None else item.get('duration')):
        update_kick_position(url, 0, 0)
        return 0.0
    return seconds


def kick_continue_watching():
    """Kick continue watching."""
    found = []
    for item in kick_history():
        if item.get('kind') != 'vod':
            continue
        seconds = int(item.get('s') or 0)
        if seconds < IPTV_RESUME_MIN_S:
            continue
        if _yt_resume_near_end(seconds, item.get('duration') or 0):
            continue
        found.append(item)
    return found


def clear_kick_position(url):
    """Limpia kick position."""
    update_kick_position(url, 0, 0)


def kick_history():
    """Kick historial."""
    items = []
    seen = set()
    for raw in load().get('kick_history') or []:
        entry = _clean_kick_history_entry(raw)
        if not entry or entry['url'] in seen:
            continue
        seen.add(entry['url'])
        items.append(entry)
    return items[:MAX_KICK_HISTORY]


def kick_history_item_by_url(url):
    """Kick historial item by url."""
    wanted = str(url or '').strip()
    if not wanted:
        return None
    for item in kick_history():
        if item.get('url') == wanted:
            return item
    return None


def kick_history_label(item, limit=46, with_time=False):
    """Kick historial label."""
    name = str((item or {}).get('name') or 'Kick').strip()
    name = truncate_ui_text(name, limit)
    base = f'Kick · {name}'
    seconds = int((item or {}).get('s') or 0)
    if not with_time or seconds < IPTV_RESUME_MIN_S or (item or {}).get('kind') != 'vod':
        return base
    stamp = format_iptv_clock(seconds)
    try:
        duration = int((item or {}).get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration > 0:
        return f'{base}  ·  {stamp} / {format_iptv_clock(duration)}'
    return f'{base}  ·  {stamp}'


def clear_kick_history():
    """Limpia kick historial."""
    data = load()
    if not data.get('kick_history'):
        return
    data['kick_history'] = []
    save()


def _clean_youtube_queue_item(item):
    """Uso interno: clean youtube cola item."""
    if isinstance(item, (tuple, list)) and len(item) >= 2:
        name, url = item[0], item[1]
        item = {'name': name, 'url': url}
    if not isinstance(item, dict):
        return None
    url = str(item.get('url') or '').strip()
    if not url:
        return None
    return {
        'name': str(item.get('name') or '').strip() or 'YouTube',
        'url': url,
    }


def youtube_queue():
    """Youtube cola."""
    items = []
    seen = set()
    for raw in load().get('youtube_queue') or []:
        entry = _clean_youtube_queue_item(raw)
        if not entry or entry['url'] in seen:
            continue
        seen.add(entry['url'])
        items.append(entry)
    return items[:MAX_YT_QUEUE]


def enqueue_youtube_queue(items):
    """Enqueue youtube cola."""
    queue = youtube_queue()
    existing = {entry['url'] for entry in queue}
    added = 0
    for raw in items or []:
        entry = _clean_youtube_queue_item(raw)
        if not entry or entry['url'] in existing:
            continue
        queue.append(entry)
        existing.add(entry['url'])
        added += 1
    if added:
        data = load()
        data['youtube_queue'] = queue[:MAX_YT_QUEUE]
        save()
    return added


def pop_youtube_queue(index=0):
    """Pop youtube cola."""
    queue = youtube_queue()
    if not (0 <= index < len(queue)):
        return None
    item = queue.pop(index)
    data = load()
    data['youtube_queue'] = queue
    save()
    return item


def move_youtube_queue(index, delta):
    """Mueve youtube cola."""
    queue = youtube_queue()
    dest = index + int(delta or 0)
    if not (0 <= index < len(queue) and 0 <= dest < len(queue)):
        return False
    item = queue.pop(index)
    queue.insert(dest, item)
    data = load()
    data['youtube_queue'] = queue
    save()
    return True


def remove_youtube_queue(index):
    """Quita youtube cola."""
    return pop_youtube_queue(index) is not None


def clear_youtube_queue():
    """Limpia youtube cola."""
    data = load()
    if not data.get('youtube_queue'):
        return
    data['youtube_queue'] = []
    save()


def _is_youtube_url(url):
    """Uso interno: is youtube URL."""
    text = (url or '').lower()
    return 'youtube.com' in text or 'youtu.be' in text


def format_iptv_clock(seconds):
    """Formatea IPTV clock."""
    try:
        total = max(0, int(float(seconds or 0)))
    except (TypeError, ValueError):
        total = 0
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{secs:02d}'
    return f'{minutes:02d}:{secs:02d}'


def _clean_iptv_history_entry(item):
    """Uso interno: clean IPTV historial entry."""
    if not isinstance(item, dict):
        return None
    url = str(item.get('url') or '').strip()
    if not url or _is_youtube_url(url):
        return None
    kind = 'vod' if item.get('kind') == 'vod' or is_iptv_vod(url) else 'live'
    try:
        seconds = max(0, int(float(item.get('s') or 0)))
    except (TypeError, ValueError):
        seconds = 0
    try:
        duration = max(0, int(float(item.get('duration') or 0)))
    except (TypeError, ValueError):
        duration = 0
    try:
        updated = int(item.get('updated') or 0)
    except (TypeError, ValueError):
        updated = 0
    if kind != 'vod':
        seconds = 0
        duration = 0
    return {
        'name': str(item.get('name') or '').strip() or 'Sin nombre',
        'url': url,
        'kind': kind,
        'group': str(item.get('group') or '').strip(),
        's': seconds,
        'duration': duration,
        'updated': updated,
    }


def iptv_history():
    """Iptv historial."""
    items = []
    seen = set()
    for raw in load().get('iptv_history') or []:
        entry = _clean_iptv_history_entry(raw)
        if not entry or entry['url'] in seen:
            continue
        seen.add(entry['url'])
        items.append(entry)
    return items[:MAX_IPTV_HISTORY]


def iptv_history_item(url):
    """Iptv historial item."""
    url = str(url or '').strip()
    if not url:
        return None
    for item in iptv_history():
        if item['url'] == url:
            return item
    return None


def iptv_history_label(item, with_time=False, limit=46):
    """Iptv historial label."""
    name = str((item or {}).get('name') or 'Sin nombre').strip() or 'Sin nombre'
    name = truncate_ui_text(name, limit)
    if not with_time or (item or {}).get('kind') != 'vod':
        return name
    try:
        seconds = int((item or {}).get('s') or 0)
    except (TypeError, ValueError):
        seconds = 0
    if seconds < IPTV_RESUME_MIN_S:
        return name
    stamp = format_iptv_clock(seconds)
    try:
        duration = int((item or {}).get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration > 0:
        return f'{name}  ·  {stamp} / {format_iptv_clock(duration)}'
    return f'{name}  ·  {stamp}'


def iptv_continue_watching():
    """Iptv continue watching."""
    found = []
    for item in iptv_history():
        if item.get('kind') != 'vod':
            continue
        seconds = int(item.get('s') or 0)
        if seconds < IPTV_RESUME_MIN_S:
            continue
        if _yt_resume_near_end(seconds, item.get('duration') or 0):
            continue
        found.append(item)
    return found


def remember_iptv_history(name, url, group=''):
    """Remember iptv historial."""
    url = str(url or '').strip()
    if not url or _is_youtube_url(url):
        return
    kind = 'vod' if is_iptv_vod(url) else 'live'
    data = load()
    items = []
    previous = None
    for raw in data.get('iptv_history') or []:
        entry = _clean_iptv_history_entry(raw)
        if not entry:
            continue
        if entry['url'] == url:
            previous = entry
            continue
        items.append(entry)
    seconds = int((previous or {}).get('s') or 0) if kind == 'vod' else 0
    duration = int((previous or {}).get('duration') or 0) if kind == 'vod' else 0
    items.insert(0, {
        'name': str(name or '').strip() or (previous or {}).get('name') or 'Sin nombre',
        'url': url,
        'kind': kind,
        'group': str(group or '').strip() or (previous or {}).get('group') or '',
        's': seconds,
        'duration': duration,
        'updated': int(time.time()),
    })
    data['iptv_history'] = items[:MAX_IPTV_HISTORY]
    save()


def update_iptv_position(url, seconds, duration_s=None):
    """Actualiza IPTV position."""
    url = str(url or '').strip()
    if not url or _is_youtube_url(url) or not is_iptv_vod(url):
        return
    try:
        seconds = float(seconds or 0)
    except (TypeError, ValueError):
        return
    data = load()
    items = []
    current = None
    for raw in data.get('iptv_history') or []:
        entry = _clean_iptv_history_entry(raw)
        if not entry:
            continue
        if entry['url'] == url:
            current = entry
            continue
        items.append(entry)
    if current is None:
        return
    if seconds < IPTV_RESUME_MIN_S or _yt_resume_near_end(seconds, duration_s):
        current['s'] = 0
        current['duration'] = 0
    else:
        current['s'] = int(seconds)
        try:
            current['duration'] = max(0, int(float(duration_s or 0)))
        except (TypeError, ValueError):
            current['duration'] = int(current.get('duration') or 0)
    current['updated'] = int(time.time())
    current['kind'] = 'vod'
    items.insert(0, current)
    data['iptv_history'] = items[:MAX_IPTV_HISTORY]
    save()


def iptv_resume_seconds(url, duration_s=None):
    """Iptv resume seconds."""
    item = iptv_history_item(url)
    if not item or item.get('kind') != 'vod':
        return 0.0
    seconds = float(item.get('s') or 0)
    if seconds < IPTV_RESUME_MIN_S:
        return 0.0
    if _yt_resume_near_end(seconds, duration_s if duration_s is not None else item.get('duration')):
        update_iptv_position(url, 0, 0)
        return 0.0
    return seconds


def remove_iptv_history(url):
    """Quita IPTV historial."""
    url = str(url or '').strip()
    if not url:
        return
    data = load()
    items = [
        entry for entry in (_clean_iptv_history_entry(raw) for raw in data.get('iptv_history') or [])
        if entry and entry['url'] != url
    ]
    data['iptv_history'] = items
    save()


def clear_iptv_history():
    """Limpia IPTV historial."""
    data = load()
    if not data.get('iptv_history'):
        return
    data['iptv_history'] = []
    save()


def remember_window(name, geometry):
    """Remember ventana."""
    if not geometry:
        return
    save({'windows': {name: geometry}})


def apply_geometry(window, name, fallback=None):
    """Aplica geometry."""
    geometry = (load().get('windows') or {}).get(name) or fallback
    if not geometry:
        return False
    try:
        window.geometry(geometry)
        window.update_idletasks()
        x, y = window.winfo_x(), window.winfo_y()
        width, height = window.winfo_width(), window.winfo_height()
        screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()
        if width < 200 or height < 150:
            return False
        if x > screen_w - 80 or y > screen_h - 80 or x + width < 80 or y + height < 80:
            return False
        return True
    except tk.TclError:
        return False


def needs_onboarding():
    """True si debe mostrarse el asistente de primer arranque."""
    if not os.path.isfile(CONFIG_PATH):
        return True
    try:
        with open(CONFIG_PATH, encoding='utf-8') as handle:
            stored = json.load(handle)
        if not isinstance(stored, dict):
            return True
        if 'onboarding_completed' not in stored:
            return False
        return not bool(stored.get('onboarding_completed'))
    except (OSError, json.JSONDecodeError):
        return True


def set_onboarding_completed(value=True):
    """Marca el asistente de configuración como completado u omitido."""
    save({'onboarding_completed': bool(value)})


def get_onboarding_completed():
    """True si el usuario ya completó u omitió el asistente."""
    return not needs_onboarding()


def needs_player_shortcuts_hint():
    """True si debe mostrarse el overlay de atajos la primera vez en el reproductor."""
    if not os.path.isfile(CONFIG_PATH):
        return True
    try:
        with open(CONFIG_PATH, encoding='utf-8') as handle:
            stored = json.load(handle)
        if not isinstance(stored, dict):
            return True
        if 'player_shortcuts_hint_shown' not in stored:
            return False
        return not bool(stored.get('player_shortcuts_hint_shown'))
    except (OSError, json.JSONDecodeError):
        return True


def set_player_shortcuts_hint_shown(value=True):
    """Marca el overlay de atajos del reproductor como ya visto."""
    save({'player_shortcuts_hint_shown': bool(value)})


def should_show_vlc_subtitle_style_warn():
    """True si aún no se mostró el aviso de subtítulos sin estilo freetype."""
    return not bool(load().get('vlc_subtitle_style_warn_shown', False))


def set_vlc_subtitle_style_warn_shown(value=True):
    """Marca el aviso de subtítulos VLC como ya mostrado."""
    save({'vlc_subtitle_style_warn_shown': bool(value)})


def get_usage_profile():
    """Obtiene el perfil de uso seleccionado."""
    from usage_profiles import normalize_usage_profile
    return normalize_usage_profile(load().get('usage_profile', 'custom'))


def set_usage_profile(profile_id):
    """Guarda el id del perfil de uso."""
    from usage_profiles import normalize_usage_profile
    save({'usage_profile': normalize_usage_profile(profile_id)})


def capture_geometry(window):
    """Capture geometry."""
    try:
        if window.state() == 'zoomed':
            return None
        return window.geometry()
    except tk.TclError:
        return None
