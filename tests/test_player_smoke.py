"""Tests de humo para navegación, subtítulos off, cachés y perfil."""

from player_navigation import PREVIOUS_RESTART_MS, PlayerNavigationMixin


class _NavHost(PlayerNavigationMixin):
    def __init__(self):
        self.player = object()
        self._elapsed = 0
        self._seek_to = None
        self._relative = None

    def _playback_elapsed_ms(self):
        return self._elapsed

    def _apply_seek(self, ms):
        self._seek_to = ms

    def _play_relative_channel(self, delta):
        self._relative = delta

    def restart_current_media(self):
        # Override mixin to avoid needing vlc states in smoke test.
        self._apply_seek(0)


def test_play_previous_restarts_when_past_threshold():
    host = _NavHost()
    host._elapsed = PREVIOUS_RESTART_MS + 500
    host.play_previous_media()
    assert host._seek_to == 0
    assert host._relative is None


def test_play_previous_goes_back_near_start():
    host = _NavHost()
    host._elapsed = 500
    host.play_previous_media()
    assert host._relative == -1
    assert host._seek_to is None


def test_play_next_media_advances():
    host = _NavHost()
    host.play_next_media()
    assert host._relative == 1


def test_youtube_auto_subtitles_default_off(tmp_path, monkeypatch):
    import app_config

    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    assert app_config.get_youtube_auto_subtitles() is False


def test_iptv_skip_dead_defaults(tmp_path, monkeypatch):
    import app_config

    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    assert app_config.get_iptv_skip_dead() is False
    assert app_config.get_iptv_skip_dead_delay_s() == 4
    app_config.set_iptv_skip_dead(True)
    assert app_config.get_iptv_skip_dead() is True


def test_clear_all_caches_smoke(tmp_path, monkeypatch):
    import cache_cleanup
    import ttl_cache

    epg = tmp_path / 'epg'
    yt = tmp_path / 'yt'
    epg.mkdir()
    yt.mkdir()
    (epg / 'a.png').write_bytes(b'x' * 20)
    monkeypatch.setattr(cache_cleanup, 'epg_cache_dirs', lambda: [str(epg)])
    monkeypatch.setattr(cache_cleanup, 'youtube_cache_dir', lambda: str(yt))
    ttl_cache.invalidate()
    removed, freed = cache_cleanup.clear_all_caches()
    assert removed >= 1
    assert freed >= 20


def test_profile_backup_roundtrip(tmp_path):
    import json
    import profile_backup

    (tmp_path / 'config.json').write_text(json.dumps({'theme': 'dark'}), encoding='utf-8')
    (tmp_path / 'favoritos.json').write_text('[]', encoding='utf-8')
    zip_path = tmp_path / 'out.zip'
    count, dest = profile_backup.export_profile_zip(str(zip_path), base=str(tmp_path))
    assert count >= 2
    other = tmp_path / 'other'
    other.mkdir()
    written = profile_backup.import_profile_zip(str(dest), base=str(other), reload_config=False)
    assert 'config.json' in written
    assert (other / 'config.json').is_file()


def test_youtube_download_fallback_helper():
    from video_player import youtube_should_try_download_fallback

    assert youtube_should_try_download_fallback(6) is True
    assert youtube_should_try_download_fallback(5) is False


def test_session_prompt_import():
    from session_prompt import offer_reexport_cookies

    assert callable(offer_reexport_cookies)
