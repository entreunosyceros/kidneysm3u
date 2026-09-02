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
    """Bytes y número de archivos en una carpeta (sin recursión profunda)."""
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


def epg_cache_dir():
    """Carpeta epg_cache/."""
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


def stats():
    """Estadísticas de las cachés conocidas."""
    epg_dir = epg_cache_dir()
    yt_dir = youtube_cache_dir()
    rec_dir = recordings_folder()
    logo_bytes = 0
    logo_files = 0
    if epg_dir and os.path.isdir(epg_dir):
        try:
            for name in os.listdir(epg_dir):
                if not name.lower().endswith('.png'):
                    continue
                path = os.path.join(epg_dir, name)
                try:
                    if os.path.isfile(path):
                        logo_bytes += os.path.getsize(path)
                        logo_files += 1
                except OSError:
                    pass
        except OSError:
            pass
    old_rec = old_recordings_stats(OLD_RECORDINGS_DAYS, rec_dir)
    return {
        'epg_cache': _folder_stats(epg_dir),
        'logos': {'path': epg_dir, 'bytes': logo_bytes, 'files': logo_files},
        'youtube': _folder_stats(yt_dir),
        'old_recordings': old_rec,
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


def clear_epg_cache():
    """Vacía todos los archivos de epg_cache/."""
    folder = epg_cache_dir()
    removed = 0
    freed = 0
    if not folder or not os.path.isdir(folder):
        return removed, freed
    try:
        names = os.listdir(folder)
    except OSError:
        return 0, 0
    for name in names:
        path = os.path.join(folder, name)
        try:
            if os.path.isfile(path):
                freed += os.path.getsize(path)
                os.remove(path)
                removed += 1
        except OSError:
            pass
    return removed, freed


def clear_logo_cache():
    """Vacía solo miniaturas .png de epg_cache/."""
    folder = epg_cache_dir()
    removed = 0
    freed = 0
    if not os.path.isdir(folder):
        return removed, freed
    try:
        names = os.listdir(folder)
    except OSError:
        return 0, 0
    for name in names:
        if not name.lower().endswith('.png'):
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


def clear_youtube_cache():
    """Vacía kidneysm3u_yt_cache."""
    folder = youtube_cache_dir()
    removed = 0
    freed = 0
    if not folder or not os.path.isdir(folder):
        return removed, freed
    try:
        names = os.listdir(folder)
    except OSError:
        return 0, 0
    for name in names:
        path = os.path.join(folder, name)
        try:
            if os.path.isfile(path):
                freed += os.path.getsize(path)
                os.remove(path)
                removed += 1
        except OSError:
            pass
    return removed, freed


def clear_old_recordings(max_age_days=OLD_RECORDINGS_DAYS, folder=None):
    """Borra grabaciones .ts/.mkv antiguas en la carpeta de descargas."""
    folder = (folder or recordings_folder() or '').strip()
    removed = 0
    freed = 0
    if not folder or not os.path.isdir(folder):
        return removed, freed
    cutoff = time.time() - max(1, int(max_age_days)) * 86400
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
