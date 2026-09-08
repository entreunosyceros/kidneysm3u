"""Caché corta de metadatos yt-dlp (extract_info) para evitar extracciones repetidas."""

import copy
import threading
import time

DEFAULT_TTL_S = 120
MAX_ENTRIES = 48

_lock = threading.Lock()
_store = {}


def _normalize_url(url):
    """Normaliza URL para clave de caché."""
    text = (url or '').strip()
    if not text:
        return ''
    return text.split('#', 1)[0].rstrip('/')


def _cache_key(url, tag=''):
    """Clave interna (url, tag)."""
    return (_normalize_url(url), (tag or '').strip())


def get_cached_info(url, tag=''):
    """Devuelve info cacheada o None si no hay / caducó."""
    key = _cache_key(url, tag)
    if not key[0]:
        return None
    now = time.monotonic()
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None
        expires_at, info = entry
        if expires_at <= now:
            _store.pop(key, None)
            return None
        try:
            return copy.deepcopy(info)
        except Exception:
            return info


def put_cached_info(url, info, tag='', ttl=DEFAULT_TTL_S):
    """Guarda info en caché con TTL corto."""
    key = _cache_key(url, tag)
    if not key[0] or info is None:
        return
    try:
        ttl = max(15, min(int(ttl or DEFAULT_TTL_S), 600))
    except (TypeError, ValueError):
        ttl = DEFAULT_TTL_S
    expires_at = time.monotonic() + ttl
    with _lock:
        _store[key] = (expires_at, info)
        if len(_store) > MAX_ENTRIES:
            oldest = sorted(_store.items(), key=lambda item: item[1][0])
            for stale_key, _ in oldest[: max(1, len(_store) - MAX_ENTRIES)]:
                _store.pop(stale_key, None)


def invalidate_cached_info(url=None, tag=None):
    """Invalida una URL (todas las tags), una tag concreta, o toda la caché."""
    with _lock:
        if url is None and tag is None:
            _store.clear()
            return
        if url is not None and tag is not None:
            _store.pop(_cache_key(url, tag), None)
            return
        if url is not None:
            needle = _normalize_url(url)
            for key in [item for item in _store if item[0] == needle]:
                _store.pop(key, None)
            return
        needle_tag = (tag or '').strip()
        for key in [item for item in _store if item[1] == needle_tag]:
            _store.pop(key, None)


def extract_info_cached(ydl, url, download=False, tag='', ttl=DEFAULT_TTL_S, use_cache=True):
    """extract_info con caché opcional (solo download=False)."""
    if use_cache and not download:
        cached = get_cached_info(url, tag=tag)
        if cached is not None:
            return cached
    info = ydl.extract_info(url, download=download)
    if use_cache and not download and info is not None:
        put_cached_info(url, info, tag=tag, ttl=ttl)
    return info


def cache_stats():
    """Estadísticas simples (tests / depuración)."""
    now = time.monotonic()
    with _lock:
        alive = sum(1 for expires_at, _ in _store.values() if expires_at > now)
        return {'entries': len(_store), 'alive': alive}
