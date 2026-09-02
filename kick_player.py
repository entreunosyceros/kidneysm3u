"""Reproducción de Kick.com (directos, VOD y clips) con yt-dlp + VLC."""

import os
import re
import sys
import threading
import time
import webbrowser
from urllib.parse import urlparse

import tkinter as tk
from tkinter import messagebox

import app_config
from app_paths import data_dir
from display_text import plain_display_text, plain_ui_line
from ui_clipboard import ask_string
from ui_theme import get_colors, get_font
from twitch_player import pick_twitch_stream
from youtube_player import (
    _cookie_load_hint,
    _copy_sqlite_for_read,
    _jar_from_ytdlp_browser,
    _normalize_cookie_expiry,
    cookie_browser_loaders,
    firefox_cookie_sqlite_paths,
    youtube_format_selector,
    youtube_ydl_opts,
)

KICK_COOKIES_PATH = os.path.join(data_dir(), 'kick_cookies.txt')
_KICK_COOKIE_DOMAINS = ('kick.com',)
_KICK_AUTH_ERROR_MARKERS = (
    '403',
    'forbidden',
    'login required',
    'log in',
    'authentication',
    'cloudflare',
    'use --cookies',
    'impersonate',
)
_KICK_HOSTS = ('kick.com', 'www.kick.com')
_KICK_RESERVED = {
    'about', 'browse', 'categories', 'community', 'dashboard', 'dmca',
    'following', 'legal', 'privacy', 'settings', 'terms', 'video',
}
KICK_LIVE_CHECK_MS = 18000
KICK_LIVE_STALL_S = 28
KICK_LIVE_MAX_RECONNECTS = 12


def curl_cffi_available():
    """True si curl_cffi está instalado (mejora VOD Kick con impersonate)."""
    try:
        import curl_cffi  # noqa: F401
        return True
    except ImportError:
        return False


def _kick_impersonate_target():
    """Objeto impersonate compatible con la versión instalada de yt-dlp."""
    if not curl_cffi_available():
        return None
    try:
        from yt_dlp.networking.impersonate import ImpersonateTarget
        return ImpersonateTarget.from_str('chrome')
    except Exception:
        pass
    return 'chrome'


def is_kick_url(url):
    """Indica si la URL es de Kick."""
    text = (url or '').strip()
    if not text.lower().startswith(('http://', 'https://')):
        return False
    lower = text.lower()
    if not any(host in lower for host in _KICK_HOSTS):
        return False
    parsed = urlparse(text)
    path = (parsed.path or '').strip('/')
    if not path:
        return False
    parts = [segment for segment in path.split('/') if segment]
    if not parts:
        return False
    if parts[0].lower() in _KICK_RESERVED and len(parts) == 1:
        return False
    return True


def normalize_kick_url(url):
    """Normaliza kick URL."""
    return (url or '').strip()


def kick_display_name_from_url(url):
    """Nombre legible a partir de la URL Kick."""
    text = normalize_kick_url(url)
    if not text:
        return ''
    parsed = urlparse(text)
    path = (parsed.path or '').strip('/')
    parts = [segment for segment in path.split('/') if segment]
    if not parts:
        return ''
    if parts[0].lower() == 'video' and len(parts) >= 2:
        return plain_display_text(f'VOD {parts[1][:8]}…', f'VOD {parts[1][:8]}')
    if len(parts) >= 3 and parts[1].lower() == 'videos':
        return plain_display_text(parts[0], parts[0])
    if len(parts) >= 2 and parts[1].lower() == 'clips':
        return plain_display_text(parts[0], parts[0])
    if parts[0].lower() in _KICK_RESERVED:
        return ''
    return plain_display_text(parts[0], parts[0])


def kick_default_title(url, title=None):
    """Título por defecto para Kick."""
    text = plain_display_text(title, '')
    if text and text not in ('Kick', normalize_kick_url(url)):
        return text
    return kick_display_name_from_url(url) or 'Kick'


def is_kick_vod_url(url):
    """True si la URL apunta a un VOD de Kick."""
    text = normalize_kick_url(url).lower()
    if not is_kick_url(text):
        return False
    if '/videos/' in text:
        return True
    parsed = urlparse(text)
    parts = [segment for segment in (parsed.path or '').strip('/').split('/') if segment]
    return len(parts) >= 2 and parts[0].lower() == 'video'


def is_kick_channel_url(url):
    """True si la URL apunta a la página de un canal (no VOD ni clip)."""
    text = normalize_kick_url(url)
    if not is_kick_url(text):
        return False
    lower = text.lower().split('?', 1)[0].rstrip('/')
    if '/videos/' in lower or '/clips/' in lower:
        return False
    parsed = urlparse(text)
    parts = [segment for segment in (parsed.path or '').strip('/').split('/') if segment]
    if len(parts) != 1:
        return False
    return parts[0].lower() not in _KICK_RESERVED


def normalize_kick_channel_input(value):
    """Normaliza nombre o slug de canal Kick."""
    text = (value or '').strip()
    if not text:
        return ''
    if is_kick_url(text):
        slug = kick_display_name_from_url(text)
        if not slug or slug.startswith('VOD '):
            return ''
        return slug.lower()
    return text.lstrip('@').split('/')[0].strip().lower()


def _kick_api_headers():
    """Cabeceras HTTP para la API pública de Kick."""
    headers = {
        'Accept': 'application/json',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) '
            'Gecko/20100101 Firefox/125.0'
        ),
        'Referer': 'https://kick.com/',
        'Origin': 'https://kick.com',
    }
    cookie = _cookie_header_from_kick_file()
    if cookie:
        headers['Cookie'] = cookie
    return headers


def _parse_kick_vod_item(item, channel_slug):
    """Convierte un ítem de la API de Kick en dict url/title/duration."""
    if not item or not isinstance(item, dict):
        return None
    video = item.get('video') or {}
    uuid = video.get('uuid') or item.get('uuid')
    if not uuid:
        return None
    slug = plain_display_text(channel_slug, '').strip().lower()
    if not slug:
        return None
    vod_url = f'https://kick.com/{slug}/videos/{uuid}'
    title = plain_display_text(item.get('session_title') or '', '')
    duration = item.get('duration')
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = None
    if duration and duration > 86400:
        duration = duration // 1000
    return {
        'url': vod_url,
        'title': title or f'VOD {str(uuid)[:8]}',
        'duration': duration,
        'id': str(uuid),
    }


def fetch_kick_channel_vods(channel, limit=30):
    """Lista VODs recientes de un canal. Devuelve (videos, channel_slug)."""
    import requests

    channel = normalize_kick_channel_input(channel)
    if not channel:
        return [], ''
    limit = max(1, min(int(limit or 30), 50))
    api_url = f'https://kick.com/api/v2/channels/{channel}/videos'
    try:
        response = requests.get(
            api_url,
            headers=_kick_api_headers(),
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f'[Kick] No se pudo listar VOD de {channel}: {exc}')
        raise
    if not isinstance(data, list):
        return [], channel
    videos = []
    seen = set()
    for item in data:
        parsed = _parse_kick_vod_item(item, channel)
        if not parsed or parsed['url'] in seen:
            continue
        seen.add(parsed['url'])
        videos.append(parsed)
        if len(videos) >= limit:
            break
    return videos, channel


def fetch_kick_latest_vod(channel):
    """Devuelve el VOD más reciente de un canal, o None."""
    videos, channel_name = fetch_kick_channel_vods(channel, limit=1)
    if not videos:
        return None
    item = videos[0]
    return {
        'url': item['url'],
        'title': item.get('title') or '',
        'channel': channel_name,
        'id': item.get('id') or '',
    }


def is_kick_offline_error(exc):
    """Indica si el canal no está en directo."""
    text = str(exc or '').lower()
    return (
        'not currently live' in text
        or 'channel is offline' in text
        or 'is offline' in text
        or 'no livestream' in text
    )


def kick_cookies_file_path():
    """Ruta de kick_cookies.txt."""
    return KICK_COOKIES_PATH


def _kick_cookie_domain_ok(domain):
    """Uso interno: dominio kick válido."""
    host = (domain or '').lstrip('.').lower()
    return any(host == item or host.endswith('.' + item) for item in _KICK_COOKIE_DOMAINS)


def _kick_cookie_load_hint(exc):
    """Uso interno: hint al cargar cookies."""
    return _cookie_load_hint(exc).replace('YouTube', 'Kick')


def _jar_from_browser_cookie3_kick(name, loader, cookie_file=None):
    """Uso interno: jar desde browser_cookie3."""
    if cookie_file:
        return loader(cookie_file=cookie_file, domain_name='kick.com')
    return loader(domain_name='kick.com')


def _jar_has_kick_cookies(cookies):
    """Uso interno: hay cookies kick.com vigentes."""
    now = int(time.time())
    for cookie in cookies or []:
        value = getattr(cookie, 'value', '') or ''
        if not value:
            continue
        domain = (getattr(cookie, 'domain', '') or '').lower()
        if not _kick_cookie_domain_ok(domain):
            continue
        exp = _normalize_cookie_expiry(getattr(cookie, 'expires', None)) or 0
        if exp == 0 or exp >= now:
            return True
    return False


def _kick_cookie_keep(cookie, now=None):
    """Uso interno: conservar cookie kick."""
    name = getattr(cookie, 'name', '') or ''
    value = getattr(cookie, 'value', '') or ''
    domain = getattr(cookie, 'domain', '') or ''
    if not name or not value:
        return False
    if not _kick_cookie_domain_ok(domain):
        return False
    exp = _normalize_cookie_expiry(getattr(cookie, 'expires', None))
    if exp is not None and exp < int(now or time.time()):
        return False
    return True


def load_kick_login_jar():
    """Prueba navegadores hasta encontrar cookies kick.com vigentes."""
    notes = []
    loaders = cookie_browser_loaders()
    configured = app_config.get_cookie_browser()
    if configured and configured != 'auto':
        loaders = [(name, fn) for name, fn in loaders if name == configured] + [
            (name, fn) for name, fn in loaders if name != configured
        ]

    attempts = []
    for name, loader in loaders:
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
            jar = _jar_from_browser_cookie3_kick(name, loader, cookie_file=readable)
        except TypeError:
            try:
                jar = loader(domain_name='kick.com')
            except Exception as exc:
                notes.append(f'{name}: {_kick_cookie_load_hint(exc)}')
                continue
        except Exception as exc:
            notes.append(f'{name}: {_kick_cookie_load_hint(exc)}')
            continue
        finally:
            if readable and readable != cookie_file:
                for path in (readable, readable + '-wal', readable + '-shm'):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        if jar and _jar_has_kick_cookies(jar):
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
            notes.append(f'{name} (yt-dlp): {_kick_cookie_load_hint(exc)}')
            continue
        if jar and _jar_has_kick_cookies(jar):
            return jar, name, notes
    return None, None, notes


def preferred_kick_browser():
    """Navegador preferido para cookies Kick."""
    _jar, source, _notes = load_kick_login_jar()
    if source:
        return source
    configured = app_config.get_cookie_browser()
    return configured if configured and configured != 'auto' else 'firefox'


def inspect_kick_session(path=None):
    """Estado de kick_cookies.txt."""
    path = path or kick_cookies_file_path()
    now = int(time.time())
    if not os.path.isfile(path) or os.path.getsize(path) < 20:
        return {'ok': False, 'label': 'sin archivo', 'reason': 'no hay kick_cookies.txt'}
    has_kick = False
    expired = False
    try:
        with open(path, encoding='utf-8') as handle:
            for line in handle:
                if not line.strip() or line.startswith('#'):
                    continue
                fields = line.rstrip('\n').split('\t')
                if len(fields) < 7:
                    continue
                domain, expiry, value = fields[0], fields[4], fields[6]
                if not _kick_cookie_domain_ok(domain) or not value:
                    continue
                has_kick = True
                exp = _normalize_cookie_expiry(expiry) or 0
                if exp > 0 and exp < now:
                    expired = True
    except OSError:
        return {'ok': False, 'label': 'caducada', 'reason': 'no se pudo leer kick_cookies.txt'}
    if not has_kick:
        return {'ok': False, 'label': 'vacía', 'reason': 'no hay cookies de kick.com'}
    if expired:
        return {'ok': False, 'label': 'caducada', 'reason': 'cookies caducadas'}
    return {'ok': True, 'label': 'OK', 'reason': ''}


def kick_auth_blocked(exc):
    """True si el error sugiere cookies, 403 o login."""
    text = str(exc or '').lower()
    return any(marker in text for marker in _KICK_AUTH_ERROR_MARKERS)


def kick_auth_help():
    """Ayuda cuando Kick bloquea la extracción."""
    lines = [
        'Kick puede bloquear la extracción (403 / Cloudflare).',
        'Prueba:',
        '· Inicia sesión en kick.com (Firefox en Windows) y pulsa «Reexportar cookies».',
        '· Actualiza yt-dlp (menú Youtube → Actualizar yt-dlp).',
    ]
    if not curl_cffi_available():
        lines.append('· Instala curl-cffi en el .venv: pip install curl-cffi')
    return '\n'.join(lines)


def _cookie_header_from_kick_file():
    """Uso interno: cabecera Cookie desde kick_cookies.txt."""
    path = kick_cookies_file_path()
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
                if not _kick_cookie_domain_ok(domain) or not name or not value:
                    continue
                parts.append(f'{name}={value}')
    except OSError:
        return None
    return '; '.join(parts) if parts else None


def kick_ydl_opts(**extra):
    """Opciones yt-dlp para Kick."""
    extra.pop('extractor_args', None)
    use_cookiefile = extra.pop('use_cookiefile', True)
    cookie_browser = extra.pop('cookie_browser', None)
    opts = youtube_ydl_opts(use_cookiefile=False, silent=True, **extra)
    opts.pop('extractor_args', None)
    headers = dict(opts.get('http_headers') or {})
    headers.setdefault('Referer', 'https://kick.com/')
    headers.setdefault('Origin', 'https://kick.com')
    opts['http_headers'] = headers
    impersonate = _kick_impersonate_target()
    if impersonate is not None:
        opts['impersonate'] = impersonate
    cookies_path = kick_cookies_file_path()
    if cookie_browser:
        opts['cookiesfrombrowser'] = (cookie_browser,)
    elif use_cookiefile and os.path.exists(cookies_path):
        opts['cookiefile'] = cookies_path
    return opts


def kick_format_selector(max_height=None):
    """Selector de formato Kick."""
    return youtube_format_selector(app_config.effective_kick_quality(max_height))


def _ydl_used_cookies(ydl_opts):
    """Uso interno: ydl used cookies."""
    if not ydl_opts:
        return False
    return bool(ydl_opts.get('cookiefile') or ydl_opts.get('cookiesfrombrowser'))


def kick_favorite_url(url):
    """URL habitual para favoritos."""
    text = normalize_kick_url(url)
    if not text:
        return ''
    if is_kick_vod_url(text):
        return text
    channel = kick_display_name_from_url(text)
    if channel and not channel.startswith('VOD '):
        return f'https://kick.com/{channel}'
    return text


def kick_loading_detail(stream, url=''):
    """Texto de detalle para overlay de carga."""
    stream = stream or {}
    parts = []
    channel = plain_display_text(stream.get('channel') or kick_display_name_from_url(url), '')
    if channel:
        parts.append(f'Canal: {channel}')
    title = plain_display_text(stream.get('title') or '', '')
    if title and title not in ('Kick', channel):
        parts.append(title)
    parts.append('En directo' if stream.get('is_live') else 'VOD')
    try:
        resume_s = float(stream.get('resume_s') or 0)
    except (TypeError, ValueError):
        resume_s = 0
    if resume_s >= app_config.IPTV_RESUME_MIN_S:
        parts.append(f'Reanudando desde {app_config.format_iptv_clock(resume_s)}')
    quality = app_config.kick_quality_label(app_config.effective_kick_quality())
    parts.append(f'Calidad: {quality}')
    if stream.get('used_cookies'):
        parts.append('Con cookies de sesión')
    if curl_cffi_available():
        parts.append('Impersonate Chrome')
    return plain_ui_line(' · '.join(parts))


def _enrich_kick_stream(stream, info, url, used_cookies=False):
    """Uso interno: enriquece metadatos del stream."""
    if not stream:
        return stream
    stream['channel'] = plain_display_text(
        (info or {}).get('channel') or (info or {}).get('uploader') or kick_display_name_from_url(url),
        '',
    )
    stream['used_cookies'] = bool(used_cookies)
    return stream


def pick_kick_stream(info, max_height=None):
    """Elige stream HLS jugable (misma lógica que Twitch)."""
    stream = pick_twitch_stream(info, max_height=max_height or app_config.effective_kick_quality())
    if not stream:
        return None
    headers = dict(stream.get('headers') or {})
    headers.setdefault('Referer', 'https://kick.com/')
    headers.setdefault('Origin', 'https://kick.com')
    stream['headers'] = headers
    return stream


def _headers_for_vlc(headers, page_url):
    """Uso interno: cabeceras para VLC."""
    merged = dict(headers or {})
    merged.setdefault(
        'User-Agent',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    )
    merged.setdefault('Referer', page_url or 'https://kick.com/')
    merged.setdefault('Origin', 'https://kick.com')
    cookie = merged.get('Cookie') or merged.get('cookie') or _cookie_header_from_kick_file()
    if cookie:
        merged['Cookie'] = cookie
    return merged


def extract_kick_stream(url, max_height=None):
    """Extrae URL jugable y metadatos con yt-dlp."""
    import yt_dlp

    format_sel = kick_format_selector(max_height)
    browser = preferred_kick_browser()
    attempts = []
    if os.path.exists(kick_cookies_file_path()):
        attempts.append(kick_ydl_opts(skip_download=True, format=format_sel))
    if browser:
        attempts.append(kick_ydl_opts(
            skip_download=True,
            format=format_sel,
            use_cookiefile=False,
            cookie_browser=browser,
        ))
    attempts.extend([
        kick_ydl_opts(skip_download=True, format=format_sel, use_cookiefile=False),
        kick_ydl_opts(skip_download=True, format='best', use_cookiefile=False),
    ])
    last_error = None
    for ydl_opts in attempts:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream = pick_kick_stream(info, max_height=max_height)
                if stream and stream.get('url'):
                    stream['headers'] = _headers_for_vlc(stream.get('headers'), url)
                    if not stream.get('title'):
                        stream['title'] = info.get('title') or info.get('uploader') or 'Kick'
                    stream['is_live'] = bool(stream.get('is_live') or info.get('is_live'))
                    if stream.get('duration') is None:
                        stream['duration'] = info.get('duration')
                    return _enrich_kick_stream(stream, info, url, used_cookies=_ydl_used_cookies(ydl_opts))
        except Exception as exc:
            last_error = exc
            if is_kick_offline_error(exc):
                raise exc
            print(f'[Kick] Error al extraer stream: {exc}')
    if last_error:
        raise last_error
    return None


class KickHandler:
    """Reproduce Kick en el reproductor integrado."""

    def __init__(self, video_player):
        """Inicializa KickHandler."""
        self.video_player = video_player
        self._play_gen = 0
        self._loading_frame = None
        self._loading_status_label = None
        self._loading_title_label = None
        self._loading_detail_label = None
        self._current_url = ''
        self._session_override = None
        self._session_override_reason = ''
        self._live_watch_gen = 0
        self._live_watch_job = None
        self._live_source_url = ''
        self._live_reconnects = 0
        self._live_last_ok = 0.0
        self._current_stream = None

    def session_view(self):
        """Estado de sesión Kick."""
        info = inspect_kick_session()
        if self._session_override == 'caducada':
            info = {
                'ok': False,
                'label': 'caducada',
                'reason': self._session_override_reason or info.get('reason') or 'Kick bloqueó la extracción',
            }
        return info

    def notify_session(self):
        """Actualiza la UI de sesión."""
        info = self.session_view()

        def apply():
            player = self.video_player
            refresh = getattr(player, 'update_kick_session_ui', None)
            if refresh:
                refresh(info)

        self._ui_after(apply)

    def mark_session_from_error(self, exc):
        """Marca sesión caducada si el error lo indica."""
        if not kick_auth_blocked(exc):
            self.notify_session()
            return
        self._session_override = 'caducada'
        self._session_override_reason = 'Kick bloqueó la extracción o pide sesión'
        print('[Kick] Extracción bloqueada. Reexporta cookies o actualiza yt-dlp.')
        self.notify_session()

    def reexport_kick_cookies(self):
        """Reexporta cookies del navegador a kick_cookies.txt."""
        path = self.export_cookies_from_browser(silent=False)
        if path:
            self._session_override = None
            self._session_override_reason = ''
        self.notify_session()
        info = self.session_view()
        if path and info.get('ok'):
            messagebox.showinfo('Cookies de Kick', 'Cookies reexportadas. Sesión Kick: OK.')
        elif path:
            messagebox.showwarning(
                'Cookies de Kick',
                'Se escribieron cookies, pero puede que no haya sesión vigente.\n'
                'Abre kick.com en Firefox, inicia sesión y vuelve a reexportar.',
            )
        return path

    def export_cookies_from_browser(self, output_path=None, silent=False):
        """Exporta cookies kick.com desde el navegador."""

        def _error(message):
            if silent:
                print(f'[Kick] {message}')
            else:
                messagebox.showerror('Error', message)

        def _warn(message):
            if silent:
                print(f'[Kick] {message}')
            else:
                messagebox.showwarning('Cookies de Kick', message)

        try:
            from http.cookiejar import MozillaCookieJar
        except ImportError:
            _error('No se pudo cargar el soporte de cookies de Python.')
            return None

        if output_path is None:
            output_path = kick_cookies_file_path()

        cookies, source, notes = load_kick_login_jar()
        if not cookies:
            lines = [
                'No hay cookies de kick.com que se puedan leer.',
                'En Windows, Chrome y Edge suelen cifrar las cookies; lo fiable es Firefox.',
                'Visita kick.com, cierra el navegador y pulsa Reexportar cookies.',
            ]
            unique = []
            for note in notes:
                if note not in unique:
                    unique.append(note)
            if unique:
                lines.extend([''] + unique[:6])
            _warn('\n'.join(lines))
            return None
        try:
            cj = MozillaCookieJar(output_path)
            now = time.time()
            for cookie in cookies:
                if not _kick_cookie_keep(cookie, now=now):
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
            if not _jar_has_kick_cookies(cj):
                _warn(
                    'Las cookies del navegador no incluyen kick.com vigentes.\n'
                    'No se ha sobrescrito kick_cookies.txt.'
                )
                return None
            cj.save(ignore_discard=True, ignore_expires=True)
            print(f'[Kick] Cookies exportadas desde {source}')
            return output_path
        except Exception:
            _error('No se pudieron guardar las cookies del navegador.')
            return None

    def prompt_kick_url(self, url=None):
        """Pide URL Kick y reproduce."""
        if url is None:
            ensure = getattr(self.video_player, 'ensure_window', None)
            if ensure:
                ensure()
            url = ask_string(
                self.video_player.window,
                'Cargar Kick',
                'Introduce la URL de Kick (canal, VOD o clip):',
            )
        if url:
            player = getattr(self, 'video_player', None)
            if player is not None:
                play = getattr(player, 'play_kick_url', None)
                if play:
                    play(url)
                    return
            self.play_kick_url(url)

    def play_kick_url(self, url, title=None, show_progress=None):
        """Reproduce URL Kick."""
        url = normalize_kick_url(url)
        if not is_kick_url(url):
            messagebox.showerror('Kick', 'La URL no parece ser de Kick.')
            return

        player = self.video_player
        for saver in (
            getattr(player, 'save_youtube_resume', None),
            getattr(player, 'save_iptv_resume', None),
            getattr(player, 'save_twitch_resume', None),
            getattr(player, 'save_kick_resume', None),
        ):
            if saver:
                saver()

        player._playing_youtube = False
        player._playing_twitch = False
        player._playing_kick = True
        player._yt_standalone = True
        player.clear_youtube_subtitles()
        twitch = getattr(player, 'twitch_handler', None)
        if twitch:
            twitch.close_chat(notify_ui=False)

        display_title = kick_default_title(url, title)
        app_config.remember_kick_watch(url, title=display_title)
        refresh = getattr(player, '_refresh_history_ui', None)
        if refresh:
            try:
                refresh()
            except tk.TclError:
                pass

        gen = self._new_play_gen()
        self._stop_live_watch()
        self._current_url = url
        self._current_stream = None
        is_channel = is_kick_channel_url(url)
        loading_status = (
            'Comprobando si el canal está en directo…'
            if is_channel
            else 'Obteniendo vídeo de Kick…'
        )
        self._show_loading(loading_status, title=display_title)

        def work():
            err = None
            stream = None
            offline = False
            try:
                try:
                    path = self.export_cookies_from_browser(silent=True)
                    if path:
                        self._session_override = None
                        self._session_override_reason = ''
                    self.notify_session()
                except Exception as exc:
                    print(f'[Kick] No se pudieron exportar cookies: {exc}')
                stream = extract_kick_stream(url)
            except Exception as exc:
                err = exc
                if is_channel and is_kick_offline_error(exc):
                    offline = True

            def cont():
                if gen != self._play_gen:
                    return
                if offline:
                    self.hide_loading()
                    channel = kick_display_name_from_url(url)
                    latest = None
                    try:
                        latest = fetch_kick_latest_vod(channel)
                    except Exception as exc:
                        print(f'[Kick] No se pudo obtener el último VOD de {channel}: {exc}')
                    self._offer_offline_channel(url, channel, latest)
                    return
                if err or not stream:
                    self.hide_loading()
                    if err:
                        self.mark_session_from_error(err)
                    detail = str(err or 'No se pudo obtener el stream.')
                    extra = ''
                    if err and kick_auth_blocked(err):
                        extra = f'\n\n{kick_auth_help()}'
                    messagebox.showerror(
                        'Kick',
                        f'No se pudo reproducir.\n\n{detail}{extra}',
                    )
                    return
                if is_channel and stream.get('is_live'):
                    self._set_loading_status('Canal en directo — abriendo…')
                    self._set_loading_detail(kick_loading_detail(stream, url))
                self._begin_playback(url, stream, show_progress=show_progress)

            self._ui_after(cont)

        threading.Thread(target=work, daemon=True).start()

    def _offer_offline_channel(self, url, channel, latest=None):
        """Informa que el canal no está en directo y ofrece el último VOD."""
        name = plain_display_text(channel, 'Canal') or 'Canal'
        lines = [f'«{name}» no está en directo ahora.']
        latest = latest or {}
        vod_title = plain_display_text(latest.get('title') or '', '')
        if vod_title:
            lines.extend(['', f'Último VOD: {vod_title}'])
        message = '\n'.join(lines)
        vod_url = latest.get('url') if latest else None
        if vod_url:
            choice = messagebox.askyesnocancel(
                'Kick — canal offline',
                message + '\n\n'
                'Sí = reproducir el último VOD\n'
                'No = abrir el canal en el navegador\n'
                'Cancelar = cerrar',
            )
            if choice is True:
                self.play_kick_url(vod_url, title=vod_title or None)
            elif choice is False:
                webbrowser.open(url)
            return
        if messagebox.askyesno(
            'Kick — canal offline',
            message + '\n\n¿Abrir el canal en el navegador?',
        ):
            webbrowser.open(url)

    def _begin_playback(self, url, stream, show_progress=None):
        """Inicia VLC con el stream extraído."""
        player = self.video_player
        self._current_stream = stream
        title = plain_display_text(stream.get('title'), '')
        if not title or title == 'Kick':
            title = kick_default_title(url)
        if title:
            self._set_loading_title(title)
            app_config.remember_kick_watch(url, title=title)
            self._sync_sidebar_title(url, title)

        detail = kick_loading_detail(stream, url)
        self._set_loading_detail(detail)

        is_live = bool(stream.get('is_live'))
        if show_progress is None:
            show_progress = not is_live

        resume_s = 0.0
        if not is_live:
            resume_s = app_config.kick_resume_seconds(url, stream.get('duration'))
            if resume_s >= app_config.IPTV_RESUME_MIN_S:
                stream = dict(stream)
                stream['resume_s'] = resume_s
                detail = kick_loading_detail(stream, url)
                self._set_loading_detail(detail)

        self._set_loading_status('Abriendo el vídeo…')
        print(f"[Kick] Reproduciendo: {stream['url'][:80]}… live={is_live}")

        prepare = getattr(player, '_prepare_web_stream_player', None)
        if prepare:
            prepare()

        def on_fail():
            if is_live:
                self._schedule_live_check(getattr(self, '_live_watch_gen', 0))
            else:
                self.hide_loading()
                messagebox.showerror(
                    'Kick',
                    'VLC no pudo abrir el stream.\n'
                    'Prueba otra calidad en Preferencias o abre el enlace en el navegador.',
                )
                webbrowser.open(url)

        player.play_video_url(
            stream['url'],
            force_pulse=True,
            show_progress=show_progress,
            http_headers=stream.get('headers'),
            duration_s=stream.get('duration'),
            fail_after_s=25,
            on_fail=on_fail,
            start_s=resume_s if not is_live else 0,
        )
        self.hide_loading()
        if is_live:
            self._start_live_watch(url)
        else:
            self._stop_live_watch()

    def add_current_to_favorites(self):
        """Añade la reproducción actual a favoritos."""
        url = self._current_url
        if not url or not is_kick_url(url):
            messagebox.showinfo('Kick', 'Reproduce un canal o VOD de Kick primero.')
            return False
        fav_url = kick_favorite_url(url)
        stream = self._current_stream or {}
        title = plain_display_text(stream.get('title') or kick_default_title(url), '')
        channel = plain_display_text(stream.get('channel') or kick_display_name_from_url(url), '')
        if channel and (not title or title in ('Kick', url) or title == channel):
            name = channel
        elif title:
            name = title
        else:
            name = kick_default_title(url)
        add = getattr(self.video_player, 'add_favorite_entry', None)
        if add:
            return add(name, fav_url, notify=True)
        return False

    def _sync_sidebar_title(self, url, title):
        """Actualiza título en la barra lateral."""
        title = plain_display_text(title, '')
        if not title or not url or title in ('Kick', url):
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

    def _stop_live_watch(self):
        """Detiene vigilancia de directo."""
        self._live_watch_gen = getattr(self, '_live_watch_gen', 0) + 1
        job = getattr(self, '_live_watch_job', None)
        self._live_watch_job = None
        if job:
            window = getattr(self.video_player, 'window', None)
            if window:
                try:
                    window.after_cancel(job)
                except tk.TclError:
                    pass
        self._live_source_url = ''
        self._live_reconnects = 0
        self._live_bytes_prev = 0
        self._live_stall_ticks = 0
        self._live_media_started = False

    def _start_live_watch(self, url):
        """Inicia vigilancia de directo."""
        self._stop_live_watch()
        self._live_source_url = url
        self._live_reconnects = 0
        self._live_last_ok = time.time()
        self._live_bytes_prev = 0
        self._live_stall_ticks = 0
        self._live_media_started = False
        self._live_token_refresh_at = time.time() + (25 * 60)
        gen = self._live_watch_gen
        self._schedule_live_check(gen)

    def _schedule_live_check(self, watch_gen, delay_ms=None):
        """Programa comprobación de directo."""
        if delay_ms is None:
            delay_ms = KICK_LIVE_CHECK_MS
        window = getattr(self.video_player, 'window', None)
        if not window:
            return

        def tick():
            if watch_gen != self._live_watch_gen:
                return
            self._check_live_stream(watch_gen)

        try:
            self._live_watch_job = window.after(delay_ms, tick)
        except tk.TclError:
            pass

    def _media_stats(self):
        """Estadísticas VLC del media actual."""
        player = getattr(self.video_player, 'player', None)
        if not player:
            return None
        try:
            media = player.get_media()
        except Exception:
            return None
        if media is None:
            return None
        try:
            import vlc
            stats = vlc.MediaStats()
            if not media.get_stats(stats):
                return None
            return stats
        except Exception:
            return None

    def _check_live_stream(self, watch_gen):
        """Comprueba stall o fin de directo y reconecta si hace falta."""
        if watch_gen != self._live_watch_gen:
            return
        player = self.video_player
        if not getattr(player, '_playing_kick', False):
            self._stop_live_watch()
            return
        url = getattr(self, '_live_source_url', '') or self._current_url
        if not url:
            self._stop_live_watch()
            return

        vlc_player = getattr(player, 'player', None)
        if not vlc_player:
            self._schedule_live_check(watch_gen)
            return

        try:
            import vlc
            state = vlc_player.get_state()
        except Exception:
            self._schedule_live_check(watch_gen)
            return

        from iptv_buffer import iptv_bytes_progress, vlc_state_name

        stats = self._media_stats()
        bytes_now = iptv_bytes_progress(stats)
        bytes_prev = int(getattr(self, '_live_bytes_prev', 0) or 0)
        state_name = vlc_state_name(state)
        growing = bytes_now > bytes_prev
        if bytes_now > bytes_prev:
            self._live_bytes_prev = bytes_now

        started = bool(getattr(self, '_live_media_started', False))
        if state_name == 'Playing':
            self._live_media_started = True
            started = True
        if started and state_name in ('Playing', 'Buffering') and growing:
            self._live_last_ok = time.time()
            self._live_stall_ticks = 0
        elif started and state_name == 'Buffering' and not growing:
            self._live_stall_ticks = int(getattr(self, '_live_stall_ticks', 0) or 0) + 1
        elif growing:
            self._live_stall_ticks = 0

        stall_limit = max(2, int(KICK_LIVE_STALL_S * 1000 / KICK_LIVE_CHECK_MS))
        need_reconnect = False
        reason = ''
        if started and state_name in ('Error', 'Ended', 'Stopped'):
            need_reconnect = True
            reason = 'VLC detuvo el directo'
        elif started and self._live_stall_ticks >= stall_limit:
            need_reconnect = True
            reason = 'Sin datos del stream'
        elif time.time() >= getattr(self, '_live_token_refresh_at', 0):
            need_reconnect = True
            reason = 'Renovando enlace HLS'
            self._live_token_refresh_at = time.time() + (25 * 60)

        if need_reconnect:
            if self._live_reconnects >= KICK_LIVE_MAX_RECONNECTS:
                print(f'[Kick] Reconexión abandonada tras {self._live_reconnects} intentos ({reason})')
                self._stop_live_watch()
                return
            self._live_reconnects += 1
            print(f'[Kick] Reconexión {self._live_reconnects}/{KICK_LIVE_MAX_RECONNECTS}: {reason}')
            self._reconnect_live(url, watch_gen)
            return

        self._schedule_live_check(watch_gen)

    def _reconnect_live(self, url, watch_gen):
        """Vuelve a extraer y reproducir el directo."""
        play_gen = self._play_gen

        def work():
            err = None
            stream = None
            try:
                stream = extract_kick_stream(url)
            except Exception as exc:
                err = exc

            def cont():
                if watch_gen != self._live_watch_gen or play_gen != self._play_gen:
                    return
                if err or not stream:
                    print(f'[Kick] Reconexión fallida: {err or "sin stream"}')
                    self._schedule_live_check(watch_gen)
                    return
                self._live_bytes_prev = 0
                self._live_stall_ticks = 0
                self._live_media_started = False
                self._current_stream = stream
                player = self.video_player
                prepare = getattr(player, '_prepare_web_stream_player', None)
                if prepare:
                    prepare()
                player.play_video_url(
                    stream['url'],
                    force_pulse=True,
                    show_progress=False,
                    http_headers=stream.get('headers'),
                    duration_s=stream.get('duration'),
                    fail_after_s=25,
                )
                self._schedule_live_check(watch_gen)

            self._ui_after(cont)

        threading.Thread(target=work, daemon=True).start()

    def cancel_pending_play(self):
        """Cancela reproducción pendiente."""
        self._stop_live_watch()
        self._new_play_gen()
        self._current_stream = None
        self.hide_loading()

    def _new_play_gen(self):
        """Nueva generación de play (invalida hilos antiguos)."""
        self._play_gen = getattr(self, '_play_gen', 0) + 1
        return self._play_gen

    def _ui_after(self, fn, delay_ms=0):
        """Ejecuta fn en el hilo UI."""
        window = getattr(self.video_player, 'window', None)
        if not window:
            return
        try:
            window.after(delay_ms, fn)
        except tk.TclError:
            pass

    def hide_loading(self):
        """Oculta overlay de carga."""
        frame = getattr(self, '_loading_frame', None)
        self._loading_frame = None
        self._loading_status_label = None
        self._loading_title_label = None
        self._loading_detail_label = None
        if frame:
            try:
                frame.destroy()
            except tk.TclError:
                pass

    def _loading_alive(self):
        """True si el overlay sigue visible."""
        frame = getattr(self, '_loading_frame', None)
        try:
            return bool(frame and frame.winfo_exists())
        except tk.TclError:
            return False

    def _show_loading(self, status, title=None):
        """Muestra overlay de carga."""
        player = self.video_player
        video_frame = getattr(player, 'video_frame', None)
        if not video_frame:
            return
        if self._loading_alive():
            self._set_loading_status(status)
            if title:
                self._set_loading_title(title)
            return

        self.hide_loading()
        colors = get_colors()
        overlay = tk.Frame(video_frame, bg='#000000', highlightthickness=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        try:
            overlay.lift()
        except tk.TclError:
            pass
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

        title_label = tk.Label(
            card,
            text=plain_display_text(title, '') or 'Kick',
            font=get_font(13, 'bold'),
            bg=colors['surface'],
            fg=colors['text'],
            wraplength=420,
            justify='center',
        )
        title_label.pack(pady=(0, 6))
        self._loading_title_label = title_label

        status_label = tk.Label(
            card,
            text=plain_ui_line(status),
            font=get_font(10),
            bg=colors['surface'],
            fg=colors['text_muted'],
            wraplength=420,
            justify='center',
        )
        status_label.pack(pady=(0, 6))
        self._loading_status_label = status_label

        detail_label = tk.Label(
            card,
            text='',
            font=get_font(9),
            bg=colors['surface'],
            fg=colors['text_muted'],
            wraplength=420,
            justify='center',
        )
        detail_label.pack()
        self._loading_detail_label = detail_label

    def _set_loading_status(self, text):
        """Actualiza texto de estado."""
        label = getattr(self, '_loading_status_label', None)
        if label:
            try:
                label.configure(text=plain_ui_line(text))
            except tk.TclError:
                pass

    def _set_loading_title(self, title):
        """Actualiza título en overlay."""
        label = getattr(self, '_loading_title_label', None)
        if label:
            try:
                label.configure(text=plain_display_text(title, '') or 'Kick')
            except tk.TclError:
                pass

    def _set_loading_detail(self, text):
        """Actualiza detalle en overlay."""
        label = getattr(self, '_loading_detail_label', None)
        if label:
            try:
                label.configure(text=plain_display_text(text, ''))
            except tk.TclError:
                pass
