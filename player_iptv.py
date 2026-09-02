"""Reproducción IPTV: VLC remoto, reintento MPEG-TS y detección de stream muerto."""

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer

import vlc

import app_config
from iptv_buffer import (
    PROFILE_LABELS,
    SOFT_REBUFFER_EXTRA_MS,
    iptv_bytes_progress,
    iptv_cache_ms,
    iptv_deadman_should_fail,
    iptv_overlay_message,
    iptv_rebuffer_decision,
    iptv_soft_rebuffer_note,
    iptv_soft_rebuffer_should_bump,
    iptv_startup_decision,
    iptv_vlc_buffer_options,
    vlc_aout_option,
    vlc_state_name,
)
from m3u_parse import (
    IPTV_USER_AGENT,
    classify_iptv_url,
    describe_iptv_url,
    iptv_upstream_candidates,
    is_iptv_vod,
)
from subtitle_style import vlc_media_options
from youtube_player import _GrowingTSHandler


class IptvPlaybackMixin:
    """Clase que representa iptvplaybackmixin."""
    def _iptv_show_overlay(self, event):
        """Uso interno: aviso breve sobre el vídeo (reconexión, buffer, etc.)."""
        show = getattr(self, '_show_iptv_progress_overlay', None)
        if not callable(show):
            return
        title, detail = iptv_overlay_message(event)
        show(title, detail)

    def _iptv_hide_overlay_if_playing(self):
        """Uso interno: quita el aviso cuando ya hay imagen o audio decodificado."""
        if not self._iptv_has_real_media():
            return
        hide = getattr(self, '_hide_iptv_progress_overlay', None)
        if callable(hide):
            hide()

    def _play_iptv_url(self, name, url):
        """Uso interno: play IPTV URL."""
        url = (url or '').strip()
        if not url:
            self._show_channel_unavailable(name)
            return
        self._media_started = False
        self._playing_youtube = False
        self._playing_twitch = False
        twitch = getattr(self, 'twitch_handler', None)
        if twitch:
            twitch.close_chat()
        self._iptv_ok_ticks = 0
        kind = classify_iptv_url(url)
        print(f"[IPTV] '{name}' → {describe_iptv_url(url)} tipo={kind}")
        if kind == 'container' or is_iptv_vod(url):
            self._known_duration_ms = 0
            self.show_youtube_progress_bar()
        else:
            self.hide_progress_bar()
        self._iptv_retry_name = name
        self._iptv_source_url = url
        self._iptv_kind = kind
        self._iptv_did_ts_retry = False
        self._iptv_bytes_prev = 0
        self._iptv_reconnects = 0
        self._iptv_rebuffer_stall = 0
        self._iptv_cache_extra_ms = 0
        self._iptv_soft_bumped = False
        self._iptv_soft_times = []
        self._iptv_soft_was_buffering = False
        self._iptv_check_gen = getattr(self, '_iptv_check_gen', 0) + 1
        check_gen = self._iptv_check_gen
        self._start_vlc_remote(name, url, kind)
        self._iptv_show_overlay('connecting')
        self.window.after(800, lambda: self._watch_iptv_start(check_gen, name, url, kind, 0))
        self.window.after(12000, lambda: self._iptv_deadman(check_gen, name, 12))
        self.window.after(2500, lambda: self._check_iptv_stream(check_gen))

    def _sanitize_iptv_log(self, text):
        """Uso interno: sanitize IPTV log."""
        return re.sub(r'https?://\S+', '[url]', text or '')

    def _iptv_media_stats(self):
        """Uso interno: IPTV media stats."""
        if not self.player:
            return None
        try:
            media = self.player.get_media()
        except Exception:
            return None
        if media is None:
            return None
        try:
            stats = vlc.MediaStats()
            if not media.get_stats(stats):
                return None
            return stats
        except Exception:
            return None

    def _iptv_has_real_media(self):
        """Playing/Buffering con pantalla negra no cuenta: hace falta decodificar algo."""
        stats = self._iptv_media_stats()
        if stats is None:
            return False
        for field in ('decoded_video', 'decoded_audio', 'displayed_pictures', 'played_abuffers'):
            try:
                if int(getattr(stats, field, 0) or 0) > 0:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    def _iptv_cache_extra(self):
        """Uso interno: IPTV cache extra."""
        try:
            return max(0, int(getattr(self, '_iptv_cache_extra_ms', 0) or 0))
        except (TypeError, ValueError):
            return 0

    def _iptv_remote_options(self, kind, force_ts=False):
        """Uso interno: IPTV remote options."""
        url = getattr(self, '_iptv_source_url', '') or ''
        vod = is_iptv_vod(url) or kind == 'container'
        profile = app_config.get_iptv_buffer()
        options = iptv_vlc_buffer_options(
            kind,
            vod=vod,
            local=False,
            profile=profile,
            force_ts=force_ts,
            extra_ms=self._iptv_cache_extra(),
        )
        options.extend([
            ':audio-resampler=soxr',
            ':codec=avcodec',
            f':http-user-agent={IPTV_USER_AGENT}',
            ':http-reconnect=true',
        ])
        if not app_config.iptv_use_hw_decode():
            options.insert(0, ':avcodec-hw=none')
        aout = vlc_aout_option()
        if aout:
            options.append(aout)
        if force_ts:
            options.extend([':demux=ts', ':no-ts-trust-pcr'])
        elif kind == 'mpegts':
            options.append(':no-ts-trust-pcr')
        options.extend(vlc_media_options())
        return options

    def _start_vlc_remote(self, name, url, kind, force_ts=False):
        """Uso interno: start VLC remote."""
        if not self.instance:
            return
        if self.player is None:
            self.player = self.instance.media_player_new()
            try:
                self.player.audio_set_volume(self.volume)
            except Exception:
                pass
        try:
            self.player.stop()
        except Exception:
            pass
        how = 'mpegts forzado' if force_ts else kind
        cache = iptv_cache_ms(
            kind,
            vod=is_iptv_vod(url) or kind == 'container',
            profile=app_config.get_iptv_buffer(),
            force_ts=force_ts,
            extra_ms=self._iptv_cache_extra(),
        )
        label = PROFILE_LABELS.get(app_config.get_iptv_buffer(), app_config.get_iptv_buffer())
        print(f"[IPTV] Abriendo {describe_iptv_url(url)} ({how}) buffer={cache}ms ({label})")
        media = self.instance.media_new(url)
        for option in self._iptv_remote_options(kind, force_ts=force_ts):
            media.add_option(option)
        self.player.set_media(media)
        self._embed_vlc_in_frame()
        self.player.play()
        self.adjust_video_settings()
        self.start_update_time()
        self._schedule_track_refresh()
        self._iptv_retry_name = name

    def _iptv_deadman(self, check_gen, name, elapsed=12):
        """Uso interno: IPTV deadman."""
        if check_gen != getattr(self, '_iptv_check_gen', 0):
            return
        if getattr(self, '_iptv_failed', False) or getattr(self, '_playing_youtube', False):
            return
        if self._iptv_has_real_media():
            self._media_started = True
            self._iptv_hide_overlay_if_playing()
            apply = getattr(self, '_apply_pending_iptv_resume', None)
            if apply:
                apply()
            return
        stats = self._iptv_media_stats()
        bytes_now = iptv_bytes_progress(stats)
        bytes_prev = int(getattr(self, '_iptv_bytes_prev', 0) or 0)
        kind = getattr(self, '_iptv_kind', 'mpegts')
        if not iptv_deadman_should_fail(
            decoded=False,
            bytes_now=bytes_now,
            bytes_prev=bytes_prev,
            elapsed_s=elapsed,
            kind=kind,
        ):
            self._iptv_bytes_prev = max(bytes_prev, bytes_now)
            if self._widget_exists(self.window):
                self.window.after(4000, lambda: self._iptv_deadman(check_gen, name, elapsed + 4))
            return
        self._iptv_report_unavailable(name)

    def _watch_iptv_start(self, check_gen, name, url, kind, ticks=0):
        """Uso interno: watch IPTV start."""
        if check_gen != getattr(self, '_iptv_check_gen', 0):
            return
        if getattr(self, '_iptv_failed', False):
            return
        if not self.player or getattr(self, '_playing_youtube', False):
            if ticks >= 4:
                self._iptv_report_unavailable(name)
            elif not getattr(self, '_playing_youtube', False):
                self.window.after(2000, lambda: self._watch_iptv_start(check_gen, name, url, kind, ticks + 1))
            return
        try:
            state = self.player.get_state()
        except Exception:
            if ticks >= 4:
                self._iptv_report_unavailable(name)
            else:
                self.window.after(2000, lambda: self._watch_iptv_start(check_gen, name, url, kind, ticks + 1))
            return
        stats = self._iptv_media_stats()
        decoded_v = int(getattr(stats, 'decoded_video', 0) or 0) if stats else 0
        decoded_a = int(getattr(stats, 'decoded_audio', 0) or 0) if stats else 0
        pictures = int(getattr(stats, 'displayed_pictures', 0) or 0) if stats else 0
        bytes_now = iptv_bytes_progress(stats)
        bytes_prev = int(getattr(self, '_iptv_bytes_prev', 0) or 0)
        if ticks < 8:
            print(
                f"[IPTV] VLC {state} decoded_v={decoded_v} decoded_a={decoded_a} "
                f"pictures={pictures} bytes={bytes_now}"
            )
        decoded = self._iptv_has_real_media()
        action = iptv_startup_decision(
            state=state,
            decoded=decoded,
            bytes_now=bytes_now,
            bytes_prev=bytes_prev,
            ticks=ticks,
            kind=kind,
            already_retried_ts=bool(getattr(self, '_iptv_did_ts_retry', False)),
        )
        self._iptv_bytes_prev = max(bytes_prev, bytes_now)
        if action == 'ready':
            self._media_started = True
            self._iptv_hide_overlay_if_playing()
            apply = getattr(self, '_apply_pending_iptv_resume', None)
            if apply:
                apply()
            return
        if action == 'retry_ts':
            self._iptv_did_ts_retry = True
            print("[IPTV] El contenedor cortó al abrir; reintento como MPEG-TS")
            self._iptv_show_overlay('retry_ts')
            self._iptv_check_gen = check_gen + 1
            retry_gen = self._iptv_check_gen
            self._iptv_bytes_prev = 0
            self._start_vlc_remote(name, url, kind, force_ts=True)
            self.window.after(2000, lambda: self._watch_iptv_start(retry_gen, name, url, kind, 0))
            self.window.after(12000, lambda: self._iptv_deadman(retry_gen, name, 12))
            self.window.after(2500, lambda: self._check_iptv_stream(retry_gen))
            return
        if action == 'fail':
            self._iptv_report_unavailable(name)
            return
        if ticks >= 1:
            self._iptv_show_overlay('connecting')
        self.window.after(2000, lambda: self._watch_iptv_start(check_gen, name, url, kind, ticks + 1))

    def _iptv_local_options(self):
        """Uso interno: IPTV local options."""
        profile = app_config.get_iptv_buffer()
        options = iptv_vlc_buffer_options(
            'mpegts',
            vod=False,
            local=True,
            profile=profile,
            extra_ms=self._iptv_cache_extra(),
            prefix='',
        )
        options.extend([
            'audio-resampler=soxr',
            'demux=ts',
            'no-ts-trust-pcr',
        ])
        if not app_config.iptv_use_hw_decode():
            options.insert(0, 'avcodec-hw=none')
        aout = vlc_aout_option(prefix='')
        if aout:
            options.append(aout)
        options.extend(vlc_media_options(prefix=''))
        return options

    def _start_vlc_local_ts(self, name, url):
        """VLC solo abre localhost; no usa el HTTP remoto que falla tras el 302."""
        if not self.instance:
            return
        if self.player is None:
            self.player = self.instance.media_player_new()
            try:
                self.player.audio_set_volume(self.volume)
            except Exception:
                pass
        try:
            if self.player.is_playing():
                self.player.stop()
        except Exception:
            pass
        media = self.instance.media_new(url)
        for option in self._iptv_local_options():
            media.add_option(option)
        self.player.set_media(media)
        self._embed_vlc_in_frame()
        self.player.play()
        self.adjust_video_settings()
        self.start_update_time()
        self._schedule_track_refresh()
        self._iptv_retry_name = name

    def _check_iptv_stream(self, check_gen=None, waited=0):
        """Uso interno: check IPTV stream."""
        if check_gen is not None and check_gen != getattr(self, '_iptv_check_gen', 0):
            return
        if getattr(self, '_iptv_failed', False) or getattr(self, '_playing_youtube', False):
            return
        if not self.player:
            return
        try:
            state = self.player.get_state()
        except Exception:
            return
        stats = self._iptv_media_stats()
        bytes_now = iptv_bytes_progress(stats)
        bytes_prev = int(getattr(self, '_iptv_bytes_prev', 0) or 0)
        if self._iptv_has_real_media():
            self._media_started = True
            self._iptv_hide_overlay_if_playing()
        started = bool(getattr(self, '_media_started', False))
        stall = int(getattr(self, '_iptv_rebuffer_stall', 0) or 0)
        state_name = vlc_state_name(state)
        growing = bytes_now > bytes_prev
        if started and state_name == 'Buffering' and not growing:
            stall += 1
        else:
            stall = 0
        self._iptv_rebuffer_stall = stall
        url = getattr(self, '_iptv_source_url', '') or ''
        vod = is_iptv_vod(url)
        was_soft = bool(getattr(self, '_iptv_soft_was_buffering', False))
        bump_now = False
        if started and state_name == 'Buffering' and growing and not vod:
            times = iptv_soft_rebuffer_note(
                getattr(self, '_iptv_soft_times', []),
                time.time(),
                is_new_event=not was_soft,
            )
            self._iptv_soft_times = times
            self._iptv_soft_was_buffering = True
            bump_now = iptv_soft_rebuffer_should_bump(
                len(times),
                getattr(self, '_iptv_soft_bumped', False),
            )
        else:
            self._iptv_soft_was_buffering = False
        action = iptv_rebuffer_decision(
            started=started,
            state=state,
            stall_ticks=stall,
            bytes_now=bytes_now,
            bytes_prev=bytes_prev,
            reconnects=int(getattr(self, '_iptv_reconnects', 0) or 0),
            vod=vod,
        )
        self._iptv_bytes_prev = max(bytes_prev, bytes_now)
        if action == 'reconnect':
            name = getattr(self, '_iptv_retry_name', '') or ''
            kind = getattr(self, '_iptv_kind', 'mpegts')
            print('[IPTV] Buffer vacío; reconecto el mismo enlace')
            self._iptv_show_overlay('reconnect')
            self._iptv_reconnects = int(getattr(self, '_iptv_reconnects', 0) or 0) + 1
            self._iptv_rebuffer_stall = 0
            self._iptv_bytes_prev = 0
            self._start_vlc_remote(name, url, kind)
        elif action == 'fail':
            name = getattr(self, '_iptv_retry_name', '') or ''
            self._iptv_report_unavailable(name)
            return
        elif bump_now:
            name = getattr(self, '_iptv_retry_name', '') or ''
            kind = getattr(self, '_iptv_kind', 'mpegts')
            self._iptv_soft_bumped = True
            self._iptv_cache_extra_ms = SOFT_REBUFFER_EXTRA_MS
            cache = iptv_cache_ms(
                kind,
                vod=vod or kind == 'container',
                profile=app_config.get_iptv_buffer(),
                extra_ms=self._iptv_cache_extra(),
            )
            print(f'[IPTV] buffer corto en alta calidad; subo caché a {cache}ms')
            self._iptv_show_overlay('buffer_bump')
            self._iptv_rebuffer_stall = 0
            self._iptv_bytes_prev = 0
            self._start_vlc_remote(name, url, kind)
        elif action == 'wait' and started and state_name == 'Buffering':
            self._iptv_show_overlay('buffering')
        if self._widget_exists(getattr(self, 'window', None)):
            self.window.after(2000, lambda: self._check_iptv_stream(check_gen))

    def _stop_iptv_relay(self):
        """Uso interno: stop IPTV relay."""
        server = getattr(self, '_iptv_relay_server', None)
        self._iptv_relay_server = None
        if server:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
        for proc in getattr(self, '_iptv_relay_procs', []) or []:
            try:
                proc.terminate()
            except Exception:
                pass
        for proc in getattr(self, '_iptv_relay_procs', []) or []:
            try:
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._iptv_relay_procs = []
        tmpdir = getattr(self, '_iptv_relay_tmpdir', None)
        self._iptv_relay_tmpdir = None
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _ffmpeg_pull_cmd(self, ffmpeg, source, ts_path):
        """Uso interno: ffmpeg pull cmd."""
        return [
            ffmpeg, '-hide_banner', '-loglevel', 'error',
            '-user_agent', IPTV_USER_AGENT,
            '-reconnect', '1', '-reconnect_streamed', '1',
            '-reconnect_delay_max', '5',
            '-i', source,
            '-c', 'copy', '-f', 'mpegts', ts_path,
        ]

    def _start_iptv_ffmpeg_relay(self, name, url):
        """Uso interno: start IPTV ffmpeg relay."""
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            print("[IPTV] ffmpeg no está instalado")
            print(f"[IPTV] No se pudo abrir el canal '{name}'")
            set_status = getattr(self, 'set_player_status', None)
            if callable(set_status):
                set_status('Sin ffmpeg · no se puede retransmitir el canal', timeout_ms=12000)
            return
        self._stop_iptv_relay()
        tmpdir = tempfile.mkdtemp(prefix='kidneys_iptv_')
        ts_path = os.path.join(tmpdir, 'stream.ts')
        self._iptv_relay_tmpdir = tmpdir
        check_gen = getattr(self, '_iptv_check_gen', 0) + 1
        self._iptv_check_gen = check_gen

        server = ThreadingHTTPServer(('127.0.0.1', 0), _GrowingTSHandler)
        server.ts_path = ts_path
        server.yt_procs = []
        self._iptv_relay_server = server
        threading.Thread(target=server.serve_forever, daemon=True).start()
        local_url = f'http://127.0.0.1:{server.server_address[1]}/stream.ts'

        def producer():
            """Producer."""
            try:
                sources = iptv_upstream_candidates(url)
            except Exception as err:
                print(f"[IPTV] No se pudieron preparar orígenes ({err})")
                sources = [url]
            if getattr(self, '_iptv_check_gen', 0) != check_gen:
                return
            print(f"[IPTV] Retransmitiendo por 127.0.0.1 ({len(sources)} origen(es))")
            for index, source in enumerate(sources, start=1):
                if getattr(self, '_iptv_check_gen', 0) != check_gen:
                    return
                try:
                    if os.path.exists(ts_path):
                        os.remove(ts_path)
                except OSError:
                    pass
                cmd = self._ffmpeg_pull_cmd(ffmpeg, source, ts_path)
                try:
                    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
                except Exception as exc:
                    print(f"[IPTV] ffmpeg no arrancó ({exc})")
                    continue
                self._iptv_relay_procs = [proc]
                if self._iptv_relay_server:
                    self._iptv_relay_server.yt_procs = self._iptv_relay_procs
                deadline = time.time() + 12
                got_data = False
                while time.time() < deadline:
                    if getattr(self, '_iptv_check_gen', 0) != check_gen:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        return
                    try:
                        if os.path.exists(ts_path) and os.path.getsize(ts_path) >= 32 * 1024:
                            got_data = True
                            break
                    except OSError:
                        pass
                    if proc.poll() is not None:
                        break
                    time.sleep(0.2)
                if got_data:
                    err = None
                    try:
                        err = proc.communicate()[1]
                    except Exception:
                        pass
                    if err:
                        text = err.decode('utf-8', errors='replace')[-400:]
                        if text.strip():
                            print(f"[IPTV ffmpeg] {self._sanitize_iptv_log(text)}")
                    return
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                err = b''
                try:
                    err = proc.stderr.read() if proc.stderr else b''
                except Exception:
                    pass
                if err:
                    print(f"[IPTV] origen {index}/{len(sources)} sin datos: {self._sanitize_iptv_log(err.decode('utf-8', errors='replace')[-200:])}")
                else:
                    print(f"[IPTV] origen {index}/{len(sources)} sin datos")
            if self._widget_exists(self.window):
                self.window.after(0, lambda: self._iptv_report_unavailable(name))

        def wait_and_play():
            """Wait and play."""
            deadline = time.time() + 45
            while time.time() < deadline:
                if getattr(self, '_iptv_check_gen', 0) != check_gen:
                    return
                try:
                    if os.path.exists(ts_path) and os.path.getsize(ts_path) >= 32 * 1024:
                        break
                except OSError:
                    pass
                time.sleep(0.2)
            else:
                return
            if not self._widget_exists(self.window):
                return
            self.window.after(0, lambda: self._start_vlc_local_ts(name, local_url))

        threading.Thread(target=producer, daemon=True).start()
        threading.Thread(target=wait_and_play, daemon=True).start()
