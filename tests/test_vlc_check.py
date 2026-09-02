"""Tests de comprobación VLC y aviso de subtítulos."""

import app_config
from vlc_check import (
    VlcInstanceResult,
    args_include_subtitle_style,
    should_warn_subtitle_style,
    vlc_install_hint,
    vlc_version_text,
)


def test_args_include_subtitle_style():
    """Detecta opciones freetype en los argumentos de libvlc_new."""
    assert args_include_subtitle_style(['--quiet', '--freetype-opacity=255']) is True
    assert args_include_subtitle_style(['--quiet', '--sub-text-scale=100']) is True
    assert args_include_subtitle_style(['--quiet', '--avcodec-hw=none']) is False


def test_vlc_version_text_returns_string():
    """La versión detectada es texto legible."""
    version = vlc_version_text()
    assert isinstance(version, str)
    assert version


def test_vlc_install_hint_mentions_videolan_on_windows(monkeypatch):
    """En Windows la ayuda apunta a videolan.org o PATH."""
    monkeypatch.setattr('vlc_check.sys.platform', 'win32')
    monkeypatch.setattr('vlc_check.vlc_install_path', lambda: None)
    hint = vlc_install_hint()
    assert 'videolan.org' in hint


def test_should_warn_subtitle_style_only_when_needed(tmp_path, monkeypatch):
    """El aviso solo salta si se intentó freetype y no se aplicó."""
    previous = app_config._cache
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    try:
        ok = VlcInstanceResult(
            instance=object(),
            subtitle_style_applied=True,
            attempted_subtitle_style=True,
            vlc_version='3.0.20',
            install_path=None,
        )
        failed = VlcInstanceResult(
            instance=object(),
            subtitle_style_applied=False,
            attempted_subtitle_style=True,
            vlc_version='3.0.20',
            install_path=None,
        )
        assert should_warn_subtitle_style(ok) is False
        assert should_warn_subtitle_style(failed) is True
        app_config.set_vlc_subtitle_style_warn_shown(True)
        assert should_warn_subtitle_style(failed) is False
        assert should_warn_subtitle_style(failed, force=True) is True
    finally:
        app_config._cache = previous
