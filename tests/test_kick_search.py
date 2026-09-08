"""Tests de búsqueda y VODs Kick."""

from kick_player import probe_kick_channel_live
from kick_search import (
    _parse_channel_item,
    _parse_vod_item,
    kick_search_label,
    search_kick,
)


def test_parse_channel_item_live():
    """Canal en directo desde api/search."""
    item = {
        'slug': 'demo',
        'isLive': True,
        'followersCount': 1200,
        'user': {'username': 'Demo'},
    }
    parsed = _parse_channel_item(item)
    assert parsed['kind'] == 'live'
    assert parsed['url'] == 'https://kick.com/demo'
    assert parsed['login'] == 'demo'
    assert parsed['followers'] == 1200


def test_parse_channel_item_offline():
    """Canal offline desde api/search."""
    item = {
        'slug': 'other',
        'isLive': False,
        'followers_count': 10,
        'user': {'username': 'Other'},
    }
    parsed = _parse_channel_item(item)
    assert parsed['kind'] == 'channel'
    assert parsed['followers'] == 10


def test_parse_vod_item():
    """VOD normalizado para la lista de búsqueda."""
    parsed = _parse_vod_item(
        {
            'url': 'https://kick.com/demo/videos/abc',
            'title': 'Stream de ayer',
            'duration': 3600,
        },
        'demo',
    )
    assert parsed['kind'] == 'vod'
    assert parsed['url'].endswith('/videos/abc')
    assert parsed['duration'] == 3600


def test_kick_search_label():
    """Etiquetas de resultados."""
    live = {'kind': 'live', 'login': 'demo', 'title': 'Playing', 'viewers': 1500}
    assert 'Directo' in kick_search_label(live)
    channel = {'kind': 'channel', 'login': 'demo', 'title': 'Demo', 'followers': 1000}
    assert 'Canal' in kick_search_label(channel)
    vod = {'kind': 'vod', 'login': 'demo', 'title': 'Old', 'duration': 120}
    assert 'VOD' in kick_search_label(vod)


def test_search_kick_merged(monkeypatch):
    """Combina canales de búsqueda + VODs del slug exacto."""
    from ttl_cache import invalidate
    invalidate()
    monkeypatch.setattr(
        'kick_search._search_get',
        lambda query: {
            'channels': [
                {
                    'slug': 'demo',
                    'isLive': True,
                    'followersCount': 50,
                    'user': {'username': 'Demo'},
                },
                {
                    'slug': 'other',
                    'isLive': False,
                    'followersCount': 5,
                    'user': {'username': 'Other'},
                },
            ],
        },
    )
    monkeypatch.setattr(
        'kick_search.probe_kick_channel_live',
        lambda channel: {
            'live': True,
            'channel': 'demo',
            'url': 'https://kick.com/demo',
            'title': 'Live now',
            'viewers': 42,
        },
    )
    monkeypatch.setattr(
        'kick_search.fetch_kick_channel_vods',
        lambda channel, limit=10: (
            [{
                'url': 'https://kick.com/demo/videos/uuid-1',
                'title': 'Old stream',
                'duration': 60,
            }],
            'demo',
        ),
    )
    items = search_kick('demo', limit=10)
    kinds = [item['kind'] for item in items]
    assert kinds[0] == 'live'
    assert items[0]['title'] == 'Live now'
    assert items[0]['viewers'] == 42
    assert 'channel' in kinds
    assert 'vod' in kinds
    assert any(item['url'].endswith('uuid-1') for item in items if item['kind'] == 'vod')


def test_probe_kick_channel_live(monkeypatch):
    """probe_kick_channel_live lee livestream de la API v2."""
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                'slug': 'demo',
                'user': {'username': 'Demo'},
                'livestream': {
                    'is_live': True,
                    'session_title': 'Now playing',
                    'viewer_count': 99,
                },
            }

    monkeypatch.setattr('requests.get', lambda *a, **k: _Resp())
    live = probe_kick_channel_live('Demo')
    assert live['live'] is True
    assert live['title'] == 'Now playing'
    assert live['viewers'] == 99
    assert live['url'] == 'https://kick.com/demo'
