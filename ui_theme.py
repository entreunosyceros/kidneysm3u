"""Tema visual compartido para la interfaz de Kidneys M3U."""

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from tkinter import font as tkfont

from app_paths import resource_dir

_DARK = False
_FONT_FAMILY = 'helvetica'
_FONT_OBJS = {}
_ICON_REF = None
APP_WM_CLASS = 'Kidneysm3u'

PALETTES = {
    'light': {
        'bg': '#f3f5f8',
        'surface': '#ffffff',
        'surface_alt': '#e8edf3',
        'header_bg': '#ffffff',
        'status_bg': '#eef1f5',
        'border': '#d5dde6',
        'text': '#1b2430',
        'text_muted': '#5d6b7a',
        'accent': '#0d9488',
        'accent_hover': '#0f766e',
        'accent_text': '#ffffff',
        'danger': '#dc2626',
        'danger_hover': '#b91c1c',
        'danger_text': '#ffffff',
        'select_bg': '#ccfbf1',
        'select_fg': '#134e4a',
        'progress': '#0d9488',
        'trough': '#e2e8f0',
        'drop_bg': '#f0fdfa',
        'drop_border': '#5eead4',
        'list_bg': '#ffffff',
        'list_fg': '#1b2430',
        'menu_bg': '#ffffff',
        'menu_fg': '#1b2430',
        'menu_active_bg': '#0d9488',
        'menu_active_fg': '#ffffff',
        'entry_bg': '#ffffff',
        'disabled_bg': '#e5e7eb',
        'disabled_fg': '#9aa3af',
        'tooltip_bg': '#1b2430',
        'tooltip_fg': '#f8fafc',
    },
    'dark': {
        'bg': '#10151c',
        'surface': '#181f28',
        'surface_alt': '#232c38',
        'header_bg': '#151c24',
        'status_bg': '#151c24',
        'border': '#2c3846',
        'text': '#e8eef4',
        'text_muted': '#8b9aab',
        'accent': '#2dd4bf',
        'accent_hover': '#5eead4',
        'accent_text': '#042f2e',
        'danger': '#f87171',
        'danger_hover': '#fca5a5',
        'danger_text': '#1f1315',
        'select_bg': '#115e59',
        'select_fg': '#ccfbf1',
        'progress': '#2dd4bf',
        'trough': '#1f2937',
        'drop_bg': '#0f2a28',
        'drop_border': '#0f766e',
        'list_bg': '#121920',
        'list_fg': '#e8eef4',
        'menu_bg': '#181f28',
        'menu_fg': '#e8eef4',
        'menu_active_bg': '#0d9488',
        'menu_active_fg': '#ffffff',
        'entry_bg': '#121920',
        'disabled_bg': '#1b2430',
        'disabled_fg': '#6b7785',
        'tooltip_bg': '#232c38',
        'tooltip_fg': '#e8eef4',
    },
}


def is_dark():
    return _DARK


def get_colors():
    return PALETTES['dark' if _DARK else 'light']


def get_font(size=10, weight='normal'):
    """Devuelve una fuente con nombre de Tk, nunca una familia inexistente."""
    key = (int(size), weight)
    font = _FONT_OBJS.get(key)
    if font is not None:
        return font
    if weight != 'normal':
        return (_FONT_FAMILY, int(size), weight)
    return (_FONT_FAMILY, int(size))


def _pick_font_family(root):
    """Elige una familia que Tk pueda resolver (XLFD o fontconfig)."""
    available = {name.lower(): name for name in tkfont.families(root)}
    preferred = [
        'nimbus sans l', 'helvetica', 'arial', 'dejavu sans', 'ubuntu',
        'noto sans', 'cantarell', 'liberation sans', 'segoe ui',
        'sf pro text', 'helvetica neue',
    ]
    for name in preferred:
        if name in available:
            return available[name]
    family = tkfont.nametofont('TkDefaultFont').actual('family')
    if family and family.lower() != 'fixed':
        return family
    return 'helvetica'


def _init_fonts(root):
    """Crea fuentes con nombre a partir de una familia que Tk conoce."""
    global _FONT_FAMILY, _FONT_OBJS
    family = _pick_font_family(root)
    _FONT_FAMILY = family
    default_size = abs(int(tkfont.nametofont('TkDefaultFont').actual('size') or 10))
    if default_size < 8:
        default_size = 10
    specs = {
        (9, 'normal'): max(8, default_size - 1),
        (9, 'bold'): max(8, default_size - 1),
        (10, 'normal'): max(10, default_size),
        (10, 'bold'): max(10, default_size),
        (12, 'normal'): max(11, default_size + 1),
        (12, 'bold'): max(12, default_size + 1),
        (16, 'bold'): max(14, default_size + 5),
        (20, 'bold'): max(16, default_size + 7),
    }
    for (size, weight), px in specs.items():
        name = f'KidneysFont_{size}_{weight}'
        try:
            font = tkfont.nametofont(name)
            font.configure(family=family, size=px, weight=weight)
        except tk.TclError:
            font = tkfont.Font(root=root, name=name, family=family, size=px, weight=weight)
        _FONT_OBJS[(size, weight)] = font

    ui_size = specs[(10, 'normal')]
    for std, extra in (
        ('TkDefaultFont', {'size': ui_size, 'weight': 'normal'}),
        ('TkTextFont', {'size': ui_size, 'weight': 'normal'}),
        ('TkMenuFont', {'size': ui_size, 'weight': 'normal'}),
        ('TkHeadingFont', {'size': ui_size, 'weight': 'bold'}),
        ('TkCaptionFont', {'size': max(11, ui_size + 1), 'weight': 'bold'}),
    ):
        try:
            tkfont.nametofont(std).configure(family=family, **extra)
        except tk.TclError:
            pass


def apply_theme(root, dark=False):
    """Aplica el tema ttk a toda la aplicación."""
    global _DARK
    _DARK = bool(dark)
    _init_fonts(root)
    colors = get_colors()
    font = get_font(10)
    font_small = get_font(9)
    font_title = get_font(20, 'bold')
    font_subtitle = get_font(10)
    font_section = get_font(9, 'bold')

    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except tk.TclError:
        pass

    root.configure(bg=colors['bg'])
    font_name = font.name if hasattr(font, 'name') else font
    root.option_add('*Font', font_name)
    root.option_add('*Menu.font', font_name)
    root.option_add('*Menu.background', colors['menu_bg'])
    root.option_add('*Menu.foreground', colors['menu_fg'])
    root.option_add('*Menu.activeBackground', colors['menu_active_bg'])
    root.option_add('*Menu.activeForeground', colors['menu_active_fg'])
    root.option_add('*Menu.relief', 'solid')
    root.option_add('*Menu.borderWidth', 1)
    root.option_add('*TCombobox*Listbox.background', colors['list_bg'])
    root.option_add('*TCombobox*Listbox.foreground', colors['list_fg'])
    root.option_add('*TCombobox*Listbox.selectBackground', colors['select_bg'])
    root.option_add('*TCombobox*Listbox.selectForeground', colors['select_fg'])
    root.option_add('*TCombobox*Listbox.font', font_name)

    style.configure('.', background=colors['bg'], foreground=colors['text'], font=font)

    style.configure('TFrame', background=colors['bg'])
    style.configure('Card.TFrame', background=colors['surface'])
    style.configure('Header.TFrame', background=colors['header_bg'])
    style.configure('Status.TFrame', background=colors['status_bg'])
    style.configure('Sizer.TFrame', background=colors['border'])

    style.configure('TLabel', background=colors['bg'], foreground=colors['text'], font=font)
    style.configure('Card.TLabel', background=colors['surface'], foreground=colors['text'], font=font)
    style.configure('Muted.TLabel', background=colors['bg'], foreground=colors['text_muted'], font=font_small)
    style.configure('CardMuted.TLabel', background=colors['surface'], foreground=colors['text_muted'], font=font_small)
    style.configure('Header.TLabel', background=colors['header_bg'], foreground=colors['text'], font=font)
    style.configure('Title.TLabel', background=colors['header_bg'], foreground=colors['text'], font=font_title)
    style.configure('PageTitle.TLabel', background=colors['bg'], foreground=colors['text'], font=font_title)
    style.configure('Subtitle.TLabel', background=colors['header_bg'], foreground=colors['text_muted'], font=font_subtitle)
    style.configure('Section.TLabel', background=colors['surface'], foreground=colors['text_muted'], font=font_section)
    style.configure('Status.TLabel', background=colors['status_bg'], foreground=colors['text_muted'], font=font_small)
    style.configure('Link.TLabel', background=colors['bg'], foreground=colors['accent'], font=font)
    style.configure('SessionOk.TLabel', background=colors['bg'], foreground=colors['accent'], font=font_small)
    style.configure('SessionBad.TLabel', background=colors['bg'], foreground=colors['danger'], font=font_small)

    _configure_button(style, 'TButton', colors['surface_alt'], colors['text'],
                      colors['border'], colors['border'], colors['disabled_bg'], colors['disabled_fg'])
    _configure_button(style, 'Compact.TButton', colors['surface_alt'], colors['text'],
                      colors['border'], colors['border'], colors['disabled_bg'], colors['disabled_fg'])
    style.configure('Compact.TButton', padding=(8, 6), font=get_font(9))
    _configure_button(style, 'Accent.TButton', colors['accent'], colors['accent_text'],
                      colors['accent'], colors['accent_hover'], colors['disabled_bg'], colors['disabled_fg'])
    _configure_button(style, 'Danger.TButton', colors['danger'], colors['danger_text'],
                      colors['danger'], colors['danger_hover'], colors['disabled_bg'], colors['disabled_fg'])
    _configure_button(style, 'Ghost.TButton', colors['header_bg'], colors['text'],
                      colors['border'], colors['surface_alt'], colors['disabled_bg'], colors['disabled_fg'])
    _configure_button(style, 'Icon.TButton', colors['surface_alt'], colors['text'],
                      colors['border'], colors['border'], colors['disabled_bg'], colors['disabled_fg'])
    style.configure('Icon.TButton', padding=(10, 8), font=get_font(10))
    _configure_button(style, 'IconRecord.TButton', colors['danger'], colors['danger_text'],
                      colors['danger'], colors['danger_hover'], colors['disabled_bg'], colors['disabled_fg'])
    style.configure('IconRecord.TButton', padding=(10, 8), font=get_font(10))

    style.configure(
        'TEntry',
        fieldbackground=colors['entry_bg'],
        background=colors['entry_bg'],
        foreground=colors['text'],
        insertcolor=colors['text'],
        bordercolor=colors['border'],
        lightcolor=colors['border'],
        darkcolor=colors['border'],
        padding=8,
    )
    style.map(
        'TEntry',
        fieldbackground=[('disabled', colors['disabled_bg']), ('readonly', colors['surface_alt'])],
        foreground=[('disabled', colors['disabled_fg'])],
        bordercolor=[('focus', colors['accent'])],
        lightcolor=[('focus', colors['accent'])],
        darkcolor=[('focus', colors['accent'])],
    )

    style.configure(
        'TCombobox',
        fieldbackground=colors['entry_bg'],
        background=colors['surface_alt'],
        foreground=colors['text'],
        arrowcolor=colors['text'],
        bordercolor=colors['border'],
        lightcolor=colors['border'],
        darkcolor=colors['border'],
        padding=6,
    )
    style.map(
        'TCombobox',
        fieldbackground=[('readonly', colors['entry_bg'])],
        foreground=[('readonly', colors['text'])],
        bordercolor=[('focus', colors['accent'])],
    )

    style.configure(
        'TSpinbox',
        fieldbackground=colors['entry_bg'],
        background=colors['surface'],
        foreground=colors['text'],
        arrowcolor=colors['text'],
        bordercolor=colors['border'],
        padding=6,
    )

    style.configure(
        'TLabelframe',
        background=colors['surface'],
        foreground=colors['text_muted'],
        bordercolor=colors['border'],
        lightcolor=colors['border'],
        darkcolor=colors['border'],
        relief='solid',
        borderwidth=1,
    )
    style.configure(
        'TLabelframe.Label',
        background=colors['surface'],
        foreground=colors['text_muted'],
        font=font_section,
    )

    style.configure(
        'TRadiobutton',
        background=colors['surface'],
        foreground=colors['text'],
        indicatorcolor=colors['entry_bg'],
        font=font,
        padding=4,
    )
    style.map(
        'TRadiobutton',
        background=[('active', colors['surface'])],
        indicatorcolor=[('selected', colors['accent']), ('!selected', colors['entry_bg'])],
        foreground=[('disabled', colors['disabled_fg'])],
    )

    style.configure(
        'TCheckbutton',
        background=colors['bg'],
        foreground=colors['text'],
        indicatorcolor=colors['entry_bg'],
        font=font,
        padding=4,
    )
    style.map(
        'TCheckbutton',
        background=[('active', colors['bg'])],
        indicatorcolor=[('selected', colors['accent']), ('!selected', colors['entry_bg'])],
    )
    style.configure(
        'Card.TCheckbutton',
        background=colors['surface'],
        foreground=colors['text'],
        indicatorcolor=colors['entry_bg'],
        font=font,
        padding=4,
    )
    style.map(
        'Card.TCheckbutton',
        background=[('active', colors['surface'])],
        indicatorcolor=[('selected', colors['accent']), ('!selected', colors['entry_bg'])],
    )

    style.configure(
        'TProgressbar',
        background=colors['progress'],
        troughcolor=colors['trough'],
        bordercolor=colors['trough'],
        lightcolor=colors['progress'],
        darkcolor=colors['progress'],
        thickness=8,
    )

    style.configure(
        'Horizontal.TScale',
        background=colors['bg'],
        troughcolor=colors['trough'],
        bordercolor=colors['border'],
        lightcolor=colors['accent'],
        darkcolor=colors['accent'],
    )

    style.configure(
        'TScrollbar',
        background=colors['surface_alt'],
        troughcolor=colors['bg'],
        bordercolor=colors['bg'],
        arrowcolor=colors['text_muted'],
        relief='flat',
    )
    style.map(
        'TScrollbar',
        background=[('active', colors['border'])],
        arrowcolor=[('active', colors['text'])],
    )

    style.configure(
        'TSeparator',
        background=colors['border'],
    )

    style.configure(
        'Treeview',
        background=colors['list_bg'],
        fieldbackground=colors['list_bg'],
        foreground=colors['list_fg'],
        bordercolor=colors['border'],
        font=font,
        rowheight=26,
    )
    style.configure(
        'Treeview.Heading',
        background=colors['surface_alt'],
        foreground=colors['text'],
        font=font_section,
        bordercolor=colors['border'],
    )
    style.map(
        'Treeview',
        background=[('selected', colors['select_bg'])],
        foreground=[('selected', colors['select_fg'])],
    )

    style.configure('TNotebook', background=colors['bg'], bordercolor=colors['border'])
    style.configure(
        'TNotebook.Tab',
        background=colors['surface_alt'],
        foreground=colors['text_muted'],
        padding=(14, 8),
        font=font,
    )
    style.map(
        'TNotebook.Tab',
        background=[('selected', colors['surface'])],
        foreground=[('selected', colors['text'])],
    )
    from ui_clipboard import install_entry_clipboard
    install_entry_clipboard(root)


def _configure_button(style, name, bg, fg, border, hover, disabled_bg, disabled_fg):
    style.configure(
        name,
        background=bg,
        foreground=fg,
        bordercolor=border,
        lightcolor=bg,
        darkcolor=border,
        relief='flat',
        borderwidth=1,
        focusthickness=0,
        focuscolor=bg,
        padding=(14, 8),
        font=get_font(10),
    )
    style.map(
        name,
        background=[('active', hover), ('pressed', hover), ('disabled', disabled_bg)],
        foreground=[('disabled', disabled_fg)],
        bordercolor=[('disabled', disabled_bg), ('active', hover)],
        lightcolor=[('active', hover), ('disabled', disabled_bg)],
        darkcolor=[('active', hover), ('disabled', disabled_bg)],
    )


def style_window(window):
    colors = get_colors()
    try:
        window.configure(bg=colors['bg'])
    except tk.TclError:
        pass
    from ui_clipboard import install_entry_clipboard
    install_entry_clipboard(window)


def style_listbox(listbox):
    colors = get_colors()
    listbox.configure(
        background=colors['list_bg'],
        foreground=colors['list_fg'],
        selectbackground=colors['select_bg'],
        selectforeground=colors['select_fg'],
        highlightthickness=1,
        highlightbackground=colors['border'],
        highlightcolor=colors['accent'],
        borderwidth=0,
        relief='flat',
        activestyle='none',
        font=get_font(10),
    )


def style_text(widget):
    colors = get_colors()
    widget.configure(
        background=colors['entry_bg'],
        foreground=colors['text'],
        insertbackground=colors['text'],
        selectbackground=colors['select_bg'],
        selectforeground=colors['select_fg'],
        highlightthickness=1,
        highlightbackground=colors['border'],
        highlightcolor=colors['accent'],
        borderwidth=0,
        relief='flat',
        font=get_font(10),
    )


def style_menu(menu):
    colors = get_colors()
    try:
        menu.configure(
            background=colors['menu_bg'],
            foreground=colors['menu_fg'],
            activebackground=colors['menu_active_bg'],
            activeforeground=colors['menu_active_fg'],
            disabledforeground=colors['disabled_fg'],
            borderwidth=1,
            relief='solid',
        )
    except tk.TclError:
        pass


def style_menu_tree(menu):
    if menu is None:
        return
    style_menu(menu)
    try:
        last = menu.index('end')
    except tk.TclError:
        return
    if last is None:
        return
    for i in range(last + 1):
        try:
            if menu.type(i) == 'cascade':
                style_menu_tree(menu.nametowidget(menu.entrycget(i, 'menu')))
        except tk.TclError:
            continue


def set_window_icon(window):
    global _ICON_REF
    try:
        window.tk.call('wm', 'class', window._w, APP_WM_CLASS, APP_WM_CLASS)
    except (tk.TclError, AttributeError):
        pass
    logo = Path(resource_dir()) / 'img' / 'logo.png'
    if not logo.exists():
        return
    try:
        icon = tk.PhotoImage(file=str(logo))
        window.iconphoto(True, icon)
        _ICON_REF = icon
        window._theme_icon = icon
    except tk.TclError:
        pass


def _hex_to_rgba(color):
    color = color.lstrip('#')
    if len(color) == 3:
        color = ''.join(ch * 2 for ch in color)
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16), 255)


def make_control_icons(color, size=20, record_color=None):
    """Iconos vectoriales para los controles del reproductor (independientes de la fuente)."""
    from PIL import Image, ImageDraw, ImageTk

    fill = _hex_to_rgba(color)

    def blank():
        return Image.new('RGBA', (size, size), (0, 0, 0, 0))

    def photo(img):
        return ImageTk.PhotoImage(img)

    def triangle(draw, points):
        draw.polygon(points, fill=fill)

    def bar(draw, x0, y0, x1, y1):
        draw.rectangle([x0, y0, x1, y1], fill=fill)

    p = max(2, size // 6)
    icons = {}

    img = blank()
    d = ImageDraw.Draw(img)
    bar(d, p, p, p + 2, size - p)
    triangle(d, [(p + 4, size // 2), (size // 2 + 1, p), (size // 2 + 1, size - p)])
    triangle(d, [(size // 2, size // 2), (size - p, p), (size - p, size - p)])
    icons['skip_back'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    triangle(d, [(p, size // 2), (size - p, p), (size - p, size - p)])
    icons['rewind'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    mid = size // 2
    triangle(d, [(p, p + 1), (p, size - p - 1), (mid + 1, mid)])
    w = max(2, size // 8)
    bar(d, mid + 3, p + 1, mid + 3 + w, size - p - 1)
    bar(d, mid + 5 + w, p + 1, mid + 5 + 2 * w, size - p - 1)
    icons['play_pause'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    triangle(d, [(p, p), (p, size - p), (size - p, size // 2)])
    icons['forward'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    triangle(d, [(p, p), (p, size - p), (size // 2, size // 2)])
    triangle(d, [(size // 2 - 1, p), (size // 2 - 1, size - p), (size - p - 3, size // 2)])
    bar(d, size - p - 2, p, size - p, size - p)
    icons['skip_forward'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    bar(d, p + 2, p + 2, size - p - 2, size - p - 2)
    icons['stop'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    pad = p + 1
    d.ellipse([pad, pad, size - pad - 1, size - pad - 1], outline=fill, width=max(2, size // 10))
    icons['record'] = photo(img)

    rec = _hex_to_rgba(record_color or '#dc2626')
    img = blank()
    d = ImageDraw.Draw(img)
    inner = p + 3
    d.ellipse([inner, inner, size - inner - 1, size - inner - 1], fill=rec)
    icons['record_on'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    cy = size // 2
    bar(d, p, cy - 3, p + 4, cy + 3)
    triangle(d, [(p + 3, cy - 6), (p + 3, cy + 6), (p + 9, cy)])
    d.arc([p + 10, cy - 5, p + 16, cy + 5], start=-50, end=50, fill=fill, width=2)
    d.arc([p + 12, cy - 8, p + 18, cy + 8], start=-50, end=50, fill=fill, width=2)
    icons['volume'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    t = max(2, size // 10)
    # Esquinas de pantalla completa
    bar(d, p, p, p + 7, p + t)
    bar(d, p, p, p + t, p + 7)
    bar(d, size - p - 7, p, size - p, p + t)
    bar(d, size - p - t, p, size - p, p + 7)
    bar(d, p, size - p - t, p + 7, size - p)
    bar(d, p, size - p - 7, p + t, size - p)
    bar(d, size - p - 7, size - p - t, size - p, size - p)
    bar(d, size - p - t, size - p - 7, size - p, size - p)
    icons['fullscreen'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    for i, y in enumerate((p + 1, size // 2 - 1, size - p - 3)):
        bar(d, p, y, size - p, y + 2)
    icons['playlist'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    cy = size // 2
    bar(d, p, cy - 3, p + 3, cy + 3)
    triangle(d, [(p + 2, cy - 6), (p + 2, cy + 6), (p + 8, cy)])
    d.arc([p + 9, cy - 4, p + 15, cy + 4], start=-55, end=55, fill=fill, width=2)
    d.arc([p + 11, cy - 7, p + 19, cy + 7], start=-55, end=55, fill=fill, width=2)
    icons['audio'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    bar(d, p + 6, size - p - 2, size - p, size - p)
    bar(d, p + 3, cy - 1, size - p, cy + 1)
    bar(d, p, p + 2, size - p, p + 4)
    icons['quality'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        [p, p + 2, size - p, size - p - 2],
        radius=max(2, size // 8),
        outline=fill,
        width=max(1, size // 12),
    )
    bar(d, p + 4, cy - 3, size - p - 4, cy - 1)
    bar(d, p + 4, cy + 2, size - p - 6, cy + 4)
    icons['subtitles'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    d.polygon(
        [
            (size // 2, p),
            (size // 2 + 3, size // 2 - 2),
            (size - p, size // 2 - 2),
            (size // 2 + 4, size // 2 + 2),
            (size // 2 + 6, size - p),
            (size // 2, size // 2 + 4),
            (size // 2 - 6, size - p),
            (size // 2 - 4, size // 2 + 2),
            (p, size // 2 - 2),
            (size // 2 - 3, size // 2 - 2),
        ],
        fill=fill,
    )
    icons['star'] = photo(img)

    img = blank()
    d = ImageDraw.Draw(img)
    d.rectangle([p, p, size - p - 3, size - p - 3], outline=fill, width=max(1, size // 12))
    d.rectangle([size // 2 - 1, size // 2 - 1, size - p, size - p], fill=fill)
    icons['pip'] = photo(img)

    return icons


def center_window(window, width=None, height=None):
    window.update_idletasks()
    width = width or window.winfo_width()
    height = height or window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f'{width}x{height}+{x}+{y}')
