"""Navegación del reproductor: seek, reinicio, anterior/siguiente."""

import time

try:
    import vlc
except Exception:  # pragma: no cover
    vlc = None

PREVIOUS_RESTART_MS = 3000


class PlayerNavigationMixin:
    """Seek relativo, reinicio y salto anterior/siguiente en la lista."""

    def seek_relative(self, seconds):
        """Avanza o retrocede el vídeo en segundos."""
        if not self.player or vlc is None:
            return
        now = time.time()
        last_at, last_delta = getattr(self, '_seek_relative_at', (0, None))
        if last_delta == seconds and (now - last_at) < 0.12:
            return
        self._seek_relative_at = (now, seconds)
        try:
            state = self.player.get_state()
        except Exception:
            return
        if state not in (vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering):
            return
        current = self._playback_elapsed_ms()
        hint = getattr(self, '_seek_hint_ms', None)
        if hint is not None and now < getattr(self, '_seek_hint_until', 0):
            current = hint
        self._apply_seek(current + int(seconds * 1000))

    def restart_current_media(self):
        """Vuelve al comienzo del vídeo en reproducción."""
        if not self.player or vlc is None:
            return
        try:
            state = self.player.get_state()
        except Exception:
            return
        if state not in (vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering):
            return
        self._apply_seek(0)

    def play_next_media(self):
        """Pasa al siguiente vídeo o canal de la lista lateral."""
        self._play_relative_channel(1)

    def play_previous_media(self):
        """Si van >3 s, reinicia; si no, va al anterior de la lista."""
        try:
            elapsed = int(self._playback_elapsed_ms() or 0)
        except Exception:
            elapsed = 0
        if elapsed > PREVIOUS_RESTART_MS:
            self.restart_current_media()
            return
        self._play_relative_channel(-1)
