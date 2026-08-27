import app_config
from youtube_player import youtube_format_selector
from youtube_search import (
    youtube_channel_tab_url,
    youtube_result_line,
    youtube_star_hit,
    is_youtube_channel_url,
    is_youtube_playlist_url,
    youtube_video_id,
    youtube_search_sp,
    youtube_search_sp_from_ui,
    sort_search_entries,
    parse_relative_upload_text,
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
    assert youtube_channel_tab_url('https://www.youtube.com/@demo/videos', 'shorts') == (
        'https://www.youtube.com/@demo/shorts'
    )


def test_channel_url_from_query_and_name_match():
    from youtube_search import channel_url_from_query, channel_name_matches_query

    assert channel_url_from_query('@MrBeast') == 'https://www.youtube.com/@MrBeast'
    assert channel_url_from_query('https://www.youtube.com/@demo') == (
        'https://www.youtube.com/@demo'
    )
    assert channel_url_from_query('gatos') is None
    assert channel_name_matches_query('mrbeast', 'MrBeast') is True
    assert channel_name_matches_query('Mr Beast', '@MrBeast') is True
    assert channel_name_matches_query('python tutorial', 'Python') is False


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

    assert filename_matches_sub_lang('vid.en-orig.vlc.srt', 'en-orig')
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
    from youtube_subs import json3_to_vtt, prepare_subtitle_for_vlc, sanitize_youtube_vtt, vtt_to_srt

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
    first_stamp = [row for row in vtt.splitlines() if '-->' in row][0]
    assert first_stamp.startswith('00:00:00.160 --> 00:00:02.34')

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
    assert first_end.startswith('00:00:02.15')

    source = tmp_path / 'caption_es.vtt'
    source.write_text(raw_vtt, encoding='utf-8')
    ready = prepare_subtitle_for_vlc(str(source), ext='vtt')
    assert ready.endswith('.vlc.srt')
    body = (tmp_path / 'caption_es.vlc.srt').read_text(encoding='utf-8')
    assert 'align:start' not in body
    assert 'hola mundo esto' in body
    assert '00:00:00,160 --> 00:00:02,34' in body
    srt = vtt_to_srt(raw_vtt)
    assert srt.splitlines()[0] == '1'


def test_youtube_rollup_stays_one_line_and_does_not_overlap():
    from youtube_subs import sanitize_youtube_vtt, vtt_to_srt

    raw_vtt = """WEBVTT

00:00:00.000 --> 00:00:04.000 align:start position:0%
hola a todos

00:00:02.000 --> 00:00:06.000 align:start position:0%
hola a todos
bienvenidos al vídeo

00:00:04.000 --> 00:00:08.000 align:start position:0%
hola a todos
bienvenidos al vídeo
hoy vamos a ver

00:00:06.000 --> 00:00:10.000 align:start position:0%
bienvenidos al vídeo
hoy vamos a ver
esta receta
"""
    vtt = sanitize_youtube_vtt(raw_vtt)
    texts = []
    stamps = []
    for block in vtt.split('\n\n'):
        rows = [row for row in block.split('\n') if row.strip()]
        if len(rows) < 2 or '-->' not in rows[0] and '-->' not in rows[1]:
            continue
        header = rows[0] if '-->' in rows[0] else rows[1]
        payload = rows[1:] if '-->' in rows[0] else rows[2:]
        if '-->' not in header:
            continue
        stamps.append(header)
        texts.append('\n'.join(payload))
    assert texts
    assert all('\n' not in text for text in texts)
    assert 'esta receta' in texts[-1]
    assert 'hola a todos bienvenidos' not in texts[-1]
    starts = []
    ends = []
    for header in stamps:
        start, end = [part.strip() for part in header.split('-->')]
        starts.append(start)
        ends.append(end.split()[0])
    for index in range(len(ends) - 1):
        assert ends[index] <= starts[index + 1]
    srt = vtt_to_srt(raw_vtt)
    assert srt.count('\n\n') >= 2
    for block in srt.strip().split('\n\n'):
        payload = block.split('\n')[2:]
        assert len(payload) == 1


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


def test_firefox_cookie_sqlite_paths_from_profiles_ini(tmp_path, monkeypatch):
    from youtube_player import firefox_cookie_sqlite_paths, _cookie_load_hint

    root = tmp_path / 'Roaming' / 'Mozilla' / 'Firefox'
    profile = root / 'Profiles' / 'abcd1234.default-release'
    profile.mkdir(parents=True)
    (profile / 'cookies.sqlite').write_bytes(b'sqlite')
    (root / 'profiles.ini').write_text(
        '[InstallABC]\nDefault=Profiles/abcd1234.default-release\n'
        '[Profile0]\nName=default\nIsRelative=1\n'
        'Path=Profiles/abcd1234.default-release\nDefault=1\n',
        encoding='utf-8',
    )
    monkeypatch.setattr('youtube_player.sys.platform', 'win32')
    paths = firefox_cookie_sqlite_paths(environ={
        'APPDATA': str(tmp_path / 'Roaming'),
        'LOCALAPPDATA': str(tmp_path / 'Local'),
    })
    assert paths
    assert paths[0].endswith('cookies.sqlite')
    hint = _cookie_load_hint(RuntimeError('Failed to decrypt the cipher text with DPAPI'))
    assert 'Firefox' in hint
    locked = _cookie_load_hint(OSError('Unable to read database file'))
    assert 'bloqueadas' in locked


def test_librewolf_cookie_sqlite_paths_windows(tmp_path, monkeypatch):
    from youtube_player import firefox_cookie_sqlite_paths

    profile = tmp_path / 'Roaming' / 'librewolf' / 'Profiles' / 'xyz.default'
    profile.mkdir(parents=True)
    (profile / 'cookies.sqlite').write_bytes(b'sqlite')
    monkeypatch.setattr('youtube_player.sys.platform', 'win32')
    paths = firefox_cookie_sqlite_paths(
        environ={
            'APPDATA': str(tmp_path / 'Roaming'),
            'LOCALAPPDATA': str(tmp_path / 'Local'),
        },
        brand='librewolf',
    )
    assert paths
    assert 'librewolf' in paths[0].replace('\\', '/')


def test_youtube_search_history_unique_and_capped(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        assert app_config.youtube_search_history() == []
        app_config.remember_youtube_search('  ')
        assert app_config.youtube_search_history() == []
        app_config.remember_youtube_search('gatos', type_name='Vídeos')
        app_config.remember_youtube_search('perros', type_name='Shorts')
        app_config.remember_youtube_search('gatos', type_name='Vídeos')
        items = app_config.youtube_search_history()
        assert [item['query'] for item in items] == ['gatos', 'perros']
        assert items[0]['type'] == 'Vídeos'
        assert items[1]['type'] == 'Shorts'
        app_config.remember_youtube_search('gatos', type_name='Shorts')
        items = app_config.youtube_search_history()
        assert [(item['query'], item['type']) for item in items] == [
            ('gatos', 'Shorts'),
            ('gatos', 'Vídeos'),
            ('perros', 'Shorts'),
        ]
        assert app_config.youtube_search_label(items[0]) == 'gatos  ·  Shorts'
        assert app_config.youtube_search_label({'query': 'solo'}) == 'solo'
        for index in range(8):
            app_config.remember_youtube_search(f'tema {index}')
        items = app_config.youtube_search_history()
        assert len(items) == 5
        assert items[0]['query'] == 'tema 7'
        assert items[-1]['query'] == 'tema 3'
    finally:
        app_config._cache = previous


def test_parse_relative_upload_text_spanish():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    three_days = parse_relative_upload_text('hace 3 días')
    assert three_days is not None
    assert abs((now - three_days).days - 3) <= 1
    hour = parse_relative_upload_text('Transmitido hace 1 hora')
    assert hour is not None
    assert 0 <= (now - hour).total_seconds() <= 2 * 3600
    assert parse_relative_upload_text('hace un día') is not None
    assert parse_relative_upload_text('ayer') is not None
    assert parse_relative_upload_text('3 days ago') is None
    assert parse_relative_upload_text('') is None


def test_youtube_search_sp_fecha_puts_upload_date_first():
    import base64

    video_date = youtube_search_sp_from_ui('Vídeos', 'Fecha')
    shorts_date = youtube_search_sp_from_ui('Shorts', 'Fecha')
    lists_date = youtube_search_sp_from_ui('Listas de reproducción', 'Fecha')
    video_rel = youtube_search_sp_from_ui('Vídeos', 'Relevancia')

    def decoded(sp):
        padding = '=' * ((4 - len(sp) % 4) % 4)
        return base64.urlsafe_b64decode(sp + padding)

    assert decoded(video_date)[:2] == b'\x08\x02'
    assert decoded(shorts_date)[:2] == b'\x08\x02'
    assert decoded(lists_date)[:2] == b'\x08\x02'
    assert decoded(video_rel)[:2] != b'\x08\x02'
    assert decoded(video_date) == b'\x08\x02\x12\x02\x10\x01'
    assert decoded(shorts_date) == b'\x08\x02\x12\x02\x10\x09'
    assert decoded(lists_date) == b'\x08\x02\x12\x02\x10\x03'
    assert youtube_search_sp('date', 'video') == 'CAISAhAB'
    assert youtube_search_sp('relevance', 'video') != youtube_search_sp('date', 'video')


def test_sort_search_entries_newest_first_when_fecha():
    older = {'title': 'viejo', 'timestamp': 100}
    newer = {'title': 'nuevo', 'timestamp': 300}
    mid = {'title': 'medio', 'timestamp': 200}
    ordered = sort_search_entries([older, newer, mid], 'Fecha')
    assert [item['title'] for item in ordered] == ['nuevo', 'medio', 'viejo']
    by_day = sort_search_entries(
        [
            {'title': 'viejo', 'upload_date': '20200101'},
            {'title': 'nuevo', 'upload_date': '20240101'},
            {'title': 'medio', 'upload_date': '20220101'},
        ],
        'Fecha',
    )
    assert [item['title'] for item in by_day] == ['nuevo', 'medio', 'viejo']
    mixed = sort_search_entries(
        [
            {'title': 'viejo', 'upload_date': '20200101'},
            {'title': 'nuevo', 'timestamp': 1_704_067_200},
        ],
        'Fecha',
    )
    assert [item['title'] for item in mixed] == ['nuevo', 'viejo']
    unchanged = sort_search_entries([older, newer], 'Relevancia')
    assert [item['title'] for item in unchanged] == ['viejo', 'nuevo']
    without_dates = sort_search_entries([{'title': 'a'}, {'title': 'b'}], 'Fecha')
    assert [item['title'] for item in without_dates] == ['a', 'b']


def test_should_offer_youtube_replay_only_for_standalone():
    from video_player import should_offer_youtube_replay

    assert should_offer_youtube_replay(True, True, False, False) is True
    assert should_offer_youtube_replay(True, True, True, False) is False
    assert should_offer_youtube_replay(True, True, False, True) is False
    assert should_offer_youtube_replay(True, False, False, False) is False
    assert should_offer_youtube_replay(False, True, False, False) is False


