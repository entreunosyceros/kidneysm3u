from pathlib import Path

import app_config
from descargas import download_history_label, resolve_downloaded_path


def _isolate_config(tmp_path, monkeypatch):
    previous = app_config._cache
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    return previous


def test_open_folder_after_download_pref(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        assert app_config.get_open_folder_after_download() is True
        app_config.set_open_folder_after_download(False)
        assert app_config.get_open_folder_after_download() is False
        app_config.set_open_folder_after_download(True)
        assert app_config.get_open_folder_after_download() is True
    finally:
        app_config._cache = previous


def test_download_url_history_unique_and_capped(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        assert app_config.download_url_history() == []
        app_config.remember_download_url('  ')
        assert app_config.download_url_history() == []
        first = 'https://www.youtube.com/watch?v=abcdefghijk'
        second = 'https://cdn.example/file.mp4?token=secret'
        app_config.remember_download_url(first, 'Uno')
        app_config.remember_download_url(second, 'Dos')
        app_config.remember_download_url(first, 'Uno otra vez')
        items = app_config.download_url_history()
        assert [item['url'] for item in items] == [first, second]
        assert items[0]['name'] == 'Uno otra vez'
        for index in range(20):
            app_config.remember_download_url(f'https://cdn.example/v{index}.mp4', f'V{index}')
        items = app_config.download_url_history()
        assert len(items) == app_config.MAX_DOWNLOAD_URLS
        assert items[0]['name'] == 'V19'
        label = download_history_label({'url': second, 'name': ''})
        assert 'token=' not in label
        assert 'secret' not in label
    finally:
        app_config._cache = previous


def test_resolve_downloaded_path_finds_extension(tmp_path):
    planned = tmp_path / 'canal'
    saved = tmp_path / 'canal.mp4'
    saved.write_bytes(b'data')
    assert resolve_downloaded_path(str(planned)) == str(saved.resolve())
    assert resolve_downloaded_path(str(saved)) == str(saved.resolve())


def test_reveal_in_file_manager_linux_selects_file(tmp_path, monkeypatch):
    from descargas import reveal_in_file_manager

    saved = tmp_path / 'video.mp4'
    saved.write_bytes(b'data')
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(('run', list(cmd)))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr('descargas.sys.platform', 'linux')
    monkeypatch.setattr('descargas.subprocess.run', fake_run)
    monkeypatch.setattr('descargas.subprocess.Popen', lambda *a, **k: calls.append(('popen', a)))
    assert reveal_in_file_manager(str(saved)) is True
    assert calls and calls[0][0] == 'run'
    cmd = calls[0][1]
    assert cmd[0] == 'dbus-send'
    assert 'org.freedesktop.FileManager1.ShowItems' in cmd
    uri = Path(saved).resolve().as_uri()
    assert f'array:string:{uri}' in cmd
    assert not any(flag == 'xdg-open' for item in calls for flag in (item[1] if item[0] == 'popen' else []))
