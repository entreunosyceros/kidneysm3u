"""Tests de la biblioteca unificada."""

import app_config
from library import (
    collect_library_items,
    library_row_label,
    remove_library_item,
    source_from_url,
)


def test_source_from_url():
    """Detecta fuente por URL."""
    assert source_from_url('https://www.youtube.com/watch?v=abc') == 'youtube'
    assert source_from_url('https://www.twitch.tv/demo') == 'twitch'
    assert source_from_url('https://kick.com/demo') == 'kick'
    assert source_from_url('http://example.com/live.ts') == 'iptv'


def test_collect_filters_by_source_and_section(tmp_path, monkeypatch):
    """Filtros de sección y fuente."""
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    try:
        app_config.remember_youtube_watch('dQw4w9WgXcQ', title='YT uno', url='https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        app_config.remember_twitch_watch('https://www.twitch.tv/videos/1', title='TW vod')
        app_config.remember_kick_watch('https://kick.com/demo', title='Kick live')
        app_config.remember_iptv_history('Canal IPTV', 'http://example.com/a.ts')

        favorites = [
            ['Fav YT', 'https://www.youtube.com/watch?v=favxxxxxxx'],
            ['Fav Kick', 'https://kick.com/fav'],
        ]

        yt_only = collect_library_items(favorites=favorites, section='all', source='youtube')
        assert all(item['source'] == 'youtube' for item in yt_only)
        assert any(item['bucket'] == 'favorite' for item in yt_only)
        assert any(item['bucket'] == 'history' for item in yt_only)

        favs = collect_library_items(favorites=favorites, section='favorites', source='all')
        assert len(favs) == 2
        assert all(item['bucket'] == 'favorite' for item in favs)

        kick_hist = collect_library_items(favorites=[], section='history', source='kick')
        assert len(kick_hist) == 1
        assert kick_hist[0]['name'] == 'Kick live'
    finally:
        app_config._cache = None


def test_collect_query_filter(tmp_path, monkeypatch):
    """La búsqueda textual filtra por nombre."""
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    try:
        favorites = [
            ['Partido final', 'http://example.com/match'],
            ['Noticias', 'http://example.com/news'],
        ]
        items = collect_library_items(favorites=favorites, section='favorites', query='partido')
        assert len(items) == 1
        assert 'Partido' in items[0]['name']
    finally:
        app_config._cache = None


def test_library_row_label():
    """Etiqueta legible."""
    label = library_row_label({
        'bucket': 'favorite',
        'source': 'twitch',
        'name': 'demo',
    })
    assert 'Favorito' in label
    assert 'Twitch' in label
    assert 'demo' in label


def test_remove_twitch_and_kick_history(tmp_path, monkeypatch):
    """remove_*_history quita una URL concreta."""
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    try:
        app_config.remember_twitch_watch('https://www.twitch.tv/a', title='A')
        app_config.remember_twitch_watch('https://www.twitch.tv/b', title='B')
        app_config.remove_twitch_history('https://www.twitch.tv/a')
        urls = [item['url'] for item in app_config.twitch_history()]
        assert urls == ['https://www.twitch.tv/b']

        app_config.remember_kick_watch('https://kick.com/a', title='A')
        app_config.remember_kick_watch('https://kick.com/b', title='B')
        app_config.remove_kick_history('https://kick.com/b')
        urls = [item['url'] for item in app_config.kick_history()]
        assert urls == ['https://kick.com/a']
    finally:
        app_config._cache = None


def test_remove_library_item_favorite():
    """Quitar favorito delega en el player."""
    calls = []

    class _Player:
        def remove_favorite_entry(self, name, url, notify=False):
            calls.append((name, url))

    ok = remove_library_item(
        _Player(),
        {'bucket': 'favorite', 'source': 'iptv', 'name': 'X', 'url': 'http://x'},
    )
    assert ok
    assert calls == [('X', 'http://x')]
