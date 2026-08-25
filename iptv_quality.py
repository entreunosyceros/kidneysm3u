"""Variantes SD/HD/FHD del mismo canal en un M3U. Solo URLs que ya están en la lista."""

import re
import unicodedata

_QUALITY_RULES = (
    (re.compile(r'\b(uhd|4k|2160p)\b', re.I), 'UHD', 2160),
    (re.compile(r'\b(fhd|1080p|full\s*hd)\b', re.I), 'FHD', 1080),
    (re.compile(r'(?<![a-z])hd(?![a-z])|\b720p\b', re.I), 'HD', 720),
    (re.compile(r'\b(sd|480p|576p|360p)\b', re.I), 'SD', 480),
)
_STRIP_RE = re.compile(
    r'[\[\(\|._-]*(?:uhd|4k|fhd|full\s*hd|(?<![a-z])hd(?![a-z])|sd|'
    r'2160p|1080p|720p|480p|576p|360p|hevc|h\.?265|h\.?264|50fps|60fps)[\]\)]*',
    re.I,
)
_JUNK_RE = re.compile(r'[\s_|.-]+')

IPTV_QUALITY_CHOICES = (
    (0, 'Mejor'),
    (2160, 'UHD'),
    (1080, 'FHD'),
    (720, 'HD'),
    (480, 'SD'),
)


def detect_iptv_quality(name, group=''):
    """Devuelve (etiqueta, altura) o ('', 0) si no hay marca SD/HD/FHD."""
    text = f'{name or ''} {group or ''}'
    for pattern, label, height in _QUALITY_RULES:
        if pattern.search(text):
            return label, height
    return '', 0


def strip_quality_tokens(name):
    text = unicodedata.normalize('NFKC', name or '')
    text = _STRIP_RE.sub(' ', text)
    text = _JUNK_RE.sub(' ', text)
    return text.strip(' |-_').strip()


def channel_match_key(name, tvg_id=''):
    tvg_id = str(tvg_id or '').strip().lower()
    if tvg_id:
        return ('id', tvg_id)
    base = strip_quality_tokens(name).casefold()
    return ('name', base) if base else ('name', (name or '').casefold())


def names_are_same_channel(left, right):
    if not left or not right:
        return False
    if left == right:
        return True
    return strip_quality_tokens(left).casefold() == strip_quality_tokens(right).casefold()


def collect_channel_variants(entries):
    """Agrupa [(name, url, group, tvg_id), ...] por canal lógico."""
    groups = {}
    for index, entry in enumerate(entries or []):
        if len(entry) < 2:
            continue
        name = entry[0]
        url = (entry[1] or '').strip()
        group = entry[2] if len(entry) > 2 else ''
        tvg_id = entry[3] if len(entry) > 3 else ''
        if not url:
            continue
        key = channel_match_key(name, tvg_id)
        label, height = detect_iptv_quality(name, group)
        item = {
            'index': index,
            'name': name,
            'url': url,
            'group': group or '',
            'tvg_id': tvg_id or '',
            'label': label or 'Auto',
            'height': height or 720,
        }
        bucket = groups.setdefault(key, [])
        if any(existing['url'] == url for existing in bucket):
            continue
        bucket.append(item)
    return groups


def variants_for_channel(entries, name, url='', tvg_id=''):
    """Mismo canal por tvg-id o por nombre sin SD/HD/FHD. No inventa URLs."""
    url = (url or '').strip()
    tvg_id = str(tvg_id or '').strip().lower()
    found = []
    seen = set()
    for index, entry in enumerate(entries or []):
        if len(entry) < 2:
            continue
        item_name = entry[0]
        item_url = (entry[1] or '').strip()
        item_group = entry[2] if len(entry) > 2 else ''
        item_tvg = str(entry[3] if len(entry) > 3 else '').strip().lower()
        if not item_url or item_url in seen:
            continue
        same = False
        if tvg_id and item_tvg and item_tvg == tvg_id:
            same = True
        elif names_are_same_channel(item_name, name):
            same = True
        elif url and item_url == url:
            same = True
        if not same:
            continue
        seen.add(item_url)
        label, height = detect_iptv_quality(item_name, item_group)
        found.append({
            'index': index,
            'name': item_name,
            'url': item_url,
            'group': item_group or '',
            'tvg_id': item_tvg,
            'label': label or 'Auto',
            'height': height or 720,
        })
    found.sort(key=lambda item: item['height'])
    return found


def pick_iptv_variant(variants, preferred=0, current_url=''):
    if not variants:
        return None
    unique = []
    seen = set()
    for item in variants:
        if item['url'] in seen:
            continue
        seen.add(item['url'])
        unique.append(item)
    if len(unique) == 1:
        return unique[0]
    preferred = int(preferred or 0)
    if preferred <= 0:
        return max(unique, key=lambda item: item['height'])
    at_or_below = [item for item in unique if item['height'] <= preferred]
    if at_or_below:
        return max(at_or_below, key=lambda item: item['height'])
    return min(unique, key=lambda item: item['height'])


def fallback_urls(entries, name, url, group='', backup_entries=None):
    """Otras URLs con el mismo nombre (otro grupo o lista de respaldo). No inventa rutas."""
    url = (url or '').strip()
    name = name or ''
    ordered = []
    seen = {url} if url else set()

    def consider(item_name, item_url, item_group, source, exact):
        item_url = (item_url or '').strip()
        if not item_url or item_url in seen:
            return
        if exact:
            if item_name != name:
                return
        elif not names_are_same_channel(item_name, name):
            return
        seen.add(item_url)
        ordered.append({
            'name': item_name,
            'url': item_url,
            'group': item_group or '',
            'source': source,
        })

    rows = list(entries or [])
    for exact in (True, False):
        for entry in rows:
            if len(entry) < 2:
                continue
            item_group = entry[2] if len(entry) > 2 else ''
            consider(entry[0], entry[1], item_group, 'lista', exact)
        for entry in backup_entries or []:
            if len(entry) < 2:
                continue
            item_group = entry[2] if len(entry) > 2 else ''
            consider(entry[0], entry[1], item_group, 'respaldo', exact)
    return ordered


def iptv_quality_label(height):
    try:
        height = int(height)
    except (TypeError, ValueError):
        height = 0
    for value, label in IPTV_QUALITY_CHOICES:
        if value == height:
            return label
    return 'Mejor'
