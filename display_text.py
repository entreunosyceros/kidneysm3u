"""Texto legible en la interfaz Tk: sin emojis ni símbolos que la fuente no pinta bien."""

import re
import unicodedata

# Emoji, pictogramas y adornos frecuentes en títulos de canales / YouTube.
_EMOJI_RE = re.compile(
    '[\U0001F300-\U0001FAFF'
    '\U00002600-\U000027BF'
    '\U0001F600-\U0001F64F'
    '\U0001F680-\U0001F6FF'
    '\U0001F1E0-\U0001F1FF'
    '\U00002702-\U000027B0'
    '\U000024C2-\U0001F251'
    '\U0000FE00-\U0000FE0F'
    '\U0000200D'
    '\U0000200C'
    ']+',
    flags=re.UNICODE,
)
_WS_RE = re.compile(r'[^\S\n]+')


def plain_display_text(value, fallback=''):
    """Devuelve texto plano apto para listas, etiquetas y tooltips del reproductor."""
    text = unicodedata.normalize('NFKC', str(value or ''))
    if not text:
        return fallback
    text = _EMOJI_RE.sub('', text)
    parts = []
    for ch in text:
        if ch == '\ufffd':
            continue
        cat = unicodedata.category(ch)
        if cat in ('Cc', 'Cs', 'Co', 'Cn'):
            if ch in '\t\n\r':
                parts.append(ch)
            continue
        if cat in ('So', 'Sk') and ord(ch) > 0x2400:
            continue
        parts.append(ch)
    result = _WS_RE.sub(' ', ''.join(parts))
    result = re.sub(r' *\n *', '\n', result).strip()
    return result or fallback


def plain_ui_line(value, fallback=''):
    """Una línea de interfaz: sin emojis y con puntos suspensivos ASCII."""
    text = plain_display_text(value, fallback)
    return text.replace('\u2026', '...')


def truncate_ui_text(value, limit, fallback=''):
    """Texto truncado para la interfaz, con puntos suspensivos ASCII."""
    text = plain_display_text(value, fallback)
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + '...'


def busy_status_text(message, percent=None, fallback='Cargando...'):
    """Texto del overlay de carga M3U/IPTV, con porcentaje legible si hay."""
    text = plain_ui_line(message, fallback)
    if percent is None:
        return text
    try:
        pct = max(0, min(100, int(round(float(percent)))))
    except (TypeError, ValueError):
        return text
    return f'{text}  {pct} %'
