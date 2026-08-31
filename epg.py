"""EPG sencillo: ahora / a continuación a partir de XMLTV (tvg-id)."""

import gzip
import os
import re
import ssl
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from io import BytesIO

from display_text import plain_display_text, truncate_ui_text
from urllib.parse import unquote
from urllib.request import Request, urlopen

from m3u_parse import IPTV_USER_AGENT

MAX_EPG_BYTES = 80 * 1024 * 1024
MAX_PROGRAMMES = 24
WINDOW_PAST = timedelta(hours=1)
WINDOW_FUTURE = timedelta(hours=8)
DEFAULT_DURATION = 30 * 60
FETCH_TIMEOUT = 90
_XMLTV_DT = re.compile(r'^(\d{14})(?:\s*([+-]\d{2}):?(\d{2}))?')
_HOSTISH = re.compile(r'^(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:[:/?]|$)', re.I)
_SPACE = re.compile(r'\s+')


def _norm_epg_name(text):
    return _SPACE.sub(' ', (text or '').strip()).lower()


class Programme:
    __slots__ = ('start', 'stop', 'title')

    def __init__(self, start, stop, title):
        self.start = start
        self.stop = stop
        self.title = title or ''

    @property
    def clock(self):
        try:
            return datetime.fromtimestamp(self.start).strftime('%H:%M')
        except (OSError, OverflowError, ValueError):
            return ''


class Guide:
    def __init__(self, programmes=None, icons=None):
        self._by_id = programmes or {}
        self._icons = icons or {}

    def channel_count(self):
        return len({key for key in self._by_id if key and key != key.lower()}) or len(self._by_id)

    def _items(self, tvg_id):
        key = (tvg_id or '').strip()
        if not key:
            return []
        return self._by_id.get(key) or self._by_id.get(key.lower()) or []

    def now_next(self, tvg_id, now=None):
        items = self._items(tvg_id)
        if not items:
            return None, None
        now = time_now() if now is None else now
        current = None
        nxt = None
        for prog in items:
            if prog.stop <= now:
                continue
            if prog.start <= now < prog.stop:
                current = prog
                continue
            if prog.start >= now:
                nxt = prog
                break
        return current, nxt

    def now_title(self, tvg_id, now=None, limit=36):
        current, _nxt = self.now_next(tvg_id, now=now)
        if not current:
            return ''
        return _short(current.title, limit)

    def programmes_between(self, tvg_id, start, stop):
        items = self._items(tvg_id)
        if not items or stop <= start:
            return []
        found = []
        for prog in items:
            if prog.stop <= start or prog.start >= stop:
                continue
            found.append(prog)
        return found

    def icon(self, tvg_id):
        key = (tvg_id or '').strip()
        if not key:
            return ''
        return self._icons.get(key) or self._icons.get(key.lower()) or ''


def time_now():
    return datetime.now().timestamp()


def parse_xmltv_datetime(value):
    text = (value or '').strip()
    match = _XMLTV_DT.match(text)
    if not match:
        return None
    stamp, off_h, off_m = match.group(1), match.group(2), match.group(3)
    try:
        naive = datetime.strptime(stamp, '%Y%m%d%H%M%S')
    except ValueError:
        return None
    if off_h is None:
        try:
            return naive.timestamp()
        except (OSError, OverflowError, ValueError):
            return None
    try:
        hours = int(off_h)
        minutes = int(off_m or 0)
        offset = timezone(timedelta(hours=hours, minutes=minutes if hours >= 0 else -minutes))
        return naive.replace(tzinfo=offset).timestamp()
    except (OSError, OverflowError, ValueError):
        return None


def format_now_next(current, nxt):
    lines = []
    if current:
        title = _short(current.title)
        clock = current.clock
        lines.append(f'Ahora: {clock} {title}'.strip())
    if nxt:
        title = _short(nxt.title)
        clock = nxt.clock
        lines.append(f'A continuación: {clock} {title}'.strip())
    return '\n'.join(lines)


def _short(text, limit=80):
    text = plain_display_text(text)
    text = re.sub(r'\s+', ' ', text or '').strip()
    return truncate_ui_text(text, limit)


def _local_name(tag):
    if not tag:
        return ''
    return tag.split('}', 1)[-1]


def _programme_title(elem):
    chosen = ''
    for child in elem:
        if _local_name(child.tag) != 'title':
            continue
        text = (child.text or '').strip()
        if not text:
            continue
        lang = (child.get('lang') or '').lower()
        if lang.startswith('es'):
            return text
        if not chosen:
            chosen = text
    return chosen


def parse_xmltv(source, wanted_ids, now=None, wanted_names=None):
    """Lee XMLTV y deja la ventana ahora→unas horas de los tvg-id o nombres pedidos."""
    wanted = {str(item).strip() for item in wanted_ids if item and str(item).strip()}
    wanted_l = {item.lower() for item in wanted}
    name_index = {}
    for item in list(wanted_names or []) + list(wanted):
        item = str(item).strip()
        if not item:
            continue
        name_index.setdefault(_norm_epg_name(item), []).append(item)
    if not wanted and not name_index:
        return Guide()
    now = time_now() if now is None else now
    start_min = now - WINDOW_PAST.total_seconds()
    stop_max = now + WINDOW_FUTURE.total_seconds()
    collected = defaultdict(list)
    icons = {}
    aliases = {}
    try:
        for _event, elem in ET.iterparse(source, events=('end',)):
            tag = _local_name(elem.tag)
            if tag == 'channel':
                channel = (elem.get('id') or '').strip()
                names = []
                icon_src = ''
                for child in elem:
                    local = _local_name(child.tag)
                    if local == 'display-name':
                        text = (child.text or '').strip()
                        if text:
                            names.append(text)
                    elif local == 'icon' and not icon_src:
                        icon_src = (child.get('src') or '').strip()
                hit = bool(channel) and (channel in wanted or channel.lower() in wanted_l)
                extra = []
                if not hit and name_index:
                    for name in names:
                        extra.extend(name_index.get(_norm_epg_name(name)) or [])
                    hit = bool(extra)
                if hit and channel:
                    wanted.add(channel)
                    wanted_l.add(channel.lower())
                    if icon_src:
                        icons[channel] = icon_src
                        icons.setdefault(channel.lower(), icon_src)
                    for label in names + extra:
                        aliases[label] = channel
                        aliases[label.lower()] = channel
                        if icon_src:
                            icons.setdefault(label, icon_src)
                            icons.setdefault(label.lower(), icon_src)
                elem.clear()
                continue
            if tag != 'programme':
                continue
            channel = (elem.get('channel') or '').strip()
            if channel not in wanted and channel.lower() not in wanted_l:
                elem.clear()
                continue
            start = parse_xmltv_datetime(elem.get('start'))
            stop = parse_xmltv_datetime(elem.get('stop'))
            if start is None:
                elem.clear()
                continue
            if stop is None or stop <= start:
                if start < start_min:
                    elem.clear()
                    continue
                stop = (now + DEFAULT_DURATION) if start <= now else (start + DEFAULT_DURATION)
            if stop <= start_min or start >= stop_max:
                elem.clear()
                continue
            title = _programme_title(elem)
            collected[channel].append(Programme(start, stop, title))
            elem.clear()
    except ET.ParseError:
        if not collected:
            return Guide()
    result = {}
    for key, items in collected.items():
        items.sort(key=lambda item: item.start)
        items = items[:MAX_PROGRAMMES]
        result[key] = items
        lower = key.lower()
        if lower not in result:
            result[lower] = items
    for alias, channel in aliases.items():
        items = result.get(channel) or result.get(channel.lower())
        if items and alias not in result:
            result[alias] = items
    return Guide(result, icons)


def _read_limited(handle, limit=MAX_EPG_BYTES):
    chunks = []
    total = 0
    while True:
        chunk = handle.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ValueError('EPG demasiado grande')
        chunks.append(chunk)
    return b''.join(chunks)


def _maybe_gunzip(raw):
    data = raw or b''
    for _ in range(2):
        if data[:2] != b'\x1f\x8b':
            break
        data = gzip.decompress(data)
    return data


def _looks_like_html(raw):
    head = (raw or b'').lstrip()[:180].lower()
    return head.startswith(b'<html') or head.startswith(b'<!doctype html')


def normalize_epg_source(value):
    """URL http(s), file:// o ruta local. Sin el esquema, un host pasa a https://."""
    text = (value or '').strip().strip('\'"')
    if not text:
        return ''
    if text.startswith(('http://', 'https://', 'file://')):
        return text
    if os.path.isfile(text):
        return os.path.abspath(text)
    if text.startswith('//'):
        return 'https:' + text
    if _HOSTISH.match(text):
        host = text.split('/', 1)[0]
        port = host.rsplit(':', 1)[-1] if ':' in host else ''
        scheme = 'http' if port == '80' else 'https'
        return f'{scheme}://{text}'
    return text


def _urlopen_bytes(request):
    try:
        with urlopen(request, timeout=FETCH_TIMEOUT) as response:
            return _maybe_gunzip(_read_limited(response))
    except Exception as exc:
        reason = getattr(exc, 'reason', None)
        if not isinstance(exc, ssl.SSLError) and not isinstance(reason, ssl.SSLError):
            raise
        ctx = ssl._create_unverified_context()
        with urlopen(request, timeout=FETCH_TIMEOUT, context=ctx) as response:
            return _maybe_gunzip(_read_limited(response))


def _fetch_http(url):
    last_error = None
    for user_agent in (IPTV_USER_AGENT, 'Mozilla/5.0'):
        request = Request(
            url,
            headers={
                'User-Agent': user_agent,
                'Accept': 'application/xml, text/xml, application/gzip, */*',
            },
        )
        try:
            raw = _urlopen_bytes(request)
        except Exception as exc:
            last_error = exc
            continue
        if raw and not _looks_like_html(raw):
            return raw
    if last_error is not None:
        raise last_error
    return b''


def _fetch_bytes(source):
    source = normalize_epg_source(source)
    if not source:
        return b''
    if source.startswith(('http://', 'https://')):
        return _fetch_http(source)
    path = source
    if source.startswith('file://'):
        path = unquote(source[7:])
        if path.startswith('//'):
            path = path[1:]
    if os.path.isfile(path):
        with open(path, 'rb') as handle:
            return _maybe_gunzip(_read_limited(handle))
    return b''


def load_guide(urls, wanted_ids, wanted_names=None):
    """Descarga y mezcla hasta 3 XMLTV. No registra las URLs (pueden llevar token)."""
    wanted = [item for item in wanted_ids if item]
    names = [item for item in (wanted_names or []) if item]
    if not urls or (not wanted and not names):
        return Guide()
    merged = {}
    icons = {}
    parsed_any = False
    for source in list(urls)[:3]:
        source = (source or '').strip()
        if not source:
            continue
        try:
            raw = _fetch_bytes(source)
            if not raw or _looks_like_html(raw):
                print('[EPG] No se pudo leer una guía XMLTV (formato)')
                continue
            guide = parse_xmltv(BytesIO(raw), wanted, wanted_names=names)
            parsed_any = True
        except Exception as exc:
            print(f'[EPG] No se pudo leer una guía XMLTV ({type(exc).__name__})')
            continue
        merged.update(guide._by_id)
        for key, src in (guide._icons or {}).items():
            if key not in icons:
                icons[key] = src
        if len({k.lower() for k in merged if k}) >= len(set(item.lower() for item in wanted)):
            break
    if parsed_any and not merged:
        print('[EPG] Guía leída, pero no coincidió con los canales de la lista')
    return Guide(merged, icons)


def load_guide_from_text(xml_text, wanted_ids, now=None, wanted_names=None):
    raw = xml_text.encode('utf-8') if isinstance(xml_text, str) else xml_text
    return parse_xmltv(BytesIO(raw), wanted_ids, now=now, wanted_names=wanted_names)
