"""Tests de la caché corta de yt-dlp."""

import ydl_cache


def setup_function():
    """Limpia la caché entre tests."""
    ydl_cache.invalidate_cached_info()


def test_put_get_and_ttl(monkeypatch):
    """Guarda y recupera; caduca con TTL."""
    clock = {'now': 1000.0}
    monkeypatch.setattr(ydl_cache.time, 'monotonic', lambda: clock['now'])
    ydl_cache.put_cached_info('https://example.com/a', {'id': 'a'}, tag='play', ttl=30)
    assert ydl_cache.get_cached_info('https://example.com/a', tag='play')['id'] == 'a'
    clock['now'] = 1040.0
    assert ydl_cache.get_cached_info('https://example.com/a', tag='play') is None


def test_tags_are_independent():
    """Tags distintas no se pisan."""
    ydl_cache.put_cached_info('https://yt/x', {'v': 1}, tag='yt:play')
    ydl_cache.put_cached_info('https://yt/x', {'v': 2}, tag='yt:subs')
    assert ydl_cache.get_cached_info('https://yt/x', tag='yt:play')['v'] == 1
    assert ydl_cache.get_cached_info('https://yt/x', tag='yt:subs')['v'] == 2


def test_invalidate_url():
    """Invalidar URL borra todas las tags."""
    ydl_cache.put_cached_info('https://kick.com/c', {'ok': True}, tag='a')
    ydl_cache.put_cached_info('https://kick.com/c', {'ok': True}, tag='b')
    ydl_cache.invalidate_cached_info('https://kick.com/c')
    assert ydl_cache.get_cached_info('https://kick.com/c', tag='a') is None
    assert ydl_cache.get_cached_info('https://kick.com/c', tag='b') is None


def test_extract_info_cached_hits(monkeypatch):
    """extract_info_cached evita una segunda llamada real."""
    calls = {'n': 0}

    class _FakeYdl:
        def extract_info(self, url, download=False):
            calls['n'] += 1
            return {'url': url, 'n': calls['n']}

    ydl = _FakeYdl()
    first = ydl_cache.extract_info_cached(ydl, 'https://example.com/v', tag='t')
    second = ydl_cache.extract_info_cached(ydl, 'https://example.com/v', tag='t')
    assert calls['n'] == 1
    assert first['n'] == 1
    assert second['n'] == 1


def test_extract_info_cached_bypass():
    """use_cache=False fuerza nueva extracción."""
    calls = {'n': 0}

    class _FakeYdl:
        def extract_info(self, url, download=False):
            calls['n'] += 1
            return {'n': calls['n']}

    ydl = _FakeYdl()
    ydl_cache.extract_info_cached(ydl, 'https://example.com/z', tag='t')
    ydl_cache.extract_info_cached(ydl, 'https://example.com/z', tag='t', use_cache=False)
    assert calls['n'] == 2
