"""Reproducción de Twitch (directos, VOD y clips) con yt-dlp + VLC."""

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


TWITCH_COOKIES_PATH = os.path.join(data_dir(), 'twitch_cookies.txt')
_TWITCH_AUTH_COOKIES = {'auth-token', 'login', 'twilight-user'}
_TWITCH_COOKIE_DOMAINS = ('twitch.tv',)
_TWITCH_AUTH_ERROR_MARKERS = (
    'login required',
    'log in',
    'authentication',
    'auth token',
    'subscriber',
    'subscription',
    'subscribers-only',
    'cookies are no longer valid',
    'use --cookies',
)

_TWITCH_HOSTS = ('twitch.tv', 'www.twitch.tv', 'm.twitch.tv', 'clips.twitch.tv')
_TWITCH_URL_RE = re.compile(
    r'^https?://(?:www\.|m\.)?twitch\.tv/(?:videos/\d+|[^/?#\s]+|clip/[^/?#\s]+)',
    re.I,
)
_TWITCH_CLIP_RE = re.compile(r'^https?://clips\.twitch\.tv/[^/?#\s]+', re.I)
TWITCH_LIVE_CHECK_MS = 18000
TWITCH_LIVE_STALL_S = 28
TWITCH_LIVE_MAX_RECONNECTS = 12


def is_twitch_url(url):
    text = (url or '').strip()
    if not text.lower().startswith(('http://', 'https://')):
        return False
    lower = text.lower()
    if not any(host in lower for host in _TWITCH_HOSTS):
        return False
    return bool(_TWITCH_URL_RE.match(text) or _TWITCH_CLIP_RE.match(text))


def normalize_twitch_url(url):
    return (url or '').strip()


def twitch_display_name_from_url(url):
    """Nombre legible a partir de la URL (canal, clip o VOD) antes de extraer metadatos."""
    text = normalize_twitch_url(url)
    if not text:
        return ''
    parsed = urlparse(text)
    host = (parsed.netloc or '').lower()
    path = (parsed.path or '').strip('/')
    if not path:
        return ''
    parts = [segment for segment in path.split('/') if segment]
    if not parts:
        return ''
    if host == 'clips.twitch.tv':
        return plain_display_text(parts[0], parts[0])
    if parts[0].lower() == 'videos' and len(parts) >= 2:
        return plain_display_text(f'VOD {parts[1]}', f'VOD {parts[1]}')
    if len(parts) >= 2 and parts[1].lower() == 'clip':
        return plain_display_text(parts[2] if len(parts) >= 3 else parts[0], parts[0])
    if parts[0].lower() == 'clip' and len(parts) >= 2:
        return plain_display_text(parts[1], parts[1])
    reserved = {'directory', 'downloads', 'jobs', 'p', 'settings', 'subscriptions', 'videos', 'clip'}
    if parts[0].lower() in reserved:
        return ''
    return plain_display_text(parts[0], parts[0])


def twitch_default_title(url, title=None):
    text = plain_display_text(title, '')
    if text and text not in ('Twitch', normalize_twitch_url(url)):
        return text
    return twitch_display_name_from_url(url) or 'Twitch'


def is_twitch_channel_url(url):
    """True si la URL apunta a la página de un canal (no VOD ni clip)."""
    text = normalize_twitch_url(url)
    if not is_twitch_url(text):
        return False
    lower = text.lower().split('?', 1)[0].rstrip('/')
    if 'clips.twitch.tv' in lower:
        return False
    if '/videos/' in lower or lower.endswith('/videos'):
        return False
    if re.search(r'/clip(/|$)', lower):
        return False
    parsed = urlparse(text)
    path = (parsed.path or '').strip('/')
    parts = [segment for segment in path.split('/') if segment]
    if len(parts) != 1:
        return False
    reserved = {'directory', 'downloads', 'jobs', 'p', 'settings', 'subscriptions', 'videos', 'clip'}
    return parts[0].lower() not in reserved


def is_twitch_vod_url(url):
    """True si la URL apunta a un VOD de Twitch."""
    text = normalize_twitch_url(url).lower()
    return is_twitch_url(text) and '/videos/' in text


def is_twitch_offline_error(exc):
    text = str(exc or '').lower()
    return 'not currently live' in text or 'channel is offline' in text or 'is offline' in text


def normalize_twitch_channel_input(text):
    """Convierte texto pegado o nombre suelto en login de canal."""
    raw = (text or '').strip()
    if not raw:
        return ''
    if is_twitch_url(raw):
        if is_twitch_vod_url(raw) or not is_twitch_channel_url(raw):
            parsed = twitch_display_name_from_url(raw)
            if parsed and not parsed.startswith('VOD '):
                return parsed
            return ''
        return twitch_display_name_from_url(raw) or ''
    return raw.lstrip('@').strip().strip('/')


def _twitch_videos_ydl_attempts(playlistend):
    browser = preferred_twitch_browser()
    attempts = []
    if os.path.exists(twitch_cookies_file_path()):
        attempts.append(twitch_ydl_opts(
            skip_download=True,
            extract_flat=True,
            playlistend=playlistend,
            quiet=True,
        ))
    if browser:
        attempts.append(twitch_ydl_opts(
            skip_download=True,
            extract_flat=True,
            playlistend=playlistend,
            quiet=True,
            use_cookiefile=False,
            cookie_browser=browser,
        ))
    attempts.append(twitch_ydl_opts(
        skip_download=True,
        extract_flat=True,
        playlistend=playlistend,
        quiet=True,
        use_cookiefile=False,
    ))
    return attempts


def _parse_twitch_vod_entry(entry):
    if not entry:
        return None
    vod_url = entry.get('url') or entry.get('webpage_url') or entry.get('id')
    if vod_url and not str(vod_url).startswith('http'):
        vod_url = f'https://www.twitch.tv/videos/{vod_url}'
    if not vod_url or '/videos/' not in str(vod_url).lower():
        return None
    title = plain_display_text(entry.get('title') or '', 'Twitch')
    duration = entry.get('duration')
    try:
        duration = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
    vod_id = str(entry.get('id') or '')
    if not vod_id and '/videos/' in str(vod_url):
        vod_id = str(vod_url).rstrip('/').split('/')[-1]
    return {
        'url': normalize_twitch_url(vod_url),
        'title': title or f'VOD {vod_id or "Twitch"}',
        'duration': duration,
        'id': vod_id,
    }


def fetch_twitch_channel_vods(channel, limit=30):
    """Lista VODs recientes de un canal. Devuelve (videos, channel_name)."""
    import yt_dlp

    channel = plain_display_text(normalize_twitch_channel_input(channel), '').strip()
    if not channel:
        return [], ''
    limit = max(5, min(int(limit or 30), 50))
    page = f'https://www.twitch.tv/{channel}/videos'
    last_error = None
    for ydl_opts in _twitch_videos_ydl_attempts(limit):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(page, download=False)
            entries = list((info or {}).get('entries') or [])
            if not entries and info:
                entries = [info]
            videos = []
            seen = set()
            for entry in entries:
                item = _parse_twitch_vod_entry(entry)
                if not item or item['url'] in seen:
                    continue
                seen.add(item['url'])
                videos.append(item)
                if len(videos) >= limit:
                    break
            channel_name = plain_display_text(
                (info or {}).get('channel') or (info or {}).get('uploader') or channel,
                channel,
            )
            return videos, channel_name
        except Exception as exc:
            last_error = exc
            print(f'[Twitch] No se pudo listar VOD de {channel}: {exc}')
    if last_error:
        raise last_error
    return [], channel


def probe_twitch_channel_live(channel):
    """Comprueba si un canal emite en directo. Devuelve dict live/url/title/channel."""
    import yt_dlp

    channel = plain_display_text(normalize_twitch_channel_input(channel), '').strip()
    if not channel:
        return {'live': False, 'channel': '', 'url': '', 'title': ''}
    url = f'https://www.twitch.tv/{channel}'
    offline = False
    last_error = None
    for ydl_opts in _twitch_videos_ydl_attempts(1):
        opts = dict(ydl_opts)
        opts.pop('extract_flat', None)
        opts.pop('playlistend', None)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if info and info.get('is_live'):
                title = plain_display_text(info.get('title') or '', '')
                return {
                    'live': True,
                    'channel': channel,
                    'url': url,
                    'title': title or channel,
                }
            return {'live': False, 'channel': channel, 'url': url, 'title': ''}
        except Exception as exc:
            last_error = exc
            if is_twitch_offline_error(exc):
                offline = True
                break
    if offline:
        return {'live': False, 'channel': channel, 'url': url, 'title': ''}
    if last_error:
        print(f'[Twitch] No se pudo comprobar directo de {channel}: {last_error}')
    return {'live': False, 'channel': channel, 'url': url, 'title': ''}


def fetch_twitch_latest_vod(channel):
    """Devuelve el VOD más reciente de un canal, o None."""
    videos, _channel = fetch_twitch_channel_vods(channel, limit=1)
    if not videos:
        return None
    item = videos[0]
    return {
        'url': item['url'],
        'title': item.get('title') or '',
        'channel': plain_display_text(normalize_twitch_channel_input(channel), ''),
    }


def twitch_history_id(url):
    text = normalize_twitch_url(url).lower()
    if not text:
        return ''
    text = text.split('?', 1)[0].rstrip('/')
    return text


def twitch_cookies_file_path():
    return TWITCH_COOKIES_PATH


def _twitch_cookie_load_hint(exc):
    return _cookie_load_hint(exc).replace('YouTube', 'Twitch')


def _twitch_cookie_domain_ok(domain):
    host = (domain or '').lstrip('.').lower()
    return any(host == item or host.endswith('.' + item) for item in _TWITCH_COOKIE_DOMAINS)


def _jar_from_browser_cookie3_twitch(name, loader, cookie_file=None):
    if cookie_file:
        return loader(cookie_file=cookie_file, domain_name='twitch.tv')
    return loader(domain_name='twitch.tv')


def _jar_has_live_twitch_login(cookies):
    now = int(time.time())
    for cookie in cookies or []:
        name = getattr(cookie, 'name', '') or ''
        value = getattr(cookie, 'value', '') or ''
        if name not in _TWITCH_AUTH_COOKIES or not value:
            continue
        domain = (getattr(cookie, 'domain', '') or '').lower()
        if 'twitch' not in domain:
            continue
        exp = _normalize_cookie_expiry(getattr(cookie, 'expires', None)) or 0
        if exp == 0 or exp >= now:
            return True
    return False


def _twitch_cookie_keep(cookie, now=None):
    name = getattr(cookie, 'name', '') or ''
    value = getattr(cookie, 'value', '') or ''
    domain = getattr(cookie, 'domain', '') or ''
    if not name or not value:
        return False
    if not _twitch_cookie_domain_ok(domain):
        return False
    exp = _normalize_cookie_expiry(getattr(cookie, 'expires', None))
    if exp is not None and exp < int(now or time.time()):
        return False
    return True


def load_twitch_login_jar():
    """Prueba navegadores hasta encontrar login de Twitch vigente."""
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
            jar = _jar_from_browser_cookie3_twitch(name, loader, cookie_file=readable)
        except TypeError:
            try:
                jar = loader(domain_name='twitch.tv')
            except Exception as exc:
                notes.append(f'{name}: {_twitch_cookie_load_hint(exc)}')
                continue
        except Exception as exc:
            notes.append(f'{name}: {_twitch_cookie_load_hint(exc)}')
            continue
        finally:
            if readable and readable != cookie_file:
                for path in (readable, readable + '-wal', readable + '-shm'):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        if jar and _jar_has_live_twitch_login(jar):
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
            notes.append(f'{name} (yt-dlp): {_twitch_cookie_load_hint(exc)}')
            continue
        if jar and _jar_has_live_twitch_login(jar):
            return jar, name, notes
    return None, None, notes


def preferred_twitch_browser():
    _jar, source, _notes = load_twitch_login_jar()
    if source:
        return source
    configured = app_config.get_cookie_browser()
    return configured if configured and configured != 'auto' else 'firefox'


def inspect_twitch_session(path=None):
    path = path or twitch_cookies_file_path()
    now = int(time.time())
    if not os.path.isfile(path) or os.path.getsize(path) < 20:
        return {'ok': False, 'label': 'caducada', 'reason': 'no hay twitch_cookies.txt'}
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
                if 'twitch' not in domain.lower():
                    continue
                if name not in _TWITCH_AUTH_COOKIES or not value:
                    continue
                has_auth = True
                exp = _normalize_cookie_expiry(expiry) or 0
                if exp > 0 and exp < now:
                    expired_auth = True
    except OSError:
        return {'ok': False, 'label': 'caducada', 'reason': 'no se pudo leer twitch_cookies.txt'}
    if not has_auth:
        return {'ok': False, 'label': 'caducada', 'reason': 'no hay cookies de login'}
    if expired_auth:
        return {'ok': False, 'label': 'caducada', 'reason': 'cookies caducadas'}
    return {'ok': True, 'label': 'OK', 'reason': ''}


def twitch_auth_blocked(exc):
    text = str(exc or '').lower()
    return any(marker in text for marker in _TWITCH_AUTH_ERROR_MARKERS)


def twitch_auth_help():
    return (
        'Twitch pide iniciar sesión o la emisión es solo para suscriptores.\n'
        'Inicia sesión en twitch.tv (Firefox en Windows) y pulsa «Reexportar cookies».'
    )


def _cookie_header_from_twitch_file():
    path = twitch_cookies_file_path()
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
                if 'twitch' not in domain.lower() or not name or not value:
                    continue
                parts.append(f'{name}={value}')
    except OSError:
        return None
    return '; '.join(parts) if parts else None


def twitch_ydl_opts(**extra):
    """Opciones yt-dlp para Twitch (sin extractor_args de YouTube)."""
    extra.pop('extractor_args', None)
    use_cookiefile = extra.pop('use_cookiefile', True)
    cookie_browser = extra.pop('cookie_browser', None)
    opts = youtube_ydl_opts(use_cookiefile=False, silent=True, **extra)
    opts.pop('extractor_args', None)
    headers = dict(opts.get('http_headers') or {})
    headers.setdefault('Referer', 'https://www.twitch.tv/')
    headers.setdefault('Origin', 'https://www.twitch.tv')
    opts['http_headers'] = headers
    cookies_path = twitch_cookies_file_path()
    if cookie_browser:
        opts['cookiesfrombrowser'] = (cookie_browser,)
    elif use_cookiefile and os.path.exists(cookies_path):
        opts['cookiefile'] = cookies_path
    return opts


def twitch_favorite_url(url):
    """URL habitual para favoritos: canal en directo si la entrada es un canal."""
    text = normalize_twitch_url(url)
    if not text:
        return ''
    lower = text.lower()
    if '/videos/' in lower or 'clips.twitch.tv' in lower or '/clip/' in lower:
        return text
    channel = twitch_display_name_from_url(text)
    if channel:
        return f'https://www.twitch.tv/{channel}'
    return text


def twitch_format_selector(max_height=None):
    return youtube_format_selector(app_config.effective_twitch_quality(max_height))


def _info_subscriber_only(info):
    if not info:
        return False
    avail = str(info.get('availability') or '').lower()
    return 'subscriber' in avail


def _ydl_used_cookies(ydl_opts):
    if not ydl_opts:
        return False
    if ydl_opts.get('cookiefile') or ydl_opts.get('cookiesfrombrowser'):
        return True
    return False


def twitch_loading_detail(stream, url=''):
    stream = stream or {}
    parts = []
    channel = plain_display_text(stream.get('channel') or twitch_display_name_from_url(url), '')
    if channel:
        parts.append(f'Canal: {channel}')
    title = plain_display_text(stream.get('title') or '', '')
    if title and title not in ('Twitch', channel):
        parts.append(title)
    if stream.get('is_live'):
        parts.append('En directo')
    else:
        parts.append('VOD')
    try:
        resume_s = float(stream.get('resume_s') or 0)
    except (TypeError, ValueError):
        resume_s = 0
    if resume_s >= app_config.IPTV_RESUME_MIN_S:
        parts.append(f'Reanudando desde {app_config.format_iptv_clock(resume_s)}')
    quality = app_config.twitch_quality_label(app_config.effective_twitch_quality())
    parts.append(f'Calidad: {quality}')
    if stream.get('used_cookies'):
        parts.append('Con cookies de sesión')
    if stream.get('subscriber_only'):
        if stream.get('used_cookies'):
            parts.append('Canal suscriptor detectado')
        else:
            parts.append('Solo suscriptores')
    return plain_ui_line(' · '.join(parts))


def _enrich_twitch_stream(stream, info, url, used_cookies=False):
    if not stream:
        return stream
    stream['channel'] = plain_display_text(
        (info or {}).get('channel') or (info or {}).get('uploader') or twitch_display_name_from_url(url),
        '',
    )
    stream['used_cookies'] = bool(used_cookies)
    stream['subscriber_only'] = _info_subscriber_only(info)
    return stream


def _protocol_of(fmt):
    return (fmt.get('protocol') or '').lower()


def pick_twitch_stream(info, max_height=None):
    """Elige un stream HLS o progresivo que VLC pueda abrir."""
    if not info:
        return None
    url = info.get('url')
    if url and info.get('vcodec', 'none') not in ('none', '', None):
        headers = dict(info.get('http_headers') or {})
        return {
            'url': url,
            'headers': headers,
            'duration': info.get('duration'),
            'title': info.get('title') or info.get('uploader') or '',
            'is_live': bool(info.get('is_live')),
        }

    formats = list(info.get('formats') or [])
    headers = dict(info.get('http_headers') or {})
    preferred = app_config.effective_twitch_quality(max_height)
    if preferred <= 0:
        preferred = 10000

    def is_playable(fmt):
        if not fmt.get('url'):
            return False
        if fmt.get('vcodec', 'none') in ('none', '', None):
            return False
        proto = _protocol_of(fmt)
        if 'dash' in proto or proto == 'http_dash_segments':
            return False
        return True

    def is_hls(fmt):
        proto = _protocol_of(fmt)
        target = fmt.get('url') or ''
        return 'm3u8' in proto or '.m3u8' in target

    def is_progressive(fmt):
        acodec = fmt.get('acodec') or 'none'
        vcodec = fmt.get('vcodec') or 'none'
        return acodec not in ('none', '') and vcodec not in ('none', '')

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
        if is_hls(fmt):
            score += 60
        elif is_progressive(fmt):
            score += 30
        candidates.append((score, fmt))

    if not candidates:
        return None

    _, best = max(candidates, key=lambda item: item[0])
    fmt_headers = dict(best.get('http_headers') or headers)
    fmt_headers.setdefault('Referer', 'https://www.twitch.tv/')
    fmt_headers.setdefault('Origin', 'https://www.twitch.tv')
    return {
        'url': best['url'],
        'headers': fmt_headers,
        'duration': info.get('duration'),
        'title': info.get('title') or info.get('uploader') or '',
        'is_live': bool(info.get('is_live')),
    }


def extract_twitch_stream(url, max_height=None):
    """Extrae URL jugable y metadatos con yt-dlp."""
    import yt_dlp

    format_sel = twitch_format_selector(max_height)
    browser = preferred_twitch_browser()
    attempts = []
    if os.path.exists(twitch_cookies_file_path()):
        attempts.append(twitch_ydl_opts(skip_download=True, format=format_sel))
    if browser:
        attempts.append(twitch_ydl_opts(
            skip_download=True,
            format=format_sel,
            use_cookiefile=False,
            cookie_browser=browser,
        ))
    attempts.extend([
        twitch_ydl_opts(skip_download=True, format=format_sel, use_cookiefile=False),
        twitch_ydl_opts(skip_download=True, format='best', use_cookiefile=False),
    ])
    last_error = None
    for ydl_opts in attempts:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream = pick_twitch_stream(info, max_height=max_height)
                if stream and stream.get('url'):
                    stream['headers'] = _headers_for_vlc(stream.get('headers'), url)
                    if not stream.get('title'):
                        stream['title'] = info.get('title') or info.get('uploader') or 'Twitch'
                    stream['is_live'] = bool(stream.get('is_live') or info.get('is_live'))
                    if stream.get('duration') is None:
                        stream['duration'] = info.get('duration')
                    return _enrich_twitch_stream(stream, info, url, used_cookies=_ydl_used_cookies(ydl_opts))
        except Exception as exc:
            last_error = exc
            print(f"[Twitch] Error al extraer stream: {exc}")
    if last_error:
        raise last_error
    return None


def _headers_for_vlc(headers, page_url):
    merged = dict(headers or {})
    merged.setdefault(
        'User-Agent',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    )
    merged.setdefault('Referer', page_url or 'https://www.twitch.tv/')
    merged.setdefault('Origin', 'https://www.twitch.tv')
    cookie = merged.get('Cookie') or merged.get('cookie') or _cookie_header_from_twitch_file()
    if cookie:
        merged['Cookie'] = cookie
    return merged


class TwitchHandler:
    def __init__(self, video_player):
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
        from twitch_chat import TwitchChatPanel
        self._chat = TwitchChatPanel(self)

    def session_view(self):
        info = inspect_twitch_session()
        if self._session_override == 'caducada':
            info = {
                'ok': False,
                'label': 'caducada',
                'reason': self._session_override_reason or info.get('reason') or 'Twitch pide iniciar sesión',
            }
        return info

    def notify_session(self):
        info = self.session_view()

        def apply():
            player = self.video_player
            refresh = getattr(player, 'update_twitch_session_ui', None)
            if refresh:
                refresh(info)

        self._ui_after(apply)

    def notify_chat_ui(self):
        def apply():
            player = self.video_player
            refresh = getattr(player, 'update_twitch_chat_ui', None)
            if refresh:
                refresh()

        self._ui_after(apply)

    def toggle_chat(self):
        chat = getattr(self, '_chat', None)
        if chat:
            chat.toggle()

    def open_chat(self):
        chat = getattr(self, '_chat', None)
        if chat:
            chat.open()

    def close_chat(self, notify_ui=True):
        chat = getattr(self, '_chat', None)
        if chat:
            chat.close(notify_ui=notify_ui)

    def mark_session_from_error(self, exc):
        if not twitch_auth_blocked(exc):
            self.notify_session()
            return
        self._session_override = 'caducada'
        self._session_override_reason = 'Twitch pide iniciar sesión o suscripción'
        print('[Twitch] Sesión caducada o emisión restringida. Reexporta las cookies del navegador.')
        self.notify_session()

    def reexport_twitch_cookies(self):
        path = self.export_cookies_from_browser(silent=False)
        if path:
            self._session_override = None
            self._session_override_reason = ''
        self.notify_session()
        info = self.session_view()
        if path and info.get('ok'):
            messagebox.showinfo(
                'Cookies de Twitch',
                'Cookies reexportadas. Sesión Twitch: OK.',
            )
        elif path:
            messagebox.showwarning(
                'Cookies de Twitch',
                'Se escribieron cookies, pero no hay login vigente.\n'
                'Abre twitch.tv en Firefox, inicia sesión y vuelve a reexportar.',
            )
        return path

    def export_cookies_from_browser(self, output_path=None, silent=False):
        def _error(message):
            if silent:
                print(f"[Twitch] {message}")
            else:
                messagebox.showerror('Error', message)

        def _warn(message):
            if silent:
                print(f"[Twitch] {message}")
            else:
                messagebox.showwarning('Cookies de Twitch', message)

        try:
            from http.cookiejar import MozillaCookieJar
        except ImportError:
            _error('No se pudo cargar el soporte de cookies de Python.')
            return None

        if output_path is None:
            output_path = twitch_cookies_file_path()

        cookies, source, notes = load_twitch_login_jar()
        if not cookies:
            lines = [
                'No hay sesión de Twitch vigente que se pueda leer.',
                'En Windows, Chrome y Edge suelen cifrar las cookies; lo fiable es Firefox.',
                'Inicia sesión en twitch.tv, cierra el navegador y pulsa Reexportar cookies.',
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
                if not _twitch_cookie_keep(cookie, now=now):
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
            if not _jar_has_live_twitch_login(cj):
                _warn(
                    'Las cookies del navegador no incluyen un login de Twitch vigente.\n'
                    'No se ha sobrescrito twitch_cookies.txt.'
                )
                return None
            cj.save(ignore_discard=True, ignore_expires=True)
            print(f'[Twitch] Cookies exportadas desde {source}')
            return output_path
        except Exception:
            _error('No se pudieron guardar las cookies del navegador.')
            return None

    def prompt_twitch_url(self, url=None):
        if url is None:
            ensure = getattr(self.video_player, 'ensure_window', None)
            if ensure:
                ensure()
            url = ask_string(
                self.video_player.window,
                'Cargar Twitch',
                'Introduce la URL de Twitch (canal, VOD o clip):',
            )
        if url:
            player = getattr(self, 'video_player', None)
            if player is not None:
                play = getattr(player, 'play_twitch_url', None)
                if play:
                    play(url)
                    return
            self.play_twitch_url(url)

    def play_twitch_url(self, url, title=None, show_progress=None):
        url = normalize_twitch_url(url)
        if not is_twitch_url(url):
            messagebox.showerror('Twitch', 'La URL no parece ser de Twitch.')
            return

        player = self.video_player
        save_yt = getattr(player, 'save_youtube_resume', None)
        if save_yt:
            save_yt()
        save_iptv = getattr(player, 'save_iptv_resume', None)
        if save_iptv:
            save_iptv()
        save_tw = getattr(player, 'save_twitch_resume', None)
        if save_tw:
            save_tw()

        player._playing_youtube = False
        player._playing_twitch = True
        player._yt_standalone = True
        player.clear_youtube_subtitles()

        display_title = twitch_default_title(url, title)
        app_config.remember_twitch_watch(url, title=display_title)
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
        is_channel = is_twitch_channel_url(url)
        loading_status = (
            'Comprobando si el canal está en directo…'
            if is_channel
            else 'Obteniendo emisión de Twitch…'
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
                    print(f"[Twitch] No se pudieron exportar cookies: {exc}")
                stream = extract_twitch_stream(url)
            except Exception as exc:
                err = exc
                if is_channel and is_twitch_offline_error(exc):
                    offline = True

            def cont():
                if gen != self._play_gen:
                    return
                if offline:
                    self.hide_loading()
                    channel = twitch_display_name_from_url(url)
                    latest = fetch_twitch_latest_vod(channel)
                    self._offer_offline_channel(url, channel, latest)
                    return
                if err or not stream:
                    self.hide_loading()
                    if err:
                        self.mark_session_from_error(err)
                    detail = str(err or 'No se pudo obtener el stream.')
                    extra = ''
                    if err and twitch_auth_blocked(err):
                        extra = f'\n\n{twitch_auth_help()}'
                    messagebox.showerror(
                        'Twitch',
                        f'No se pudo reproducir la emisión.\n\n{detail}{extra}',
                    )
                    webbrowser.open(url)
                    return
                if is_channel and stream.get('is_live'):
                    self._set_loading_status('Canal en directo — abriendo…')
                    self._set_loading_detail(twitch_loading_detail(stream, url))
                self._begin_playback(url, stream, show_progress=show_progress)

            self._ui_after(cont)

        threading.Thread(target=work, daemon=True).start()

    def _offer_offline_channel(self, url, channel, latest=None):
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
                'Twitch — canal offline',
                message + '\n\n'
                'Sí = reproducir el último VOD\n'
                'No = abrir el canal en el navegador\n'
                'Cancelar = cerrar',
            )
            if choice is True:
                self.play_twitch_url(vod_url, title=vod_title or None)
            elif choice is False:
                webbrowser.open(url)
            return
        if messagebox.askyesno(
            'Twitch — canal offline',
            message + '\n\n¿Abrir el canal en el navegador?',
        ):
            webbrowser.open(url)

    def _sync_sidebar_title(self, url, title):
        title = plain_display_text(title, '')
        if not title or not url or title in ('Twitch', url):
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

    def _begin_playback(self, url, stream, show_progress=None):
        player = self.video_player
        self._current_stream = stream
        title = plain_display_text(stream.get('title'), '')
        if not title or title == 'Twitch':
            title = twitch_default_title(url)
        if title:
            self._set_loading_title(title)
            app_config.remember_twitch_watch(url, title=title)
            self._sync_sidebar_title(url, title)

        detail = twitch_loading_detail(stream, url)
        self._set_loading_detail(detail)

        is_live = bool(stream.get('is_live'))
        if show_progress is None:
            show_progress = not is_live

        resume_s = 0.0
        if not is_live:
            resume_s = app_config.twitch_resume_seconds(url, stream.get('duration'))
            if resume_s >= app_config.IPTV_RESUME_MIN_S:
                stream = dict(stream)
                stream['resume_s'] = resume_s
                detail = twitch_loading_detail(stream, url)
                self._set_loading_detail(detail)

        self._set_loading_status('Abriendo el vídeo…')
        print(f"[Twitch] Reproduciendo: {stream['url'][:80]}… live={is_live}")
        if detail:
            print(f"[Twitch] {detail}")

        prepare = getattr(player, '_prepare_web_stream_player', None)
        if prepare:
            prepare()

        def on_fail():
            if is_live:
                self._schedule_live_check(getattr(self, '_live_watch_gen', 0))
            else:
                self.hide_loading()
                messagebox.showerror(
                    'Twitch',
                    'VLC no pudo abrir el stream de Twitch.\n'
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
            self.notify_chat_ui()
            chat = getattr(self, '_chat', None)
            if chat and (chat.is_open() or app_config.get_twitch_chat_auto_open()):
                self.open_chat()
        else:
            self._stop_live_watch()
            self.close_chat()
            self.notify_chat_ui()

    def add_current_to_favorites(self):
        url = self._current_url
        if not url or not is_twitch_url(url):
            messagebox.showinfo('Twitch', 'Reproduce un canal o VOD de Twitch primero.')
            return False
        fav_url = twitch_favorite_url(url)
        stream = self._current_stream or {}
        title = plain_display_text(stream.get('title') or twitch_default_title(url), '')
        channel = plain_display_text(stream.get('channel') or twitch_display_name_from_url(url), '')
        if channel and (not title or title in ('Twitch', url) or title == channel):
            name = channel
        elif title:
            name = title
        else:
            name = twitch_default_title(url)
        add = getattr(self.video_player, 'add_favorite_entry', None)
        if add:
            return add(name, fav_url, notify=True)
        return False

    def _stop_live_watch(self):
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
        if delay_ms is None:
            delay_ms = TWITCH_LIVE_CHECK_MS
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
        if watch_gen != self._live_watch_gen:
            return
        player = self.video_player
        if not getattr(player, '_playing_twitch', False):
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

        stall_limit = max(2, int(TWITCH_LIVE_STALL_S * 1000 / TWITCH_LIVE_CHECK_MS))
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
            reason = 'Renovando enlace HLS (caducidad)'
            self._live_token_refresh_at = time.time() + (25 * 60)

        if need_reconnect:
            if self._live_reconnects >= TWITCH_LIVE_MAX_RECONNECTS:
                print(
                    f'[Twitch] Reconexión abandonada tras {self._live_reconnects} intentos ({reason})'
                )
                self._stop_live_watch()
                return
            self._live_reconnects += 1
            print(
                f'[Twitch] Reconexión {self._live_reconnects}/{TWITCH_LIVE_MAX_RECONNECTS}: {reason}'
            )
            self._reconnect_live(url, watch_gen)
            return

        self._schedule_live_check(watch_gen)

    def _reconnect_live(self, url, watch_gen):
        play_gen = self._play_gen

        def work():
            err = None
            stream = None
            try:
                stream = extract_twitch_stream(url)
            except Exception as exc:
                err = exc

            def cont():
                if watch_gen != self._live_watch_gen or play_gen != self._play_gen:
                    return
                if err or not stream:
                    print(f'[Twitch] Reconexión fallida: {err or "sin stream"}')
                    self._schedule_live_check(watch_gen)
                    return
                self._live_bytes_prev = 0
                self._live_stall_ticks = 0
                self._live_last_ok = time.time()
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
                detail = twitch_loading_detail(stream, url)
                print(f'[Twitch] Reconectado: {stream["url"][:80]}…')
                if detail:
                    print(f'[Twitch] {detail}')
                self._schedule_live_check(watch_gen)

            self._ui_after(cont)

        threading.Thread(target=work, daemon=True).start()

    def cancel_pending_play(self):
        self._stop_live_watch()
        self._new_play_gen()
        self._current_stream = None
        self.close_chat()
        self.hide_loading()

    def _new_play_gen(self):
        self._play_gen = getattr(self, '_play_gen', 0) + 1
        return self._play_gen

    def _ui_after(self, fn, delay_ms=0):
        window = getattr(self.video_player, 'window', None)
        if not window:
            return
        try:
            window.after(delay_ms, fn)
        except tk.TclError:
            pass

    def hide_loading(self):
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
        frame = getattr(self, '_loading_frame', None)
        try:
            return bool(frame and frame.winfo_exists())
        except tk.TclError:
            return False

    def _show_loading(self, status, title=None):
        player = self.video_player
        parent = getattr(player, 'player_frame', None) or getattr(player, 'video_frame', None)
        video_frame = getattr(player, 'video_frame', None)
        if not parent or not video_frame:
            return
        if self._loading_alive():
            self._set_loading_status(status)
            if title:
                self._set_loading_title(title)
            return

        self.hide_loading()
        colors = get_colors()
        overlay = tk.Frame(parent, bg='#000000', highlightthickness=0)
        try:
            overlay.place(in_=video_frame, relx=0, rely=0, relwidth=1, relheight=1)
            overlay.lift(video_frame)
        except tk.TclError:
            overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
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
            text=plain_display_text(title, 'Twitch'),
            font=get_font(14, 'bold'),
            bg=colors['surface'],
            fg=colors['text'],
            wraplength=420,
            justify='center',
        )
        title_label.pack(pady=(0, 10))
        self._loading_title_label = title_label

        status_label = tk.Label(
            card,
            text=plain_ui_line(status),
            font=get_font(11),
            bg=colors['surface'],
            fg=colors['text_muted'],
            wraplength=420,
            justify='center',
        )
        status_label.pack()
        self._loading_status_label = status_label

        detail_label = tk.Label(
            card,
            text='',
            font=get_font(10),
            bg=colors['surface'],
            fg=colors['text_muted'],
            wraplength=420,
            justify='center',
        )
        detail_label.pack(pady=(8, 0))
        self._loading_detail_label = detail_label

        from ui_layout import bind_loading_card
        bind_loading_card(overlay, card, [title_label, status_label, detail_label])

    def _set_loading_detail(self, text):
        label = getattr(self, '_loading_detail_label', None)
        if not label:
            return
        try:
            label.configure(text=plain_ui_line(text or ''))
        except tk.TclError:
            pass

    def _set_loading_status(self, text):
        label = getattr(self, '_loading_status_label', None)
        if not label:
            return
        try:
            label.configure(text=plain_ui_line(text))
        except tk.TclError:
            pass

    def _set_loading_title(self, text):
        label = getattr(self, '_loading_title_label', None)
        if not label:
            return
        try:
            label.configure(text=plain_display_text(text, 'Twitch'))
        except tk.TclError:
            pass
