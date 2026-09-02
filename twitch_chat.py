"""Chat de Twitch en directo: ventana flotante con embed web o navegador externo."""

import html
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import messagebox
from urllib.parse import quote

import app_config
from display_text import plain_display_text, plain_ui_line

try:
    import webview
except ImportError:
    webview = None

_CHANNEL_RE = re.compile(r'^[a-z0-9_]{1,25}$')
_GEOM_RE = re.compile(r'^(\d+)x(\d+)(?:\+-?\d+\+-?\d+)?$')
_GI_CHECK = (
    'import gi; '
    'gi.require_version("Gtk", "3.0"); '
    'gi.require_version("WebKit2", "4.1"); '
    'from gi.repository import Gtk, WebKit2'
)
_LAUNCHER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'twitch_chat_launcher.py')


def twitch_popout_chat_url(channel):
    """Twitch popout chat url."""
    channel = (channel or '').strip().lower()
    if not channel:
        return ''
    return f'https://www.twitch.tv/popout/{quote(channel)}/chat?popout='


def chat_embed_html(channel, parent_host='127.0.0.1'):
    """Chat embed html."""
    channel = plain_display_text(channel, '').strip().lower()
    if not _CHANNEL_RE.match(channel):
        channel = 'twitch'
    safe = html.escape(channel, quote=True)
    parent = html.escape(str(parent_host or '127.0.0.1'), quote=True)
    sandbox = (
        'allow-storage-access-by-user-activation allow-scripts allow-same-origin '
        'allow-popups allow-popups-to-escape-sandbox allow-modals'
    )
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<style>html,body{margin:0;padding:0;height:100%;background:#18181b;}'
        'iframe{border:0;width:100%;height:100%;}</style></head><body>'
        f'<iframe sandbox="{sandbox}" '
        f'src="https://www.twitch.tv/embed/{safe}/chat?parent={parent}&darkpopout"></iframe>'
        '</body></html>'
    )


def twitch_chat_window_url(channel):
    """URL para la ventana integrada de chat (popout oficial de Twitch)."""
    url = twitch_popout_chat_url(channel)
    return url or chat_local_embed_url(channel)


def chat_local_embed_url(channel, host='127.0.0.1', port=0):
    """Chat local embed url."""
    if port:
        return f'http://{host}:{port}/'
    return ''


def pywebview_integrated_ready():
    """True si pywebview puede abrir ventanas en esta plataforma (GTK, WebView2, Cocoa…)."""
    if webview is None:
        return False
    try:
        import webview.guilib as guilib_module

        if guilib_module.guilib is not None:
            return True
        guilib_module.initialize()
        return guilib_module.guilib is not None
    except Exception:
        return False


def pywebview_gtk_ready():
    """Compatibilidad: en Linux comprueba GTK; en el resto, cualquier backend de pywebview."""
    if sys.platform.startswith('linux'):
        if webview is None:
            return False
        try:
            from webview.guilib import import_gtk
            import_gtk()
            return True
        except Exception:
            return False
    return pywebview_integrated_ready()


def _python_has_gi(python_exe):
    """Uso interno: python has gi."""
    if not python_exe or not os.path.isfile(python_exe):
        return False
    try:
        completed = subprocess.run(
            [python_exe, '-c', _GI_CHECK],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if completed.returncode != 0:
            return False
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def system_python_with_gi():
    """Python del sistema con gi/WebKit, para lanzar la ventana en subprocess (solo Linux)."""
    if not sys.platform.startswith('linux'):
        return ''
    if pywebview_integrated_ready():
        return ''
    seen = set()
    for candidate in ('/usr/bin/python3', '/usr/local/bin/python3'):
        if not os.path.isfile(candidate):
            continue
        real = os.path.realpath(candidate)
        if real in seen:
            continue
        seen.add(real)
        if _python_has_gi(candidate):
            return candidate
    which = shutil.which('python3')
    if which:
        real = os.path.realpath(which)
        if real not in seen and _python_has_gi(which):
            return which
    return ''


def _browser_fallback_reason():
    """Mensaje al abrir el chat en el navegador por falta de ventana integrada."""
    if webview is None:
        return 'Falta instalar pywebview en el entorno virtual (run_app.py).'
    if sys.platform == 'win32':
        return (
            'No se pudo abrir la ventana integrada con pywebview.\n'
            'Reinstala dependencias desde la carpeta del programa:\n'
            '  .venv\\Scripts\\pip install pywebview pythonnet\n'
            'También necesitas Microsoft Edge WebView2 Runtime (habitual en Windows 10/11).'
        )
    if sys.platform == 'darwin':
        return (
            'No se pudo abrir la ventana integrada.\n'
            'Reinstala dependencias: pip install pywebview'
        )
    return (
        'PyGObject (gi) no está disponible para este Python.\n'
        'En Ubuntu: sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1\n'
        'Si usaste otro Python (p. ej. Conda), borra .venv y arranca con: /usr/bin/python3 run_app.py'
    )


def chat_backend_status():
    """Chat backend status."""
    if pywebview_integrated_ready():
        return 'pywebview', ''
    if sys.platform.startswith('linux'):
        system_py = system_python_with_gi()
        if system_py:
            return 'system_gtk', system_py
    return 'browser', _browser_fallback_reason()


class _ChatHandler(BaseHTTPRequestHandler):
    """Clase que representa chathandler."""
    channel = ''
    parent_host = '127.0.0.1'

    def log_message(self, format, *args):
        """Log message."""
        pass

    def do_GET(self):
        """Do get."""
        if self.path not in ('/', '/index.html'):
            self.send_error(404)
            return
        body = chat_embed_html(self.channel, self.parent_host).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _ChatServer:
    """Clase que representa chatserver."""
    def __init__(self):
        """Inicializa _ChatServer."""
        self.server = None
        self.port = 0
        self.thread = None

    def start(self, channel):
        """Start."""
        self.stop()
        handler = type('_Handler', (_ChatHandler,), {'channel': channel})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.port

    def stop(self):
        """Stop."""
        server = self.server
        self.server = None
        if not server:
            return
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass


def resolve_twitch_channel(handler):
    """Resolve twitch canal."""
    from twitch_player import twitch_display_name_from_url

    stream = getattr(handler, '_current_stream', None) or {}
    channel = plain_display_text(stream.get('channel') or '', '').strip()
    if channel and not channel.upper().startswith('VOD'):
        lowered = channel.lower()
        if _CHANNEL_RE.match(lowered):
            return lowered
    url = getattr(handler, '_current_url', '') or ''
    name = twitch_display_name_from_url(url)
    if name and not name.upper().startswith('VOD'):
        lowered = name.lower()
        if _CHANNEL_RE.match(lowered):
            return lowered
    return ''


def can_show_twitch_chat(handler=None, stream=None, url=''):
    """Can show twitch chat."""
    if handler is not None:
        stream = getattr(handler, '_current_stream', None) or stream or {}
        url = getattr(handler, '_current_url', '') or url
    stream = stream or {}
    if not stream.get('is_live'):
        return False
    if handler is not None:
        return bool(resolve_twitch_channel(handler))
    return bool(_channel_from_stream(stream, url))


def _channel_from_stream(stream, url=''):
    """Uso interno: canal from stream."""
    from twitch_player import twitch_display_name_from_url

    channel = plain_display_text((stream or {}).get('channel') or '', '').strip()
    if channel and not channel.upper().startswith('VOD'):
        lowered = channel.lower()
        if _CHANNEL_RE.match(lowered):
            return lowered
    name = twitch_display_name_from_url(url)
    if name and not name.upper().startswith('VOD'):
        lowered = name.lower()
        if _CHANNEL_RE.match(lowered):
            return lowered
    return ''


def _chat_window_size():
    """Uso interno: chat ventana size."""
    raw = (app_config.load().get('windows') or {}).get('twitch_chat') or '380x640'
    match = _GEOM_RE.match(str(raw).strip())
    if not match:
        return 380, 640
    width = max(280, min(900, int(match.group(1))))
    height = max(320, min(1200, int(match.group(2))))
    return width, height


def _remember_chat_size(width, height):
    """Uso interno: remember chat size."""
    try:
        width = max(280, min(900, int(width)))
        height = max(320, min(1200, int(height)))
    except (TypeError, ValueError):
        return
    app_config.remember_window('twitch_chat', f'{width}x{height}')


class TwitchChatPanel:
    """Clase que representa twitchchatpanel."""
    def __init__(self, handler):
        """Inicializa TwitchChatPanel."""
        self.handler = handler
        self._server = _ChatServer()
        self._channel = ''
        self._open = False
        self._browser_fallback = False
        self._webview_thread = None
        self._webview_window = None
        self._helper_proc = None
        self._lock = threading.Lock()

    def is_open(self):
        """Indica si open."""
        with self._lock:
            return bool(self._open)

    def available(self):
        """Available."""
        return can_show_twitch_chat(self.handler)

    def toggle(self):
        """Toggle."""
        if self.is_open():
            self.close()
            return
        self.open()

    def open(self, channel=None):
        """Open."""
        if not self.available():
            parent = getattr(getattr(self.handler, 'video_player', None), 'window', None)
            messagebox.showinfo(
                'Chat de Twitch',
                'El chat solo está disponible mientras ves un directo de Twitch.',
                parent=parent,
            )
            return False
        if channel is None:
            channel = resolve_twitch_channel(self.handler)
        channel = plain_display_text(channel, '').strip().lower()
        if not channel or not _CHANNEL_RE.match(channel):
            parent = getattr(getattr(self.handler, 'video_player', None), 'window', None)
            messagebox.showinfo(
                'Chat de Twitch',
                'No se pudo identificar el canal del directo.',
                parent=parent,
            )
            return False

        with self._lock:
            if self._open and self._channel == channel:
                return True
        self.close()
        self._channel = channel

        width, height = _chat_window_size()
        backend, detail = chat_backend_status()
        url = twitch_chat_window_url(channel)
        if not url:
            return False

        if backend == 'pywebview':
            thread = threading.Thread(
                target=self._run_pywebview,
                args=(url, channel, width, height),
                daemon=True,
                name='twitch-chat-webview',
            )
            self._webview_thread = thread
            thread.start()
            with self._lock:
                self._open = True
            self._notify_ui()
            return True

        if backend == 'system_gtk':
            if self._run_system_gtk(url, channel, width, height, detail):
                with self._lock:
                    self._open = True
                self._notify_ui()
                return True
            print('[TwitchChat] Falló la ventana GTK integrada; usando navegador.')

        return self._open_browser(channel, reason=detail)

    def close(self, notify_ui=True):
        """Close."""
        proc = self._helper_proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        window = self._webview_window
        if window is not None and webview is not None:
            try:
                webview.destroy_window(window)
            except Exception:
                pass
        self._server.stop()
        with self._lock:
            self._open = False
            self._browser_fallback = False
            self._channel = ''
            self._webview_window = None
            self._webview_thread = None
            self._helper_proc = None
        if notify_ui:
            self._notify_ui()

    def close_if_not_live(self):
        """Cierra if not live."""
        if not self.available():
            self.close()

    def _run_system_gtk(self, url, channel, width, height, python_exe):
        """Uso interno: run system gtk."""
        if not os.path.isfile(_LAUNCHER_PATH):
            print(f'[TwitchChat] No se encontró {_LAUNCHER_PATH}')
            return False
        if not python_exe:
            print('[TwitchChat] No hay Python del sistema con gi/WebKit.')
            return False
        try:
            proc = subprocess.Popen(
                [
                    python_exe,
                    _LAUNCHER_PATH,
                    '--url', url,
                    '--title', plain_ui_line(f'Chat · {channel}'),
                    '--width', str(width),
                    '--height', str(height),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
        except OSError as exc:
            print(f'[TwitchChat] No se pudo lanzar WebKitGTK: {exc}')
            return False
        if proc.poll() is not None:
            err = ''
            try:
                err = (proc.stderr.read() if proc.stderr else '').strip()
            except Exception:
                pass
            print(f'[TwitchChat] Ventana GTK terminó al instante{": " + err if err else ""}')
            return False
        self._helper_proc = proc
        threading.Thread(
            target=self._watch_helper_proc,
            args=(proc,),
            daemon=True,
            name='twitch-chat-gtk-watch',
        ).start()
        return True

    def _watch_helper_proc(self, proc):
        """Uso interno: watch helper proc."""
        err = ''
        try:
            _, err = proc.communicate()
        except Exception:
            pass
        if proc.returncode not in (0, None, -15, -9):
            if err:
                print(f'[TwitchChat] Ventana GTK: {err.strip()}')
        with self._lock:
            if self._helper_proc is proc:
                self._helper_proc = None
                self._open = False
                self._channel = ''
        self._server.stop()
        self._notify_ui()

    def _open_browser(self, channel, reason='', integrated=True):
        """Uso interno: open browser."""
        url = twitch_popout_chat_url(channel)
        if not url:
            return False
        webbrowser.open(url)
        with self._lock:
            self._open = True
            self._browser_fallback = True
            self._channel = channel
        parent = getattr(getattr(self.handler, 'video_player', None), 'window', None)
        if parent and integrated:
            lines = ['Se abrió el chat en el navegador.', '']
            if reason:
                lines.append(reason)
            else:
                lines.append(_browser_fallback_reason())
            messagebox.showinfo('Chat de Twitch', '\n'.join(lines), parent=parent)
        self._notify_ui()
        return True

    def _run_pywebview(self, url, channel, width, height):
        """Uso interno: run pywebview."""
        window = None
        try:
            window = webview.create_window(
                plain_ui_line(f'Chat · {channel}'),
                url=url,
                width=width,
                height=height,
                resizable=True,
                text_select=True,
            )
            with self._lock:
                self._webview_window = window

            def on_closed():
                """Responde al evento closed."""
                self._on_webview_closed(window)

            window.events.closed += on_closed
            webview.start()
        except Exception as exc:
            print(f'[TwitchChat] No se pudo abrir pywebview: {exc}')
            with self._lock:
                self._open = False
                self._webview_window = None
            self._server.stop()
            _, reason = chat_backend_status()
            self._open_browser(channel, reason=str(exc) or reason)
            return
        finally:
            self._server.stop()

    def _on_webview_closed(self, window):
        """Callback interno para webview closed."""
        with self._lock:
            if not self._open:
                return
        try:
            _remember_chat_size(window.width, window.height)
        except Exception:
            pass
        with self._lock:
            self._open = False
            self._browser_fallback = False
            self._channel = ''
            self._webview_window = None
            self._webview_thread = None
        self._server.stop()
        self._notify_ui()

    def _notify_ui(self):
        """Uso interno: notify interfaz."""
        player = getattr(self.handler, 'video_player', None)
        if not player:
            return
        window = getattr(player, 'window', None)
        refresh = getattr(player, 'update_twitch_chat_ui', None)
        if not refresh or not window:
            return
        try:
            if not window.winfo_exists():
                return
            window.after(0, refresh)
        except (tk.TclError, AttributeError, RuntimeError):
            pass


def start_chat_server(channel):
    """Inicia chat server."""
    server = _ChatServer()
    return server.start(channel), server
