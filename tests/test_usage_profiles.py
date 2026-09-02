"""Tests de perfiles de uso."""

import app_config
import usage_profiles


def _isolate_config(tmp_path, monkeypatch):
    """Uso interno: config aislada."""
    previous = app_config._cache
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    return previous


def test_usage_profile_defaults(tmp_path, monkeypatch):
    """Perfil por defecto es personalizado."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        assert app_config.get_usage_profile() == usage_profiles.PROFILE_CUSTOM
        assert usage_profiles.detect_usage_profile() == usage_profiles.PROFILE_CUSTOM
    finally:
        app_config._cache = previous


def test_apply_live_tv_profile(tmp_path, monkeypatch):
    """TV en directo: buffer estable y sin logos."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        payload = usage_profiles.apply_profile_settings(usage_profiles.PROFILE_LIVE_TV)
        app_config.save(payload)
        assert app_config.get_usage_profile() == usage_profiles.PROFILE_LIVE_TV
        assert app_config.get_iptv_buffer() == 'stable'
        assert app_config.get_show_channel_logos() is False
        assert app_config.get_light_mode() is False
        assert app_config.get_remember_last_list() is True
    finally:
        app_config._cache = previous


def test_apply_cinema_vod_profile(tmp_path, monkeypatch):
    """Cine/VOD: buffer amplio, logos y resume."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        payload = usage_profiles.apply_profile_settings(usage_profiles.PROFILE_CINEMA_VOD)
        app_config.save(payload)
        assert app_config.get_usage_profile() == usage_profiles.PROFILE_CINEMA_VOD
        assert app_config.get_iptv_buffer() == 'stable'
        assert app_config.get_show_channel_logos() is True
        assert app_config.get_light_mode() is False
        assert app_config.get_remember_last_list() is True
        assert app_config.get_youtube_quality() == 720
        assert app_config.get_twitch_quality() == 720
    finally:
        app_config._cache = previous


def test_apply_low_end_pc_profile(tmp_path, monkeypatch):
    """PC débil: modo ligero y calidad 360p."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        payload = usage_profiles.apply_profile_settings(usage_profiles.PROFILE_LOW_END_PC)
        app_config.save(payload)
        assert app_config.get_usage_profile() == usage_profiles.PROFILE_LOW_END_PC
        assert app_config.get_light_mode() is True
        assert app_config.get_light_mode_hw_decode() is True
        assert app_config.get_show_channel_logos() is False
        assert app_config.get_youtube_quality() == 360
        assert app_config.get_twitch_quality() == 360
        assert app_config.get_iptv_buffer() == 'fast'
        assert app_config.effective_youtube_quality() == 360
        assert app_config.effective_show_channel_logos() is False
    finally:
        app_config._cache = previous


def test_detect_usage_profile_from_settings(tmp_path, monkeypatch):
    """Detecta perfil guardado o inferido por ajustes."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.set_usage_profile(usage_profiles.PROFILE_LIVE_TV)
        assert usage_profiles.detect_usage_profile() == usage_profiles.PROFILE_LIVE_TV

        app_config.save({
            'usage_profile': usage_profiles.PROFILE_CUSTOM,
            **usage_profiles.profile_settings(usage_profiles.PROFILE_LOW_END_PC),
        })
        assert usage_profiles.detect_usage_profile() == usage_profiles.PROFILE_LOW_END_PC
    finally:
        app_config._cache = previous


def test_normalize_invalid_profile():
    """Ids desconocidos vuelven a personalizado."""
    assert usage_profiles.normalize_usage_profile('') == usage_profiles.PROFILE_CUSTOM
    assert usage_profiles.normalize_usage_profile('no_existe') == usage_profiles.PROFILE_CUSTOM
