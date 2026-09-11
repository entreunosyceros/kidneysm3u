"""Comprobaciones específicas de rutas y opciones en Windows."""

import os
import sys

import app_paths
import iptv_buffer


def test_data_dir_windows_frozen_uses_localappdata(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    path = app_paths.data_dir()
    assert path == str(tmp_path / 'kidneysm3u')
    assert os.path.isdir(path)


def test_vlc_aout_none_on_windows(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')
    assert iptv_buffer.vlc_aout_option(force_pulse=True) is None
    assert iptv_buffer.vlc_aout_option(force_pulse=False) is None


def test_cookie_browser_labels_include_firefox():
    from preferences import COOKIE_LABELS

    keys = {key for key, _label in COOKIE_LABELS}
    assert 'auto' in keys
    assert 'firefox' in keys
    # En Windows Chrome/Edge no se ofrecen (cookies cifradas).
    assert 'chrome' not in keys
