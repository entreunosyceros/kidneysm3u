"""Tamaños y limpieza de cachés locales desde Preferencias."""

import os
import re
import time

import app_config

OLD_RECORDINGS_DAYS = 30
_RECORDING_NAME = re.compile(r'_\d{8}-\d{6}\.(ts|mkv)$', re.I)
_RECORDING_EXT = {'.ts', '.mkv'}


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


def _folder_stats(folder):
    """Bytes y número de archivos en una carpeta (solo archivos de primer nivel)."""
    total = 0
    count = 0
    if not folder or not os.path.isdir(folder):
        return {'path': folder or '', 'bytes': 0, 'files': 0}
    try:
        names = os.listdir(folder)
    except OSError:
        return {'path': folder, 'bytes': 0, 'files': 0}
    for name in names:
        path = os.path.join(folder, name)
        try:
            if os.path.isfile(path):
                total += os.path.getsize(path)
                count += 1
        except OSError:
            continue
    return {'path': folder, 'bytes': total, 'files': count}


def _merge_folder_stats(folders):
    """Suma varias carpetas (p. ej. epg_cache actual + legacy)."""
    paths = []
    total = 0
    count = 0
    seen = set()
    for folder in folders:
        folder = (folder or '').strip()
        if not folder:
            continue
        key = os.path.normpath(folder)
        if key in seen:
            continue
        seen.add(key)
        part = _folder_stats(folder)
        if part['path']:
            paths.append(part['path'])
        total += int(part['bytes'] or 0)
        count += int(part['files'] or 0)
    return {
        'path': paths[0] if paths else '',
        'paths': paths,
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
    """Carpeta temporal kidneysm3u_yt_cache."""
    from youtube_player import youtube_cache_dir as yt_dir
    return yt_dir()


def recordings_folder():
    """Carpeta donde se guardan grabaciones y descargas."""
    folder = (app_config.get_download_dir() or app_config.suggested_download_dir() or '').strip()
    return folder


def _logo_stats(folders):
    """Cuenta solo miniaturas .png en las carpetas dadas."""
    logo_bytes = 0
    logo_files = 0
    paths = []
    seen = set()
    for folder in folders:
        folder = (folder or '').strip()
        if not folder or not os.path.isdir(folder):
            continue
        key = os.path.normpath(folder)
        if key in seen:
            continue
        seen.add(key)
        paths.append(folder)
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if not name.lower().endswith('.png'):
                continue
            path = os.path.join(folder, name)
            try:
                if os.path.isfile(path):
                    logo_bytes += os.path.getsize(path)
                    logo_files += 1
            except OSError:
                pass
    return {
        'path': paths[0] if paths else '',
        'paths': paths,
        'bytes': logo_bytes,
        'files': logo_files,
    }


def stats():
    """Estadísticas de las cachés conocidas."""
    epg_dirs = epg_cache_dirs()
    yt_dir = youtube_cache_dir()
    rec_dir = recordings_folder()
    old_rec = old_recordings_stats(OLD_RECORDINGS_DAYS, rec_dir)
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
    return {
        'epg_cache': _merge_folder_stats(epg_dirs),
        'logos': _logo_stats(epg_dirs),
        'youtube': _folder_stats(yt_dir),
        'old_recordings': old_rec,
        'search_memory': search_mem,
        'ydl_memory': ydl_mem,
    }


def old_recordings_stats(max_age_days=OLD_RECORDINGS_DAYS, folder=None):
    """Archivos de grabación antiguos en la carpeta de descargas."""
    folder = (folder or recordings_folder() or '').strip()
    if not folder or not os.path.isdir(folder):
        return {'path': folder or '', 'bytes': 0, 'files': 0, 'days': max_age_days}
    cutoff = time.time() - max(1, int(max_age_days)) * 86400
    total = 0
    count = 0
    try:
        names = os.listdir(folder)
    except OSError:
        return {'path': folder, 'bytes': 0, 'files': 0, 'days': max_age_days}
    for name in names:
        path = os.path.join(folder, name)
        ext = os.path.splitext(name)[1].lower()
        if ext not in _RECORDING_EXT or not _RECORDING_NAME.search(name):
            continue
        try:
            if not os.path.isfile(path):
                continue
            if os.path.getmtime(path) > cutoff:
                continue
            total += os.path.getsize(path)
            count += 1
        except OSError:
            continue
    return {'path': folder, 'bytes': total, 'files': count, 'days': max_age_days}


def _clear_files_in_folders(folders, predicate=None):
    """Borra archivos de primer nivel que cumplan predicate (o todos)."""
    removed = 0
    freed = 0
    seen = set()
    for folder in folders:
        folder = (folder or '').strip()
        if not folder or not os.path.isdir(folder):
            continue
        key = os.path.normpath(folder)
        if key in seen:
            continue
        seen.add(key)
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if predicate and not predicate(name):
                continue
            path = os.path.join(folder, name)
            try:
                if os.path.isfile(path):
                    freed += os.path.getsize(path)
                    os.remove(path)
                    removed += 1
            except OSError:
                pass
    return removed, freed


def clear_epg_cache():
    """Vacía todos los archivos de epg_cache/ (actual + legacy)."""
    return _clear_files_in_folders(epg_cache_dirs())


def clear_logo_cache():
    """Vacía solo miniaturas .png de epg_cache/."""
    return _clear_files_in_folders(
        epg_cache_dirs(),
        predicate=lambda name: name.lower().endswith('.png'),
    )


def clear_youtube_cache():
    """Vacía kidneysm3u_yt_cache."""
    folder = youtube_cache_dir()
    return _clear_files_in_folders([folder])


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
    stats = old_recordings_stats(max_age_days, folder)
    if not folder or not os.path.isdir(folder) or stats['files'] <= 0:
        return 0, 0
    cutoff = time.time() - max(1, int(max_age_days)) * 86400
    removed = 0
    freed = 0
    try:
        names = os.listdir(folder)
    except OSError:
        return 0, 0
    for name in names:
        path = os.path.join(folder, name)
        ext = os.path.splitext(name)[1].lower()
        if ext not in _RECORDING_EXT or not _RECORDING_NAME.search(name):
            continue
        try:
            if not os.path.isfile(path):
                continue
            if os.path.getmtime(path) > cutoff:
                continue
            freed += os.path.getsize(path)
            os.remove(path)
            removed += 1
        except OSError:
            pass
    return removed, freed
