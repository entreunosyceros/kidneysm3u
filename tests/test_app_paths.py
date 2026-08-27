def test_data_dir_windows_frozen_uses_localappdata(tmp_path, monkeypatch):
    import app_paths

    monkeypatch.setattr(app_paths.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(app_paths.sys, 'platform', 'win32')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'Local'))
    path = app_paths.data_dir()
    assert path == str(tmp_path / 'Local' / 'kidneysm3u')
    assert (tmp_path / 'Local' / 'kidneysm3u').is_dir()


def test_data_dir_unfrozen_is_source_tree():
    import os
    import app_paths

    assert app_paths.data_dir() == os.path.dirname(os.path.abspath(app_paths.__file__))
