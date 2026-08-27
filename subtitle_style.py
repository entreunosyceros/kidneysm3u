"""Estilo de subtítulos de texto (VLC freetype). No aplica a DVB/PGS de imagen."""

SUBTITLE_SIZES = (
    (0, 'Automático'),
    (18, 'Pequeño'),
    (24, 'Normal'),
    (32, 'Grande'),
    (44, 'Muy grande'),
)
SUBTITLE_OUTLINES = (
    (0, 'Ninguno'),
    (1, 'Fino'),
    (2, 'Grueso'),
)

_DEFAULTS = {
    'subtitle_size': 0,
    'subtitle_color': '#FFFFFF',
    'subtitle_opacity': 255,
    'subtitle_outline': 1,
    'subtitle_outline_color': '#000000',
    'subtitle_bg_color': '#000000',
    'subtitle_bg_opacity': 0,
    'subtitle_margin': 0,
    'subtitle_delay_ds': 0,
}


def normalize_hex_color(value, fallback='#FFFFFF'):
    text = str(value or '').strip()
    if text.startswith('#'):
        text = text[1:]
    if len(text) == 3 and all(char in '0123456789abcdefABCDEF' for char in text):
        text = ''.join(char * 2 for char in text)
    if len(text) == 6 and all(char in '0123456789abcdefABCDEF' for char in text):
        return f'#{text.upper()}'
    return fallback


def hex_to_vlc_color(value, fallback='#FFFFFF'):
    hex_color = normalize_hex_color(value, fallback)[1:]
    return int(hex_color, 16)


def _clamp_int(value, minimum, maximum, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def normalize_subtitle_style(data=None):
    raw = data if isinstance(data, dict) else {}
    allowed_sizes = tuple(item[0] for item in SUBTITLE_SIZES)
    size = _clamp_int(raw.get('subtitle_size', _DEFAULTS['subtitle_size']), 0, 64, 0)
    if size not in allowed_sizes:
        size = min(allowed_sizes, key=lambda item: abs(item - size))
    return {
        'subtitle_size': size,
        'subtitle_color': normalize_hex_color(raw.get('subtitle_color'), '#FFFFFF'),
        'subtitle_opacity': _clamp_int(raw.get('subtitle_opacity'), 40, 255, 255),
        'subtitle_outline': _clamp_int(raw.get('subtitle_outline'), 0, 2, 1),
        'subtitle_outline_color': normalize_hex_color(raw.get('subtitle_outline_color'), '#000000'),
        'subtitle_bg_color': normalize_hex_color(raw.get('subtitle_bg_color'), '#000000'),
        'subtitle_bg_opacity': _clamp_int(raw.get('subtitle_bg_opacity'), 0, 255, 0),
        'subtitle_margin': _clamp_int(raw.get('subtitle_margin'), 0, 150, 0),
        'subtitle_delay_ds': _clamp_int(raw.get('subtitle_delay_ds'), -50, 50, 0),
    }


def get_subtitle_style():
    import app_config
    return normalize_subtitle_style(app_config.load())


def delay_label(tenths):
    value = _clamp_int(tenths, -50, 50, 0)
    seconds = value / 10.0
    if seconds == 0:
        return '0,0 s'
    sign = '+' if seconds > 0 else ''
    text = f'{seconds:.1f}'.replace('.', ',')
    return f'{sign}{text} s'


def opacity_percent(value):
    return int(round(_clamp_int(value, 0, 255, 0) * 100 / 255.0))


def percent_to_opacity(percent):
    return int(round(_clamp_int(percent, 0, 100, 0) * 255 / 100.0))


def fingerprint(style=None):
    cfg = normalize_subtitle_style(style if style is not None else get_subtitle_style())
    return tuple(sorted(cfg.items()))


def vlc_option_pairs(style=None):
    cfg = normalize_subtitle_style(style if style is not None else get_subtitle_style())
    pairs = [
        ('freetype-fontsize', str(cfg['subtitle_size'])),
        ('freetype-color', str(hex_to_vlc_color(cfg['subtitle_color']))),
        ('freetype-opacity', str(cfg['subtitle_opacity'])),
        ('freetype-background-color', str(hex_to_vlc_color(cfg['subtitle_bg_color'], '#000000'))),
        ('freetype-background-opacity', str(cfg['subtitle_bg_opacity'])),
        ('freetype-outline-thickness', str(cfg['subtitle_outline'])),
        ('freetype-outline-color', str(hex_to_vlc_color(cfg['subtitle_outline_color'], '#000000'))),
        ('sub-margin', str(cfg['subtitle_margin'])),
        ('sub-delay', str(cfg['subtitle_delay_ds'])),
    ]
    return pairs


def vlc_instance_args(style=None):
    return [f'--{name}={value}' for name, value in vlc_option_pairs(style)]


def vlc_media_options(style=None, prefix=':'):
    prefix = prefix or ''
    return [f'{prefix}{name}={value}' for name, value in vlc_option_pairs(style)]


def apply_spu_delay(player, style=None):
    if player is None:
        return
    cfg = normalize_subtitle_style(style if style is not None else get_subtitle_style())
    microseconds = int(cfg['subtitle_delay_ds']) * 100000
    try:
        player.video_set_spu_delay(microseconds)
    except Exception:
        pass
