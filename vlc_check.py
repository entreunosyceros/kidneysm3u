"""Comprobación de libVLC, versión detectada y avisos de estilo de subtítulos."""

from __future__ import annotations

import os
import sys
import webbrowser
from dataclasses import dataclass

import tkinter as tk
from tkinter import ttk

import app_config
from iptv_buffer import vlc_aout_instance_args
from m3u_parse import IPTV_USER_AGENT
from subtitle_style import vlc_instance_args
from ui_layout import bind_wraplength, setup_resizable_dialog
from ui_theme import center_window, get_colors, get_font, set_window_icon, style_window

VLC_DOWNLOAD_URL = 'https://www.videolan.org/vlc/'


@dataclass(frozen=True)
class VlcInstanceResult:
    """Resultado de crear una instancia libVLC."""

    instance: object
    subtitle_style_applied: bool
    attempted_subtitle_style: bool
    vlc_version: str
    install_path: str | None


def vlc_version_text():
    """Devuelve la versión de libVLC detectada o «desconocida»."""
    try:
        import vlc
    except ImportError:
        return 'no instalado (python-vlc ausente)'
    try:
        raw = vlc.libvlc_get_version()
    except Exception:
        return 'desconocida'
    if isinstance(raw, bytes):
        return raw.decode('utf-8', 'replace').strip() or 'desconocida'
    text = str(raw or '').strip()
    return text or 'desconocida'


def vlc_install_path():
    """Ruta de instalación de VLC en Windows, si existe."""
    if sys.platform != 'win32':
        return None
    for base in (
        os.environ.get('ProgramFiles', r'C:\Program Files'),
        os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
    ):
        if not base:
            continue
        candidate = os.path.join(base, 'VideoLAN', 'VLC')
        if os.path.isfile(os.path.join(candidate, 'libvlc.dll')):
            return candidate
    return None


def vlc_install_hint():
    """Texto de ayuda para instalar o reparar VLC."""
    if sys.platform == 'win32':
        install_dir = vlc_install_path()
        if install_dir:
            return (
                f'VLC parece instalado en {install_dir}, pero libVLC no aceptó el estilo '
                'de subtítulos. Reinstala VLC 3.x, reinicia el PC o añade esa carpeta al PATH.'
            )
        return (
            'Instala VLC 3 desde videolan.org. Durante la instalación marca '
            '«Add to PATH» o añade C:\\Program Files\\VideoLAN\\VLC al PATH del sistema.'
        )
    if sys.platform == 'darwin':
        return 'Instala VLC 3 con Homebrew (brew install --cask vlc) o desde videolan.org.'
    return 'En Ubuntu/Debian: sudo apt install vlc python3-vlc. En otros Linux, el paquete vlc del sistema.'


def args_include_subtitle_style(args):
    """True si los argumentos de libvlc_new incluyen opciones freetype/sub-text-scale."""
    return any(
        str(arg).startswith('--freetype-') or str(arg).startswith('--sub-text-scale=')
        for arg in (args or [])
    )


def make_vlc_instance():
    """Crea libVLC; freetype/sub-text-scale solo en libvlc_new (no en media)."""
    os.environ['LIBVA_MESSAGING_LEVEL'] = '0'
    use_hw = app_config.iptv_use_hw_decode()
    core = [
        '--quiet',
        '--verbose=0',
        '--audio-resampler=soxr',
        '--network-caching=3000',
        '--live-caching=3000',
        '--file-caching=3000',
        '--sout-mux-caching=3000',
        f'--http-user-agent={IPTV_USER_AGENT}',
    ]
    if not use_hw:
        core.insert(2, '--avcodec-hw=none')
    core.extend(vlc_aout_instance_args())
    freetype = vlc_instance_args()
    attempts = []
    seen = set()

    def _add(args):
        key = tuple(args)
        if key not in seen:
            seen.add(key)
            attempts.append(list(args))

    if freetype:
        _add(core + freetype)
        lite = [arg for arg in freetype if 'background' not in arg]
        if lite != freetype:
            _add(core + lite)
    _add(core)
    if not use_hw:
        if freetype:
            _add(['--quiet', '--avcodec-hw=none'] + freetype)
        _add(['--quiet', '--avcodec-hw=none'])
    else:
        if freetype:
            _add(['--quiet'] + freetype)
        _add(['--quiet'])

    import vlc

    last_error = None
    attempted_subtitle_style = bool(freetype)
    winning_args = None
    instance = None
    for args in attempts:
        try:
            candidate = vlc.Instance(*args)
        except Exception as exc:
            last_error = exc
            continue
        if candidate is not None:
            instance = candidate
            winning_args = args
            break

    if instance is None:
        detail = f' ({last_error})' if last_error else ''
        raise RuntimeError(
            'VLC no pudo crear el reproductor. Comprueba que libvlc está instalado.'
            + detail
        )

    subtitle_style_applied = (
        not attempted_subtitle_style
        or args_include_subtitle_style(winning_args)
    )
    return VlcInstanceResult(
        instance=instance,
        subtitle_style_applied=subtitle_style_applied,
        attempted_subtitle_style=attempted_subtitle_style,
        vlc_version=vlc_version_text(),
        install_path=vlc_install_path(),
    )


def show_vlc_subtitle_style_dialog(parent, result=None, vlc_version=None, install_path=None):
    """Diálogo cuando libVLC arranca sin aplicar el estilo freetype de subtítulos."""
    if parent is None:
        return
    version = vlc_version or (result.vlc_version if result else vlc_version_text())
    path = install_path if install_path is not None else (
        result.install_path if result else vlc_install_path()
    )
    dialog = tk.Toplevel(parent)
    dialog.title('Subtítulos personalizados')
    setup_resizable_dialog(dialog, 520, 360, 420, 300)
    dialog.transient(parent)
    dialog.grab_set()
    style_window(dialog)
    set_window_icon(dialog)

    frame = ttk.Frame(dialog, padding=24)
    frame.pack(fill=tk.BOTH, expand=True)
    bind_wraplength(frame, padding=40)

    ttk.Label(frame, text='Estilo de subtítulos no disponible', style='PageTitle.TLabel').pack(
        anchor=tk.W,
        pady=(0, 10),
    )
    body = (
        'VLC arrancó, pero no aceptó las opciones de personalización de subtítulos '
        '(tamaño, color, fondo). Los subtítulos seguirán con el aspecto por defecto de VLC.\n\n'
        f'Versión detectada de libVLC: {version}'
    )
    if path:
        body += f'\nRuta de instalación: {path}'
    body += f'\n\n{vlc_install_hint()}'
    ttk.Label(frame, text=body, wraplength=460, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 14))

    colors = get_colors()
    link = tk.Label(
        frame,
        text='Descargar VLC desde videolan.org',
        fg=colors['accent'],
        bg=colors['bg'],
        cursor='hand2',
        font=get_font(10),
    )
    link.pack(anchor=tk.W, pady=(0, 18))
    link.bind('<Button-1>', lambda _event: webbrowser.open_new(VLC_DOWNLOAD_URL))

    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X)
    ttk.Button(
        buttons,
        text='Abrir página de VLC',
        command=lambda: webbrowser.open_new(VLC_DOWNLOAD_URL),
    ).pack(side=tk.LEFT)
    ttk.Button(buttons, text='Entendido', style='Accent.TButton', command=dialog.destroy).pack(
        side=tk.RIGHT,
    )
    center_window(dialog, parent)


def should_warn_subtitle_style(result, force=False):
    """True si conviene mostrar el aviso de subtítulos."""
    if result is None:
        return False
    if result.subtitle_style_applied or not result.attempted_subtitle_style:
        return False
    if force:
        return True
    return app_config.should_show_vlc_subtitle_style_warn()


def mark_vlc_subtitle_style_warn_shown():
    """Marca el aviso como ya mostrado."""
    app_config.set_vlc_subtitle_style_warn_shown(True)
