"""Configuración persistente: sesión, ventanas y archivos recientes."""

import json
import os
import time
import tkinter as tk

from m3u_parse import is_iptv_vod

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
MAX_RECENT = 12
MAX_YT_RESUME = 80
MAX_YT_HISTORY = 40
MAX_YT_QUEUE = 80
MAX_IPTV_HISTORY = 25
YT_RESUME_MIN_S = 15
YT_RESUME_END_S = 20
IPTV_RESUME_MIN_S = 15
YOUTUBE_QUALITIES = (0, 360, 720, 1080)

COOKIE_BROWSERS = ('auto', 'firefox', 'chrome', 'chromium', 'brave', 'edge')

_DEFAULTS = {
    'theme': 'dark',
    'recent_files': [],
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
    'youtube_queue': [],
    'iptv_history': [],
    'youtube_quality': 720,
}

_cache = None


def _deep_merge(base, incoming):
    merged = dict(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load():
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
    theme = str(load().get('theme') or 'dark').strip().lower()
    return 'dark' if theme in ('dark', 'equilux') else 'light'


def set_theme(theme):
    save({'theme': 'dark' if theme in ('dark', 'equilux', True) else 'light'})


def get_volume():
    try:
        return max(0, min(100, int(load().get('volume', 50))))
    except (TypeError, ValueError):
        return 50


def set_volume(value):
    try:
        save({'volume': max(0, min(100, int(value)))})
    except (TypeError, ValueError):
        pass


def suggested_download_dir():
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
    stored = str(load().get('download_dir') or '').strip()
    if stored and os.path.isdir(stored):
        return stored
    return suggested_download_dir()


def set_download_dir(path):
    save({'download_dir': str(path or '').strip()})


def get_open_folder_after_download():
    return bool(load().get('open_folder_after_download', True))


def set_open_folder_after_download(value):
    save({'open_folder_after_download': bool(value)})


def get_cookie_browser():
    value = str(load().get('cookie_browser') or 'auto').strip().lower()
    return value if value in COOKIE_BROWSERS else 'auto'


def set_cookie_browser(name):
    value = str(name or 'auto').strip().lower()
    save({'cookie_browser': value if value in COOKIE_BROWSERS else 'auto'})


def get_remember_last_list():
    return bool(load().get('remember_last_list', True))


def set_remember_last_list(value):
    save({'remember_last_list': bool(value)})


def get_show_channel_logos():
    return bool(load().get('show_channel_logos', True))


def set_show_channel_logos(value):
    save({'show_channel_logos': bool(value)})


def get_epg_url():
    return str(load().get('epg_url') or '').strip()


def set_epg_url(url):
    save({'epg_url': str(url or '').strip()})


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
    height = normalize_youtube_quality(
        get_youtube_quality() if value is None else value
    )
    if height <= 0:
        return 'Mejor disponible'
    return f'{height}p'


def youtube_quality_cache_key(value=None):
    height = normalize_youtube_quality(
        get_youtube_quality() if value is None else value
    )
    return 'best' if height <= 0 else str(height)


def get_youtube_quality():
    return normalize_youtube_quality(load().get('youtube_quality', 720))


def set_youtube_quality(height):
    save({'youtube_quality': normalize_youtube_quality(height)})


def remember_playlist(path, kind='file'):
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


def remember_sidebar(items, source='', kind='items', groups=None, tvg_ids=None, epg_urls=None, logos=None):
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
    if isinstance(entry, (int, float)):
        return float(entry)
    if isinstance(entry, dict):
        try:
            return float(entry.get('s') or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _yt_resume_near_end(seconds, duration_s):
    try:
        duration_s = float(duration_s or 0)
    except (TypeError, ValueError):
        duration_s = 0.0
    if duration_s <= 0 or seconds < 0:
        return False
    margin = min(YT_RESUME_END_S, max(5.0, duration_s * 0.05))
    return (duration_s - seconds) <= margin


def youtube_resume_seconds(video_id, duration_s=None):
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
    video_id = str(video_id or '').strip()
    if len(video_id) != 11:
        return
    data = load()
    _upsert_youtube_history(data, video_id, title=title, url=url)
    save()


def youtube_history():
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
    video_id = str(video_id or '').strip()
    if len(video_id) != 11:
        return None
    for item in youtube_history():
        if item['id'] == video_id:
            return item
    return None


def youtube_history_item_by_url(url):
    url = str(url or '').strip()
    if not url:
        return None
    for item in youtube_history():
        if item.get('url') == url:
            return item
    return None


def youtube_history_label(item, with_time=False, limit=46):
    name = str((item or {}).get('name') or 'YouTube').strip() or 'YouTube'
    if len(name) > limit:
        name = name[: limit - 1] + '…'
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
    data = load()
    changed = bool(data.get('youtube_history') or data.get('youtube_resume'))
    if not changed:
        return
    data['youtube_history'] = []
    data['youtube_resume'] = {}
    save()


def _clean_youtube_queue_item(item):
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
    queue = youtube_queue()
    if not (0 <= index < len(queue)):
        return None
    item = queue.pop(index)
    data = load()
    data['youtube_queue'] = queue
    save()
    return item


def move_youtube_queue(index, delta):
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
    return pop_youtube_queue(index) is not None


def clear_youtube_queue():
    data = load()
    if not data.get('youtube_queue'):
        return
    data['youtube_queue'] = []
    save()


def _is_youtube_url(url):
    text = (url or '').lower()
    return 'youtube.com' in text or 'youtu.be' in text


def format_iptv_clock(seconds):
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
    url = str(url or '').strip()
    if not url:
        return None
    for item in iptv_history():
        if item['url'] == url:
            return item
    return None


def iptv_history_label(item, with_time=False, limit=46):
    name = str((item or {}).get('name') or 'Sin nombre').strip() or 'Sin nombre'
    if len(name) > limit:
        name = name[: limit - 1] + '…'
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
    data = load()
    if not data.get('iptv_history'):
        return
    data['iptv_history'] = []
    save()


def remember_window(name, geometry):
    if not geometry:
        return
    save({'windows': {name: geometry}})


def apply_geometry(window, name, fallback=None):
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


def capture_geometry(window):
    try:
        if window.state() == 'zoomed':
            return None
        return window.geometry()
    except tk.TclError:
        return None
