import yt_dlp
import json
import re
import webbrowser
import urllib.request
import urllib.error
import os
import shutil
import sys
import subprocess
import tempfile
import threading
import time
import atexit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog, ttk
import app_config


YT_TEMP_PREFIX = 'kidneys_yt_'


def cleanup_youtube_temp_dirs(keep=None):
    """Borra las copias temporales de reproducción para que no se amontonen."""
    temp_root = tempfile.gettempdir()
    keep_path = os.path.abspath(keep) if keep else None
    try:
        for name in os.listdir(temp_root):
            if not name.startswith(YT_TEMP_PREFIX):
                continue
            path = os.path.join(temp_root, name)
            if keep_path and os.path.abspath(path) == keep_path:
                continue
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


atexit.register(cleanup_youtube_temp_dirs)


def detect_js_runtimes():
    """Runtimes JS que yt-dlp puede usar para los retos de YouTube."""
    runtimes = {}
    for name, binary in (
        ('deno', 'deno'),
        ('node', 'node'),
        ('bun', 'bun'),
        ('quickjs', 'qjs'),
    ):
        path = shutil.which(binary)
        if path:
            runtimes[name] = {'path': path}
    if 'quickjs' not in runtimes:
        path = shutil.which('quickjs')
        if path:
            runtimes['quickjs'] = {'path': path}
    return runtimes


def _merge_extractor_args(base, extra):
    merged = {}
    for source in (base, extra):
        if not source:
            continue
        for key, value in source.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def youtube_ydl_opts(**extra):
    """Opciones comunes de yt-dlp: runtime JS + cookies de navegador/archivo."""
    extra_extractor = extra.pop('extractor_args', None)
    silent = extra.pop('silent', False)
    opts = {
        'quiet': True,
        'no_warnings': False,
        'nocheckcertificate': True,
        'noplaylist': True,
        'geo_bypass_country': 'ES',
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) '
                'Gecko/20100101 Firefox/125.0'
            ),
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        },
        'remote_components': {'ejs:github'},
    }
    runtimes = detect_js_runtimes()
    if runtimes:
        opts['js_runtimes'] = runtimes
        if not silent:
            print("[yt-dlp] Runtimes JS: " + ", ".join(f"{n}={info.get('path')}" for n, info in runtimes.items()))
    elif not silent:
        print("[yt-dlp] No se encontró Deno ni Node. YouTube puede bloquear la extracción.")

    cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
    browser = extra.pop('cookie_browser', None)
    use_cookiefile = extra.pop('use_cookiefile', True)
    if browser:
        opts['cookiesfrombrowser'] = (browser,)
    elif use_cookiefile and os.path.exists(cookies_path):
        opts['cookiefile'] = cookies_path

    opts.update(extra)
    opts['extractor_args'] = _merge_extractor_args(
        {'youtube': {'lang': ['es']}},
        extra_extractor,
    )
    return opts


_YT_LANG_NAMES = {
    'es': 'Español',
    'es-ES': 'Español (España)',
    'es-419': 'Español (Latinoamérica)',
    'en': 'English',
    'en-US': 'English (US)',
    'en-GB': 'English (UK)',
    'fr': 'Français',
    'de': 'Deutsch',
    'it': 'Italiano',
    'pt': 'Português',
    'pt-BR': 'Português (Brasil)',
    'ca': 'Català',
    'eu': 'Euskara',
    'gl': 'Galego',
    'ja': '日本語',
    'ko': '한국어',
    'zh': '中文',
    'zh-Hans': '中文 (简体)',
    'ar': 'العربية',
    'ru': 'Русский',
}


def _subtitle_file_url(entries):
    """Elige una URL de subtítulo que VLC pueda abrir (vtt/srt), sin relanzar yt-dlp."""
    if not entries:
        return None, None
    by_ext = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = entry.get('url')
        ext = (entry.get('ext') or '').lower()
        if url and ext:
            by_ext[ext] = url
    for ext in ('vtt', 'srt', 'ttml'):
        if ext in by_ext:
            return by_ext[ext], ext
    return None, None


def collect_youtube_subs(info):
    """Lista subtítulos oficiales y automáticos, priorizando es/en."""
    official = info.get('subtitles') or {}
    automatic = info.get('automatic_captions') or {}

    def pretty(code, auto=False):
        base = _YT_LANG_NAMES.get(code) or _YT_LANG_NAMES.get(str(code).split('-')[0]) or code
        return f'{base} (auto)' if auto else base

    def add(code, entries, kind, auto=False):
        url, ext = _subtitle_file_url(entries)
        if not url:
            return False
        items.append({
            'lang': code,
            'kind': kind,
            'label': pretty(code, auto),
            'url': url,
            'ext': ext or 'vtt',
        })
        return True

    items = []
    seen = set()
    for code in ('es', 'es-ES', 'es-419', 'en', 'en-US', 'en-GB'):
        if code not in seen and add(code, official.get(code), 'official'):
            seen.add(code)
    for code, entries in official.items():
        if code in seen or code == 'live_chat':
            continue
        if add(code, entries, 'official'):
            seen.add(code)
        if len(items) >= 14:
            break
    bases = {str(item['lang']).split('-')[0] for item in items}
    for code in ('es', 'es-ES', 'es-419', 'en', 'en-US'):
        if code in seen or str(code).split('-')[0] in bases:
            continue
        if add(code, automatic.get(code), 'auto', auto=True):
            seen.add(code)
            bases.add(str(code).split('-')[0])
    return items


def preferred_youtube_browser():
    """Elige un navegador que tenga cookies de YouTube, si es posible."""
    try:
        import browser_cookie3
    except ImportError:
        return 'firefox'
    loaders = (
        ('firefox', getattr(browser_cookie3, 'firefox', None)),
        ('chrome', getattr(browser_cookie3, 'chrome', None)),
        ('chromium', getattr(browser_cookie3, 'chromium', None)),
        ('brave', getattr(browser_cookie3, 'brave', None)),
        ('edge', getattr(browser_cookie3, 'edge', None)),
    )
    for name, loader in loaders:
        if not loader:
            continue
        try:
            cookies = loader(domain_name='youtube.com')
            if cookies and any(True for _ in cookies):
                return name
        except Exception:
            continue
    return 'firefox'
 
class _GrowingTSHandler(BaseHTTPRequestHandler):
    """Sirve un MPEG-TS que ffmpeg sigue escribiendo."""

    def log_message(self, format, *args):
        return

    def _range_start(self):
        header = self.headers.get('Range') or ''
        match = re.match(r'bytes=(\d+)-', header)
        return int(match.group(1)) if match else 0

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Type', 'video/MP2T')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()

    def do_GET(self):
        path = self.server.ts_path
        pos = self._range_start()
        if pos > 0:
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {pos}-/*')
        else:
            self.send_response(200)
        self.send_header('Content-Type', 'video/MP2T')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        idle = 0.0
        try:
            while idle < 45:
                try:
                    size = os.path.getsize(path) if os.path.exists(path) else 0
                except OSError:
                    size = 0
                if size > pos:
                    with open(path, 'rb') as fh:
                        fh.seek(pos)
                        data = fh.read(size - pos)
                    if data:
                        self.wfile.write(data)
                        pos += len(data)
                        idle = 0.0
                        continue
                procs = getattr(self.server, 'yt_procs', [])
                finished = procs and all(p.poll() is not None for p in procs)
                if finished and size <= pos:
                    break
                time.sleep(0.05)
                idle += 0.05
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


class YouTubeHandler:
    def __init__(self, video_player):
        self.video_player = video_player
        self._yt_procs = []
        self._yt_tmpdir = None
        self._yt_server = None
        self._current_url = ''
        self._play_kwargs = {}
        self._sub_429_until = 0
        self._direct_url = ''
        self._direct_headers = {}
        self._play_gen = 0
        self._loading_frame = None
        self._loading_bar = None
        self._loading_title_label = None
        self._loading_status_label = None
        self._loading_thumb_label = None
        self._loading_title_text = ''
        self._loading_video_id = None
        self._thumb_photos = {}
        cleanup_youtube_temp_dirs()

    def stop_pipeline(self):
        server = self._yt_server
        self._yt_server = None
        if server:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
        for proc in self._yt_procs:
            try:
                proc.terminate()
            except Exception:
                pass
        for proc in self._yt_procs:
            try:
                proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._yt_procs = []
        current = self._yt_tmpdir
        self._yt_tmpdir = None
        if current and os.path.isdir(current):
            shutil.rmtree(current, ignore_errors=True)
        cleanup_youtube_temp_dirs()
        
    def prompt_youtube_url(self, url=None):
        if url is None:
            url = simpledialog.askstring("Cargar YouTube", "Introduce la URL del video de YouTube:")
        if url:
            self.play_youtube_url(url)

    def play_youtube_url(self, url, force_pulse=False, show_progress=False, is_sequential=False, title=None):
        """Reproduce un vídeo de YouTube dentro del reproductor integrado."""
        save_resume = getattr(self.video_player, 'save_youtube_resume', None)
        if save_resume:
            save_resume()
        video_id = self.extract_youtube_id(url)
        if not video_id:
            messagebox.showerror("Error", "No se pudo extraer el ID del vídeo de YouTube")
            return
        self.video_player._playing_youtube = True

        gen = self._new_play_gen()
        self._current_url = url
        self._play_kwargs = {
            'force_pulse': force_pulse,
            'show_progress': show_progress,
            'is_sequential': is_sequential,
        }
        resume_s = app_config.youtube_resume_seconds(video_id)
        if resume_s:
            status = f"Reanudando en {self._resume_clock(resume_s)}…"
        else:
            status = "Obteniendo vídeo de YouTube…"
        self._show_loading(
            status,
            video_id=video_id,
            title=title,
        )
        self.stop_pipeline()
        self.video_player.clear_youtube_subtitles()

        def work():
            err = None
            stream = None
            try:
                try:
                    self.export_cookies_from_browser(silent=True)
                except Exception as exc:
                    print(f"[YouTubeHandler] No se pudieron exportar cookies: {exc}")
                stream = self.get_best_vlc_url(url)
            except Exception as exc:
                err = exc

            def cont():
                if gen != self._play_gen:
                    return
                if err:
                    messagebox.showerror("Error", f"Error al procesar el vídeo: {err}")
                    self.open_in_browser(url)
                    return
                self._begin_playback(url, stream, force_pulse, show_progress, is_sequential)

            self._ui_after(cont)

        threading.Thread(target=work, daemon=True).start()

    def _begin_playback(self, url, stream, force_pulse, show_progress, is_sequential):
        subs = (stream or {}).get('subtitles') or []
        video_id = self.extract_youtube_id(url)
        resume_s = app_config.youtube_resume_seconds(
            video_id,
            (stream or {}).get('duration'),
        )
        if stream:
            self._direct_url = stream.get('url') or ''
            self._direct_headers = stream.get('headers') or {}
            if stream.get('title'):
                self._set_loading_title(stream['title'])
                self._sync_sidebar_title(url, stream['title'])
        if resume_s:
            self._set_loading_status(f"Reanudando en {self._resume_clock(resume_s)}…")
        if stream and self._stream_ok_for_vlc(stream):
            print(f"[YouTubeHandler] Reproduciendo en el reproductor: {stream['url'][:80]}…")
            if not resume_s:
                self._set_loading_status("Abriendo el vídeo…")

            def fallback():
                print("[YouTubeHandler] VLC no pudo abrir el stream directo; retransmitiendo la URL ya extraída")
                if not self._play_via_pipe(
                    url, force_pulse, show_progress, is_sequential,
                    duration=stream.get('duration'),
                    source_url=stream.get('url'),
                    http_headers=stream.get('headers'),
                    start_s=resume_s,
                ):
                    self._show_playback_error(url)

            self.video_player.play_video_url(
                stream['url'],
                force_pulse=force_pulse,
                show_progress=show_progress,
                is_sequential=is_sequential,
                http_headers=stream.get('headers'),
                duration_s=stream.get('duration'),
                fail_after_s=20,
                on_fail=fallback,
                start_s=resume_s,
            )
            self.video_player.set_youtube_subtitles(subs)
            return

        if stream:
            print("[YouTubeHandler] Retransmitiendo la URL extraída (sin volver a pedir el vídeo a YouTube)")
        duration = (stream or {}).get('duration')
        if self._play_via_pipe(
            url, force_pulse, show_progress, is_sequential,
            duration=duration,
            source_url=(stream or {}).get('url'),
            http_headers=(stream or {}).get('headers'),
            start_s=resume_s,
        ):
            self.video_player.set_youtube_subtitles(subs)
            return

        self._show_playback_error(url)

    def _resume_clock(self, seconds):
        formatter = getattr(self.video_player, '_format_clock', None)
        if formatter:
            return formatter(int(float(seconds) * 1000))
        total = max(0, int(float(seconds)))
        minutes, secs = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f'{hours}:{minutes:02d}:{secs:02d}'
        return f'{minutes:02d}:{secs:02d}'

    def _new_play_gen(self):
        self._play_gen = getattr(self, '_play_gen', 0) + 1
        return self._play_gen

    def cancel_pending_play(self):
        self._new_play_gen()
        self.hide_loading()

    def _ui_after(self, fn, delay_ms=0):
        window = getattr(self.video_player, 'window', None)
        if not window:
            return
        try:
            window.after(delay_ms, fn)
        except tk.TclError:
            pass

    def _clear_video_surface(self):
        frame = getattr(self.video_player, 'video_frame', None)
        if not frame:
            return
        try:
            for widget in frame.winfo_children():
                widget.destroy()
        except tk.TclError:
            pass

    def _loading_alive(self):
        frame = getattr(self, '_loading_frame', None)
        try:
            return bool(frame and frame.winfo_exists())
        except tk.TclError:
            return False

    def hide_loading(self):
        bar = getattr(self, '_loading_bar', None)
        if bar:
            try:
                bar.stop()
            except tk.TclError:
                pass
        self._loading_bar = None
        frame = getattr(self, '_loading_frame', None)
        self._loading_frame = None
        self._loading_title_label = None
        self._loading_status_label = None
        self._loading_thumb_label = None
        if frame:
            try:
                frame.destroy()
            except tk.TclError:
                pass

    def _show_status(self, text):
        if self._loading_alive():
            self._set_loading_status(text)
            return
        self._show_loading(text)

    def _show_loading(self, status, video_id=None, title=None):
        from ui_theme import get_colors, get_font

        video_id = video_id or getattr(self, '_loading_video_id', None)
        old_id = getattr(self, '_loading_video_id', None)
        if title:
            self._loading_title_text = title
        elif video_id != old_id:
            self._loading_title_text = 'YouTube'
        if self._loading_alive() and video_id == old_id:
            self._set_loading_status(status)
            if title:
                self._set_loading_title(title)
            return
        self._loading_video_id = video_id

        player = self.video_player
        parent = getattr(player, 'player_frame', None) or getattr(player, 'video_frame', None)
        video_frame = getattr(player, 'video_frame', None)
        if not parent or not video_frame:
            return

        self.hide_loading()
        colors = get_colors()
        overlay = tk.Frame(parent, bg='#000000', highlightthickness=0)
        place_opts = {'relx': 0, 'rely': 0, 'relwidth': 1, 'relheight': 1}
        try:
            overlay.place(in_=video_frame, **place_opts)
            overlay.lift(video_frame)
        except tk.TclError:
            overlay.place(**place_opts)
        self._loading_frame = overlay

        card = tk.Frame(
            overlay,
            bg=colors['surface'],
            highlightbackground=colors['border'],
            highlightthickness=1,
            padx=22,
            pady=18,
        )
        card.place(relx=0.5, rely=0.5, anchor='center')

        thumb_wrap = tk.Frame(card, bg=colors['surface_alt'], width=440, height=248)
        thumb_wrap.pack()
        thumb_wrap.pack_propagate(False)
        thumb = tk.Label(
            thumb_wrap,
            text='▶',
            font=get_font(28),
            bg=colors['surface_alt'],
            fg=colors['text_muted'],
        )
        thumb.pack(fill=tk.BOTH, expand=True)
        self._loading_thumb_label = thumb
        cached = self._thumb_photos.get(video_id) if video_id else None
        if cached:
            thumb.configure(image=cached, text='')
            thumb.image = cached

        title_label = tk.Label(
            card,
            text=self._loading_title_text or 'YouTube',
            font=get_font(13, 'bold'),
            bg=colors['surface'],
            fg=colors['text'],
            wraplength=420,
            justify='center',
        )
        title_label.pack(pady=(14, 6))
        self._loading_title_label = title_label

        status_label = tk.Label(
            card,
            text=status,
            font=get_font(10),
            bg=colors['surface'],
            fg=colors['text_muted'],
            wraplength=420,
            justify='center',
        )
        status_label.pack(pady=(0, 10))
        self._loading_status_label = status_label

        bar_wrap = ttk.Frame(card)
        bar_wrap.pack(fill=tk.X)
        bar = ttk.Progressbar(bar_wrap, mode='indeterminate', length=280)
        bar.pack()
        bar.start(12)
        self._loading_bar = bar

        gen = self._play_gen
        have_title = bool(title) or (
            bool(self._loading_title_text) and self._loading_title_text != 'YouTube'
        )
        if video_id:
            threading.Thread(
                target=self._load_loading_meta,
                args=(gen, video_id, have_title),
                daemon=True,
            ).start()
        try:
            player.window.update_idletasks()
        except tk.TclError:
            pass

    def _set_loading_status(self, text):
        label = getattr(self, '_loading_status_label', None)
        try:
            if label and label.winfo_exists():
                label.configure(text=text)
        except tk.TclError:
            pass

    def _set_loading_title(self, title):
        title = (title or '').strip()
        if not title or title == 'YouTube':
            return
        self._loading_title_text = title
        label = getattr(self, '_loading_title_label', None)
        try:
            if label and label.winfo_exists():
                label.configure(text=title)
        except tk.TclError:
            pass

    def _load_loading_meta(self, gen, video_id, have_title):
        title = None if have_title else self._oembed_title(video_id)
        data = None
        if video_id not in getattr(self, '_thumb_photos', {}):
            data = self._download_thumb_bytes(video_id)

        def apply():
            if gen != self._play_gen:
                return
            if title:
                self._set_loading_title(title)
                self._sync_sidebar_title(self._current_url, title)
            if data:
                self._apply_thumb_bytes(video_id, data)

        self._ui_after(apply)

    def _oembed_title(self, video_id):
        url = (
            'https://www.youtube.com/oembed?format=json'
            f'&url=https://www.youtube.com/watch?v={video_id}'
        )
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) '
                    'Gecko/20100101 Firefox/125.0'
                ),
            })
            with urllib.request.urlopen(req, timeout=6) as resp:
                info = json.loads(resp.read().decode('utf-8', errors='replace'))
            return (info.get('title') or '').strip() or None
        except Exception:
            return None

    def _download_thumb_bytes(self, video_id):
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) '
                'Gecko/20100101 Firefox/125.0'
            ),
        }
        for name in ('hqdefault.jpg', 'mqdefault.jpg', 'default.jpg'):
            url = f'https://i.ytimg.com/vi/{video_id}/{name}'
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = resp.read()
                if data:
                    return data
            except Exception:
                continue
        return None

    def _apply_thumb_bytes(self, video_id, data):
        try:
            from PIL import Image, ImageTk
        except Exception:
            return
        try:
            img = Image.open(BytesIO(data)).convert('RGB')
        except Exception:
            return
        width, height = img.size
        target_h = int(width * 9 / 16)
        if height > target_h + 8:
            top = (height - target_h) // 2
            img = img.crop((0, top, width, top + target_h))
        img = img.resize((440, 248), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        self._thumb_photos[video_id] = photo
        label = getattr(self, '_loading_thumb_label', None)
        try:
            if label and label.winfo_exists():
                label.configure(image=photo, text='')
                label.image = photo
        except tk.TclError:
            pass

    def _sync_sidebar_title(self, url, title):
        title = (title or '').strip()
        if not title or not url or title in ('YouTube', url):
            return
        player = self.video_player
        updated = False
        for attr in ('all_channels', 'channels'):
            items = getattr(player, attr, None)
            if not items:
                continue
            for i, (name, item_url) in enumerate(items):
                if item_url != url or name == title:
                    continue
                items[i] = (title, url)
                updated = True
                if attr == 'channels':
                    try:
                        box = player.channels_listbox
                        if i < box.size():
                            box.delete(i)
                            box.insert(i, title)
                    except (tk.TclError, AttributeError):
                        pass
        if updated:
            persist = getattr(player, '_persist_sidebar', None)
            if persist:
                persist()
            return
        add = getattr(player, 'add_channel_to_list', None)
        if add and not any(item_url == url for _, item_url in getattr(player, 'all_channels', [])):
            add(title, url)

    def _show_playback_error(self, url):
        from ui_theme import get_colors, get_font
        self.hide_loading()
        self._clear_video_surface()
        colors = get_colors()
        info_frame = tk.Frame(self.video_player.video_frame, bg=colors['bg'])
        info_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            info_frame,
            text="No se pudo reproducir el vídeo",
            font=get_font(16, 'bold'),
            bg=colors['bg'],
            fg=colors['text'],
        ).pack(pady=(50, 10))
        tk.Label(
            info_frame,
            text="YouTube está limitando el acceso (a menudo un 429). Espera un minuto y prueba otra vez, o ábrelo en el navegador.",
            font=get_font(10),
            bg=colors['bg'],
            fg=colors['text_muted'],
            wraplength=520,
            justify='center',
        ).pack(pady=(0, 16))
        tk.Button(
            info_frame,
            text="Abrir en navegador",
            font=get_font(10),
            command=lambda: self.open_in_browser(url),
            padx=12,
            pady=6,
            bg=colors['surface_alt'],
            fg=colors['text'],
            activebackground=colors['border'],
            activeforeground=colors['text'],
            relief=tk.FLAT,
        ).pack(pady=10)

    def _ffmpeg_header_block(self, headers):
        parts = []
        for key, value in (headers or {}).items():
            if value:
                parts.append(f'{key}: {value}')
        return ('\r\n'.join(parts) + '\r\n') if parts else ''

    def _stream_ok_for_vlc(self, stream):
        """Si hay URL, VLC la prueba. Los filtros antiguos mandaban todo al relevo y YouTube lo cortaba."""
        return bool((stream or {}).get('url'))

    def replay_from(self, start_s):
        """Reinicia la retransmisión local desde un instante (el MPEG-TS no admite seek)."""
        url = self._current_url
        if not url:
            return False
        kwargs = dict(self._play_kwargs)
        duration = None
        try:
            known = int(getattr(self.video_player, '_known_duration_ms', 0) or 0)
            if known > 0:
                duration = known / 1000.0
        except (TypeError, ValueError):
            duration = None
        if float(start_s or 0) < 0.5 and int(getattr(self.video_player, '_yt_start_offset_ms', 0) or 0) < 500:
            return False
        self.video_player._yt_via_pipe = True
        return self._play_via_pipe(
            url,
            kwargs.get('force_pulse', True),
            kwargs.get('show_progress', True),
            kwargs.get('is_sequential', False),
            duration=duration,
            start_s=max(0.0, float(start_s or 0)),
            source_url=self._direct_url,
            http_headers=self._direct_headers,
        )

    def _play_via_pipe(self, youtube_url, force_pulse, show_progress, is_sequential, duration=None, start_s=0, source_url=None, http_headers=None):
        """Retransmite a MPEG-TS. Prefiere la URL ya extraída para no volver a golpear YouTube."""
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            return self._play_via_download(youtube_url, force_pulse, show_progress, is_sequential, duration=duration)

        self._current_url = youtube_url
        self._play_kwargs = {
            'force_pulse': force_pulse,
            'show_progress': show_progress,
            'is_sequential': is_sequential,
        }
        self.stop_pipeline()
        self._show_status("Preparando vídeo…" if start_s < 0.5 else "Saltando al punto elegido…")
        tmpdir = tempfile.mkdtemp(prefix='kidneys_yt_')
        ts_path = os.path.join(tmpdir, 'stream.ts')
        self._yt_tmpdir = tmpdir
        source_url = source_url or self._direct_url
        http_headers = http_headers or self._direct_headers

        def producer():
            try:
                if source_url:
                    ffmpeg_cmd = [
                        ffmpeg, '-hide_banner', '-loglevel', 'error',
                        '-fflags', '+genpts+discardcorrupt',
                    ]
                    header_block = self._ffmpeg_header_block(http_headers)
                    if header_block:
                        ffmpeg_cmd.extend(['-headers', header_block])
                    try:
                        start_at = float(start_s or 0)
                    except (TypeError, ValueError):
                        start_at = 0
                    if start_at >= 0.5:
                        ffmpeg_cmd.extend(['-ss', f'{start_at:.1f}'])
                    ffmpeg_cmd.extend([
                        '-i', source_url,
                        '-c', 'copy', '-bsf:v', 'h264_mp4toannexb',
                        '-f', 'mpegts', ts_path,
                    ])
                    ffproc = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.PIPE)
                    self._yt_procs = [ffproc]
                    if self._yt_server:
                        self._yt_server.yt_procs = self._yt_procs
                    ff_err = ffproc.communicate()[1]
                else:
                    ytdlp_cmd = self._ytdlp_argv(youtube_url, start_s=start_s)
                    ffmpeg_cmd = [
                        ffmpeg, '-hide_banner', '-loglevel', 'error',
                        '-fflags', '+genpts+discardcorrupt',
                        '-i', 'pipe:0',
                        '-c', 'copy', '-bsf:v', 'h264_mp4toannexb',
                        '-f', 'mpegts', ts_path,
                    ]
                    ytdlp = subprocess.Popen(ytdlp_cmd, stdout=subprocess.PIPE)
                    ffproc = subprocess.Popen(
                        ffmpeg_cmd, stdin=ytdlp.stdout, stderr=subprocess.PIPE
                    )
                    ytdlp.stdout.close()
                    self._yt_procs = [ytdlp, ffproc]
                    if self._yt_server:
                        self._yt_server.yt_procs = self._yt_procs
                    ff_err = ffproc.communicate()[1]
                    ytdlp.wait()
                if ffproc.returncode not in (0, -15, None) and ff_err:
                    print(f"[ffmpeg] {ff_err.decode('utf-8', errors='replace')[-1500:]}")
            except Exception as exc:
                print(f"[YouTubeHandler] Error en la retransmisión: {exc}")

        server = ThreadingHTTPServer(('127.0.0.1', 0), _GrowingTSHandler)
        server.ts_path = ts_path
        server.yt_procs = []
        self._yt_server = server
        threading.Thread(target=server.serve_forever, daemon=True).start()
        stream_url = f'http://127.0.0.1:{server.server_address[1]}/stream.ts'
        threading.Thread(target=producer, daemon=True).start()

        def wait_and_play():
            min_bytes = 256 * 1024
            deadline = time.time() + 75
            while time.time() < deadline:
                try:
                    if os.path.exists(ts_path) and os.path.getsize(ts_path) >= min_bytes:
                        break
                except OSError:
                    pass
                dead = self._yt_procs and all(p.poll() is not None for p in self._yt_procs)
                if dead:
                    self.video_player.window.after(
                        0, lambda: self._show_playback_error(youtube_url)
                    )
                    return
                time.sleep(0.2)
            else:
                print("[YouTubeHandler] ffmpeg no generó datos a tiempo; descargando el archivo")
                self.video_player.window.after(0, lambda: self._play_via_download(
                    youtube_url, force_pulse, show_progress, is_sequential, duration=duration
                ))
                return

            def start_player():
                size = os.path.getsize(ts_path)
                print(f"[YouTubeHandler] Reproduciendo stream local ({size} bytes) {stream_url}")
                self._clear_video_surface()
                self.video_player._yt_via_pipe = True
                self.video_player._yt_start_offset_ms = int(max(0.0, float(start_s or 0)) * 1000)
                self.video_player.play_video_url(
                    stream_url,
                    force_pulse=force_pulse,
                    show_progress=show_progress,
                    is_sequential=is_sequential,
                    local_file=True,
                    fail_after_s=25,
                    duration_s=duration,
                    on_fail=lambda: self._show_playback_error(youtube_url),
                )

            self.video_player.window.after(0, start_player)

        threading.Thread(target=wait_and_play, daemon=True).start()
        print(f"[YouTubeHandler] Retransmitiendo a {ts_path}")
        return True

    def _play_via_download(self, youtube_url, force_pulse, show_progress, is_sequential, duration=None):
        """Si no hay ffmpeg, descarga a un temporal y luego reproduce en VLC."""
        self.stop_pipeline()
        self._show_status("Descargando vídeo para reproducirlo…")
        tmpdir = tempfile.mkdtemp(prefix='kidneys_yt_')
        self._yt_tmpdir = tmpdir
        outtmpl = os.path.join(tmpdir, 'video.%(ext)s')

        def work():
            try:
                opts = youtube_ydl_opts(
                    outtmpl=outtmpl,
                    format='best[ext=mp4][acodec!=none][vcodec!=none]/best',
                    quiet=True,
                )
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)
                    path = ydl.prepare_filename(info)
                if not path or not os.path.exists(path):
                    raise FileNotFoundError('No se descargó el archivo')
                self.video_player.window.after(
                    0,
                    lambda: self.video_player.play_video_url(
                        path,
                        force_pulse=force_pulse,
                        show_progress=show_progress,
                        is_sequential=is_sequential,
                        duration_s=duration or info.get('duration'),
                    ),
                )
            except Exception as exc:
                print(f"[YouTubeHandler] Descarga para reproducción fallida: {exc}")
                self.video_player.window.after(0, lambda: self._show_playback_error(youtube_url))

        threading.Thread(target=work, daemon=True).start()
        return True

    def _ytdlp_argv(self, youtube_url, start_s=0):
        cmd = [
            sys.executable, '-m', 'yt_dlp', youtube_url,
            '-o', '-',
            '-f', 'best[ext=mp4][acodec!=none][vcodec!=none]/best[acodec!=none][vcodec!=none]/best',
            '--no-playlist', '--newline',
            '--sleep-interval', '0',
            '--max-sleep-interval', '0',
            '--sleep-requests', '0',
            '--extractor-args', 'youtube:lang=es',
            '--geo-bypass-country', 'ES',
            '--remote-components', 'ejs:github',
        ]
        try:
            start_s = float(start_s or 0)
        except (TypeError, ValueError):
            start_s = 0
        if start_s >= 0.5:
            cmd.extend(['--download-sections', f'*{start_s:.1f}-inf'])
        cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if os.path.exists(cookies_path):
            cmd.extend(['--cookies', cookies_path])
        else:
            browser = preferred_youtube_browser()
            if browser:
                cmd.extend(['--cookies-from-browser', browser])
        runtimes = detect_js_runtimes()
        for name in ('node', 'deno', 'bun', 'quickjs'):
            if name in runtimes and runtimes[name].get('path'):
                cmd.extend(['--js-runtimes', f"{name}:{runtimes[name]['path']}"])
        return cmd

    def extract_youtube_id(self, url):
        """Extrae el ID del video de YouTube de la URL"""
        if match := re.search(r'(?:v=|/v/|/shorts/|youtu\.be/)([^"&?/\s]{11})', url):
            return match.group(1)
        return None

    def load_playlist(self, playlist_url):
        """Carga todos los vídeos de una playlist de YouTube."""
        try:
            # Exportar cookies automáticamente antes de cargar la playlist
            self.export_cookies_from_browser()
            ydl_opts = youtube_ydl_opts(
                extract_flat=True,
                skip_download=True,
                force_generic_extractor=False,
                noplaylist=False,
            )
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                videos = info.get('entries', [])
                if not videos:
                    messagebox.showinfo("Info", "No se encontraron vídeos en la playlist.")
                    return None
                channels = []
                for video in videos:
                    title = video.get('title', 'Sin título')
                    video_url = f"https://www.youtube.com/watch?v={video.get('id')}"
                    channels.append((title, video_url))
                return channels
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo obtener la playlist: {e}")
            return None
           
    def download_youtube_video(self, url=None):
        """Permite al usuario descargar un vídeo de YouTube."""
        if url is None:
            url = simpledialog.askstring("Descargar vídeo de YouTube", "Introduce la URL del video de YouTube:")
        
        if not url:
            return
            
        try:
            # Primero obtenemos información del vídeo para mostrar el título
            with yt_dlp.YoutubeDL(youtube_ydl_opts(skip_download=True)) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get('title', 'video')
                
            # Limpiamos el título para usarlo como nombre de archivo
            safe_title = re.sub(r'[\\/*?:"<>|]', "", video_title)
            
            # Pedimos al usuario dónde guardar el archivo
            filepath = filedialog.asksaveasfilename(
                title="Guardar vídeo",
                initialfile=safe_title,
                filetypes=[("Archivos MP4", "*.mp4"), ("Todos los archivos", "*.*")]
            )
            
            if not filepath:
                return  # Usuario canceló
                
            # Aseguramos que el archivo tenga extensión .mp4
            if not filepath.lower().endswith('.mp4'):
                filepath += '.mp4'
                
            # Iniciamos la descarga en un hilo separado
            download_thread = threading.Thread(
                target=self._execute_download, 
                args=(url, filepath, video_title)
            )
            download_thread.daemon = True  # El hilo terminará cuando el programa principal termine
            download_thread.start()
            
            messagebox.showinfo("Descarga iniciada", 
                               f"Iniciando descarga de '{video_title}'.\nSe te notificará cuando termine.")
                
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar la descarga: {str(e)}")
            
    def _execute_download(self, url, filepath, title):
        """Ejecuta la descarga del vídeo de YouTube."""
        try:
            ydl_opts = youtube_ydl_opts(
                format='best',
                outtmpl=filepath,
                quiet=False,
                noprogress=False,
            )
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            # Notificar al usuario en el hilo principal
            self.video_player.window.after(0, lambda: messagebox.showinfo(
                "Descarga completada", 
                f"'{title}' descargado en:\n{filepath}"
            ))
            
        except Exception as e:
            # Capturar el error y mostrarlo
            error_message = str(e)
            self.video_player.window.after(0, lambda msg=error_message: messagebox.showerror(
                "Error de descarga", 
                f"No se pudo descargar '{title}':\n{msg}\n\nPosibles soluciones:\n"
                f"1. Verifica que el enlace sea accesible\n"
                f"2. Prueba con otro vídeo\n"
                f"3. Comprueba tu conexión a internet"
            ))
            
            # Intentar eliminar archivo parcial si existe
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass  # No hacer nada si no se puede borrar


    def _sub_cache_dir(self):
        player = self.video_player
        current = getattr(player, '_yt_sub_dir', None)
        if current and os.path.isdir(current):
            return current
        tmpdir = tempfile.mkdtemp(prefix='kidneys_yt_sub_')
        player._yt_sub_dir = tmpdir
        return tmpdir

    def _find_sub_file(self, directory, lang=None):
        if not directory or not os.path.isdir(directory):
            return None
        lang = (lang or '').lower()
        matches = []
        others = []
        for name in os.listdir(directory):
            lower = name.lower()
            if not lower.endswith(('.vtt', '.srt')):
                continue
            full = os.path.join(directory, name)
            if lang and lang in lower:
                matches.append(full)
            else:
                others.append(full)
        if matches:
            return sorted(matches)[0]
        if len(others) == 1:
            return others[0]
        return None

    def _write_subs_from_info(self, ydl, info, items):
        """Guarda el VTT español (o el primero) con la misma sesión de extract_info."""
        if not items:
            return
        preferred = next(
            (item for item in items if str(item.get('lang') or '').split('-')[0] == 'es'),
            items[0],
        )
        tmpdir = self._sub_cache_dir()
        ydl.params['writesubtitles'] = True
        ydl.params['writeautomaticsub'] = True
        ydl.params['subtitleslangs'] = [preferred['lang']]
        ydl.params['subtitlesformat'] = 'vtt'
        ydl.params['ignoreerrors'] = True
        info = dict(info)
        try:
            info['requested_subtitles'] = ydl.process_subtitles(
                info.get('id'),
                info.get('subtitles'),
                info.get('automatic_captions'),
            )
            ydl._write_subtitles(info, os.path.join(tmpdir, 'vid'))
        except Exception as exc:
            print(f"[YouTube] No se pudieron guardar subtítulos en la extracción: {exc}")
            self._sub_429_until = time.time() + 90
            return
        requested = info.get('requested_subtitles') or {}
        for lang, sub_info in requested.items():
            path = sub_info.get('filepath')
            if not path or not os.path.isfile(path):
                continue
            for item in items:
                if item.get('lang') == lang:
                    item['path'] = path
            print(f"[YouTube] Subtítulo listo {lang} → {path}")

    def _dl_sub_url(self, url, lang, ext='vtt'):
        if not url:
            return None
        if time.time() < getattr(self, '_sub_429_until', 0):
            wait = int(self._sub_429_until - time.time())
            print(f"[YouTube] YouTube limita subtítulos; espera {wait}s y prueba otra vez")
            return None
        dest = os.path.join(self._sub_cache_dir(), f'caption_{lang}.{ext or "vtt"}')
        opts = youtube_ydl_opts(silent=True, quiet=True, no_warnings=True, ignoreerrors=True)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.dl(dest, {'url': url, 'http_headers': ydl.params.get('http_headers')}, subtitle=True)
        except Exception as exc:
            text = str(exc)
            if '429' in text:
                self._sub_429_until = time.time() + 90
                print('[YouTube] YouTube ha limitado los subtítulos (429). Espera un minuto.')
            else:
                print(f"[YouTube] Subtítulo no disponible: {exc}")
            return None
        return dest if os.path.isfile(dest) else None

    def fetch_subtitle_file(self, lang, auto=False, url=None, ext='vtt', path=None):
        """Usa el VTT de la primera extracción. No relanza yt-dlp (eso provoca 429)."""
        if path and os.path.isfile(path):
            return path
        found = self._find_sub_file(getattr(self.video_player, '_yt_sub_dir', None), lang)
        if found:
            return found
        return self._dl_sub_url(url, lang, ext)

    def get_best_vlc_url(self, youtube_url):
        """Obtiene una URL de stream que VLC pueda reproducir dentro de la ventana."""
        format_sel = (
            'best[ext=mp4][acodec!=none][vcodec!=none]/'
            'best[acodec!=none][vcodec!=none]/'
            'best'
        )
        attempts = [
            # Sin cookies: permite clientes android/ios, cuyas URLs VLC suele abrir
            youtube_ydl_opts(
                use_cookiefile=False,
                skip_download=True,
                extractor_args={'youtube': {'player_client': ['android', 'ios', 'web']}},
                format=format_sel,
            ),
        ]
        browser = preferred_youtube_browser()
        cookie_clients = {'youtube': {'player_client': ['tv', 'web', 'mweb']}}
        if browser:
            attempts.append(youtube_ydl_opts(
                cookie_browser=browser,
                use_cookiefile=False,
                skip_download=True,
                extractor_args=cookie_clients,
                format=format_sel,
            ))
        attempts.append(youtube_ydl_opts(
            skip_download=True,
            extractor_args=cookie_clients,
            format=format_sel,
        ))

        last_error = None
        for ydl_opts in attempts:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=False)
                    stream = self._pick_playable_stream(info)
                    if stream:
                        stream['headers'] = self._headers_for_vlc(stream.get('headers'))
                        stream['duration'] = info.get('duration')
                        stream['title'] = info.get('title') or ''
                        stream['subtitles'] = collect_youtube_subs(info)
                        self._write_subs_from_info(ydl, info, stream['subtitles'])
                        return stream
            except Exception as e:
                last_error = e
                print(f"Error al obtener la URL compatible para VLC: {e}")
                continue
        if last_error:
            print(f"[yt-dlp] Ningún intento de extracción funcionó: {last_error}")
        return None

    def _headers_for_vlc(self, headers):
        merged = dict(headers or {})
        cookie = merged.get('Cookie') or merged.get('cookie') or self._cookie_header_from_file()
        if cookie:
            merged['Cookie'] = cookie
        merged.setdefault('Referer', 'https://www.youtube.com/')
        merged.setdefault('Origin', 'https://www.youtube.com')
        return merged

    def _cookie_header_from_file(self):
        path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if not os.path.exists(path):
            return None
        parts = []
        try:
            with open(path, encoding='utf-8') as handle:
                for line in handle:
                    if not line.strip() or line.startswith('#'):
                        continue
                    fields = line.rstrip('\n').split('\t')
                    if len(fields) < 7:
                        continue
                    domain, name, value = fields[0], fields[5], fields[6]
                    if 'youtube' in domain or 'google' in domain:
                        parts.append(f'{name}={value}')
        except OSError:
            return None
        return '; '.join(parts) if parts else None

    def _pick_playable_stream(self, info):
        formats = list(info.get('formats') or [])
        headers = dict(info.get('http_headers') or {})

        def protocol_of(fmt):
            return (fmt.get('protocol') or '').lower()

        def is_playable(fmt):
            if not fmt.get('url'):
                return False
            if fmt.get('vcodec', 'none') in ('none', '', None):
                return False
            proto = protocol_of(fmt)
            if 'dash' in proto or proto == 'http_dash_segments':
                return False
            if fmt.get('fragment_base_url') and 'm3u8' not in proto:
                return False
            return True

        def is_progressive(fmt):
            acodec = fmt.get('acodec') or 'none'
            vcodec = fmt.get('vcodec') or 'none'
            return acodec not in ('none', '') and vcodec not in ('none', '')

        def is_hls(fmt):
            proto = protocol_of(fmt)
            url = fmt.get('url') or ''
            return 'm3u8' in proto or '.m3u8' in url

        progressive = [f for f in formats if is_playable(f) and is_progressive(f) and not is_hls(f)]
        hls = [f for f in formats if is_playable(f) and is_hls(f)]
        mp4_prog = [
            f for f in progressive
            if (f.get('ext') == 'mp4' or str(f.get('vcodec', '')).startswith('avc1'))
            and (f.get('height') or 0) <= 720
        ]
        other_prog = [f for f in progressive if f not in mp4_prog]
        candidates = []
        for group, score_base in ((hls, 4000), (mp4_prog, 2000), (other_prog, 1000)):
            for fmt in group:
                url = fmt.get('url') or ''
                score = score_base + (fmt.get('height') or 0)
                # rqh=1 en clientes WEB suele devolver HTTP 403 en VLC
                if 'rqh=1' in url:
                    score -= 5000
                candidates.append((score, fmt))

        usable = [item for item in candidates if item[0] > 0]
        ranked = usable or candidates
        if ranked:
            _, best = max(ranked, key=lambda item: item[0])
            fmt_headers = dict(best.get('http_headers') or headers)
            print(
                f"[yt-dlp] Stream: id={best.get('format_id')} ext={best.get('ext')} "
                f"vcodec={best.get('vcodec')} acodec={best.get('acodec')} "
                f"proto={best.get('protocol')} height={best.get('height')}"
            )
            return {
                'url': best['url'],
                'headers': fmt_headers,
                'ext': best.get('ext'),
                'format_id': best.get('format_id'),
            }

        url = info.get('url')
        if url:
            print("[yt-dlp] Usando URL seleccionada por yt-dlp")
            return {'url': url, 'headers': headers}
        return None

    def open_in_browser(self, url):
        """Abre una URL de YouTube en el navegador predeterminado."""
        try:
            webbrowser.open_new(url)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el navegador: {e}")

    def export_cookies_from_browser(self, output_path=None, silent=False):
        """Exporta automáticamente las cookies de YouTube desde el navegador predeterminado usando browser-cookie3."""
        def _error(message):
            if silent:
                print(f"[YouTubeHandler] {message}")
            else:
                messagebox.showerror("Error", message)

        try:
            import browser_cookie3
            if output_path is None:
                output_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
            # Intenta obtener cookies de los navegadores más comunes
            cookies = None
            try:
                cookies = browser_cookie3.load(domain_name='youtube.com')
            except Exception:
                pass
            if not cookies:
                # Prueba navegadores específicos
                for loader in [browser_cookie3.chrome, browser_cookie3.firefox, browser_cookie3.edge, browser_cookie3.opera]:
                    try:
                        cookies = loader(domain_name='youtube.com')
                        if cookies:
                            break
                    except Exception:
                        continue
            if not cookies:
                raise Exception("No se pudieron extraer cookies de ningún navegador compatible. Asegúrate de tener sesión iniciada en YouTube.")
            # Escribir cookies en formato Netscape
            from http.cookiejar import MozillaCookieJar
            cj = MozillaCookieJar(output_path)
            # Añadir cookies extraídas
            for c in cookies:
                cj.set_cookie(c)
            cj.save(ignore_discard=True, ignore_expires=True)
            return output_path
        except ImportError:
            _error("Falta el módulo browser-cookie3. Instálalo con: pip install browser-cookie3")
            return None
        except Exception as e:
            _error(f"No se pudieron exportar las cookies del navegador: {e}")
            return None