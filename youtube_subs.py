"""Subtítulos de YouTube listos para VLC: ASR original y VTT sin cues superpuestos."""

import json
import os
import re

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

_PREFERRED_LANGS = (
    'es-orig', 'es', 'es-ES', 'es-419',
    'en-orig', 'en', 'en-US', 'en-GB',
)
_SOURCE_EXTS = ('json3', 'srv3', 'vtt', 'srt', 'ttml')
_TRANSLATED_EXTS = ('vtt', 'srv3', 'srt', 'ttml', 'json3')
_VTT_TIME = re.compile(
    r'^(\d{2}:\d{2}(?::\d{2})?\.\d{3})\s+-->\s+(\d{2}:\d{2}(?::\d{2})?\.\d{3})(?:\s+\S.*)?$'
)
_CUE_TAGS = re.compile(
    r'</?c[^>]*>|<c\.[\w.]+>|<\d{2}:\d{2}(?::\d{2})?\.\d{3}>|</?v[^>]*>'
)
_HTML_TAGS = re.compile(r'<[^>]+>')


def _is_orig(code):
    return str(code or '').endswith('-orig')


def _lang_base(code):
    text = str(code or '')
    if text.endswith('-orig'):
        text = text[:-5]
    return text.split('-')[0] if text else ''


def _lang_label(code, kind):
    raw = str(code or '')
    base = raw[:-5] if raw.endswith('-orig') else raw
    name = _YT_LANG_NAMES.get(base) or _YT_LANG_NAMES.get(_lang_base(raw)) or base or raw
    if kind == 'official':
        return name
    if _is_orig(raw):
        return f'{name} (auto)'
    return f'{name} (traducción automática)'


def pick_subtitle_source(entries, translated=False):
    """json3 va bien en el ASR original; con tlang suele quedarse en inglés, mejor VTT."""
    if not entries:
        return None, None, None
    by_ext = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = entry.get('url')
        ext = (entry.get('ext') or '').lower()
        if url and ext:
            by_ext[ext] = url
    order = _TRANSLATED_EXTS if translated else _SOURCE_EXTS
    chosen_ext = next((ext for ext in order if ext in by_ext), None)
    if not chosen_ext:
        return None, None, None
    return by_ext[chosen_ext], chosen_ext, by_ext.get('vtt')


def filename_matches_sub_lang(name, lang):
    """True solo si el archivo es de ese código (no 'es' dentro de 'en-orig')."""
    base = os.path.basename(name or '').lower()
    lang = str(lang or '').lower().strip()
    if not base or not lang:
        return False
    for suffix in ('.vlc.vtt', '.json3', '.srv3', '.ttml', '.vtt', '.srt'):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return base == lang or base.endswith('_' + lang) or base.endswith('.' + lang)


def ensure_caption_tlang(url, lang):
    """Añade tlang al timedtext de una traducción. No registra la URL."""
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    lang = str(lang or '').strip()
    if not url or not lang or _is_orig(lang):
        return url
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    host = (parsed.netloc or '').lower()
    path = (parsed.path or '').lower()
    if 'youtube' not in host and 'timedtext' not in path:
        return url
    qs = parse_qs(parsed.query, keep_blank_values=True)
    orig = (qs.get('lang') or [None])[-1]
    if orig and _lang_base(orig) == _lang_base(lang):
        return url
    current = (qs.get('tlang') or [None])[-1]
    if current == lang:
        return url
    qs['tlang'] = [lang]
    query = urlencode({key: values[-1] for key, values in qs.items()})
    return urlunparse(parsed._replace(query=query))


def collect_youtube_subs(info):
    """Español primero (ASR o traducción), luego oficiales y el resto de automáticos."""
    official = info.get('subtitles') or {}
    automatic = info.get('automatic_captions') or {}
    items = []
    seen = set()

    def add(code, entries, kind):
        key = (kind, str(code))
        if key in seen:
            return False
        if kind == 'auto' and not _is_orig(code) and f'{code}-orig' in automatic:
            return False
        translated = kind == 'auto' and not _is_orig(code)
        url, ext, vtt_url = pick_subtitle_source(entries, translated=translated)
        if not url:
            return False
        if translated:
            url = ensure_caption_tlang(url, code)
            if vtt_url:
                vtt_url = ensure_caption_tlang(vtt_url, code)
        seen.add(key)
        items.append({
            'lang': code,
            'kind': kind,
            'label': _lang_label(code, kind),
            'url': url,
            'ext': ext or 'vtt',
            'vtt_url': vtt_url,
        })
        return True

    spanish_orig = [code for code in automatic if _is_orig(code) and _lang_base(code) == 'es']
    other_orig = [code for code in automatic if _is_orig(code) and _lang_base(code) != 'es']
    preferred_index = {code: index for index, code in enumerate(_PREFERRED_LANGS)}
    other_orig.sort(key=lambda code: (preferred_index.get(code, 100), code))

    for code in spanish_orig:
        add(code, automatic.get(code), 'auto')
    for code in ('es', 'es-ES', 'es-419'):
        if code in official:
            add(code, official.get(code), 'official')
    for code in ('es', 'es-ES', 'es-419'):
        if code in automatic:
            add(code, automatic.get(code), 'auto')
    orig_added = 0
    for code in other_orig:
        if add(code, automatic.get(code), 'auto'):
            orig_added += 1
        if orig_added >= 6:
            break

    for code in _PREFERRED_LANGS:
        if code in official:
            add(code, official.get(code), 'official')
    for code, entries in official.items():
        if code == 'live_chat':
            continue
        add(code, entries, 'official')
        if sum(1 for item in items if item['kind'] == 'official') >= 10:
            break

    for code in _PREFERRED_LANGS:
        if _is_orig(code) or code not in automatic:
            continue
        add(code, automatic.get(code), 'auto')

    return items[:20]


def _stamp_to_ms(stamp):
    parts = stamp.split(':')
    if len(parts) == 3:
        hours, minutes, rest = parts
    elif len(parts) == 2:
        hours = '0'
        minutes, rest = parts
    else:
        return 0
    seconds, _, millis = rest.partition('.')
    try:
        return (
            int(hours) * 3600000
            + int(minutes) * 60000
            + int(seconds) * 1000
            + int((millis + '000')[:3])
        )
    except (TypeError, ValueError):
        return 0


def _ms_to_stamp(ms):
    ms = max(0, int(ms))
    hours, rem = divmod(ms, 3600000)
    minutes, rem = divmod(rem, 60000)
    seconds, millis = divmod(rem, 1000)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}'


def _clean_cue_text(text):
    text = _CUE_TAGS.sub('', text or '')
    text = _HTML_TAGS.sub('', text)
    text = text.replace('\u200b', '')
    lines = [' '.join(line.split()) for line in text.splitlines()]
    return '\n'.join(line for line in lines if line).strip()


def _dedupe_and_deoverlap(cues):
    grouped = {}
    order = []
    for start, end, text in cues:
        if not text:
            continue
        key = (start, end)
        previous = grouped.get(key)
        if previous is None:
            grouped[key] = text
            order.append(key)
            continue
        if '<' in previous and '<' not in text:
            grouped[key] = text
        elif len(text) > len(previous):
            grouped[key] = text
    cleaned = []
    for start, end in order:
        text = _clean_cue_text(grouped[(start, end)])
        if text:
            cleaned.append([start, max(start + 80, end), text])
    cleaned.sort(key=lambda item: (item[0], item[1]))
    merged = []
    for start, end, text in cleaned:
        if merged and merged[-1][2] == text and start <= merged[-1][1] + 80:
            merged[-1][1] = max(merged[-1][1], end)
            continue
        merged.append([start, end, text])
    for index, cue in enumerate(merged[:-1]):
        nxt = merged[index + 1]
        if cue[1] > nxt[0]:
            cue[1] = max(cue[0] + 80, nxt[0])
    return [cue for cue in merged if cue[1] > cue[0]]


def _cues_to_vtt(cues):
    lines = ['WEBVTT', '']
    for index, (start, end, text) in enumerate(cues, start=1):
        lines.append(str(index))
        lines.append(f'{_ms_to_stamp(start)} --> {_ms_to_stamp(end)}')
        lines.append(text)
        lines.append('')
    return '\n'.join(lines)


def sanitize_youtube_vtt(raw):
    """Quita karaoke, settings y cues superpuestos que VLC deja congelados."""
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')
    text = (raw or '').replace('\r\n', '\n').replace('\r', '\n')
    if not text.strip():
        return 'WEBVTT\n'
    blocks = text.split('\n\n')
    cues = []
    for block in blocks:
        lines = [line for line in block.split('\n') if line.strip() != '']
        if not lines:
            continue
        header = None
        payload = []
        for line in lines:
            match = _VTT_TIME.match(line.strip())
            if match and header is None:
                header = match
                continue
            if header is not None:
                payload.append(line)
        if header is None:
            continue
        start = _stamp_to_ms(header.group(1))
        end = _stamp_to_ms(header.group(2))
        body = _clean_cue_text('\n'.join(payload))
        if body:
            cues.append([start, end, body])
    return _cues_to_vtt(_dedupe_and_deoverlap(cues))


def json3_to_vtt(raw):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')
    try:
        data = json.loads(raw or '{}')
    except json.JSONDecodeError:
        return 'WEBVTT\n'
    cues = []
    for event in data.get('events') or []:
        if not isinstance(event, dict):
            continue
        segs = event.get('segs') or []
        text = ''.join(
            str(seg.get('utf8') or '') for seg in segs if isinstance(seg, dict)
        )
        text = _clean_cue_text(text.replace('\n', ' '))
        if not text:
            continue
        try:
            start = int(event.get('tStartMs') or 0)
        except (TypeError, ValueError):
            start = 0
        try:
            duration = int(event.get('dDurationMs') or 0)
        except (TypeError, ValueError):
            duration = 0
        end = start + duration if duration > 0 else start + 2000
        cues.append([start, end, text])
    return _cues_to_vtt(_dedupe_and_deoverlap(cues))


def _looks_like_json(raw):
    sample = raw.lstrip()[:1]
    return sample in '{['


def subtitle_bytes_to_vtt(raw, ext=None):
    ext = (ext or '').lower().lstrip('.')
    if isinstance(raw, bytes):
        text = raw.decode('utf-8', errors='replace')
    else:
        text = raw or ''
    if ext == 'json3' or (not ext and _looks_like_json(text)):
        return json3_to_vtt(text)
    if ext in ('srt',):
        return sanitize_youtube_vtt('WEBVTT\n\n' + text.replace(',', '.'))
    return sanitize_youtube_vtt(text)


def prepare_subtitle_for_vlc(path, ext=None):
    """Escribe un VTT simple junto al archivo original. No registra URLs."""
    if not path or not os.path.isfile(path):
        return None
    ext = (ext or os.path.splitext(path)[1].lstrip('.') or 'vtt').lower()
    try:
        with open(path, 'rb') as handle:
            raw = handle.read()
    except OSError:
        return None
    vtt = subtitle_bytes_to_vtt(raw, ext=ext)
    if '-->' not in vtt:
        return None
    dest = path
    if not dest.lower().endswith('.vlc.vtt'):
        dest = os.path.splitext(path)[0] + '.vlc.vtt'
    try:
        with open(dest, 'w', encoding='utf-8') as handle:
            handle.write(vtt)
    except OSError:
        return None
    return dest
