from datetime import datetime, timedelta, timezone
from io import BytesIO

from epg import (
    Guide,
    Programme,
    format_now_next,
    load_guide_from_text,
    normalize_epg_source,
    parse_xmltv,
    parse_xmltv_datetime,
)
from m3u_parse import (
    classify_iptv_url,
    decode_m3u_bytes,
    describe_iptv_url,
    extm3u_header_line,
    is_iptv_vod,
    parse_m3u_channels,
    parse_m3u_entries,
    parse_m3u_epg_urls,
)


MADRID = timezone(timedelta(hours=2))
NOW = datetime(2026, 8, 24, 10, 30, tzinfo=MADRID).timestamp()

SAMPLE_M3U = """#EXTM3U url-tvg="http://epg.example/guia.xml" x-tvg-url="https://backup.example/epg.xml"
#EXTINF:-1 tvg-id="es.la1" tvg-name="La 1" group-title="España",La 1 HD
http://panel.example/live/1.ts
# comentario entre EXTINF y la URL
#EXTINF:-1 tvg-id="es.la2" group-title="España",La 2
http://panel.example/live/2.m3u8
#EXTINF:-1 tvg-logo="http://cdn.example/logo.png",Película
http://panel.example/movie/film.mkv
#EXTINF:-1,Imagen suelta
http://cdn.example/art.png
"""

SAMPLE_XMLTV = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="es.la1">
    <display-name>La 1</display-name>
    <icon src="http://cdn.example/la1.png" />
  </channel>
  <programme start="20260824100000 +0200" stop="20260824110000 +0200" channel="es.la1">
    <title lang="en">News</title>
    <title lang="es">Telediario</title>
  </programme>
  <programme start="20260824110000 +0200" stop="20260824120000 +0200" channel="es.la1">
    <title lang="es">Informativo</title>
  </programme>
  <programme start="20260824120000 +0200" stop="20260824133000 +0200" channel="es.la1">
    <title lang="es">Cine</title>
  </programme>
  <programme start="20260824080000 +0200" stop="20260824090000 +0200" channel="es.la1">
    <title lang="es">Ya pasó</title>
  </programme>
  <programme start="20260824103000 +0200" stop="20260824113000 +0200" channel="otros.id">
    <title lang="es">Otro canal</title>
  </programme>
</tv>
"""


class TestExtm3uHeader:
    def test_keeps_url_tvg(self):
        line = '#EXTM3U url-tvg="http://epg.example/guia.xml"\n'
        assert extm3u_header_line(line) == line

    def test_keeps_x_tvg_url_without_newline(self):
        line = '#EXTM3U x-tvg-url="https://backup.example/epg.xml"'
        assert extm3u_header_line(line) == line + '\n'

    def test_strips_bom(self):
        line = '\ufeff#EXTM3U url-tvg="http://epg.example/guia.xml"\n'
        assert extm3u_header_line(line) == '#EXTM3U url-tvg="http://epg.example/guia.xml"\n'

    def test_bare_header_when_first_line_is_extinf(self):
        assert extm3u_header_line('#EXTINF:-1,Canal\n') == '#EXTM3U\n'

    def test_empty_line(self):
        assert extm3u_header_line('') == '#EXTM3U\n'


class TestParseEpgUrls:
    def test_reads_url_tvg_from_header(self):
        assert parse_m3u_epg_urls(SAMPLE_M3U) == [
            'http://epg.example/guia.xml',
            'https://backup.example/epg.xml',
        ]

    def test_header_only_extm3u_loses_guide(self):
        filtered = extm3u_header_line('#EXTINF:-1,Canal\n') + (
            '#EXTINF:-1 tvg-id="es.la1",La 1\nhttp://x\n'
        )
        assert parse_m3u_epg_urls(filtered) == []

    def test_preserved_header_keeps_guide_after_filter(self):
        original = '#EXTM3U url-tvg="http://epg.example/guia.xml"\n'
        out = extm3u_header_line(original) + '#EXTINF:-1 tvg-id="es.la1",La 1\nhttp://x\n'
        assert parse_m3u_epg_urls(out) == ['http://epg.example/guia.xml']

    def test_tvg_url_on_extinf_if_no_header(self):
        text = (
            '#EXTM3U\n'
            '#EXTINF:-1 tvg-url="http://from-inf.example/epg.xml" tvg-id="a",A\n'
            'http://x\n'
        )
        assert parse_m3u_epg_urls(text) == ['http://from-inf.example/epg.xml']


class TestParseChannels:
    def test_name_group_tvg_id_and_skips_images(self):
        channels = parse_m3u_channels(SAMPLE_M3U)
        assert channels == [
            ('La 1 HD', 'http://panel.example/live/1.ts', 'España', 'es.la1', ''),
            ('La 2', 'http://panel.example/live/2.m3u8', 'España', 'es.la2', ''),
            ('Película', 'http://panel.example/movie/film.mkv', '', '', 'http://cdn.example/logo.png'),
        ]

    def test_entries_drop_group_and_id(self):
        assert parse_m3u_entries(SAMPLE_M3U) == [
            ('La 1 HD', 'http://panel.example/live/1.ts'),
            ('La 2', 'http://panel.example/live/2.m3u8'),
            ('Película', 'http://panel.example/movie/film.mkv'),
        ]

    def test_skips_comments_between_extinf_and_url(self):
        text = (
            '#EXTINF:-1 tvg-id="a",Canal\n'
            '#EXTVLCOPT:http-user-agent=VLC\n'
            'http://live.example/a.ts\n'
        )
        assert parse_m3u_channels(text) == [
            ('Canal', 'http://live.example/a.ts', '', 'a', ''),
        ]

    def test_unquoted_group_and_tvg_id(self):
        text = '#EXTINF:-1 tvg-id=es.one group-title=Deportes,Gol\nhttp://x\n'
        name, url, group, tvg_id, logo = parse_m3u_channels(text)[0]
        assert (name, url, group, tvg_id, logo) == ('Gol', 'http://x', 'Deportes', 'es.one', '')

    def test_channel_id_attribute(self):
        text = '#EXTINF:-1 channel-id="MTVEsp.sp",ES| MTV SD\nhttp://x\n'
        assert parse_m3u_channels(text)[0][3] == 'MTVEsp.sp'

    def test_bytes_and_latin1(self):
        raw = '#EXTINF:-1,Cañón\nhttp://x\n'.encode('latin-1')
        decoded = decode_m3u_bytes(raw)
        assert 'Cañón' in decoded
        assert parse_m3u_entries(raw)[0][0] == 'Cañón'

    def test_on_progress_starts_and_ends(self):
        ticks = []
        text = ''.join(f'#EXTINF:-1,C{i}\nhttp://x/{i}\n' for i in range(80))
        channels = parse_m3u_channels(text, on_progress=ticks.append)
        assert len(channels) == 80
        assert ticks[0] == 0.0
        assert ticks[-1] == 1.0
        assert all(0.0 <= t <= 1.0 for t in ticks)
        assert ticks == sorted(ticks)


class TestClassifyIptv:
    def test_hls_container_mpegts(self):
        assert classify_iptv_url('http://x/live/1.m3u8') == 'hls'
        assert classify_iptv_url('http://x/movie/a.mkv?token=1') == 'container'
        assert classify_iptv_url('http://x/live/1.ts') == 'mpegts'
        assert classify_iptv_url('http://x/live/1') == 'mpegts'

    def test_describe_does_not_echo_host(self):
        summary = describe_iptv_url('http://secret.example/live/canal.ts')
        assert 'secret.example' not in summary
        assert summary == 'live/ts'

    def test_vod_vs_live(self):
        assert is_iptv_vod('http://x/movie/u/p/1.mkv')
        assert is_iptv_vod('http://x/series/u/p/1.m3u8')
        assert is_iptv_vod('http://x/film.mp4')
        assert not is_iptv_vod('http://x/live/u/p/1.ts')
        assert not is_iptv_vod('http://x/live/u/p/1.m3u8')


class TestXmltvDatetime:
    def test_with_offset(self):
        ts = parse_xmltv_datetime('20260824100000 +0200')
        expected = datetime(2026, 8, 24, 10, 0, tzinfo=MADRID).timestamp()
        assert ts == expected

    def test_invalid(self):
        assert parse_xmltv_datetime('') is None
        assert parse_xmltv_datetime('no-es-fecha') is None


class TestParseXmltv:
    def test_now_next_spanish_title(self):
        guide = parse_xmltv(BytesIO(SAMPLE_XMLTV.encode()), ['es.la1'], now=NOW)
        current, nxt = guide.now_next('es.la1', now=NOW)
        assert current.title == 'Telediario'
        assert nxt.title == 'Informativo'
        assert guide.now_next('otros.id', now=NOW) == (None, None)

    def test_case_insensitive_id(self):
        guide = parse_xmltv(BytesIO(SAMPLE_XMLTV.encode()), ['ES.LA1'], now=NOW)
        current, nxt = guide.now_next('es.la1', now=NOW)
        assert current is not None
        assert nxt is not None

    def test_load_guide_from_text(self):
        guide = load_guide_from_text(SAMPLE_XMLTV, ['es.la1'], now=NOW)
        text = format_now_next(*guide.now_next('es.la1', now=NOW))
        assert 'Ahora:' in text
        assert 'Telediario' in text
        assert 'A continuación:' in text
        assert 'Informativo' in text

    def test_empty_wanted(self):
        assert parse_xmltv(BytesIO(SAMPLE_XMLTV.encode()), [], now=NOW).channel_count() == 0

    def test_broken_xml_returns_empty_guide(self):
        guide = parse_xmltv(BytesIO(b'<tv><programme>'), ['es.la1'], now=NOW)
        assert isinstance(guide, Guide)
        assert guide.now_next('es.la1', now=NOW) == (None, None)

    def test_grid_window_and_icon(self):
        guide = parse_xmltv(BytesIO(SAMPLE_XMLTV.encode()), ['es.la1'], now=NOW)
        assert guide.icon('es.la1') == 'http://cdn.example/la1.png'
        assert guide.now_title('es.la1', now=NOW) == 'Telediario'
        start = datetime(2026, 8, 24, 10, 0, tzinfo=MADRID).timestamp()
        stop = datetime(2026, 8, 24, 16, 0, tzinfo=MADRID).timestamp()
        titles = [item.title for item in guide.programmes_between('es.la1', start, stop)]
        assert titles == ['Telediario', 'Informativo', 'Cine']
        assert 'Ya pasó' not in titles

    def test_matches_display_name_when_no_tvg_id(self):
        guide = parse_xmltv(
            BytesIO(SAMPLE_XMLTV.encode()),
            [],
            now=NOW,
            wanted_names=['La 1'],
        )
        current, nxt = guide.now_next('La 1', now=NOW)
        assert current is not None
        assert current.title == 'Telediario'
        assert nxt.title == 'Informativo'
        assert guide.icon('La 1') == 'http://cdn.example/la1.png'
        assert guide.now_next('es.la1', now=NOW)[0].title == 'Telediario'


class TestNormalizeEpgSource:
    def test_http_and_host(self):
        assert normalize_epg_source('https://epg.example/xml') == 'https://epg.example/xml'
        assert normalize_epg_source('epg.example/xml') == 'https://epg.example/xml'
        assert normalize_epg_source('  "http://epg.example/a"  ') == 'http://epg.example/a'

    def test_get_php_port_80_stays_http(self):
        raw = 'panel.example.cc:80/get.php?username=user&password=secret'
        assert normalize_epg_source(raw) == 'http://' + raw
        with_scheme = 'http://panel.example.cc:80/xmltv.php?username=user&password=secret'
        assert normalize_epg_source(with_scheme) == with_scheme

    def test_empty(self):
        assert normalize_epg_source('') == ''
        assert normalize_epg_source(None) == ''


def test_programme_clock():
    start = datetime(2026, 8, 24, 10, 0).timestamp()
    prog = Programme(start, start + 3600, 'X')
    assert prog.clock == '10:00'


def test_logo_cache_path_and_png(tmp_path, monkeypatch):
    import logo_cache
    from PIL import Image

    monkeypatch.setattr(logo_cache, 'CACHE_DIR', str(tmp_path))
    url_a = 'http://cdn.example/a.png'
    url_b = 'http://cdn.example/b.png'
    path_a = logo_cache.path_for(url_a)
    path_b = logo_cache.path_for(url_b)
    assert path_a.endswith('.png')
    assert path_a != path_b
    assert str(tmp_path) in path_a

    image = Image.new('RGB', (40, 40), (10, 20, 30))
    raw = BytesIO()
    image.save(raw, format='PNG')
    png = logo_cache._to_png(raw.getvalue())
    out = Image.open(BytesIO(png))
    assert out.size == (logo_cache.LOGO_PX, logo_cache.LOGO_PX)


def test_show_channel_logos_pref(tmp_path, monkeypatch):
    import app_config

    previous = app_config._cache
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    try:
        app_config._cache = None
        assert app_config.get_show_channel_logos() is True
        app_config.set_show_channel_logos(False)
        app_config._cache = None
        assert app_config.get_show_channel_logos() is False
    finally:
        app_config._cache = previous
