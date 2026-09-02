"""Asistente de primer arranque: comprueba el entorno y guía la configuración inicial."""

import os
import shutil
import sys
import tkinter as tk
from tkinter import ttk

import app_config
from app_paths import data_dir
from app_version import __version__ as APP_VERSION
from ui_layout import bind_wraplength, setup_resizable_dialog
from ui_theme import set_window_icon, style_window
from vlc_check import vlc_version_text


def _status_ok(title, detail='', hint=''):
    return {
        'id': title,
        'title': title,
        'status': 'ok',
        'detail': detail,
        'hint': hint,
    }


def _status_warn(title, detail='', hint=''):
    return {
        'id': title,
        'title': title,
        'status': 'warn',
        'detail': detail,
        'hint': hint,
    }


def _status_fail(title, detail='', hint=''):
    return {
        'id': title,
        'title': title,
        'status': 'fail',
        'detail': detail,
        'hint': hint,
    }


def platform_name():
    """Nombre legible del sistema operativo actual."""
    if sys.platform == 'win32':
        return 'Windows'
    if sys.platform == 'darwin':
        return 'macOS'
    if sys.platform.startswith('linux'):
        return 'Linux'
    return sys.platform


def _windows_program_dirs():
    """Carpetas típicas de programas en Windows."""
    dirs = []
    for key in ('ProgramFiles', 'ProgramFiles(x86)', 'LocalAppData'):
        value = (os.environ.get(key) or '').strip()
        if value and value not in dirs:
            dirs.append(value)
    return dirs


def find_executable(name):
    """Busca un ejecutable en PATH y en rutas habituales (Linux y Windows)."""
    candidates = [name]
    if sys.platform == 'win32' and not name.lower().endswith('.exe'):
        candidates.append(f'{name}.exe')

    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path

    if sys.platform == 'win32':
        extra_roots = []
        for base in _windows_program_dirs():
            extra_roots.extend([
                os.path.join(base, name),
                os.path.join(base, name, 'bin'),
                os.path.join(base, 'VideoLAN', 'VLC'),
            ])
        extra_roots.extend([
            os.path.join(os.path.expanduser('~'), 'scoop', 'shapps', name, 'current'),
            os.path.join(os.path.expanduser('~'), 'scoop', 'apps', name, 'current'),
        ])
        for root in extra_roots:
            for candidate in candidates:
                path = os.path.join(root, candidate)
                if os.path.isfile(path):
                    return path
    return None


def _platform_install_hint(package):
    """Sugerencia de instalación según el sistema operativo."""
    if sys.platform.startswith('linux'):
        mapping = {
            'vlc': 'sudo apt install vlc python3-vlc',
            'ffmpeg': 'sudo apt install ffmpeg',
        }
        cmd = mapping.get(package, f'sudo apt install {package}')
        return f'Instálalo con el gestor de paquetes (p. ej. {cmd}).'
    if sys.platform == 'win32':
        mapping = {
            'vlc': (
                'Instala VLC desde videolan.org y marca «Add to PATH», '
                'o añade C:\\Program Files\\VideoLAN\\VLC al PATH.'
            ),
            'ffmpeg': (
                'Descarga ffmpeg desde ffmpeg.org/download.html '
                'o instálalo con winget/chocolatey y añádelo al PATH.'
            ),
        }
        return mapping.get(package, f'Asegúrate de que {package} está instalado y accesible desde el PATH.')
    if sys.platform == 'darwin':
        mapping = {
            'vlc': 'brew install --cask vlc',
            'ffmpeg': 'brew install ffmpeg',
        }
        cmd = mapping.get(package, f'brew install {package}')
        return f'Instálalo con Homebrew u otro gestor (p. ej. {cmd}).'
    return f'Instala {package} en el sistema.'


def _session_cookie_hint():
    """Instrucciones de cookies según plataforma."""
    if sys.platform == 'win32':
        return (
            'En Windows usa Firefox con sesión en YouTube/Twitch. '
            'Chrome, Edge y Brave cifran las cookies y no se pueden leer. '
            'Cierra Firefox y pulsa «Reexportar cookies» en Preferencias → Cookies.'
        )
    return (
        'Inicia sesión en Firefox (recomendado) o en el navegador elegido en Preferencias. '
        'Ciérralo y pulsa «Reexportar cookies» en Preferencias → Cookies.'
    )


def _data_dir_hint(path):
    """Texto de ayuda para la carpeta de datos según plataforma."""
    if sys.platform == 'win32' and getattr(sys, 'frozen', False):
        return f'Preferencias y cookies en {path} (%LOCALAPPDATA%\\kidneysm3u).'
    if sys.platform.startswith('linux') and path.startswith(os.path.expanduser('~')):
        return f'Preferencias y cookies en {path} (~/.local/share/kidneysm3u con el .deb).'
    return 'Aquí se guardan preferencias, cookies y favoritos.'


def _vlc_install_dir_windows():
    """Ruta de instalación de VLC en Windows, si existe."""
    for base in _windows_program_dirs():
        candidate = os.path.join(base, 'VideoLAN', 'VLC')
        if os.path.isfile(os.path.join(candidate, 'libvlc.dll')):
            return candidate
    return None


def check_platform():
    """Informa del sistema detectado."""
    frozen = 'instalador' if getattr(sys, 'frozen', False) else 'código fuente'
    return _status_ok(
        'Sistema operativo',
        platform_name(),
        f'Comprobaciones adaptadas a {platform_name()} ({frozen}).',
    )


def check_data_directory(path=None):
    """Comprueba que la carpeta de datos existe y es escribible."""
    path = path or data_dir()
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, '.write_test')
        with open(probe, 'w', encoding='utf-8') as handle:
            handle.write('ok')
        os.remove(probe)
    except OSError as exc:
        return _status_fail(
            'Carpeta de datos',
            f'No se puede escribir en {path}',
            str(exc),
        )
    return _status_ok(
        'Carpeta de datos',
        path,
        _data_dir_hint(path),
    )


def check_vlc():
    """Comprueba que python-vlc puede crear una instancia de libVLC."""
    try:
        import vlc
    except ImportError:
        hint = _platform_install_hint('vlc')
        if sys.platform.startswith('linux'):
            hint += ' En Ubuntu/Debian también hace falta python3-vlc.'
        return _status_fail(
            'VLC (libVLC)',
            'No está instalado el módulo python-vlc.',
            hint,
        )
    instance = None
    try:
        instance = vlc.Instance('--quiet')
        if instance is None:
            return _vlc_failure('libVLC no respondió al crear la instancia.')
    except Exception as exc:
        return _vlc_failure('No se pudo inicializar libVLC.', str(exc))
    finally:
        if instance is not None:
            try:
                instance.release()
            except Exception:
                pass
    return _status_ok(
        'VLC (libVLC)',
        f'Versión detectada: {vlc_version_text()}',
        'Reproductor IPTV y YouTube embebido.',
    )


def _vlc_failure(detail, extra=''):
    """Estado de error de VLC con pista según plataforma."""
    hint = _platform_install_hint('vlc')
    if sys.platform == 'win32':
        install_dir = _vlc_install_dir_windows()
        if install_dir:
            hint = (
                f'VLC parece instalado en {install_dir}, pero libVLC no arrancó. '
                'Reinstala VLC, reinicia el PC o añade esa carpeta al PATH.'
            )
        else:
            hint = (
                'Instala VLC desde videolan.org. Marca «Add to PATH» durante la instalación '
                'o añade C:\\Program Files\\VideoLAN\\VLC al PATH del sistema.'
            )
    elif sys.platform.startswith('linux'):
        hint += ' En Ubuntu/Debian: sudo apt install vlc python3-vlc.'
    message = hint if not extra else f'{hint} ({extra})'
    return _status_fail('VLC (libVLC)', detail, message)


def check_ffmpeg():
    """Comprueba si ffmpeg está disponible (PATH o rutas habituales)."""
    binary = find_executable('ffmpeg')
    if not binary:
        return _status_warn(
            'ffmpeg',
            'No encontrado en el PATH ni en rutas habituales.',
            f'{_platform_install_hint("ffmpeg")} Necesario para grabar IPTV y algunos relevos de YouTube.',
        )
    return _status_ok('ffmpeg', binary, 'Grabación IPTV y conversión de streams.')


def check_yt_dlp():
    """Comprueba que yt-dlp está disponible como módulo Python."""
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return _status_fail(
            'yt-dlp',
            'No se pudo importar el módulo yt-dlp.',
            'Reinstala las dependencias del programa (pip install -r requirements.txt).',
        )
    version = getattr(yt_dlp, 'version', None)
    label = getattr(version, '__version__', None) if version else None
    detail = f'v{label}' if label else 'Módulo importado correctamente.'
    return _status_ok('yt-dlp', detail, 'Búsqueda y reproducción de YouTube.')


def check_youtube_session():
    """Informa del estado de cookies.txt para YouTube."""
    from youtube_player import inspect_youtube_session

    info = inspect_youtube_session()
    if info.get('ok'):
        return _status_ok('Sesión YouTube', 'Cookies de login vigentes.')
    reason = info.get('reason') or 'sin sesión'
    return _status_warn(
        'Sesión YouTube',
        f'No hay sesión activa ({reason}).',
        _session_cookie_hint(),
    )


def check_twitch_session():
    """Informa del estado de twitch_cookies.txt."""
    from twitch_player import inspect_twitch_session

    info = inspect_twitch_session()
    if info.get('ok'):
        return _status_ok('Sesión Twitch', 'Cookies de login vigentes.')
    reason = info.get('reason') or 'sin sesión'
    return _status_warn(
        'Sesión Twitch',
        f'Sin sesión ({reason}).',
        'Opcional: inicia sesión en Twitch y reexporta cookies si usas directos de Twitch.',
    )


def check_twitch_chat_linux():
    """En Linux, avisa si falta WebKitGTK para el chat integrado de Twitch."""
    if not sys.platform.startswith('linux'):
        return None
    try:
        from twitch_chat import pywebview_integrated_ready
        if pywebview_integrated_ready():
            return _status_ok(
                'Chat Twitch',
                'Ventana integrada disponible (pywebview).',
                'Opcional: ventana de chat integrada en directos de Twitch.',
            )
    except Exception:
        pass
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('WebKit2', '4.1')
        from gi.repository import Gtk, WebKit2  # noqa: F401
    except Exception:
        return _status_warn(
            'Chat Twitch (Linux)',
            'WebKitGTK no disponible.',
            'Opcional: sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1',
        )
    return _status_ok(
        'Chat Twitch (Linux)',
        'WebKitGTK disponible.',
        'Opcional: ventana de chat integrada en directos de Twitch.',
    )


def check_twitch_chat():
    """Comprueba si el chat integrado de Twitch puede abrirse en esta plataforma."""
    if sys.platform.startswith('linux'):
        return check_twitch_chat_linux()
    try:
        from twitch_chat import chat_backend_status
        backend, detail = chat_backend_status()
    except Exception as exc:
        return _status_warn(
            'Chat Twitch',
            'No se pudo comprobar pywebview.',
            f'Reinstala dependencias con run_app.py ({exc}).',
        )
    if backend == 'pywebview':
        label = platform_name()
        return _status_ok(
            'Chat Twitch',
            f'Ventana integrada disponible ({label}).',
            'Opcional: ventana de chat integrada en directos de Twitch.',
        )
    hint = detail or 'Reinstala dependencias con run_app.py.'
    return _status_warn(
        'Chat Twitch',
        'Ventana integrada no disponible; se usará el navegador.',
        hint,
    )


def run_environment_checks(include_sessions=False):
    """Ejecuta todas las comprobaciones del asistente."""
    checks = [
        check_platform(),
        check_data_directory(),
        check_vlc(),
        check_ffmpeg(),
        check_yt_dlp(),
    ]
    twitch_chat = check_twitch_chat()
    if twitch_chat is not None:
        checks.append(twitch_chat)
    if include_sessions:
        checks.extend([check_youtube_session(), check_twitch_session()])
    return checks


def _status_label_style(status):
    if status == 'ok':
        return 'SessionOk.TLabel'
    if status == 'warn':
        return 'Muted.TLabel'
    return 'SessionBad.TLabel'


def _status_prefix(status):
    if status == 'ok':
        return 'OK'
    if status == 'warn':
        return 'Aviso'
    return 'Falta'


class OnboardingWizard:
    """Ventana modal con pasos de bienvenida, comprobaciones y sesión."""

    def __init__(self, parent, on_open_preferences=None, on_finish=None, allow_skip=True):
        self.parent = parent
        self.on_open_preferences = on_open_preferences
        self.on_finish = on_finish
        self.allow_skip = allow_skip
        self.step_index = 0
        self.check_rows = []
        self.session_rows = []

        self.window = tk.Toplevel(parent)
        self.window.title('Asistente de configuración')
        setup_resizable_dialog(self.window, 580, 560, 480, 440)
        self.window.transient(parent)
        self.window.grab_set()
        style_window(self.window)
        set_window_icon(self.window)
        self.window.protocol('WM_DELETE_WINDOW', self._skip)

        shell = ttk.Frame(self.window, padding=(20, 18, 20, 14))
        shell.pack(fill=tk.BOTH, expand=True)
        bind_wraplength(shell, padding=48)

        self.title_var = tk.StringVar()
        ttk.Label(shell, textvariable=self.title_var, style='PageTitle.TLabel').pack(anchor=tk.W)
        self.subtitle_var = tk.StringVar()
        ttk.Label(shell, textvariable=self.subtitle_var, style='Muted.TLabel').pack(
            anchor=tk.W, pady=(0, 12),
        )

        self.content = ttk.Frame(shell)
        self.content.pack(fill=tk.BOTH, expand=True)

        self.steps = [
            self._build_welcome_step(),
            self._build_checks_step(),
            self._build_session_step(),
            self._build_finish_step(),
        ]
        for step in self.steps:
            step.pack(fill=tk.BOTH, expand=True)
            step.pack_forget()

        nav = ttk.Frame(shell)
        nav.pack(fill=tk.X, pady=(12, 0))
        self.back_btn = ttk.Button(nav, text='Anterior', command=self._prev_step)
        self.back_btn.pack(side=tk.LEFT)
        self.skip_btn = ttk.Button(nav, text='Omitir asistente', command=self._skip)
        self.skip_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.next_btn = ttk.Button(nav, text='Siguiente', style='Accent.TButton', command=self._next_step)
        self.next_btn.pack(side=tk.RIGHT)
        self.prefs_btn = ttk.Button(nav, text='Abrir Preferencias', command=self._open_preferences)
        self.prefs_btn.pack(side=tk.RIGHT, padx=(0, 8))

        if not allow_skip:
            self.skip_btn.pack_forget()

        self._show_step(0)

    def _build_welcome_step(self):
        frame = ttk.Frame(self.content)
        text = (
            f'Bienvenido a Kidneys M3U (v{APP_VERSION}).\n\n'
            'Este asistente comprueba que el entorno está listo para reproducir IPTV y YouTube, '
            'y te indica cómo configurar la sesión de cookies si la necesitas.\n\n'
            'Puedes volver a abrirlo en cualquier momento desde Ayuda → Asistente de configuración.'
        )
        ttk.Label(frame, text=text, justify=tk.LEFT).pack(anchor=tk.W, fill=tk.X)
        return frame

    def _build_checks_step(self):
        frame = ttk.Frame(self.content)
        header = ttk.Frame(frame)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            header,
            text='Comprobaciones del sistema',
            style='Section.TLabel',
        ).pack(side=tk.LEFT)
        ttk.Button(header, text='Comprobar de nuevo', command=self._refresh_checks).pack(side=tk.RIGHT)

        self.checks_host = ttk.Frame(frame)
        self.checks_host.pack(fill=tk.BOTH, expand=True)
        self._render_checks(run_environment_checks(include_sessions=False))
        return frame

    def _build_session_step(self):
        frame = ttk.Frame(self.content)
        intro = (
            'YouTube y Twitch pueden pedir cookies del navegador para reproducir contenido restringido '
            'o mantener la sesión iniciada.\n\n'
            f'{_session_cookie_hint()}'
        )
        ttk.Label(frame, text=intro, justify=tk.LEFT).pack(anchor=tk.W, fill=tk.X, pady=(0, 10))

        actions = ttk.Frame(frame)
        actions.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(
            actions,
            text='Abrir pestaña Cookies',
            command=self._open_preferences,
        ).pack(side=tk.LEFT)
        ttk.Button(
            actions,
            text='Actualizar estado',
            command=self._refresh_sessions,
        ).pack(side=tk.LEFT, padx=(8, 0))

        self.session_host = ttk.Frame(frame)
        self.session_host.pack(fill=tk.BOTH, expand=True)
        self._render_sessions()
        return frame

    def _build_finish_step(self):
        frame = ttk.Frame(self.content)
        self.finish_label = ttk.Label(frame, text='', justify=tk.LEFT)
        self.finish_label.pack(anchor=tk.W, fill=tk.X)
        return frame

    def _clear_frame(self, host):
        for child in host.winfo_children():
            child.destroy()

    def _render_check_row(self, host, check, rows):
        row = ttk.Frame(host)
        row.pack(fill=tk.X, pady=(0, 10))
        rows.append(row)

        head = ttk.Frame(row)
        head.pack(fill=tk.X)
        ttk.Label(
            head,
            text=f'{_status_prefix(check["status"])} · {check["title"]}',
            style=_status_label_style(check['status']),
        ).pack(side=tk.LEFT)
        if check.get('detail'):
            ttk.Label(head, text=check['detail'], style='Muted.TLabel').pack(side=tk.RIGHT)

        if check.get('hint'):
            ttk.Label(row, text=check['hint'], style='Muted.TLabel', wraplength=500).pack(
                anchor=tk.W, fill=tk.X, pady=(2, 0),
            )

    def _render_checks(self, checks):
        self._clear_frame(self.checks_host)
        self.check_rows = []
        for check in checks:
            self._render_check_row(self.checks_host, check, self.check_rows)

    def _render_sessions(self):
        self._clear_frame(self.session_host)
        self.session_rows = []
        for check in (check_youtube_session(), check_twitch_session()):
            self._render_check_row(self.session_host, check, self.session_rows)

    def _refresh_checks(self):
        self._render_checks(run_environment_checks(include_sessions=False))

    def _refresh_sessions(self):
        self._render_sessions()

    def _open_preferences(self):
        if self.on_open_preferences:
            self.on_open_preferences()
        self.window.after(400, self._refresh_sessions)

    def _show_step(self, index):
        self.step_index = index
        for i, step in enumerate(self.steps):
            if i == index:
                step.pack(fill=tk.BOTH, expand=True)
            else:
                step.pack_forget()

        titles = [
            'Bienvenida',
            'Entorno',
            'Sesión YouTube / Twitch',
            'Listo',
        ]
        subtitles = [
            'Comprobación inicial al primer uso.',
            'Dependencias necesarias para reproducir y descargar.',
            'Opcional, pero recomendable si usas YouTube con tu cuenta.',
            'Resumen antes de empezar.',
        ]
        self.title_var.set(titles[index])
        self.subtitle_var.set(subtitles[index])

        self.back_btn.state(['!disabled'] if index > 0 else ['disabled'])
        self.prefs_btn.pack_forget()
        if index == 2:
            self.prefs_btn.pack(side=tk.RIGHT, padx=(0, 8), before=self.next_btn)

        if index == len(self.steps) - 1:
            self._update_finish_summary()
            self.next_btn.configure(text='Empezar', command=self._complete)
        else:
            self.next_btn.configure(text='Siguiente', command=self._next_step)

    def _update_finish_summary(self):
        checks = run_environment_checks(include_sessions=True)
        fails = [c for c in checks if c['status'] == 'fail']
        warns = [c for c in checks if c['status'] == 'warn']
        if fails:
            summary = (
                f'Hay {len(fails)} comprobación(es) crítica(s) pendiente(s). '
                'Puedes usar la aplicación con limitaciones o corregirlas y volver a abrir el asistente.'
            )
        elif warns:
            summary = (
                f'Todo lo esencial está listo. Quedan {len(warns)} aviso(s) opcionales '
                '(ffmpeg o sesión de cookies). Puedes continuar y ajustarlo más tarde.'
            )
        else:
            summary = 'Todo listo. Ya puedes abrir listas M3U, reproducir IPTV y buscar en YouTube.'
        self.finish_label.configure(text=summary)

    def _prev_step(self):
        if self.step_index > 0:
            self._show_step(self.step_index - 1)

    def _next_step(self):
        if self.step_index < len(self.steps) - 1:
            next_index = self.step_index + 1
            if next_index == 2:
                self._refresh_sessions()
            if next_index == len(self.steps) - 1:
                self._refresh_checks()
            self._show_step(next_index)

    def _skip(self):
        app_config.set_onboarding_completed(True)
        if self.on_finish:
            self.on_finish(skipped=True)
        self.window.destroy()

    def _complete(self):
        app_config.set_onboarding_completed(True)
        if self.on_finish:
            self.on_finish(skipped=False)
        self.window.destroy()


def show_onboarding_wizard(parent, on_open_preferences=None, on_finish=None, force=False):
    """Muestra el asistente si hace falta (o si force=True)."""
    if not force and not app_config.needs_onboarding():
        return None
    return OnboardingWizard(
        parent,
        on_open_preferences=on_open_preferences,
        on_finish=on_finish,
        allow_skip=True,
    )
