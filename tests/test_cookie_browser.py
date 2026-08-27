import app_config


def test_cookie_browsers_only_auto_and_firefox():
    assert app_config.COOKIE_BROWSERS == ('auto', 'firefox')


def test_get_cookie_browser_maps_old_chrome_values(monkeypatch):
    monkeypatch.setattr(app_config, 'load', lambda: {'cookie_browser': 'chrome'})
    assert app_config.get_cookie_browser() == 'auto'
    monkeypatch.setattr(app_config, 'load', lambda: {'cookie_browser': 'brave'})
    assert app_config.get_cookie_browser() == 'auto'
    monkeypatch.setattr(app_config, 'load', lambda: {'cookie_browser': 'firefox'})
    assert app_config.get_cookie_browser() == 'firefox'
