"""Favoritos del reproductor: (nombre, url), comparados por URL."""

import json
import os

from m3u_parse import decode_m3u_bytes, parse_m3u_entries

FAVORITES_KIND = 'kidneysm3u-favorites'
FAVORITES_FORMAT = 1
MAX_FAVORITES_FILE_BYTES = 20 * 1024 * 1024


def favorite_name(item):
    if isinstance(item, (list, tuple)) and item:
        return str(item[0] or '').strip()
    return ''


def favorite_url(item):
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return str(item[1] or '').strip()
    return ''


def favorite_entry(name, url):
    return [str(name or '').strip() or 'Canal', str(url or '').strip()]


def favorites_contain(favorites, name, url):
    wanted = str(url or '').strip()
    if not wanted:
        return False
    return any(favorite_url(item) == wanted for item in favorites or ())


def normalize_favorites(items):
    out = []
    seen = set()
    for item in items or ():
        entry = favorite_entry(favorite_name(item), favorite_url(item))
        url = entry[1]
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(entry)
    return out


def add_favorite(favorites, name, url):
    """Devuelve (lista, True) si se añadió; (lista, False) si ya estaba o no hay URL."""
    current = normalize_favorites(favorites)
    entry = favorite_entry(name, url)
    if not entry[1]:
        return current, False
    if favorites_contain(current, entry[0], entry[1]):
        return current, False
    current.append(entry)
    return current, True


def remove_favorite(favorites, name, url):
    wanted = str(url or '').strip()
    current = normalize_favorites(favorites)
    if not wanted:
        return current, False
    kept = [item for item in current if favorite_url(item) != wanted]
    return kept, len(kept) != len(current)


def merge_favorites(current, incoming):
    """Añade por URL. Devuelve (lista, añadidos, ya_estaban)."""
    out = normalize_favorites(current)
    seen = {favorite_url(item) for item in out}
    added = 0
    skipped = 0
    for item in normalize_favorites(incoming):
        url = favorite_url(item)
        if url in seen:
            skipped += 1
            continue
        seen.add(url)
        out.append(item)
        added += 1
    return out, added, skipped


def favorites_payload(items):
    return {
        'kind': FAVORITES_KIND,
        'format': FAVORITES_FORMAT,
        'items': normalize_favorites(items),
    }


def parse_favorites_payload(data):
    if isinstance(data, list):
        return normalize_favorites(data)
    if not isinstance(data, dict):
        raise ValueError('El archivo no contiene una lista de favoritos.')
    blob = data.get('items')
    if blob is None:
        blob = data.get('favorites')
    if blob is None:
        blob = data.get('channels')
    if not isinstance(blob, list):
        raise ValueError('El archivo no contiene una lista de favoritos.')
    return normalize_favorites(blob)


def favorites_to_m3u(items):
    lines = ['#EXTM3U']
    for name, url in normalize_favorites(items):
        title = ' '.join(str(name or 'Canal').split())
        lines.append(f'#EXTINF:-1,{title}')
        lines.append(url)
    lines.append('')
    return '\n'.join(lines)


def read_favorites_file(path):
    """Lee JSON (favoritos.json o exportación) o M3U. No registra URLs."""
    path = os.path.abspath(str(path or ''))
    if not path or not os.path.isfile(path):
        raise ValueError('No se encontró el archivo de favoritos.')
    size = os.path.getsize(path)
    if size > MAX_FAVORITES_FILE_BYTES:
        raise ValueError('El archivo de favoritos es demasiado grande.')
    with open(path, 'rb') as handle:
        raw = handle.read()
    text = decode_m3u_bytes(raw)
    stripped = text.lstrip()
    lower = path.lower()
    looks_m3u = lower.endswith(('.m3u', '.m3u8')) or stripped.startswith('#EXT')
    if looks_m3u and not stripped.startswith(('{', '[')):
        return normalize_favorites(parse_m3u_entries(text))
    try:
        return parse_favorites_payload(json.loads(text))
    except json.JSONDecodeError:
        if '#EXTINF' in text:
            return normalize_favorites(parse_m3u_entries(text))
        raise ValueError('El archivo no es un JSON ni una lista M3U de favoritos.')


def write_favorites_file(path, items):
    """Escribe JSON envuelto o M3U según la extensión."""
    path = os.path.abspath(str(path or ''))
    if not path:
        raise ValueError('Indica un archivo de destino.')
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    items = normalize_favorites(items)
    lower = path.lower()
    if lower.endswith(('.m3u', '.m3u8')):
        with open(path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(favorites_to_m3u(items))
        return path
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(favorites_payload(items), handle, ensure_ascii=False, indent=4)
        handle.write('\n')
    return path


class FavoritesManager:
    def __init__(self, video_player):
        self.video_player = video_player
        self.favorites = []
        self.load_favorites()

    def add_favorite(self, channel_name):
        """Añade un canal a favoritos si no está ya presente"""
        for name, url in self.video_player.channels:
            if name == channel_name:
                added = self.video_player.add_favorite_entry(name, url, notify=False)
                return bool(added)
        return False

    def remove_favorite(self, channel_name):
        """Elimina un canal de favoritos si está presente"""
        for favorite in list(self.video_player.favorites):
            if favorite_name(favorite) == channel_name:
                return bool(self.video_player.remove_favorite_entry(
                    favorite_name(favorite),
                    favorite_url(favorite),
                    notify=False,
                ))
        return False

    def load_favorites(self):
        """Carga los favoritos del video player"""
        self.video_player.load_favorites()
        self.favorites = self.video_player.favorites
