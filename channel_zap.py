"""Zap por número: 1 es el primer canal de la lista visible."""

ZAP_TIMEOUT_MS = 1400
MAX_ZAP_DIGITS = 5


def zap_max_digits(count):
    """Zap max digits."""
    if count <= 0:
        return 1
    return max(1, min(MAX_ZAP_DIGITS, len(str(int(count)))))


def zap_event_digit(event):
    """Dígito de teclado o teclado numérico. Vacío si no es un número."""
    keysym = str(getattr(event, 'keysym', None) or '')
    if keysym.startswith('KP_') and len(keysym) == 4 and keysym[-1].isdigit():
        return keysym[-1]
    if len(keysym) == 1 and keysym.isdigit():
        return keysym
    char = str(getattr(event, 'char', None) or '')
    if len(char) == 1 and char.isdigit():
        return char
    return ''


def zap_buffer_append(buffer, digit, count=0):
    """Zap buffer append."""
    if digit not in '0123456789':
        return str(buffer or '')
    text = str(buffer or '') + digit
    limit = zap_max_digits(count)
    if len(text) > limit:
        text = text[-limit:]
    return text


def zap_buffer_backspace(buffer):
    """Zap buffer backspace."""
    return str(buffer or '')[:-1]


def zap_number(buffer):
    """Zap number."""
    text = str(buffer or '').strip()
    if not text.isdigit():
        return None
    return int(text, 10)


def zap_visible_index(number, count):
    """Número 1-based → índice 0-based de la lista visible, o None."""
    try:
        count = int(count)
    except (TypeError, ValueError):
        return None
    if number is None or count <= 0:
        return None
    if number < 1 or number > count:
        return None
    return number - 1
