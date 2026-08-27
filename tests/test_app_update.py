import app_config
import app_update
import app_version


def test_normalize_and_compare_versions():
    assert app_update.normalize_version('v1.2.3') == '1.2.3'
    assert app_update.normalize_version('Kidneysm3u 1.2.3') == '1.2.3'
    assert app_update.normalize_version('Versión1.2.3') == '1.2.3'
    assert app_update.normalize_version('Versión 1.2.3') == '1.2.3'
    assert app_update.normalize_version('Version1.2.4') == '1.2.4'
    assert app_update.normalize_version('versión1.2.3') == '1.2.3'
    assert app_update.is_newer_version('1.2.3', '1.2.2') is True
    assert app_update.is_newer_version('1.2.3', '1.2.3') is False
    assert app_update.is_newer_version('1.2.2', '1.2.3') is False
    assert app_update.is_newer_version('2.0', '1.9.9') is True
    assert app_update.current_version() == '1.2.3'
    assert app_version.__version__ == '1.2.3'


def test_install_kind_windows_deb_and_source(tmp_path, monkeypatch):
    assert app_update.install_kind(frozen=True, platform='win32') == 'windows'
    assert app_update.install_kind(frozen=False, platform='linux', here=str(tmp_path), share_version=False) == 'source'
    local = tmp_path / 'share' / 'kidneysm3u'
    local.mkdir(parents=True)
    assert app_update.install_kind(
        frozen=False,
        platform='linux',
        here=str(local),
        share_version=True,
        data_home=str(tmp_path / 'share'),
    ) == 'deb'


def test_pick_release_asset_by_kind():
    assets = [
        {'name': 'kidneysm3u_1.2.3_all.deb', 'browser_download_url': 'https://github.com/x/a.deb', 'size': 10},
        {'name': 'Kidneysm3u-Setup-1.2.3.exe', 'browser_download_url': 'https://github.com/x/a.exe', 'size': 20},
        {'name': 'notes.txt', 'browser_download_url': 'https://github.com/x/notes.txt', 'size': 3},
    ]
    exe = app_update.pick_release_asset(assets, 'windows')
    deb = app_update.pick_release_asset(assets, 'deb')
    src = app_update.pick_release_asset(assets, 'source')
    assert exe['name'] == 'Kidneysm3u-Setup-1.2.3.exe'
    assert deb['name'] == 'kidneysm3u_1.2.3_all.deb'
    assert src is None
    assert app_update.safe_asset_filename('../evil.exe') is None
    assert app_update.safe_asset_filename('Kidneysm3u-Setup-1.2.3.exe') == 'Kidneysm3u-Setup-1.2.3.exe'


def test_parse_latest_release_and_check(tmp_path, monkeypatch):
    payload = {
        'tag_name': 'Versión1.9.9',
        'name': 'Versión 1.9.9',
        'html_url': 'https://github.com/entreunosyceros/kidneysm3u/releases/tag/Versi%C3%B3n1.9.9',
        'assets': [
            {
                'name': 'kidneysm3u_1.9.9_all.deb',
                'browser_download_url': 'https://github.com/entreunosyceros/kidneysm3u/releases/download/Versi%C3%B3n1.9.9/kidneysm3u_1.9.9_all.deb',
                'size': 1234,
            }
        ],
    }
    parsed = app_update.parse_latest_release(payload)
    assert parsed['version'] == '1.9.9'
    assert parsed['tag'] == 'Versión1.9.9'
    previous = app_config._cache
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    try:
        monkeypatch.setattr(app_update, 'fetch_latest_release', lambda timeout=12: parsed)
        monkeypatch.setattr(app_update, 'install_kind', lambda: 'deb')
        monkeypatch.setattr(app_update, 'current_version', lambda: '1.2.3')
        result = app_update.check_for_app_update(force=True)
        assert result['newer'] is True
        assert result['asset']['name'].endswith('.deb')
        monkeypatch.setattr(app_update, 'current_version', lambda: '1.9.9')
        current = app_update.check_for_app_update(force=True)
        assert current['newer'] is False
    finally:
        app_config._cache = previous


def test_check_app_updates_preference(tmp_path, monkeypatch):
    previous = app_config._cache
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    try:
        assert app_config.get_check_app_updates() is True
        app_config.set_check_app_updates(False)
        assert app_config.get_check_app_updates() is False
    finally:
        app_config._cache = previous
