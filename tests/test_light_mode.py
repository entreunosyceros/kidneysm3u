"""Módulo de test light mode."""

import app_config


def _isolate_config(tmp_path, monkeypatch):
    """Uso interno: isolate configuración."""
    previous = app_config._cache
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    return previous


def test_light_mode_defaults_off(tmp_path, monkeypatch):
    """Prueba light mode defaults off."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        assert app_config.get_light_mode() is False
        assert app_config.get_light_mode_hw_decode() is True
        assert app_config.get_show_cpu_monitor() is False
        assert app_config.effective_show_channel_logos() is True
        assert app_config.effective_youtube_quality() == 720
        assert app_config.effective_yt_cache_max_bytes() == 500 * 1024 * 1024
        assert app_config.epg_reload_interval_ms() == 30 * 60 * 1000
        assert app_config.epg_tick_interval_ms() == 60 * 1000
        assert app_config.iptv_use_hw_decode() is False
    finally:
        app_config._cache = previous


def test_light_mode_effective_settings(tmp_path, monkeypatch):
    """Prueba light mode effective settings."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.save({
            'light_mode': True,
            'show_channel_logos': True,
            'youtube_quality': 1080,
        })
        assert app_config.effective_show_channel_logos() is False
        assert app_config.effective_youtube_quality() == 720
        assert app_config.effective_yt_cache_max_bytes() == app_config.LIGHT_MODE_YT_CACHE_BYTES
        assert app_config.epg_reload_interval_ms() == 0
        assert app_config.epg_tick_interval_ms() == app_config.LIGHT_MODE_EPG_TICK_MS
        assert app_config.iptv_use_hw_decode() is True

        app_config.set_light_mode_hw_decode(False)
        assert app_config.iptv_use_hw_decode() is False

        app_config.save({'youtube_quality': 360})
        assert app_config.effective_youtube_quality() == 360

        app_config.save({'youtube_quality': 0})
        assert app_config.effective_youtube_quality() == 720
    finally:
        app_config._cache = previous


def test_should_skip_session_restore(tmp_path, monkeypatch):
    """Prueba should skip session restore."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.set_light_mode(False)
        session = {'playlist_kind': 'url', 'playlist': 'http://example/list.m3u'}
        assert app_config.should_skip_session_restore(session) is False

        app_config.set_light_mode(True)
        assert app_config.should_skip_session_restore(session) is True
        assert app_config.should_skip_session_restore({'sidebar': list(range(2000))}) is True
        assert app_config.should_skip_session_restore({'sidebar': list(range(10))}) is False
    finally:
        app_config._cache = previous


def test_logo_cache_clear(tmp_path, monkeypatch):
    """Prueba logo cache clear."""
    import logo_cache

    previous = app_config._cache
    cache_dir = tmp_path / 'epg_cache'
    monkeypatch.setattr(logo_cache, 'CACHE_DIR', str(cache_dir))
    try:
        cache_dir.mkdir()
        (cache_dir / 'a.png').write_bytes(b'x')
        (cache_dir / 'b.png').write_bytes(b'y')
        assert logo_cache.clear_cache() == 2
        assert logo_cache.clear_cache() == 0
    finally:
        app_config._cache = previous
