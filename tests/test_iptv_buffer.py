import app_config
from iptv_buffer import (
    CACHE_MS_MAX,
    SOFT_REBUFFER_EXTRA_MS,
    iptv_cache_ms,
    iptv_deadman_should_fail,
    iptv_rebuffer_decision,
    iptv_soft_rebuffer_note,
    iptv_soft_rebuffer_should_bump,
    iptv_startup_decision,
    iptv_vlc_buffer_options,
    normalize_iptv_buffer_profile,
    vlc_state_name,
)
from player_iptv import IptvPlaybackMixin


def _isolate_config(tmp_path, monkeypatch):
    previous = app_config._cache
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(tmp_path / 'config.json'))
    app_config._cache = None
    return previous


def test_normalize_iptv_buffer_profile():
    assert normalize_iptv_buffer_profile('fast') == 'fast'
    assert normalize_iptv_buffer_profile('Rápido') == 'fast'
    assert normalize_iptv_buffer_profile('estable') == 'stable'
    assert normalize_iptv_buffer_profile('nope') == 'balanced'


def test_iptv_cache_ms_by_kind_and_profile():
    assert iptv_cache_ms('mpegts', profile='balanced') == 5000
    assert iptv_cache_ms('hls', profile='balanced') == 8000
    assert iptv_cache_ms('container', profile='balanced') == 4000
    assert iptv_cache_ms('mpegts', vod=True, profile='balanced') == 4000
    assert iptv_cache_ms('container', force_ts=True, profile='balanced') == 5000
    assert iptv_cache_ms('hls', local=True, profile='balanced') == 1500
    assert iptv_cache_ms('mpegts', profile='fast') == 2000
    assert iptv_cache_ms('hls', profile='fast') == 5000
    assert iptv_cache_ms('hls', profile='stable') == 12000
    assert iptv_cache_ms('mpegts', profile='stable') == 8000
    assert iptv_cache_ms('mpegts', profile='balanced', extra_ms=SOFT_REBUFFER_EXTRA_MS) == 8000
    assert iptv_cache_ms('mpegts', profile='stable', extra_ms=20000) == CACHE_MS_MAX


def test_iptv_live_options_relax_clock_vod_keeps_sync():
    live = iptv_vlc_buffer_options('mpegts', profile='balanced')
    assert ':network-caching=5000' in live
    assert ':clock-synchro=0' in live
    assert ':clock-jitter=5000' in live
    assert ':clock-jitter=0' not in live
    assert all('http://' not in item for item in live)
    vod = iptv_vlc_buffer_options('container', vod=True, profile='balanced')
    assert ':network-caching=4000' in vod
    assert ':clock-synchro=0' not in vod
    assert ':clock-jitter=' not in ''.join(vod)
    hls = iptv_vlc_buffer_options('hls', profile='fast')
    assert ':network-caching=5000' in hls
    assert ':clock-synchro=0' in hls
    assert ':clock-jitter=5000' in hls
    bumped = iptv_vlc_buffer_options('mpegts', profile='balanced', extra_ms=3000)
    assert ':network-caching=8000' in bumped
    assert ':clock-jitter=8000' in bumped


def test_iptv_startup_waits_while_bytes_grow():
    assert iptv_startup_decision(
        state='Buffering', decoded=False, bytes_now=0, bytes_prev=0, ticks=2,
    ) == 'wait'
    assert iptv_startup_decision(
        state='Buffering', decoded=False, bytes_now=0, bytes_prev=0, ticks=4,
        kind='mpegts',
    ) == 'fail'
    assert iptv_startup_decision(
        state='Buffering', decoded=False, bytes_now=80000, bytes_prev=10000, ticks=6,
        kind='mpegts',
    ) == 'wait'
    assert iptv_startup_decision(
        state='Buffering', decoded=False, bytes_now=80000, bytes_prev=80000, ticks=5,
        kind='mpegts',
    ) == 'fail'
    assert iptv_startup_decision(
        state='Playing', decoded=True, bytes_now=100, bytes_prev=50, ticks=1,
    ) == 'ready'
    assert iptv_startup_decision(
        state='Ended', decoded=False, bytes_now=0, bytes_prev=0, ticks=1,
        kind='container', already_retried_ts=False,
    ) == 'retry_ts'
    assert iptv_startup_decision(
        state='Error', decoded=False, bytes_now=0, bytes_prev=0, ticks=0,
        kind='mpegts',
    ) == 'fail'


def test_iptv_hls_gets_more_time_without_bytes():
    assert iptv_startup_decision(
        state='Opening', decoded=False, bytes_now=0, bytes_prev=0, ticks=5,
        kind='hls',
    ) == 'wait'
    assert iptv_startup_decision(
        state='Opening', decoded=False, bytes_now=0, bytes_prev=0, ticks=6,
        kind='hls',
    ) == 'fail'


def test_iptv_deadman_extends_if_data_arrives():
    assert iptv_deadman_should_fail(
        decoded=True, bytes_now=1, bytes_prev=0, elapsed_s=12,
    ) is False
    assert iptv_deadman_should_fail(
        decoded=False, bytes_now=0, bytes_prev=0, elapsed_s=12, kind='mpegts',
    ) is True
    assert iptv_deadman_should_fail(
        decoded=False, bytes_now=9000, bytes_prev=1000, elapsed_s=12, kind='mpegts',
    ) is False
    assert iptv_deadman_should_fail(
        decoded=False, bytes_now=9000, bytes_prev=1000, elapsed_s=16, kind='mpegts',
    ) is True


def test_iptv_rebuffer_reconnects_once_then_fails():
    assert iptv_rebuffer_decision(
        started=True, state='Playing', stall_ticks=0,
        bytes_now=10, bytes_prev=5, reconnects=0,
    ) == 'ok'
    assert iptv_rebuffer_decision(
        started=True, state='Buffering', stall_ticks=2,
        bytes_now=10, bytes_prev=10, reconnects=0,
    ) == 'wait'
    assert iptv_rebuffer_decision(
        started=True, state='Buffering', stall_ticks=4,
        bytes_now=10, bytes_prev=10, reconnects=0,
    ) == 'reconnect'
    assert iptv_rebuffer_decision(
        started=True, state='Buffering', stall_ticks=4,
        bytes_now=10, bytes_prev=10, reconnects=1,
    ) == 'wait'
    assert iptv_rebuffer_decision(
        started=True, state='Buffering', stall_ticks=8,
        bytes_now=10, bytes_prev=10, reconnects=1,
    ) == 'fail'
    assert iptv_rebuffer_decision(
        started=True, state='Ended', stall_ticks=0,
        bytes_now=10, bytes_prev=10, reconnects=0, vod=True,
    ) == 'ok'


def test_vlc_state_name_from_string_or_attr():
    assert vlc_state_name('State.Buffering') == 'Buffering'
    assert vlc_state_name(type('S', (), {'name': 'Playing'})()) == 'Playing'


def test_remote_options_use_profile_cache(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.set_iptv_buffer('stable')

        class Dummy(IptvPlaybackMixin):
            _iptv_source_url = 'http://panel.example/live/1.ts'

        dummy = Dummy()
        options = dummy._iptv_remote_options('mpegts')
        assert ':network-caching=8000' in options
        assert ':clock-synchro=0' in options
        assert ':clock-jitter=8000' in options
        assert ':http-reconnect=true' in options
        assert all('panel.example' not in item for item in options)
        dummy._iptv_cache_extra_ms = 3000
        extra = dummy._iptv_remote_options('mpegts')
        assert ':network-caching=11000' in extra
        assert ':clock-jitter=11000' in extra
    finally:
        app_config._cache = previous


def test_iptv_soft_rebuffer_bump_once_in_window():
    assert iptv_soft_rebuffer_should_bump(2, False) is False
    assert iptv_soft_rebuffer_should_bump(3, False) is True
    assert iptv_soft_rebuffer_should_bump(5, True) is False
    times = iptv_soft_rebuffer_note([], 10.0, is_new_event=True)
    times = iptv_soft_rebuffer_note(times, 18.0, is_new_event=True)
    times = iptv_soft_rebuffer_note(times, 22.0, is_new_event=False)
    assert len(times) == 2
    times = iptv_soft_rebuffer_note(times, 25.0, is_new_event=True)
    assert len(times) == 3
    assert iptv_soft_rebuffer_should_bump(len(times), False) is True
    later = iptv_soft_rebuffer_note(times, 56.0, is_new_event=True)
    assert later == [56.0]


def test_iptv_buffer_pref_roundtrip(tmp_path, monkeypatch):
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        assert app_config.get_iptv_buffer() == 'balanced'
        app_config.set_iptv_buffer('rápido')
        assert app_config.get_iptv_buffer() == 'fast'
        app_config.set_iptv_buffer('stable')
        assert app_config.get_iptv_buffer() == 'stable'
    finally:
        app_config._cache = previous
