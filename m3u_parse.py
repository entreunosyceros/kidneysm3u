"""Lectura de listas M3U/M3U8 de IPTV (incluye #EXTVLCOPT y URLs sin extensión)."""

import re
import urllib.error
import urllib.request
from urllib.parse import urljoin

_URL_RE = re.compile(r'^(https?|rtmp|rtsp)://', re.I)
_IMAGE_EXT = re.compile(r'\.(png|jpe?g|gif|webp|bmp|ico|svg)$', re.I)
_CONTAINER_EXT = re.compile(r'\.(mkv|mp4|avi|mp3|aac|mpd)(\?.*)?$', re.I)
_HLS_EXT = re.compile(r'\.m3u8?(\?.*)?$', re.I)
# Sin espacios: VLC parte las opciones por blanco y un UA de Firefox rompe el stream.
IPTV_USER_AGENT = 'VLC/3.0.21'


_GROUP_RE = re.compile(r'group-title="([^"]*)"', re.I)


def _channel_name(extinf):
    if ',' in extinf:
        return extinf.split(',', 1)[1].strip() or extinf.strip()
    return extinf.strip()


def _channel_group(extinf):
    match = _GROUP_RE.search(extinf or '')
    return (match.group(1).strip() if match else '') or ''


def parse_m3u_channels(content):
    """Devuelve [(nombre, url, grupo), ...] ignorando comentarios entre EXTINF y la URL."""
    if isinstance(content, bytes):
        content = _decode_bytes(content)
    lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    entries = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF'):
            name = _channel_name(line)
            group = _channel_group(line)
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if nxt.startswith('#EXTINF'):
                    break
                if not nxt or nxt.startswith('#'):
                    i += 1
                    continue
                if _IMAGE_EXT.search(nxt.partition('?')[0]):
                    i += 1
                    continue
                if _URL_RE.match(nxt) or nxt.startswith(('udp:', 'rtp:', 'mms:')):
                    entries.append((name, nxt, group))
                    i += 1
                    break
                i += 1
        else:
            i += 1
    return entries


def parse_m3u_entries(content):
    """Devuelve [(nombre, url), ...] ignorando comentarios entre EXTINF y la URL."""
    return [(name, url) for name, url, _group in parse_m3u_channels(content)]


def decode_m3u_bytes(raw):
    return _decode_bytes(raw)


def _decode_bytes(raw):
    if isinstance(raw, str):
        return raw
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def describe_iptv_url(url):
    """Resumen sin credenciales: series/mkv, directo/sin-ext, etc."""
    path = (url or '').partition('?')[0]
    segs = [seg for seg in path.split('/') if seg]
    kind = next((seg for seg in segs if seg in ('live', 'movie', 'series')), 'directo')
    last = segs[-1] if segs else ''
    ext = last.rsplit('.', 1)[-1] if '.' in last else 'sin-ext'
    return f'{kind}/{ext}'


def classify_iptv_url(url):
    """container | hls | mpegts según la extensión de la URL del M3U."""
    path = (url or '').partition('?')[0]
    if _HLS_EXT.search(path):
        return 'hls'
    if _CONTAINER_EXT.search(path):
        return 'container'
    return 'mpegts'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def follow_iptv_redirect(url, timeout=6):
    """Un 302 del panel (sin descargar el vídeo ni visitar el nodo)."""
    url = (url or '').strip()
    if not url:
        return None
    request = urllib.request.Request(
        url,
        headers={'User-Agent': IPTV_USER_AGENT, 'Accept': '*/*'},
        method='GET',
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            loc = response.headers.get('Location')
            return urljoin(url, loc) if loc else None
    except urllib.error.HTTPError as err:
        if err.code in (301, 302, 303, 307, 308):
            loc = err.headers.get('Location')
            return urljoin(url, loc) if loc else None
        return None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def iptv_upstream_candidates(url):
    """Solo la URL del M3U. Reescribir el 302 en el host del panel provoca HTTP 400."""
    url = (url or '').strip()
    return [url] if url else []


def probe_iptv_url(url, timeout=5):
    """True si el servidor entrega vídeo/playlist, no HTML de error."""
    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': IPTV_USER_AGENT,
            'Accept': '*/*',
            'Connection': 'close',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if getattr(response, 'status', 200) >= 400:
                return False
            chunk = response.read(512)
            content_type = (response.headers.get('Content-Type') or '').lower()
            if not chunk:
                return False
            if chunk[:1] == b'\x47' or b'#EXTM3U' in chunk:
                return True
            if chunk[4:8] == b'ftyp' or chunk[:4] == b'\x1aE\xdf\xa3':
                return True
            if 'video' in content_type or 'mpegurl' in content_type or 'mp2t' in content_type:
                return True
            if b'<html' in chunk.lower() or b'<!doctype' in chunk.lower():
                return False
            if 'octet-stream' in content_type:
                return True
            return len(chunk) >= 32
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return False
