import yt_dlp
import json
import re
import webbrowser
import urllib.request
import urllib.error
import os
import glob
import configparser
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
from tkinter import messagebox, filedialog, ttk
import app_config
from app_paths import data_dir
from ui_clipboard import ask_string
from youtube_subs import (
    collect_youtube_subs,
    ensure_caption_tlang,
    filename_matches_sub_lang,
    prepare_subtitle_for_vlc,
)


YT_TEMP_PREFIX = 'kidneys_yt_'
YT_CACHE_DIRNAME = 'kidneysm3u_yt_cache'
YT_CACHE_MAX_BYTES = 500 * 1024 * 1024
PLAYABLE_VIDEO_EXT = {'.mp4', '.m4v', '.mkv', '.webm', '.avi', '.mov', '.mpeg', '.mpg'}


def youtube_cache_dir():
    path = os.path.join(tempfile.gettempdir(), YT_CACHE_DIRNAME)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def is_playable_local_video(path):
    """True si es un archivo local que VLC puede abrir sin remux a MPEG-TS."""
    if not path or str(path).startswith(('http://', 'https://', 'ftp://')):
        return False
    local = str(path).split('?', 1)[0]
    ext = os.path.splitext(local)[1].lower()
    if ext not in PLAYABLE_VIDEO_EXT:
        return False
    try:
        return os.path.isfile(local) and os.path.getsize(local) > 1024
    except OSError:
        return False


def youtube_format_selector(max_height=None):
    """Selector de yt-dlp: tope de altura, o el mejor stream jugable si max_height <= 0."""
    height = app_config.normalize_youtube_quality(
        app_config.get_youtube_quality() if max_height is None else max_height
    )
    if height <= 0:
        return (
            'best[ext=mp4][acodec!=none][vcodec!=none]/'
            'best[acodec!=none][vcodec!=none]/'
            'best'
        )
    return (
        f'best[height<={height}][ext=mp4][acodec!=none][vcodec!=none]/'
        f'best[height<={height}][acodec!=none][vcodec!=none]/'
        'best[ext=mp4][acodec!=none][vcodec!=none]/'
        'best[acodec!=none][vcodec!=none]/'
        'best'
    )


def find_cached_youtube_video(video_id, quality=None):
    video_id = str(video_id or '').strip()
    if len(video_id) != 11:
        return None
    key = app_config.youtube_quality_cache_key(quality)
    prefix = f'{video_id}_{key}.'
    root = youtube_cache_dir()
    try:
        names = os.listdir(root)
    except OSError:
        return None
    for name in names:
        if not name.startswith(prefix):
            continue
        path = os.path.join(root, name)
        if is_playable_local_video(path):
            try:
                os.utime(path, None)
            except OSError:
                pass
            return path
    return None


def enforce_youtube_cache_limit(max_bytes=YT_CACHE_MAX_BYTES, keep=None):
    """Borra los archivos más antiguos de la caché hasta quedar por debajo del tope."""
    root = youtube_cache_dir()
    keep_path = os.path.abspath(keep) if keep else None
    files = []
    total = 0
    try:
        names = os.listdir(root)
    except OSError:
        return
    for name in names:
        path = os.path.join(root, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        if not os.path.isfile(path):
            continue
        files.append((st.st_mtime, st.st_size, path))
        total += st.st_size
    if total <= max_bytes:
        return
    files.sort()
    for _mtime, size, path in files:
        if total <= max_bytes:
            break
        if keep_path and os.path.abspath(path) == keep_path:
            continue
        try:
            os.remove(path)
            total -= size
            print(f'[YouTube] Caché: eliminado {os.path.basename(path)} ({size // (1024 * 1024)} MB)')
        except OSError:
            pass


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
    enforce_youtube_cache_limit(keep=keep)


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

    cookies_path = cookies_file_path()
    browser = extra.pop('cookie_browser', None)
    use_cookiefile = extra.pop('use_cookiefile', True)
    if browser:
        opts['cookiesfrombrowser'] = (browser,)
    elif use_cookiefile and os.path.exists(cookies_path):
        slim_youtube_cookies_file(cookies_path)
        opts['cookiefile'] = cookies_path

    opts.update(extra)
    opts['extractor_args'] = _merge_extractor_args(
        {'youtube': {'lang': ['es']}},
        extra_extractor,
    )
    return opts


def cookie_browser_loaders():
    """Loaders de browser-cookie3, con el navegador preferido primero."""
    try:
        import browser_cookie3
    except ImportError:
        return []
    names = ['firefox', 'librewolf', 'chrome', 'chromium', 'brave', 'edge', 'opera']
    preferred = app_config.get_cookie_browser()
    if preferred and preferred != 'auto' and preferred in names:
        names = [preferred] + [name for name in names if name != preferred]
    loaders = []
    for name in names:
        loader = getattr(browser_cookie3, name, None)
        if loader:
            loaders.append((name, loader))
    return loaders


def firefox_cookie_sqlite_paths(environ=None, brand='firefox'):
    """Rutas de cookies.sqlite de Firefox/LibreWolf. En Windows no depende del glob roto de browser-cookie3."""
    env = environ if environ is not None else os.environ
    brand = (brand or 'firefox').lower()
    roots = []
    if sys.platform == 'win32':
        for key in ('APPDATA', 'LOCALAPPDATA'):
            base = (env.get(key) or '').strip()
            if not base:
                continue
            if brand == 'librewolf':
                roots.append(os.path.join(base, 'librewolf'))
            else:
                roots.append(os.path.join(base, 'Mozilla', 'Firefox'))
    else:
        home = os.path.expanduser('~')
        if brand == 'librewolf':
            roots.extend((
                os.path.join(home, '.librewolf'),
                os.path.join(home, 'snap', 'librewolf', 'common', '.librewolf'),
            ))
        else:
            roots.extend((
                os.path.join(home, '.mozilla', 'firefox'),
                os.path.join(home, 'snap', 'firefox', 'common', '.mozilla', 'firefox'),
            ))
    found = []
    seen = set()

    def _add(path):
        path = os.path.normpath(path)
        if path in seen or not os.path.isfile(path):
            return
        seen.add(path)
        found.append(path)

    for root in roots:
        ini = os.path.join(root, 'profiles.ini')
        if os.path.isfile(ini):
            parser = configparser.ConfigParser()
            parser.read(ini, encoding='utf-8')
            for section in parser.sections():
                rel = parser[section].get('Path')
                if not rel:
                    continue
                folder = rel if parser[section].get('IsRelative', '1') == '0' else os.path.join(
                    os.path.dirname(ini), rel,
                )
                _add(os.path.join(folder, 'cookies.sqlite'))
        for pattern in (
            os.path.join(root, 'Profiles', '*', 'cookies.sqlite'),
            os.path.join(root, '*', 'cookies.sqlite'),
        ):
            for path in sorted(glob.glob(pattern)):
                _add(path)
    return found


def _copy_sqlite_for_read(src):
    """Copia cookies.sqlite (y WAL) para leerlo aunque el navegador lo tenga abierto."""
    fd, dest = tempfile.mkstemp(suffix='.sqlite')
    os.close(fd)

    def _copy_sidecars():
        for suffix in ('-wal', '-shm'):
            extra = src + suffix
            if os.path.isfile(extra):
                try:
                    shutil.copy2(extra, dest + suffix)
                except OSError:
                    pass

    try:
        shutil.copy2(src, dest)
        _copy_sidecars()
        return dest
    except OSError:
        pass
    if sys.platform == 'win32':
        try:
            import shadowcopy
            shadowcopy.shadow_copy(src, dest)
            _copy_sidecars()
            return dest
        except Exception:
            pass
    try:
        os.remove(dest)
    except OSError:
        pass
    return src


def _cookie_load_hint(exc):
    text = str(exc or '').lower()
    if any(token in text for token in ('decrypt', 'dpapi', 'v20', 'app-bound', 'os_crypt')):
        return 'Chrome/Edge cifran las cookies en Windows; usa Firefox con sesión en YouTube.'
    if any(token in text for token in ('unable to read database', 'locked', 'permission', 'being used')):
        return 'El navegador tiene las cookies bloqueadas. Ciérralo y vuelve a reexportar.'
    if any(token in text for token in ('could not find', 'failed to find', 'profile directory', 'cookie file')):
        return 'No se encontró el perfil de ese navegador.'
    return 'No se pudieron leer las cookies de ese navegador.'


def _jar_from_browser_cookie3(name, loader, cookie_file=None):
    if cookie_file:
        return loader(cookie_file=cookie_file, domain_name='youtube.com')
    return loader(domain_name='youtube.com')


def _jar_from_ytdlp_browser(name):
    from yt_dlp.cookies import extract_cookies_from_browser

    class _Quiet:
        def debug(self, msg):
            return None

        def info(self, msg):
            return None

        def warning(self, msg):
            return None

        def error(self, msg):
            return None

        def info_once(self, msg):
            return None

    return extract_cookies_from_browser(name, logger=_Quiet())


def load_youtube_login_jar():
    """Prueba navegadores hasta encontrar login de YouTube vigente. Devuelve (jar, origen, avisos)."""
    notes = []
    loaders = cookie_browser_loaders()
    configured = app_config.get_cookie_browser()
    if configured and configured != 'auto':
        loaders = [(name, fn) for name, fn in loaders if name == configured] + [
            (name, fn) for name, fn in loaders if name != configured
        ]

    attempts = []
    for name, loader in loaders:
        # En Windows el glob de browser-cookie3 no encuentra profiles.ini (concatena '**'
        # sin separador). Firefox y LibreWolf se leen por ruta explícita a cookies.sqlite.
        skip_auto = sys.platform == 'win32' and name in ('firefox', 'librewolf')
        if not skip_auto:
            attempts.append((name, loader, None))
        if name in ('firefox', 'librewolf'):
            for path in firefox_cookie_sqlite_paths(brand=name):
                attempts.append((name, loader, path))

    seen_files = set()
    for name, loader, cookie_file in attempts:
        if cookie_file:
            if cookie_file in seen_files:
                continue
            seen_files.add(cookie_file)
            readable = _copy_sqlite_for_read(cookie_file)
        else:
            readable = None
        try:
            jar = _jar_from_browser_cookie3(name, loader, cookie_file=readable)
        except TypeError:
            try:
                jar = loader(domain_name='youtube.com')
            except Exception as exc:
                notes.append(f'{name}: {_cookie_load_hint(exc)}')
                continue
        except Exception as exc:
            notes.append(f'{name}: {_cookie_load_hint(exc)}')
            continue
        finally:
            if readable and readable != cookie_file:
                for path in (readable, readable + '-wal', readable + '-shm'):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        if jar and _jar_has_live_youtube_login(jar):
            return jar, name, notes

    ytdlp_names = []
    if configured and configured != 'auto':
        ytdlp_names.append(configured)
    ytdlp_names.extend(name for name, _fn in loaders if name not in ytdlp_names)
    for name in ytdlp_names:
        if name not in ('firefox', 'chrome', 'chromium', 'brave', 'edge', 'opera', 'safari'):
            continue
        try:
            jar = _jar_from_ytdlp_browser(name)
        except Exception as exc:
            notes.append(f'{name} (yt-dlp): {_cookie_load_hint(exc)}')
            continue
        if jar and _jar_has_live_youtube_login(jar):
            return jar, name, notes
    return None, None, notes


def preferred_youtube_browser():
    """Elige un navegador que tenga cookies de YouTube, si es posible."""
    _jar, source, _notes = load_youtube_login_jar()
    if source:
        return source
    configured = app_config.get_cookie_browser()
    return configured if configured and configured != 'auto' else 'firefox'


COOKIES_PATH = os.path.join(data_dir(), 'cookies.txt')
_YT_AUTH_COOKIES = {
    'LOGIN_INFO', 'SID', 'SAPISID',
    '__Secure-1PSID', '__Secure-3PSID',
    '__Secure-1PAPISID', '__Secure-3PAPISID',
}
_YT_COOKIE_DOMAINS = (
    'youtube.com', 'google.com', 'youtu.be', 'youtube-nocookie.com',
)
_YT_COOKIE_MAX_VALUE = 4096
_cookies_slim_mtime = None
_YT_AUTH_ERROR_MARKERS = (
    'sign in',
    'not a bot',
    'bot check',
    'login required',
    'please log in',
    'cookies are no longer valid',
    'use --cookies',
    'confirm you’re not a bot',
    "confirm you're not a bot",
)


def cookies_file_path():
    return COOKIES_PATH


def _normalize_cookie_expiry(expires):
    """Unix en segundos. Firefox 142+ guarda milisegundos y yt-dlp acaba enviando cookies caducadas (HTTP 413)."""
    if expires in (None, '', 0, '0'):
        return None
    try:
        exp = float(expires)
    except (TypeError, ValueError):
        return None
    if exp > 1e12:
        exp /= 1000.0
    return int(exp)


def _cookie_domain_ok(domain):
    host = (domain or '').lstrip('.').lower()
    return any(host == item or host.endswith('.' + item) for item in _YT_COOKIE_DOMAINS)


def _youtube_cookie_keep(cookie, now=None):
    name = getattr(cookie, 'name', '') or ''
    value = getattr(cookie, 'value', '') or ''
    domain = getattr(cookie, 'domain', '') or ''
    if not name or not value or name.startswith('ST-'):
        return False
    if len(value) > _YT_COOKIE_MAX_VALUE:
        return False
    if not _cookie_domain_ok(domain):
        return False
    exp = _normalize_cookie_expiry(getattr(cookie, 'expires', None))
    if exp is not None and exp < int(now or time.time()):
        return False
    return True


def slim_youtube_cookies_file(path=None):
    """Quita de cookies.txt tokens ST caducados y caducidades en ms. Evita HTTP 413 en búsquedas."""
    global _cookies_slim_mtime
    path = path or cookies_file_path()
    if not os.path.isfile(path):
        return 0
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return 0
    if _cookies_slim_mtime is not None and mtime == _cookies_slim_mtime:
        return 0
    now = int(time.time())
    kept = []
    dropped = 0
    changed = False
    try:
        with open(path, encoding='utf-8') as handle:
            for line in handle:
                raw = line.rstrip('\n')
                if not raw.strip() or raw.startswith('#'):
                    continue
                fields = raw.split('\t')
                if len(fields) < 7:
                    dropped += 1
                    continue
                domain, expiry, name, value = fields[0], fields[4], fields[5], fields[6]
                if not name or name.startswith('ST-') or not _cookie_domain_ok(domain):
                    dropped += 1
                    continue
                if len(value or '') > _YT_COOKIE_MAX_VALUE:
                    dropped += 1
                    continue
                exp = _normalize_cookie_expiry(expiry)
                if exp is not None and exp < now:
                    dropped += 1
                    continue
                if exp is not None and str(exp) != str(expiry).strip():
                    fields[4] = str(exp)
                    changed = True
                kept.append('\t'.join(fields))
    except OSError:
        return 0
    if dropped == 0 and not changed:
        _cookies_slim_mtime = mtime
        return 0
    header = (
        '# Netscape HTTP Cookie File\n'
        '# This file was generated by Kidneys M3U. Do not share it.\n\n'
    )
    try:
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(header)
            if kept:
                handle.write('\n'.join(kept) + '\n')
        _cookies_slim_mtime = os.path.getmtime(path)
    except OSError:
        return 0
    if dropped:
        print(f'[YouTube] Cookies recortadas: se omitieron {dropped} caducadas o ST (evita error 413)')
    return dropped


def inspect_youtube_session(path=None):
    """Revisa cookies.txt: OK si hay cookies de login vigentes."""
    path = path or cookies_file_path()
    now = int(time.time())
    if not os.path.isfile(path) or os.path.getsize(path) < 40:
        return {'ok': False, 'label': 'caducada', 'reason': 'no hay cookies.txt'}
    has_auth = False
    expired_auth = False
    try:
        with open(path, encoding='utf-8') as handle:
            for line in handle:
                if not line.strip() or line.startswith('#'):
                    continue
                fields = line.rstrip('\n').split('\t')
                if len(fields) < 7:
                    continue
                domain, expiry, name, value = fields[0], fields[4], fields[5], fields[6]
                if 'youtube' not in domain and 'google' not in domain:
                    continue
                if name not in _YT_AUTH_COOKIES or not value:
                    continue
                has_auth = True
                exp = _normalize_cookie_expiry(expiry) or 0
                if exp > 0 and exp < now:
                    expired_auth = True
    except OSError:
        return {'ok': False, 'label': 'caducada', 'reason': 'no se pudo leer cookies.txt'}
    if not has_auth:
        return {'ok': False, 'label': 'caducada', 'reason': 'no hay cookies de login'}
    if expired_auth:
        return {'ok': False, 'label': 'caducada', 'reason': 'cookies caducadas'}
    return {'ok': True, 'label': 'OK', 'reason': ''}


def youtube_auth_blocked(exc):
    text = str(exc or '').lower()
    return any(marker in text for marker in _YT_AUTH_ERROR_MARKERS)


def youtube_auth_help():
    return (
        "YouTube pide iniciar sesión (bot-check o cookies caducadas).\n"
        "Inicia sesión en el navegador y pulsa «Reexportar cookies»."
    )


def _jar_has_live_youtube_login(cookies):
    """True si el jar tiene cookies de login de YouTube que no han caducado."""
    now = int(time.time())
    for cookie in cookies or []:
        name = getattr(cookie, 'name', '') or ''
        value = getattr(cookie, 'value', '') or ''
        if name not in _YT_AUTH_COOKIES or not value:
            continue
        domain = (getattr(cookie, 'domain', '') or '').lower()
        if 'youtube' not in domain and 'google' not in domain:
            continue
        exp = _normalize_cookie_expiry(getattr(cookie, 'expires', None)) or 0
        if exp == 0 or exp >= now:
            return True
    return False
 
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
        self._pending_resume_s = None
        self._play_gen = 0
        self._loading_frame = None
        self._loading_bar = None
        self._loading_title_label = None
        self._loading_status_label = None
        self._loading_thumb_label = None
        self._loading_title_text = ''
        self._loading_video_id = None
        self._thumb_photos = {}
        self._session_override = None
        self._session_override_reason = ''
        self._session_listeners = []
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
            ensure = getattr(self.video_player, 'ensure_window', None)
            if ensure:
                ensure()
            url = ask_string(
                self.video_player.window,
                "Cargar YouTube",
                "Introduce la URL del video de YouTube:",
            )
        if url:
            self.play_youtube_url(url)

    def play_youtube_url(self, url, force_pulse=False, show_progress=False, is_sequential=False, title=None, resume_s=None):
        """Reproduce un vídeo de YouTube dentro del reproductor integrado."""
        save_resume = getattr(self.video_player, 'save_youtube_resume', None)
        if save_resume:
            save_resume()
        video_id = self.extract_youtube_id(url)
        if not video_id:
            player = getattr(self, 'video_player', None)
            if player is not None:
                from youtube_search import is_youtube_channel_url, is_youtube_playlist_url
                if is_youtube_channel_url(url):
                    play = getattr(player, 'play_youtube_channel', None)
                    if play:
                        play(url, title=title)
                        return
                if is_youtube_playlist_url(url):
                    load = getattr(player, 'load_youtube_playlist', None)
                    if load:
                        load(url, notify=False, on_done=lambda: player.play_channel(0))
                        return
            messagebox.showerror("Error", "No se pudo extraer el ID del vídeo de YouTube")
            return
        self.video_player._playing_youtube = True
        app_config.remember_youtube_watch(video_id, title=title or '', url=url)
        refresh = getattr(self.video_player, '_refresh_history_ui', None)
        if refresh:
            try:
                refresh()
            except tk.TclError:
                pass

        gen = self._new_play_gen()
        self._current_url = url
        self._play_kwargs = {
            'force_pulse': force_pulse,
            'show_progress': show_progress,
            'is_sequential': is_sequential,
        }
        if resume_s is None:
            resume_s = app_config.youtube_resume_seconds(video_id)
        else:
            try:
                resume_s = max(0.0, float(resume_s))
            except (TypeError, ValueError):
                resume_s = 0.0
        self._pending_resume_s = resume_s
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
                    path = self.export_cookies_from_browser(silent=True)
                    if path:
                        self._session_override = None
                        self._session_override_reason = ''
                    self.notify_session()
                except Exception as exc:
                    print(f"[YouTubeHandler] No se pudieron exportar cookies: {exc}")
                stream = self.get_best_vlc_url(url)
            except Exception as exc:
                err = exc

            def cont():
                if gen != self._play_gen:
                    return
                if err:
                    self.mark_session_from_error(err)
                    messagebox.showerror("Error", f"Error al procesar el vídeo: {err}")
                    self.open_in_browser(url)
                    return
                if not stream:
                    self.mark_session_from_error(getattr(self, '_last_extract_error', None))
                self._begin_playback(url, stream, force_pulse, show_progress, is_sequential)

            self._ui_after(cont)

        threading.Thread(target=work, daemon=True).start()

    def _begin_playback(self, url, stream, force_pulse, show_progress, is_sequential):
        video_id = self.extract_youtube_id(url)
        duration = (stream or {}).get('duration')
        pending = getattr(self, '_pending_resume_s', None)
        self._pending_resume_s = None
        if pending is None:
            resume_s = app_config.youtube_resume_seconds(video_id, duration)
        else:
            resume_s = float(pending or 0)
            if app_config._yt_resume_near_end(resume_s, duration):
                resume_s = 0
        subs = (stream or {}).get('subtitles') or []
        if stream:
            self._direct_url = stream.get('url') or ''
            self._direct_headers = stream.get('headers') or {}
            if stream.get('title'):
                self._set_loading_title(stream['title'])
                self._sync_sidebar_title(url, stream['title'])
                app_config.remember_youtube_watch(video_id, title=stream['title'], url=url)
        if resume_s:
            self._set_loading_status(f"Reanudando en {self._resume_clock(resume_s)}…")
        if stream and self._stream_ok_for_vlc(stream):
            print(f"[YouTubeHandler] Reproduciendo en el reproductor: {stream['url'][:80]}…")
            if not resume_s:
                self._set_loading_status("Abriendo el vídeo…")

            def fallback():
                print("[YouTubeHandler] VLC no pudo abrir el stream directo; probando archivo local")
                if self._play_playable_file(
                    url, force_pulse, show_progress, is_sequential,
                    duration=stream.get('duration'),
                    start_s=resume_s,
                ):
                    return
                print("[YouTubeHandler] Retransmitiendo la URL ya extraída")
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
        if self._play_playable_file(
            url, force_pulse, show_progress, is_sequential,
            duration=duration,
            start_s=resume_s,
        ):
            self.video_player.set_youtube_subtitles(subs)
            return
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
        setter = getattr(player, 'update_sidebar_title', None)
        if setter and setter(url, title):
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
        session = self.session_view()
        if not session.get('ok'):
            detail = youtube_auth_help().replace('\n', ' ')
        else:
            detail = (
                "YouTube está limitando el acceso (a menudo un 429). "
                "Espera un minuto y prueba otra vez, o ábrelo en el navegador."
            )
        tk.Label(
            info_frame,
            text=detail,
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
        if not session.get('ok'):
            tk.Button(
                info_frame,
                text="Reexportar cookies",
                font=get_font(10),
                command=self.reexport_youtube_cookies,
                padx=12,
                pady=6,
                bg=colors['surface_alt'],
                fg=colors['text'],
                activebackground=colors['border'],
                activeforeground=colors['text'],
                relief=tk.FLAT,
            ).pack(pady=(0, 10))

    def _ffmpeg_header_block(self, headers):
        parts = []
        for key, value in (headers or {}).items():
            if value:
                parts.append(f'{key}: {value}')
        return ('\r\n'.join(parts) + '\r\n') if parts else ''

    def _stream_ok_for_vlc(self, stream):
        """Si hay URL, VLC la prueba. Los filtros antiguos mandaban todo al relevo y YouTube lo cortaba."""
        return bool((stream or {}).get('url'))

    def _play_local_video(self, path, force_pulse, show_progress, is_sequential, duration=None, start_s=0):
        print(f"[YouTubeHandler] Reproduciendo archivo local (sin remux): {path}")
        self.video_player._yt_via_pipe = False
        self.video_player._yt_start_offset_ms = 0
        self.video_player.play_video_url(
            path,
            force_pulse=force_pulse,
            show_progress=show_progress,
            is_sequential=is_sequential,
            local_file=True,
            duration_s=duration,
            start_s=start_s,
        )

    def _play_playable_file(self, youtube_url, force_pulse, show_progress, is_sequential, duration=None, start_s=0):
        """Usa la caché si el formato ya es jugable. No remuxea a MPEG-TS."""
        path = find_cached_youtube_video(self.extract_youtube_id(youtube_url))
        if not path:
            return False
        self._play_local_video(
            path, force_pulse, show_progress, is_sequential,
            duration=duration, start_s=start_s,
        )
        return True

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
        if self._play_playable_file(
            url,
            kwargs.get('force_pulse', True),
            kwargs.get('show_progress', True),
            kwargs.get('is_sequential', False),
            duration=duration,
            start_s=max(0.0, float(start_s or 0)),
        ):
            return True
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
        """Retransmite a MPEG-TS solo si hace falta. Un MP4/MKV local se abre tal cual."""
        source_url = source_url or self._direct_url
        http_headers = http_headers or self._direct_headers
        if is_playable_local_video(source_url):
            self._play_local_video(
                source_url, force_pulse, show_progress, is_sequential,
                duration=duration, start_s=start_s,
            )
            return True
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            return self._play_via_download(
                youtube_url, force_pulse, show_progress, is_sequential,
                duration=duration, start_s=start_s,
            )

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

    def _play_via_download(self, youtube_url, force_pulse, show_progress, is_sequential, duration=None, start_s=0):
        """Descarga a la caché un formato jugable y lo abre en VLC, sin remux."""
        video_id = self.extract_youtube_id(youtube_url)
        cached = find_cached_youtube_video(video_id)
        if cached:
            self._play_local_video(
                cached, force_pulse, show_progress, is_sequential,
                duration=duration, start_s=start_s,
            )
            return True
        self.stop_pipeline()
        self._show_status("Descargando vídeo para reproducirlo…")
        quality = app_config.get_youtube_quality()
        quality_key = app_config.youtube_quality_cache_key(quality)
        outtmpl = os.path.join(youtube_cache_dir(), f'{video_id or "video"}_{quality_key}.%(ext)s')

        def work():
            try:
                opts = youtube_ydl_opts(
                    outtmpl=outtmpl,
                    format=youtube_format_selector(quality),
                    quiet=True,
                )
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)
                    path = ydl.prepare_filename(info)
                requested = (info or {}).get('requested_downloads') or []
                if requested and requested[0].get('filepath'):
                    path = requested[0]['filepath']
                if not path or not os.path.exists(path):
                    path = find_cached_youtube_video(video_id, quality)
                if not path or not os.path.exists(path):
                    raise FileNotFoundError('No se descargó el archivo')
                enforce_youtube_cache_limit(keep=path)
                if not is_playable_local_video(path):
                    raise FileNotFoundError(f'El formato descargado no es jugable: {path}')

                def start():
                    self._play_local_video(
                        path, force_pulse, show_progress, is_sequential,
                        duration=duration or info.get('duration'),
                        start_s=start_s,
                    )

                self.video_player.window.after(0, start)
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
        cookies_path = cookies_file_path()
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
            self.mark_session_from_error(e)
            if youtube_auth_blocked(e):
                messagebox.showerror("Sesión YouTube", youtube_auth_help())
            else:
                messagebox.showerror("Error", f"No se pudo obtener la playlist: {e}")
            return None
           
    def download_youtube_video(self, url=None):
        """Permite al usuario descargar un vídeo de YouTube."""
        if url is None:
            ensure = getattr(self.video_player, 'ensure_window', None)
            if ensure:
                ensure()
            url = ask_string(
                self.video_player.window,
                "Descargar vídeo de YouTube",
                "Introduce la URL del video de YouTube:",
            )
        
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
                initialdir=app_config.get_download_dir(),
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
            self.mark_session_from_error(e)
            if youtube_auth_blocked(e):
                messagebox.showerror("Sesión YouTube", youtube_auth_help())
            else:
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
            self.mark_session_from_error(e)
            if youtube_auth_blocked(e):
                self.video_player.window.after(0, lambda: messagebox.showerror(
                    "Sesión YouTube",
                    youtube_auth_help(),
                ))
            else:
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
        for name in os.listdir(directory):
            lower = name.lower()
            if not lower.endswith(('.vtt', '.srt', '.json3')):
                continue
            if not filename_matches_sub_lang(name, lang):
                continue
            matches.append(os.path.join(directory, name))
        if not matches:
            return None
        vlc_ready = [path for path in matches if path.endswith('.vlc.vtt')]
        return sorted(vlc_ready or matches)[0]

    def _write_subs_from_info(self, ydl, info, items):
        """Guarda el ASR original (o el primero) y lo deja en un VTT que VLC no atasca."""
        if not items:
            return
        preferred = next(
            (
                item for item in items
                if item.get('kind') == 'auto'
                and str(item.get('lang') or '') in ('es-orig', 'es', 'es-ES', 'es-419')
            ),
            None,
        )
        if preferred is None:
            preferred = next(
                (
                    item for item in items
                    if item.get('kind') == 'official'
                    and str(item.get('lang') or '').startswith('es')
                ),
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
            ready = prepare_subtitle_for_vlc(path, ext='vtt') or path
            for item in items:
                if item.get('lang') == lang:
                    item['path'] = ready
            print(f"[YouTube] Subtítulo listo {lang}")

    def _dl_sub_url(self, url, lang, ext='vtt'):
        if not url:
            return None
        if time.time() < getattr(self, '_sub_429_until', 0):
            wait = int(self._sub_429_until - time.time())
            print(f"[YouTube] YouTube limita subtítulos; espera {wait}s y prueba otra vez")
            return None
        suffix = (ext or 'vtt').lstrip('.')
        dest = os.path.join(self._sub_cache_dir(), f'caption_{lang}.{suffix}')
        download_url = url
        if lang and not str(lang).endswith('-orig'):
            download_url = ensure_caption_tlang(url, lang)
        opts = youtube_ydl_opts(silent=True, quiet=True, no_warnings=True, ignoreerrors=True)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.dl(dest, {'url': download_url, 'http_headers': ydl.params.get('http_headers')}, subtitle=True)
        except Exception as exc:
            text = str(exc)
            if '429' in text:
                self._sub_429_until = time.time() + 90
                print('[YouTube] YouTube ha limitado los subtítulos (429). Espera un minuto.')
            else:
                print(f"[YouTube] Subtítulo no disponible: {exc}")
            return None
        if not os.path.isfile(dest):
            return None
        return prepare_subtitle_for_vlc(dest, ext=suffix) or dest

    def fetch_subtitle_file(self, lang, auto=False, url=None, ext='vtt', path=None, vtt_url=None):
        """Usa el archivo ya extraído o descarga json3/vtt y lo convierte para VLC."""
        if path and os.path.isfile(path) and filename_matches_sub_lang(path, lang):
            ready = path if path.endswith('.vlc.vtt') else prepare_subtitle_for_vlc(path, ext=ext)
            if ready:
                return ready
        found = self._find_sub_file(getattr(self.video_player, '_yt_sub_dir', None), lang)
        if found and filename_matches_sub_lang(found, lang):
            if found.endswith('.vlc.vtt'):
                return found
            ready = prepare_subtitle_for_vlc(found)
            if ready:
                return ready
        downloaded = self._dl_sub_url(url, lang, ext)
        if downloaded:
            return downloaded
        if vtt_url and vtt_url != url:
            return self._dl_sub_url(vtt_url, lang, 'vtt')
        return None

    def get_best_vlc_url(self, youtube_url):
        """Obtiene una URL de stream que VLC pueda reproducir dentro de la ventana."""
        max_height = app_config.get_youtube_quality()
        format_sel = youtube_format_selector(max_height)
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
                    stream = self._pick_playable_stream(info, max_height=max_height)
                    if stream:
                        stream['headers'] = self._headers_for_vlc(stream.get('headers'))
                        stream['duration'] = info.get('duration')
                        stream['title'] = info.get('title') or ''
                        stream['subtitles'] = collect_youtube_subs(info)
                        self._write_subs_from_info(ydl, info, stream['subtitles'])
                        self._last_extract_error = None
                        self._session_override = None
                        self._session_override_reason = ''
                        self.notify_session()
                        return stream
            except Exception as e:
                last_error = e
                self._last_extract_error = e
                print(f"Error al obtener la URL compatible para VLC: {e}")
                if youtube_auth_blocked(e):
                    self.mark_session_from_error(e)
                continue
        if last_error:
            print(f"[yt-dlp] Ningún intento de extracción funcionó: {last_error}")
            self.mark_session_from_error(last_error)
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
        path = cookies_file_path()
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

    def _pick_playable_stream(self, info, max_height=None):
        formats = list(info.get('formats') or [])
        headers = dict(info.get('http_headers') or {})
        preferred = app_config.normalize_youtube_quality(
            max_height if max_height is not None else app_config.get_youtube_quality()
        )
        if preferred <= 0:
            preferred = 10000

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

        def height_score(fmt):
            height = int(fmt.get('height') or 0)
            if height <= 0:
                return 1
            if height <= preferred:
                return 10000 + height
            return max(0, 800 - (height - preferred))

        candidates = []
        for fmt in formats:
            if not is_playable(fmt):
                continue
            score = height_score(fmt)
            if is_progressive(fmt) and not is_hls(fmt):
                ext = (fmt.get('ext') or '').lower()
                vcodec = str(fmt.get('vcodec') or '')
                if ext == 'mp4' or vcodec.startswith('avc1'):
                    score += 80
                else:
                    score += 40
            elif is_hls(fmt):
                score += 20
            url = fmt.get('url') or ''
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
                f"proto={best.get('protocol')} height={best.get('height')} "
                f"prefer={app_config.youtube_quality_label(max_height)}"
            )
            return {
                'url': best['url'],
                'headers': fmt_headers,
                'ext': best.get('ext'),
                'format_id': best.get('format_id'),
                'height': best.get('height'),
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

    def session_view(self):
        info = inspect_youtube_session()
        if self._session_override == 'caducada':
            info = {
                'ok': False,
                'label': 'caducada',
                'reason': self._session_override_reason or info.get('reason') or 'YouTube pide iniciar sesión',
            }
        return info

    def add_session_listener(self, callback):
        if callback and callback not in self._session_listeners:
            self._session_listeners.append(callback)

    def remove_session_listener(self, callback):
        try:
            self._session_listeners.remove(callback)
        except ValueError:
            pass

    def notify_session(self):
        info = self.session_view()
        def apply():
            player = self.video_player
            refresh = getattr(player, 'update_youtube_session_ui', None)
            if refresh:
                refresh(info)
            for callback in list(self._session_listeners):
                try:
                    callback(info)
                except Exception:
                    pass
        self._ui_after(apply)

    def mark_session_from_error(self, exc):
        if not youtube_auth_blocked(exc):
            self.notify_session()
            return
        self._session_override = 'caducada'
        self._session_override_reason = 'YouTube pide iniciar sesión (bot-check)'
        print('[YouTube] Sesión caducada o bloqueada. Reexporta las cookies del navegador.')
        self.notify_session()

    def reexport_youtube_cookies(self):
        """Reexporta cookies del navegador y actualiza el indicador de sesión."""
        path = self.export_cookies_from_browser(silent=False)
        if path:
            self._session_override = None
            self._session_override_reason = ''
        self.notify_session()
        info = self.session_view()
        if path and info.get('ok'):
            messagebox.showinfo(
                "Cookies de YouTube",
                "Cookies reexportadas. Sesión YouTube: OK.",
            )
        elif path:
            messagebox.showwarning(
                "Cookies de YouTube",
                "Se escribieron cookies, pero no hay login vigente.\n"
                "Abre YouTube en Firefox (o Chrome), inicia sesión y vuelve a reexportar.",
            )
        return path

    def export_cookies_from_browser(self, output_path=None, silent=False):
        """Exporta cookies de YouTube desde el navegador. No escribe cookies.txt si no hay login vigente."""
        def _error(message):
            if silent:
                print(f"[YouTubeHandler] {message}")
            else:
                messagebox.showerror("Error", message)

        def _warn(message):
            if silent:
                print(f"[YouTubeHandler] {message}")
            else:
                messagebox.showwarning("Cookies de YouTube", message)

        try:
            from http.cookiejar import MozillaCookieJar
        except ImportError:
            _error("No se pudo cargar el soporte de cookies de Python.")
            return None

        if output_path is None:
            output_path = cookies_file_path()

        cookies, source, notes = load_youtube_login_jar()
        if not cookies:
            lines = [
                "No hay sesión de YouTube vigente que se pueda leer.",
                "En Windows, Chrome y Edge suelen cifrar las cookies; lo fiable es Firefox.",
                "Inicia sesión en youtube.com, cierra el navegador y pulsa Reexportar.",
            ]
            unique = []
            for note in notes:
                if note not in unique:
                    unique.append(note)
            if unique:
                lines.append('')
                lines.extend(unique[:6])
            _warn('\n'.join(lines))
            return None
        try:
            cj = MozillaCookieJar(output_path)
            now = time.time()
            for cookie in cookies:
                if not _youtube_cookie_keep(cookie, now=now):
                    continue
                exp = _normalize_cookie_expiry(getattr(cookie, 'expires', None))
                if exp is not None:
                    try:
                        cookie.expires = exp
                    except Exception:
                        pass
                try:
                    cj.set_cookie(cookie)
                except Exception:
                    continue
            if not _jar_has_live_youtube_login(cj):
                _warn(
                    "Las cookies del navegador no incluyen un login de YouTube vigente.\n"
                    "No se ha sobrescrito cookies.txt."
                )
                return None
            cj.save(ignore_discard=True, ignore_expires=True)
            global _cookies_slim_mtime
            _cookies_slim_mtime = None
            slim_youtube_cookies_file(output_path)
            print(f"[YouTube] Cookies exportadas desde {source}")
            return output_path
        except Exception:
            _error("No se pudieron guardar las cookies del navegador.")
            return None