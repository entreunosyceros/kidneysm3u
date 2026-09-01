"""Módulo de test twitch search."""

from twitch_search import (
    search_twitch,
    twitch_search_label,
    _parse_live_channel,
    _parse_offline_channel,
    _parse_vod,
)


def test_parse_live_channel():
    """Prueba parse live canal."""
    item = {
        'login': 'shroud',
        'displayName': 'shroud',
        'stream': {'viewersCount': 12000},
        'broadcastSettings': {'title': 'Ranked all day'},
    }
    parsed = _parse_live_channel(item)
    assert parsed['kind'] == 'live'
    assert parsed['url'] == 'https://www.twitch.tv/shroud'
    assert parsed['viewers'] == 12000
    assert 'Ranked' in parsed['title']


def test_parse_offline_channel():
    """Prueba parse offline canal."""
    item = {
        'login': 'shroud',
        'displayName': 'shroud',
        'followers': {'totalCount': 1000000},
    }
    parsed = _parse_offline_channel(item)
    assert parsed['kind'] == 'channel'
    assert parsed['followers'] == 1000000


def test_parse_vod():
    """Prueba parse vod."""
    item = {
        'id': '1234567890',
        'title': 'Stream de ayer',
        'lengthSeconds': 3661,
        'owner': {'login': 'demo'},
    }
    parsed = _parse_vod(item)
    assert parsed['kind'] == 'vod'
    assert parsed['url'] == 'https://www.twitch.tv/videos/1234567890'
    assert parsed['duration'] == 3661


def test_twitch_search_label():
    """Prueba twitch search label."""
    live = {'kind': 'live', 'login': 'demo', 'title': 'Playing', 'viewers': 1500}
    assert 'Directo' in twitch_search_label(live)
    vod = {'kind': 'vod', 'login': 'demo', 'title': 'Clip largo', 'duration': 120}
    assert 'VOD' in twitch_search_label(vod)


def test_search_twitch_merged(monkeypatch):
    """Prueba search twitch merged."""
    channel_payload = [{
        'data': {
            'searchFor': {
                'channels': {
                    'edges': [
                        {'item': {
                            'login': 'shroud',
                            'displayName': 'shroud',
                            'stream': {'viewersCount': 500},
                            'broadcastSettings': {'title': 'Live now'},
                        }},
                        {'item': {
                            'login': 'other',
                            'displayName': 'Other',
                            'followers': {'totalCount': 10},
                        }},
                    ],
                },
                'relatedLiveChannels': {'edges': []},
            },
        },
    }]
    vod_payload = [{
        'data': {
            'searchFor': {
                'videos': {
                    'edges': [
                        {'item': {
                            'id': '999',
                            'title': 'Old stream',
                            'lengthSeconds': 60,
                            'owner': {'login': 'shroud'},
                        }},
                    ],
                },
            },
        },
    }]
    calls = []

    def fake_post(payload):
        """Fake post."""
        calls.append(payload[0]['variables']['options']['targets'][0]['index'])
        if calls[-1] == 'CHANNEL':
            return channel_payload
        return vod_payload

    monkeypatch.setattr('twitch_search._gql_post', fake_post)
    items = search_twitch('shroud', limit=10)
    assert [item['kind'] for item in items] == ['live', 'channel', 'vod']
    assert items[0]['url'] == 'https://www.twitch.tv/shroud'
    assert items[2]['url'] == 'https://www.twitch.tv/videos/999'
    assert calls == ['CHANNEL', 'VOD']
