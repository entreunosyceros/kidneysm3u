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

# Valores reales de VLC 3 (--freetype-rel-fontsize / --freetype-outline-thickness).
_VLC_REL_FONT_SIZES = {
    0: 0,
    18: 18,
    24: 16,
    32: 12,
    44: 6,
}
_VLC_OUTLINE_THICKNESS = {
    0: 0,
    1: 2,
    2: 6,
}
# Escala global de subtítulos (--sub-text-scale, 10–500). Complemento en Windows.
_VLC_TEXT_SCALE = {
    0: 0,
    18: 85,
    24: 100,
    32: 130,
    44: 165,
}
# Paleta fija de VLC freetype-color (RGB 0xRRGGBB).
_VLC_COLOR_PALETTE = (
    0,
    8421504,
    12632256,
    16777215,
    8388608,
    16711680,
    16711935,
    16776960,
    8421376,
    32768,
    32896,
    65280,
    8388736,
    128,
    255,
    65535,
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
    """Normaliza hex color."""
    text = str(value or '').strip()
    if text.startswith('#'):
        text = text[1:]
    if len(text) == 3 and all(char in '0123456789abcdefABCDEF' for char in text):
        text = ''.join(char * 2 for char in text)
    if len(text) == 6 and all(char in '0123456789abcdefABCDEF' for char in text):
        return f'#{text.upper()}'
    return fallback


def hex_to_vlc_color(value, fallback='#FFFFFF'):
    """Hex to vlc color."""
    hex_color = normalize_hex_color(value, fallback)[1:]
    return int(hex_color, 16)


def nearest_vlc_palette_color(value, fallback='#FFFFFF'):
    """VLC freetype solo admite una paleta fija; aproxima el color elegido."""
    target = hex_to_vlc_color(value, fallback)
    tr = (target >> 16) & 0xFF
    tg = (target >> 8) & 0xFF
    tb = target & 0xFF
    best = _VLC_COLOR_PALETTE[3]
    best_dist = None
    for color in _VLC_COLOR_PALETTE:
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        dist = (r - tr) ** 2 + (g - tg) ** 2 + (b - tb) ** 2
        if best_dist is None or dist < best_dist:
            best = color
            best_dist = dist
    return best


def vlc_rel_fontsize(size):
    """Vlc rel fontsize."""
    allowed = tuple(item[0] for item in SUBTITLE_SIZES)
    value = _clamp_int(size, 0, 64, 0)
    if value not in allowed:
        value = min(allowed, key=lambda item: abs(item - value))
    return _VLC_REL_FONT_SIZES.get(value, 0)


def vlc_text_scale(size):
    """Escala global de subtítulos para --sub-text-scale."""
    allowed = tuple(item[0] for item in SUBTITLE_SIZES)
    value = _clamp_int(size, 0, 64, 0)
    if value not in allowed:
        value = min(allowed, key=lambda item: abs(item - value))
    return _VLC_TEXT_SCALE.get(value, 0)


def vlc_outline_thickness(outline):
    """Vlc outline thickness."""
    value = _clamp_int(outline, 0, 2, 1)
    return _VLC_OUTLINE_THICKNESS.get(value, 2)


def _clamp_int(value, minimum, maximum, default):
    """Uso interno: clamp int."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def normalize_subtitle_style(data=None):
    """Normaliza subtitle style."""
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
    """Obtiene subtitle style."""
    import app_config
    return normalize_subtitle_style(app_config.load())


def delay_label(tenths):
    """Delay label."""
    value = _clamp_int(tenths, -50, 50, 0)
    seconds = value / 10.0
    if seconds == 0:
        return '0,0 s'
    sign = '+' if seconds > 0 else ''
    text = f'{seconds:.1f}'.replace('.', ',')
    return f'{sign}{text} s'


def opacity_percent(value):
    """Opacity percent."""
    return int(round(_clamp_int(value, 0, 255, 0) * 100 / 255.0))


def percent_to_opacity(percent):
    """Percent to opacity."""
    return int(round(_clamp_int(percent, 0, 100, 0) * 255 / 100.0))


def fingerprint(style=None):
    """Fingerprint."""
    cfg = normalize_subtitle_style(style if style is not None else get_subtitle_style())
    return tuple(sorted(cfg.items()))


def vlc_option_pairs(style=None):
    """Pares nombre=valor para libvlc_new (freetype solo en la instancia, no en media)."""
    cfg = normalize_subtitle_style(style if style is not None else get_subtitle_style())
    pairs = []
    rel = vlc_rel_fontsize(cfg['subtitle_size'])
    if rel:
        pairs.append(('freetype-rel-fontsize', str(rel)))
    scale = vlc_text_scale(cfg['subtitle_size'])
    if scale:
        pairs.append(('sub-text-scale', str(scale)))
    pairs.extend([
        ('freetype-color', str(nearest_vlc_palette_color(cfg['subtitle_color']))),
        ('freetype-opacity', str(cfg['subtitle_opacity'])),
        (
            'freetype-background-color',
            str(nearest_vlc_palette_color(cfg['subtitle_bg_color'], '#000000')),
        ),
        ('freetype-background-opacity', str(cfg['subtitle_bg_opacity'])),
        ('freetype-outline-thickness', str(vlc_outline_thickness(cfg['subtitle_outline']))),
        (
            'freetype-outline-color',
            str(nearest_vlc_palette_color(cfg['subtitle_outline_color'], '#000000')),
        ),
    ])
    return pairs


def vlc_instance_args(style=None):
    """Vlc instance args."""
    return [f'--{name}={value}' for name, value in vlc_option_pairs(style)]


def vlc_media_options(style=None, prefix=':'):
    """Reservado: el estilo freetype va en libvlc_new, no en add_option del media."""
    return []


def apply_spu_delay(player, style=None):
    """Aplica spu delay."""
    if player is None:
        return
    cfg = normalize_subtitle_style(style if style is not None else get_subtitle_style())
    microseconds = int(cfg['subtitle_delay_ds']) * 100000
    try:
        player.video_set_spu_delay(microseconds)
    except Exception:
        pass
