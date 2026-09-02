"""Estilo de subtítulos de texto (VLC freetype). No aplica a DVB/PGS de imagen."""

import sys

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

PREVIEW_SAMPLE_TEXT = 'Así se verán los subtítulos'
PREVIEW_CANVAS_BG = '#101010'
_PREVIEW_FONT_PX = {
    0: 15,
    18: 13,
    24: 16,
    32: 20,
    44: 26,
}
_PREVIEW_OUTLINE_RADIUS = {
    0: 0,
    1: 1,
    2: 2,
}


def preview_font_family():
    """Familia tipográfica legible en Linux y Windows."""
    if sys.platform == 'win32':
        return 'Segoe UI'
    if sys.platform == 'darwin':
        return 'Helvetica Neue'
    return 'DejaVu Sans'


def preview_font_size(size):
    """Tamaño en píxeles para la vista previa Tk."""
    cfg = normalize_subtitle_style({'subtitle_size': size})
    return _PREVIEW_FONT_PX.get(cfg['subtitle_size'], 16)


def vlc_palette_hex(value, fallback='#FFFFFF'):
    """Color de la paleta VLC más cercano, como hex #RRGGBB."""
    color = nearest_vlc_palette_color(value, fallback)
    red = (color >> 16) & 0xFF
    green = (color >> 8) & 0xFF
    blue = color & 0xFF
    return f'#{red:02X}{green:02X}{blue:02X}'


def _hex_to_rgb(value, fallback=(255, 255, 255)):
    """Uso interno: convierte #RRGGBB a tupla RGB."""
    text = normalize_hex_color(value, '#FFFFFF')[1:]
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except (TypeError, ValueError):
        return fallback


def _rgb_to_hex(red, green, blue):
    """Uso interno: tupla RGB a #RRGGBB."""
    return f'#{red:02X}{green:02X}{blue:02X}'


def blend_over_background(foreground, background, alpha_0_255):
    """Mezcla un color sobre el fondo del vídeo simulado."""
    alpha = max(0, min(255, int(alpha_0_255 or 0))) / 255.0
    fr, fg, fb = _hex_to_rgb(foreground)
    br, bg, bb = _hex_to_rgb(background, _hex_to_rgb(PREVIEW_CANVAS_BG))
    red = int(round(fr * alpha + br * (1.0 - alpha)))
    green = int(round(fg * alpha + bg * (1.0 - alpha)))
    blue = int(round(fb * alpha + bb * (1.0 - alpha)))
    return _rgb_to_hex(red, green, blue)


def preview_outline_offsets(outline):
    """Desplazamientos para simular contorno en un Canvas Tk."""
    radius = _PREVIEW_OUTLINE_RADIUS.get(_clamp_int(outline, 0, 2, 1), 1)
    if radius <= 0:
        return ()
    offsets = []
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            offsets.append((dx, dy))
    return tuple(offsets)


def draw_subtitle_preview(canvas, style=None, sample_text=None):
    """Pinta una muestra de subtítulo en un Canvas (Preferencias)."""
    if canvas is None:
        return
    try:
        canvas.delete('all')
    except Exception:
        return
    cfg = normalize_subtitle_style(style)
    text = str(sample_text or PREVIEW_SAMPLE_TEXT).strip() or PREVIEW_SAMPLE_TEXT
    try:
        width = max(120, int(canvas.winfo_width()))
        height = max(80, int(canvas.winfo_height()))
    except tk.TclError:
        width, height = 420, 110
    if width <= 1:
        width = 420
    if height <= 1:
        height = 110

    canvas_bg = PREVIEW_CANVAS_BG
    try:
        canvas.configure(bg=canvas_bg)
    except tk.TclError:
        pass

    text_hex = vlc_palette_hex(cfg['subtitle_color'])
    outline_hex = vlc_palette_hex(cfg['subtitle_outline_color'], '#000000')
    bg_hex = vlc_palette_hex(cfg['subtitle_bg_color'], '#000000')
    text_fill = blend_over_background(text_hex, canvas_bg, cfg['subtitle_opacity'])
    outline_fill = blend_over_background(outline_hex, canvas_bg, cfg['subtitle_opacity'])
    box_fill = blend_over_background(bg_hex, canvas_bg, cfg['subtitle_bg_opacity'])

    font_size = preview_font_size(cfg['subtitle_size'])
    font = (preview_font_family(), font_size, 'bold')
    margin = max(0, int(cfg['subtitle_margin']))
    y = max(font_size + 8, height - 16 - min(margin // 2, 36))
    x = width // 2
    text_width = max(80, width - 32)

    outline_ids = []
    offsets = preview_outline_offsets(cfg['subtitle_outline'])
    if offsets:
        for dx, dy in offsets:
            try:
                outline_ids.append(canvas.create_text(
                    x + dx,
                    y + dy,
                    text=text,
                    font=font,
                    fill=outline_fill,
                    anchor='s',
                    width=text_width,
                    justify='center',
                ))
            except tk.TclError:
                pass

    try:
        text_id = canvas.create_text(
            x,
            y,
            text=text,
            font=font,
            fill=text_fill,
            anchor='s',
            width=text_width,
            justify='center',
        )
    except tk.TclError:
        return

    boxes = [canvas.bbox(text_id)]
    for item_id in outline_ids:
        try:
            boxes.append(canvas.bbox(item_id))
        except tk.TclError:
            pass
    boxes = [box for box in boxes if box]
    if not boxes:
        return
    x1 = min(box[0] for box in boxes)
    y1 = min(box[1] for box in boxes)
    x2 = max(box[2] for box in boxes)
    y2 = max(box[3] for box in boxes)

    if cfg['subtitle_bg_opacity'] > 0:
        pad_x = 12
        pad_y = 6
        rect_id = None
        try:
            rect_id = canvas.create_rectangle(
                x1 - pad_x,
                y1 - pad_y,
                x2 + pad_x,
                y2 + pad_y,
                fill=box_fill,
                outline='',
            )
            canvas.tag_lower(rect_id)
        except tk.TclError:
            rect_id = None
    else:
        rect_id = None

    for item_id in outline_ids:
        try:
            if rect_id is not None:
                canvas.tag_raise(item_id, rect_id)
            else:
                canvas.tag_raise(item_id)
        except tk.TclError:
            pass
    try:
        canvas.tag_raise(text_id)
    except tk.TclError:
        pass


# Import tkinter only for preview drawing (evita coste si no se usa).
try:
    import tkinter as tk
except ImportError:  # pragma: no cover
    tk = None


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
