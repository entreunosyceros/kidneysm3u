import app_config


def _isolate_config(tmp_path, monkeypatch):
    previous = app_config._cache
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    return previous


def test_iptv_history_resume_and_privacy(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        live = 'http://panel.example/live/user/pass/10.ts'
        vod = 'http://panel.example/movie/user/pass/99.mkv'
        app_config.remember_iptv_history('La 1', live, group='España')
        app_config.remember_iptv_history('Film', vod)
        items = app_config.iptv_history()
        assert items[0]['name'] == 'Film'
        assert items[0]['kind'] == 'vod'
        assert items[1]['kind'] == 'live'
        assert items[1]['group'] == 'España'
        assert app_config.iptv_continue_watching() == []

        app_config.update_iptv_position(vod, 120, 3600)
        watching = app_config.iptv_continue_watching()
        assert watching[0]['s'] == 120
        assert app_config.iptv_resume_seconds(vod) == 120
        label = app_config.iptv_history_label(watching[0], with_time=True)
        assert 'Film' in label
        assert '02:00' in label
        assert 'panel.example' not in label
        assert 'user' not in label

        app_config.update_iptv_position(vod, 10, 3600)
        assert app_config.iptv_resume_seconds(vod) == 0

        app_config.update_iptv_position(vod, 200, 3600)
        app_config.update_iptv_position(vod, 3590, 3600)
        assert app_config.iptv_history_item(vod)['s'] == 0
        assert app_config.iptv_resume_seconds(vod) == 0

        app_config.remove_iptv_history(live)
        assert all(item['url'] != live for item in app_config.iptv_history())
        app_config.clear_iptv_history()
        assert app_config.iptv_history() == []
    finally:
        app_config._cache = previous


def test_iptv_history_skips_youtube_and_caps(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.remember_iptv_history('YT', 'https://www.youtube.com/watch?v=abcdefghijk')
        assert app_config.iptv_history() == []
        for index in range(30):
            app_config.remember_iptv_history(
                f'Canal {index}',
                f'http://panel.example/live/u/p/{index}.ts',
            )
        items = app_config.iptv_history()
        assert len(items) == app_config.MAX_IPTV_HISTORY
        assert items[0]['name'] == 'Canal 29'
    finally:
        app_config._cache = previous
