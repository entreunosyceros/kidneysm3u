import os
from pathlib import Path

import app_config
from descargas import resolve_downloaded_path


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
