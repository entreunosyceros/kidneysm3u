"""Módulo de test cookie browser."""

import app_config


def test_cookie_browsers_only_auto_and_firefox():
    """Prueba cookie browsers only auto and firefox."""
    assert app_config.COOKIE_BROWSERS == ('auto', 'firefox')


def test_get_cookie_browser_maps_old_chrome_values(monkeypatch):
    """Prueba get cookie browser maps old chrome values."""
    monkeypatch.setattr(app_config, 'load', lambda: {'cookie_browser': 'chrome'})
    assert app_config.get_cookie_browser() == 'auto'
    monkeypatch.setattr(app_config, 'load', lambda: {'cookie_browser': 'brave'})
    assert app_config.get_cookie_browser() == 'auto'
    monkeypatch.setattr(app_config, 'load', lambda: {'cookie_browser': 'firefox'})
    assert app_config.get_cookie_browser() == 'firefox'
