"""Fixtures y stubs para la suite de tests.

En Windows CI (y en máquinas sin VLC), ``import vlc`` falla al cargar
``libvlc.dll``. Varios módulos lo importan al cargar; este stub permite
recolectar y ejecutar tests unitarios que no necesitan libVLC real.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace


def _install_vlc_stub():
    stub = ModuleType('vlc')
    stub.State = SimpleNamespace(
        NothingSpecial=0,
        Opening=1,
        Buffering=2,
        Playing=3,
        Paused=4,
        Stopped=5,
        Ended=6,
        Error=7,
    )
    stub.EventType = SimpleNamespace(
        MediaPlayerEndReached=0,
        MediaPlayerEncounteredError=1,
        MediaPlayerPlaying=2,
    )

    class MediaStats:
        """Stub de vlc.MediaStats."""

        def __init__(self):
            self.read_bytes = 0
            self.input_bitrate = 0.0
            self.demux_bitrate = 0.0

    class Instance:
        """Stub de vlc.Instance."""

        def __init__(self, *args, **kwargs):
            pass

        def media_player_new(self):
            return None

        def media_new(self, *args, **kwargs):
            return None

    stub.MediaStats = MediaStats
    stub.Instance = Instance
    stub.libvlc_get_version = lambda: b'stub'
    sys.modules['vlc'] = stub


def _ensure_vlc():
    try:
        import vlc  # noqa: F401
    except Exception:
        sys.modules.pop('vlc', None)
        _install_vlc_stub()


_ensure_vlc()
