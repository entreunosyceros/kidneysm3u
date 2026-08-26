"""Favoritos del reproductor: (nombre, url), comparados por URL."""


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
