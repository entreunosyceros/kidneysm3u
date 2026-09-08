"""Tests de caché TTL genérica."""

import ttl_cache


def setup_function():
    """Limpia la caché entre tests."""
    ttl_cache.invalidate()


def test_put_get_and_expire(monkeypatch):
    """Guarda, recupera y caduca."""
    clock = {'now': 100.0}
    monkeypatch.setattr(ttl_cache.time, 'monotonic', lambda: clock['now'])
    ttl_cache.put_cached('twitch:search:10:demo', [{'url': 'a'}], ttl=30)
    assert ttl_cache.get_cached('twitch:search:10:demo')[0]['url'] == 'a'
    clock['now'] = 140.0
    assert ttl_cache.get_cached('twitch:search:10:demo') is None


def test_keys_normalized():
    """Las claves se normalizan en minúsculas."""
    ttl_cache.put_cached('Kick:Search:X', [1])
    assert ttl_cache.get_cached('kick:search:x') == [1]
