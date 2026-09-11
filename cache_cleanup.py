"""Tamaños y limpieza de cachés locales desde Preferencias."""

import os
import re
import time

import app_config
from app_paths import data_dir

OLD_RECORDINGS_DAYS = 30
_RECORDING_NAME = re.compile(r'_\d{8}-\d{6}\.(ts|mkv)$', re.I)
_RECORDING_EXT = {'.ts', '.mkv'}
YT_CACHE_DIRNAME = 'kidneysm3u_yt_cache'

# Orden de filas en Preferencias y en diálogos de vaciado.
CACHE_ROW_SPECS = (
    ('epg', 'epg_cache/'),
    ('logos', 'Logos'),
    ('youtube', 'YouTube (disco)'),
    ('recordings', 'Grabaciones antiguas'),
    ('search', 'Búsquedas (memoria)'),
    ('ydl', 'Metadatos yt-dlp'),
)


def format_bytes(value):
    """Devuelve un tamaño legible (B, KB, MB, GB)."""
    try:
        amount = int(value or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount < 1024:
        return f'{amount} B'
    if amount < 1024 * 1024:
        return f'{amount / 1024:.1f} KB'
    if amount < 1024 * 1024 * 1024:
        return f'{amount / (1024 * 1024):.1f} MB'
    return f'{amount / (1024 * 1024 * 1024):.2f} GB'


def _unique_dirs(folders):
    """Carpetas normalizadas sin duplicar."""
    seen = set()
    out = []
    for folder in folders or ():
        folder = (folder or '').strip()
        if not folder:
            continue
        key = os.path.normpath(folder)
        if key in seen:
            continue
        seen.add(key)
        out.append(folder)
    return out


def _iter_top_files(folders, *, suffix=None):
    """Archivos de primer nivel en carpetas (opcionalmente filtrados por extensión)."""
    suffix = (suffix or '').lower()
    for folder in _unique_dirs(folders):
        if not os.path.isdir(folder):
            continue
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if suffix and not name.lower().endswith(suffix):
                continue
            path = os.path.join(folder, name)
            try:
                if os.path.isfile(path):
                    yield path, os.path.getsize(path)
            except OSError:
                continue


def _folder_stats(folders, *, suffix=None):
    """Bytes y número de archivos (primer nivel) en una o varias carpetas."""
    folders = _unique_dirs(folders if not isinstance(folders, str) else [folders])
    total = 0
    count = 0
    for _path, size in _iter_top_files(folders, suffix=suffix):
        total += size
        count += 1
    return {
        'path': folders[0] if folders else '',
        'paths': folders,
        'bytes': total,
        'files': count,
    }


def epg_cache_dirs():
    """Carpetas de epg_cache (actual + legacy si existe y es distinta)."""
    import logo_cache

    primary = logo_cache.cache_dir()
    dirs = [primary]
    legacy = logo_cache.legacy_cache_dir()
    if (
        legacy
        and os.path.normpath(legacy) != os.path.normpath(primary)
        and os.path.isdir(legacy)
    ):
        dirs.append(legacy)
    return dirs


def epg_cache_dir():
    """Carpeta epg_cache principal (data_dir)."""
    import logo_cache
    return logo_cache.cache_dir()


def youtube_cache_dir():
    """Carpeta kidneysm3u_yt_cache en el directorio de datos."""
    path = os.path.join(data_dir(), YT_CACHE_DIRNAME)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def recordings_folder():
    """Carpeta donde se guardan grabaciones y descargas."""
    return (app_config.get_download_dir() or app_config.suggested_download_dir() or '').strip()


def _memory_stats():
    """Cachés en memoria de búsqueda y yt-dlp."""
    try:
        import ttl_cache
        search_mem = ttl_cache.cache_stats()
    except Exception:
        search_mem = {'entries': 0, 'alive': 0}
    try:
        import ydl_cache
        ydl_mem = ydl_cache.cache_stats()
    except Exception:
        ydl_mem = {'entries': 0, 'alive': 0}
    return search_mem, ydl_mem


def stats():
    """Estadísticas de las cachés conocidas."""
    epg_dirs = epg_cache_dirs()
    search_mem, ydl_mem = _memory_stats()
    return {
        'epg_cache': _folder_stats(epg_dirs),
        'logos': _folder_stats(epg_dirs, suffix='.png'),
        'youtube': _folder_stats([youtube_cache_dir()]),
        'old_recordings': old_recordings_stats(OLD_RECORDINGS_DAYS),
        'search_memory': search_mem,
        'ydl_memory': ydl_mem,
    }


def _iter_old_recordings(folder, max_age_days):
    """Rutas y tamaños de grabaciones .ts/.mkv más antiguas que max_age_days."""
    folder = (folder or '').strip()
    if not folder or not os.path.isdir(folder):
        return
    cutoff = time.time() - max(1, int(max_age_days)) * 86400
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        path = os.path.join(folder, name)
        ext = os.path.splitext(name)[1].lower()
        if ext not in _RECORDING_EXT or not _RECORDING_NAME.search(name):
            continue
        try:
            if not os.path.isfile(path) or os.path.getmtime(path) > cutoff:
                continue
            yield path, os.path.getsize(path)
        except OSError:
            continue


def old_recordings_stats(max_age_days=OLD_RECORDINGS_DAYS, folder=None):
    """Archivos de grabación antiguos en la carpeta de descargas."""
    folder = (folder or recordings_folder() or '').strip()
    total = 0
    count = 0
    for _path, size in _iter_old_recordings(folder, max_age_days):
        total += size
        count += 1
    return {'path': folder, 'bytes': total, 'files': count, 'days': max_age_days}


def _clear_files_in_folders(folders, *, suffix=None):
    """Borra archivos de primer nivel (opcionalmente por extensión)."""
    removed = 0
    freed = 0
    for path, size in _iter_top_files(folders, suffix=suffix):
        try:
            os.remove(path)
            removed += 1
            freed += size
        except OSError:
            pass
    return removed, freed


def clear_epg_cache():
    """Vacía todos los archivos de epg_cache/ (actual + legacy)."""
    return _clear_files_in_folders(epg_cache_dirs())


def clear_logo_cache():
    """Vacía solo miniaturas .png de epg_cache/."""
    return _clear_files_in_folders(epg_cache_dirs(), suffix='.png')


def clear_youtube_cache():
    """Vacía kidneysm3u_yt_cache."""
    return _clear_files_in_folders([youtube_cache_dir()])


def clear_search_memory():
    """Vacía la caché en memoria de búsquedas (TTL)."""
    import ttl_cache

    before = ttl_cache.cache_stats().get('entries') or 0
    ttl_cache.invalidate()
    return before, 0


def clear_ydl_memory():
    """Vacía la caché en memoria de metadatos yt-dlp."""
    import ydl_cache

    before = ydl_cache.cache_stats().get('entries') or 0
    ydl_cache.invalidate_cached_info()
    return before, 0


def clear_old_recordings(max_age_days=OLD_RECORDINGS_DAYS, folder=None):
    """Borra grabaciones .ts/.mkv antiguas en la carpeta de descargas."""
    folder = (folder or recordings_folder() or '').strip()
    removed = 0
    freed = 0
    for path, size in _iter_old_recordings(folder, max_age_days):
        try:
            os.remove(path)
            removed += 1
            freed += size
        except OSError:
            pass
    return removed, freed


def clear_all_caches(*, include_old_recordings=False):
    """Vacía logos/epg, YouTube en disco y cachés en memoria. Opcional: grabaciones viejas."""
    removed = 0
    freed = 0
    actions = [clear_epg_cache, clear_youtube_cache, clear_search_memory, clear_ydl_memory]
    if include_old_recordings:
        actions.append(clear_old_recordings)
    for action in actions:
        try:
            part_removed, part_freed = action()
        except Exception:
            continue
        removed += int(part_removed or 0)
        freed += int(part_freed or 0)
    return removed, freed


def _row_value(key, data):
    """Texto de tamaño/conteo para una fila de caché."""
    if key == 'epg':
        part = data.get('epg_cache') or {}
        return f"{format_bytes(part.get('bytes'))} · {part.get('files') or 0} archivos"
    if key == 'logos':
        part = data.get('logos') or {}
        return f"{format_bytes(part.get('bytes'))} · {part.get('files') or 0} logos"
    if key == 'youtube':
        part = data.get('youtube') or {}
        return f"{format_bytes(part.get('bytes'))} · {part.get('files') or 0} archivos"
    if key == 'recordings':
        part = data.get('old_recordings') or {}
        return (
            f"{format_bytes(part.get('bytes'))} · {part.get('files') or 0} grabaciones "
            f"(+{part.get('days') or OLD_RECORDINGS_DAYS} días)"
        )
    if key == 'search':
        part = data.get('search_memory') or {}
        return f"{int(part.get('alive') or 0)} vigentes · {int(part.get('entries') or 0)} entradas"
    if key == 'ydl':
        part = data.get('ydl_memory') or {}
        return f"{int(part.get('alive') or 0)} vigentes · {int(part.get('entries') or 0)} entradas"
    return '—'


def stats_display(data=None):
    """Filas (key, título, valor) para Preferencias y diálogos."""
    data = stats() if data is None else data
    return [(key, title, _row_value(key, data)) for key, title in CACHE_ROW_SPECS]


def format_stats_lines(data=None):
    """Líneas legibles para diálogos."""
    return [f'{title}: {value}' for _key, title, value in stats_display(data)]
