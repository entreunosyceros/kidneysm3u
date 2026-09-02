"""Tests para cache_cleanup."""

import os
import time

import cache_cleanup


def test_format_bytes():
    assert cache_cleanup.format_bytes(512) == '512 B'
    assert cache_cleanup.format_bytes(2048) == '2.0 KB'
    assert cache_cleanup.format_bytes(5 * 1024 * 1024) == '5.0 MB'


def test_clear_epg_and_logos(tmp_path, monkeypatch):
    epg = tmp_path / 'epg_cache'
    epg.mkdir()
    (epg / 'a.png').write_bytes(b'x' * 100)
    (epg / 'guide.dat').write_bytes(b'y' * 50)

    monkeypatch.setattr(cache_cleanup, 'epg_cache_dir', lambda: str(epg))

    stats = cache_cleanup.stats()
    assert stats['epg_cache']['bytes'] == 150
    assert stats['epg_cache']['files'] == 2
    assert stats['logos']['bytes'] == 100
    assert stats['logos']['files'] == 1

    removed, freed = cache_cleanup.clear_logo_cache()
    assert removed == 1
    assert freed == 100
    assert (epg / 'guide.dat').exists()
    assert not (epg / 'a.png').exists()

    (epg / 'b.png').write_bytes(b'z' * 20)
    removed, freed = cache_cleanup.clear_epg_cache()
    assert removed == 2
    assert freed == 70
    assert list(epg.iterdir()) == []


def test_clear_youtube_cache(tmp_path, monkeypatch):
    yt = tmp_path / 'kidneysm3u_yt_cache'
    yt.mkdir()
    (yt / 'vid_720.mp4').write_bytes(b'v' * 200)
    monkeypatch.setattr(cache_cleanup, 'youtube_cache_dir', lambda: str(yt))

    stats = cache_cleanup.stats()
    assert stats['youtube']['bytes'] == 200
    assert stats['youtube']['files'] == 1

    removed, freed = cache_cleanup.clear_youtube_cache()
    assert removed == 1
    assert freed == 200
    assert list(yt.iterdir()) == []


def test_old_recordings_stats_and_clear(tmp_path, monkeypatch):
    rec = tmp_path / 'downloads'
    rec.mkdir()
    old = rec / 'Canal_20240101-120000.ts'
    new = rec / 'Canal_20260101-120000.ts'
    old.write_bytes(b'r' * 300)
    new.write_bytes(b'n' * 100)
    other = rec / 'movie.mp4'
    other.write_bytes(b'o' * 50)

    old_time = time.time() - 40 * 86400
    os.utime(old, (old_time, old_time))
    os.utime(new, (time.time(), time.time()))

    monkeypatch.setattr(cache_cleanup, 'recordings_folder', lambda: str(rec))

    stats = cache_cleanup.old_recordings_stats(30, str(rec))
    assert stats['files'] == 1
    assert stats['bytes'] == 300

    removed, freed = cache_cleanup.clear_old_recordings(30, str(rec))
    assert removed == 1
    assert freed == 300
    assert old.exists() is False
    assert new.exists()
    assert other.exists()
