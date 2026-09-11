"""Ventana Acerca de: versión, resumen y enlace al repositorio."""

import os
import tkinter as tk
from tkinter import ttk
import webbrowser
from PIL import Image, ImageTk

from app_paths import resource_dir
from app_version import (
    __version__ as APP_VERSION,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_RELEASES_URL,
)
from ui_theme import style_window, set_window_icon, get_colors, get_font
from ui_layout import bind_wraplength, make_vertical_scroll, setup_resizable_dialog


def show_about(root):
    """Muestra la ventana Acerca de."""
    about_window = tk.Toplevel(root)
    about_window.title('Acerca de')
    setup_resizable_dialog(about_window, 560, 680, 420, 480)
    about_window.transient(root)
    about_window.grab_set()
    style_window(about_window)
    set_window_icon(about_window)

    shell = ttk.Frame(about_window, padding=(20, 16, 16, 12))
    shell.pack(fill=tk.BOTH, expand=True)

    body = ttk.Frame(shell)
    body.pack(fill=tk.BOTH, expand=True)
    _canvas, main, _sync = make_vertical_scroll(body)

    # Contenedor centrado dentro del área con scroll
    content = ttk.Frame(main)
    content.pack(anchor=tk.CENTER, expand=True, fill=tk.X, padx=12, pady=4)
    bind_wraplength(content, padding=48)

    def _centered(widget_factory, **pack_opts):
        """Crea un widget y lo empaqueta centrado."""
        widget = widget_factory(content)
        widget.pack(anchor=tk.CENTER, **pack_opts)
        return widget

    _centered(
        lambda p: ttk.Label(p, text='Kidneysm3u', style='PageTitle.TLabel'),
    )
    _centered(
        lambda p: ttk.Label(p, text=f'Versión {APP_VERSION}', style='Muted.TLabel'),
        pady=(4, 0),
    )
    _centered(
        lambda p: ttk.Label(
            p,
            text='IPTV, YouTube, Twitch y Kick en el escritorio',
            style='Muted.TLabel',
        ),
        pady=(2, 12),
    )

    try:
        image = Image.open(os.path.join(resource_dir(), 'img', 'logo.png'))
        image = image.resize((96, 115), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        logo = ttk.Label(content, image=photo)
        logo.image = photo
        logo.pack(anchor=tk.CENTER, pady=(0, 14))
    except Exception:
        _centered(
            lambda p: ttk.Label(p, text='[Logo no disponible]', style='Muted.TLabel'),
            pady=(0, 14),
        )

    intro = (
        'Filtra y reproduce listas M3U/M3U8, canales IPTV y contenido de '
        'YouTube, Twitch y Kick con VLC embebido y yt-dlp.\n'
        'No incluye enlaces a canales: solo las listas o URLs que indiques.'
    )
    intro_label = ttk.Label(
        content,
        text=intro,
        wraplength=460,
        justify=tk.CENTER,
    )
    intro_label.pack(anchor=tk.CENTER, pady=(0, 14))

    features = (
        ('Listas M3U', 'Filtrar, ordenar, EPG/parrilla, logos y buffer IPTV.'),
        ('Reproductor', 'Zap, PiP, grabación, subtítulos, modo solo vídeo y preferencias.'),
        ('YouTube / Twitch / Kick', 'Búsqueda, cookies, historial, cola y calidad por plataforma.'),
        ('Biblioteca', 'Favoritos e historial unificados, con selección múltiple.'),
        ('Sesión', 'Perfil exportable, cachés, actualizaciones desde GitHub Releases.'),
    )
    for title, detail in features:
        block = ttk.Frame(content, style='Card.TFrame')
        block.pack(anchor=tk.CENTER, fill=tk.X, pady=(0, 8))
        ttk.Label(block, text=title, style='Card.TLabel', anchor=tk.CENTER).pack(
            fill=tk.X,
        )
        ttk.Label(
            block,
            text=detail,
            style='CardMuted.TLabel',
            wraplength=440,
            justify=tk.CENTER,
            anchor=tk.CENTER,
        ).pack(fill=tk.X, pady=(2, 0))

    _centered(
        lambda p: ttk.Label(
            p,
            text=f'Desarrollo · {GITHUB_OWNER}  ·  Licencia MIT',
            style='Muted.TLabel',
        ),
        pady=(10, 6),
    )

    colors = get_colors()
    github_url = f'https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}'

    def _link(text, url):
        label = tk.Label(
            content,
            text=text,
            fg=colors['accent'],
            bg=colors['bg'],
            cursor='hand2',
            font=get_font(10),
            justify=tk.CENTER,
        )
        label.pack(anchor=tk.CENTER, pady=(0, 4))
        label.bind('<Button-1>', lambda _e, target=url: webbrowser.open_new(target))
        return label

    _link('Repositorio en GitHub', github_url)
    _link('Lanzamientos e instaladores', GITHUB_RELEASES_URL)

    footer = ttk.Frame(shell)
    footer.pack(fill=tk.X, pady=(10, 0))
    ttk.Button(
        footer,
        text='Cerrar',
        style='Accent.TButton',
        command=about_window.destroy,
    ).pack(side=tk.RIGHT)

    about_window.after_idle(_sync)
    about_window.bind('<Escape>', lambda _e: about_window.destroy())
    return about_window
