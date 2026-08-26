import app_config
from youtube_player import youtube_format_selector
from youtube_search import (
    youtube_channel_tab_url,
    youtube_result_line,
    youtube_star_hit,
    is_youtube_channel_url,
    is_youtube_playlist_url,
    youtube_video_id,
)


def _isolate_config(tmp_path, monkeypatch):
    previous = app_config._cache
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    return previous


def test_youtube_quality_1080_and_best(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        assert app_config.normalize_youtube_quality(1080) == 1080
        assert app_config.normalize_youtube_quality('best') == 0
        assert app_config.normalize_youtube_quality('mejor') == 0
        app_config.set_youtube_quality(1080)
        assert app_config.get_youtube_quality() == 1080
        assert app_config.youtube_quality_label() == '1080p'
        assert app_config.youtube_quality_cache_key() == '1080'
        app_config.set_youtube_quality(0)
        assert app_config.get_youtube_quality() == 0
        assert app_config.youtube_quality_label() == 'Mejor disponible'
        assert app_config.youtube_quality_cache_key() == 'best'
        assert 'height<=1080' in youtube_format_selector(1080)
        assert 'height<=' not in youtube_format_selector(0)
        assert 'height<=720' in youtube_format_selector(720)
    finally:
        app_config._cache = previous


def test_youtube_queue_reorder_and_pop(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        added = app_config.enqueue_youtube_queue([
            ('Uno', 'https://www.youtube.com/watch?v=abcdefghijk'),
            ('Dos', 'https://www.youtube.com/watch?v=lmnopqrstuv'),
            ('Tres', 'https://www.youtube.com/watch?v=wxyzabcde12'),
        ])
        assert added == 3
        assert app_config.enqueue_youtube_queue([
            ('Uno', 'https://www.youtube.com/watch?v=abcdefghijk'),
        ]) == 0
        assert app_config.move_youtube_queue(2, -1)
        names = [item['name'] for item in app_config.youtube_queue()]
        assert names == ['Uno', 'Tres', 'Dos']
        first = app_config.pop_youtube_queue(0)
        assert first['name'] == 'Uno'
        assert [item['name'] for item in app_config.youtube_queue()] == ['Tres', 'Dos']
        app_config.clear_youtube_queue()
        assert app_config.youtube_queue() == []
    finally:
        app_config._cache = previous


def test_youtube_history_same_window_data(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        video_id = 'abcdefghijk'
        url = f'https://www.youtube.com/watch?v={video_id}'
        app_config.remember_youtube_watch(video_id, title='Vídeo de prueba', url=url)
        items = app_config.youtube_history()
        assert items[0]['name'] == 'Vídeo de prueba'
        assert items[0]['id'] == video_id
        assert 'watch?v=' in items[0]['url']
        assert app_config.youtube_continue_watching() == []

        app_config.remember_youtube_position(video_id, 120, 600, title='Vídeo de prueba', url=url)
        watching = app_config.youtube_continue_watching()
        assert watching[0]['s'] == 120
        assert app_config.youtube_resume_seconds(video_id) == 120
        label = app_config.youtube_history_label(watching[0], with_time=True)
        assert 'Vídeo de prueba' in label
        assert '02:00' in label
        assert 'watch?v=' not in label

        app_config.remember_youtube_position(video_id, 590, 600, title='Vídeo de prueba', url=url)
        assert app_config.youtube_resume_seconds(video_id) == 0
        assert app_config.youtube_history_item(video_id)['s'] == 0

        app_config.remove_youtube_history(video_id)
        assert app_config.youtube_history() == []
    finally:
        app_config._cache = previous


def test_youtube_channel_tab_url():
    assert youtube_channel_tab_url('https://www.youtube.com/channel/UCabcdefghij') == (
        'https://www.youtube.com/channel/UCabcdefghij/videos'
    )
    assert youtube_channel_tab_url('https://www.youtube.com/@demo/videos') == (
        'https://www.youtube.com/@demo/videos'
    )


def test_youtube_channel_and_playlist_urls_are_not_videos():
    channel = 'https://www.youtube.com/channel/UCabcdefghijklmnop'
    handle = 'https://www.youtube.com/@demo'
    playlist = 'https://www.youtube.com/playlist?list=PLabcdefghij'
    watch = 'https://www.youtube.com/watch?v=abcdefghijk'
    short = 'https://www.youtube.com/shorts/abcdefghijk'
    assert is_youtube_channel_url(channel) is True
    assert is_youtube_channel_url(handle) is True
    assert is_youtube_channel_url(youtube_channel_tab_url(channel)) is True
    assert is_youtube_channel_url(watch) is False
    assert is_youtube_channel_url(short) is False
    assert is_youtube_channel_url(playlist) is False
    assert is_youtube_playlist_url(playlist) is True
    assert is_youtube_playlist_url(watch + '&list=PLabcdefghij') is False
    assert youtube_video_id(watch) == 'abcdefghijk'
    assert youtube_video_id(channel) is None
    empty = youtube_result_line('channel', 'La 1 HD', favorite=False)
    saved = youtube_result_line('channel', 'La 1 HD', favorite=True)
    assert empty.startswith('☆ ')
    assert saved.startswith('★ ')
    assert '[Canal] La 1 HD' in empty
    assert youtube_star_hit(8) is True
    assert youtube_star_hit(12, star_width=16) is True
    assert youtube_star_hit(80) is False
    video = youtube_result_line('video', 'Clip', duration_str='1:02', favorite=False)
    assert video.startswith('☆ ')
    assert '[Vídeo] Clip [1:02]' in video


def _sub_entries(ext='json3'):
    return [{'ext': ext, 'url': f'https://example.invalid/caption.{ext}'}]


def test_collect_youtube_subs_prefers_original_auto():
    from youtube_subs import collect_youtube_subs

    items = collect_youtube_subs({
        'subtitles': {'en': _sub_entries('vtt')},
        'automatic_captions': {
            'es-orig': _sub_entries('json3'),
            'es': _sub_entries('json3'),
            'en-orig': _sub_entries('json3'),
            'fr': _sub_entries('json3'),
        },
    })
    langs = [item['lang'] for item in items]
    assert langs[0] == 'es-orig'
    assert 'en-orig' in langs
    assert any(item['kind'] == 'official' and item['lang'] == 'en' for item in items)
    orig = next(item for item in items if item['lang'] == 'es-orig')
    assert orig['label'] == 'Español (auto)'
    assert orig['ext'] == 'json3'
    assert 'es' not in langs


def test_translated_spanish_uses_vtt_not_cached_english():
    from youtube_subs import (
        collect_youtube_subs,
        ensure_caption_tlang,
        filename_matches_sub_lang,
    )

    assert filename_matches_sub_lang('vid.en-orig.vlc.vtt', 'en-orig')
    assert not filename_matches_sub_lang('vid.en-orig.vlc.vtt', 'es')
    assert filename_matches_sub_lang('caption_es.vtt', 'es')
    assert not filename_matches_sub_lang('caption_es.vtt', 'en')

    timed = 'https://www.youtube.com/api/timedtext?lang=en&fmt=vtt'
    with_tlang = ensure_caption_tlang(timed, 'es')
    assert 'tlang=es' in with_tlang
    assert 'lang=en' in with_tlang
    assert 'tlang=' not in ensure_caption_tlang(timed, 'en-orig')

    items = collect_youtube_subs({
        'subtitles': {},
        'automatic_captions': {
            'en-orig': [
                {'ext': 'json3', 'url': 'https://www.youtube.com/api/timedtext?lang=en&fmt=json3'},
                {'ext': 'vtt', 'url': 'https://www.youtube.com/api/timedtext?lang=en&fmt=vtt'},
            ],
            'en': [
                {'ext': 'json3', 'url': 'https://www.youtube.com/api/timedtext?lang=en&fmt=json3'},
            ],
            'es': [
                {'ext': 'json3', 'url': 'https://www.youtube.com/api/timedtext?lang=en&fmt=json3&tlang=es'},
                {'ext': 'vtt', 'url': 'https://www.youtube.com/api/timedtext?lang=en&fmt=vtt&tlang=es'},
            ],
        },
    })
    langs = [item['lang'] for item in items]
    assert langs[0] == 'es'
    assert 'en' not in langs
    spanish = next(item for item in items if item['lang'] == 'es')
    assert spanish['ext'] == 'vtt'
    assert 'tlang=es' in spanish['url']
    assert spanish['label'] == 'Español (traducción automática)'


def test_sanitize_youtube_vtt_and_json3(tmp_path):
    from youtube_subs import json3_to_vtt, prepare_subtitle_for_vlc, sanitize_youtube_vtt

    raw_vtt = """WEBVTT
Kind: captions
Language: es

00:00:00.160 --> 00:00:02.350 align:start position:0%
hola <c>mundo</c><00:00:01.040><c> esto</c>

00:00:00.160 --> 00:00:02.350 align:start position:0%
hola mundo esto

00:00:02.350 --> 00:00:05.000 align:start position:0%
sigue el vídeo

00:00:02.350 --> 00:00:05.000 align:start position:0%
sigue el vídeo
"""
    vtt = sanitize_youtube_vtt(raw_vtt)
    assert 'align:start' not in vtt
    assert '<c>' not in vtt
    assert 'hola mundo esto' in vtt
    assert vtt.count('hola mundo esto') == 1
    assert '00:00:00.160 --> 00:00:02.350' in vtt

    json3 = json3_to_vtt('''{
      "events": [
        {"tStartMs": 160, "dDurationMs": 3000, "segs": [{"utf8": "hola "}, {"utf8": "mundo"}]},
        {"tStartMs": 2160, "dDurationMs": 2000, "segs": [{"utf8": "sigue"}]},
        {"tStartMs": 4000, "wWinId": 1}
      ]
    }''')
    assert 'hola mundo' in json3
    assert 'sigue' in json3
    assert json3.index('hola mundo') < json3.index('sigue')
    first_end = json3.split('-->')[1].split('\n')[0].strip()
    assert first_end == '00:00:02.160'

    source = tmp_path / 'caption_es.vtt'
    source.write_text(raw_vtt, encoding='utf-8')
    ready = prepare_subtitle_for_vlc(str(source), ext='vtt')
    assert ready.endswith('.vlc.vtt')
    body = (tmp_path / 'caption_es.vlc.vtt').read_text(encoding='utf-8')
    assert 'align:start' not in body
    assert 'hola mundo esto' in body


def test_yt_dlp_upgrade_command_and_pip_messages(monkeypatch):
    from preferences import parse_yt_dlp_pip_result, yt_dlp_update_message, yt_dlp_upgrade_cmd

    cmd = yt_dlp_upgrade_cmd('/tmp/fake-python')
    assert cmd[:4] == ['/tmp/fake-python', '-m', 'pip', 'install']
    assert '--upgrade' in cmd
    assert 'yt-dlp[default]' in cmd

    ok, detail = parse_yt_dlp_pip_result(
        'Successfully installed yt-dlp-2026.8.24 brotli-1.0',
        0,
    )
    assert ok is True
    assert detail == '2026.8.24'

    ok, detail = parse_yt_dlp_pip_result(
        'Requirement already satisfied: yt-dlp[default] in .venv/lib',
        0,
    )
    assert ok is True
    assert detail == 'already'

    ok, detail = parse_yt_dlp_pip_result(
        'error: externally-managed-environment\nThis environment is externally managed',
        1,
    )
    assert ok is False
    assert detail == 'externally-managed'

    monkeypatch.setattr('preferences.yt_dlp_installed_version', lambda: '2026.1.1')
    success, text = yt_dlp_update_message(True, 'already')
    assert success is True
    assert '2026.1.1' in text
    success, text = yt_dlp_update_message(True, '2026.8.24')
    assert success is True
    assert '2026.8.24' in text
    assert 'Cierra el programa' in text
    success, text = yt_dlp_update_message(False, 'externally-managed')
    assert success is False
    assert 'run_app.py' in text

