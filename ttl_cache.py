"""Caché genérica con TTL (búsquedas de plataformas, etc.)."""

import copy
import threading
import time

DEFAULT_TTL_S = 180
MAX_ENTRIES = 64

_lock = threading.Lock()
_store = {}


def _normalize_key(key):
    """Normaliza clave de caché."""
    return str(key or '').strip().lower()


def get_cached(key):
    """Devuelve valor cacheado o None si no hay / caducó."""
    cache_key = _normalize_key(key)
    if not cache_key:
        return None
    now = time.monotonic()
    with _lock:
        entry = _store.get(cache_key)
        if not entry:
            return None
        expires_at, value = entry
        if expires_at <= now:
            _store.pop(cache_key, None)
            return None
        try:
            return copy.deepcopy(value)
        except Exception:
            return value


def put_cached(key, value, ttl=DEFAULT_TTL_S):
    """Guarda valor con TTL."""
    cache_key = _normalize_key(key)
    if not cache_key or value is None:
        return
    try:
        ttl = max(15, min(int(ttl or DEFAULT_TTL_S), 900))
    except (TypeError, ValueError):
        ttl = DEFAULT_TTL_S
    expires_at = time.monotonic() + ttl
    with _lock:
        _store[cache_key] = (expires_at, value)
        if len(_store) > MAX_ENTRIES:
            oldest = sorted(_store.items(), key=lambda item: item[1][0])
            for stale_key, _ in oldest[: max(1, len(_store) - MAX_ENTRIES)]:
                _store.pop(stale_key, None)


def invalidate(key=None):
    """Invalida una clave o toda la caché."""
    with _lock:
        if key is None:
            _store.clear()
            return
        _store.pop(_normalize_key(key), None)


def cache_stats():
    """Estadísticas simples (tests)."""
    now = time.monotonic()
    with _lock:
        alive = sum(1 for expires_at, _ in _store.values() if expires_at > now)
        return {'entries': len(_store), 'alive': alive}
