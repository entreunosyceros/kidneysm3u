"""EPG sencillo: ahora / a continuación a partir de XMLTV (tvg-id)."""

import gzip
import os
import re
import ssl
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import unquote
from urllib.request import Request, urlopen

from m3u_parse import IPTV_USER_AGENT

MAX_EPG_BYTES = 80 * 1024 * 1024
MAX_PROGRAMMES = 4
WINDOW_PAST = timedelta(hours=2)
WINDOW_FUTURE = timedelta(hours=18)
DEFAULT_DURATION = 30 * 60
_XMLTV_DT = re.compile(r'^(\d{14})(?:\s*([+-]\d{2}):?(\d{2}))?')
_HOSTISH = re.compile(r'^(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:[:/?]|$)', re.I)


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
    def __init__(self, programmes=None):
        self._by_id = programmes or {}

    def channel_count(self):
        return len(self._by_id)

    def now_next(self, tvg_id, now=None):
        key = (tvg_id or '').strip()
        if not key:
            return None, None
        items = self._by_id.get(key) or self._by_id.get(key.lower())
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
    text = re.sub(r'\s+', ' ', text or '').strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + '…'


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


def parse_xmltv(source, wanted_ids, now=None):
    """Lee XMLTV y deja solo ahora/próximo de los tvg-id pedidos."""
    wanted = {item.strip() for item in wanted_ids if item and str(item).strip()}
    wanted_l = {item.lower() for item in wanted}
    if not wanted:
        return Guide()
    now = time_now() if now is None else now
    start_min = now - WINDOW_PAST.total_seconds()
    stop_max = now + WINDOW_FUTURE.total_seconds()
    collected = defaultdict(list)
    try:
        for _event, elem in ET.iterparse(source, events=('end',)):
            if _local_name(elem.tag) != 'programme':
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
            if stop <= now or start >= stop_max:
                elem.clear()
                continue
            title = _programme_title(elem)
            key = channel
            bucket = collected[key]
            if len(bucket) < MAX_PROGRAMMES:
                bucket.append(Programme(start, stop, title))
            elem.clear()
    except ET.ParseError:
        if not collected:
            return Guide()
    result = {}
    for key, items in collected.items():
        items.sort(key=lambda item: item.start)
        result[key] = items
        lower = key.lower()
        if lower not in result:
            result[lower] = items
    return Guide(result)


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
        return 'https://' + text
    return text


def _urlopen_bytes(request):
    try:
        with urlopen(request, timeout=45) as response:
            return _maybe_gunzip(_read_limited(response))
    except Exception as exc:
        reason = getattr(exc, 'reason', None)
        if not isinstance(exc, ssl.SSLError) and not isinstance(reason, ssl.SSLError):
            raise
        ctx = ssl._create_unverified_context()
        with urlopen(request, timeout=45, context=ctx) as response:
            return _maybe_gunzip(_read_limited(response))


def _fetch_http(url):
    last_error = None
    for user_agent in (IPTV_USER_AGENT, 'Mozilla/5.0'):
        request = Request(
            url,
            headers={
                'User-Agent': user_agent,
                'Accept': '*/*',
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


def load_guide(urls, wanted_ids):
    """Descarga y mezcla hasta 3 XMLTV. No registra las URLs (pueden llevar token)."""
    wanted = [item for item in wanted_ids if item]
    if not urls or not wanted:
        return Guide()
    merged = {}
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
            guide = parse_xmltv(BytesIO(raw), wanted)
            parsed_any = True
        except Exception as exc:
            print(f'[EPG] No se pudo leer una guía XMLTV ({type(exc).__name__})')
            continue
        merged.update(guide._by_id)
        if len(merged) >= len(set(item.lower() for item in wanted)):
            break
    if parsed_any and not merged:
        print('[EPG] Guía leída, pero ningún tvg-id de la lista coincidió')
    return Guide(merged)


def load_guide_from_text(xml_text, wanted_ids, now=None):
    raw = xml_text.encode('utf-8') if isinstance(xml_text, str) else xml_text
    return parse_xmltv(BytesIO(raw), wanted_ids, now=now)
