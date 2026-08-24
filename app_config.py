"""Configuración persistente: sesión, ventanas y archivos recientes."""

import json
import os
import time
import tkinter as tk

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
MAX_RECENT = 12
MAX_YT_RESUME = 80
YT_RESUME_MIN_S = 15
YT_RESUME_END_S = 20

_DEFAULTS = {
    'theme': 'dark',
    'language': 'es',
    'recent_files': [],
    'patterns': [
        'tvg-name="ES"',
        'group-title="',
        'tvg-logo="',
    ],
    'volume': 50,
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
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
    except OSError:
        pass
    return data


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


def remember_playlist(path, kind='file'):
    if not path:
        return
    path = str(path).strip()
    recent = [item for item in load().get('recent_files') or [] if item != path]
    recent.insert(0, path)
    save({
        'recent_files': recent[:MAX_RECENT],
        'session': {
            'playlist': path,
            'playlist_kind': kind,
            'sidebar': [],
        },
    })


def remember_sidebar(items, source='', kind='items'):
    snapshot = []
    for entry in items or []:
        if isinstance(entry, dict):
            name, url = entry.get('name'), entry.get('url')
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            name, url = entry[0], entry[1]
        else:
            continue
        if url:
            snapshot.append({'name': name or '', 'url': url})
    save({
        'session': {
            'playlist': source or '',
            'playlist_kind': kind or 'items',
            'sidebar': snapshot,
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


def remember_youtube_position(video_id, seconds, duration_s=None):
    video_id = str(video_id or '').strip()
    if len(video_id) != 11:
        return
    try:
        seconds = float(seconds or 0)
    except (TypeError, ValueError):
        return
    data = load()
    resume = dict(data.get('youtube_resume') or {})
    if seconds < YT_RESUME_MIN_S:
        return
    if _yt_resume_near_end(seconds, duration_s):
        if video_id in resume:
            resume.pop(video_id, None)
            data['youtube_resume'] = resume
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
    save()


def clear_youtube_position(video_id):
    video_id = str(video_id or '').strip()
    if not video_id:
        return
    data = load()
    resume = dict(data.get('youtube_resume') or {})
    if video_id not in resume:
        return
    resume.pop(video_id, None)
    data['youtube_resume'] = resume
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
