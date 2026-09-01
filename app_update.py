"""Avisos y actualización desde GitHub Releases (.exe / .deb)."""

import os
import re
import sys
import threading
import tempfile
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

import requests

import app_config
import app_version
from display_text import plain_ui_line
from ui_theme import style_window, set_window_icon, center_window
from ui_layout import bind_wraplength, setup_resizable_dialog

CHECK_INTERVAL_S = 24 * 3600
MAX_ASSET_BYTES = 200 * 1024 * 1024
_USER_AGENT = f'kidneysm3u/{app_version.__version__}'
_busy = False
_dialog = None


def current_version():
    return normalize_version(app_version.__version__) or '0'


def normalize_version(text):
    """Extrae x.y o x.y.z de tags tipo Versión1.2.3, v1.2.3 o 1.2.3."""
    raw = str(text or '').strip()
    if not raw:
        return ''
    raw = re.sub(r'(?i)^versi[oó]n\s*', '', raw)
    raw = re.sub(r'(?i)^v(?=\d)', '', raw)
    match = re.search(r'(\d+\.\d+(?:\.\d+)*)', raw)
    return match.group(1) if match else ''


def version_tuple(text):
    parts = []
    for chunk in normalize_version(text).split('.'):
        if chunk.isdigit():
            parts.append(int(chunk))
    return tuple(parts) or (0,)


def is_newer_version(remote, local):
    left = list(version_tuple(remote))
    right = list(version_tuple(local))
    size = max(len(left), len(right))
    left.extend([0] * (size - len(left)))
    right.extend([0] * (size - len(right)))
    return tuple(left) > tuple(right)


def install_kind(frozen=None, platform=None, here=None, share_version=None, data_home=None):
    """windows = instalador, deb = paquete Ubuntu, source = código."""
    frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
    platform = sys.platform if platform is None else platform
    if frozen:
        return 'windows' if platform == 'win32' else 'frozen'
    here = os.path.normpath(here or os.path.dirname(os.path.abspath(__file__)))
    share = os.path.normpath('/usr/share/kidneysm3u')
    if share_version is None:
        share_version = os.path.isfile('/usr/share/kidneysm3u/VERSION')
    xdg = data_home if data_home is not None else os.environ.get('XDG_DATA_HOME')
    if xdg:
        local = os.path.normpath(os.path.join(xdg, 'kidneysm3u'))
    else:
        local = os.path.normpath(os.path.expanduser('~/.local/share/kidneysm3u'))
    if share_version and here in (share, local):
        return 'deb'
    return 'source'


def safe_asset_filename(name):
    text = str(name or '').strip()
    if not text or text != os.path.basename(text):
        return None
    if not re.fullmatch(r'[\w.+-]+', text, re.I):
        return None
    if text.lower().endswith(('.exe', '.deb')):
        return text
    return None


def pick_release_asset(assets, kind):
    items = []
    for asset in assets or []:
        if not isinstance(asset, dict):
            continue
        name = safe_asset_filename(asset.get('name'))
        url = str(asset.get('browser_download_url') or '').strip()
        if not name or not url.startswith('https://'):
            continue
        try:
            size = int(asset.get('size') or 0)
        except (TypeError, ValueError):
            size = 0
        items.append((name, url, size))
    if kind == 'windows':
        for name, url, size in items:
            lower = name.lower()
            if lower.endswith('.exe') and 'setup' in lower and 'kidneys' in lower:
                return {'name': name, 'url': url, 'size': size}
        for name, url, size in items:
            if name.lower().endswith('.exe') and 'kidneys' in name.lower():
                return {'name': name, 'url': url, 'size': size}
    if kind == 'deb':
        for name, url, size in items:
            lower = name.lower()
            if lower.endswith('.deb') and lower.startswith('kidneysm3u'):
                return {'name': name, 'url': url, 'size': size}
    return None


def parse_latest_release(payload):
    if not isinstance(payload, dict):
        return None
    tag = str(payload.get('tag_name') or '').strip()
    title = str(payload.get('name') or '').strip()
    version = normalize_version(tag) or normalize_version(title)
    if not version:
        return None
    tag = tag or title
    assets = payload.get('assets') if isinstance(payload.get('assets'), list) else []
    page = str(payload.get('html_url') or '').strip() or app_version.GITHUB_LATEST_PAGE
    return {
        'version': version,
        'tag': tag,
        'url': page,
        'assets': [
            {
                'name': item.get('name'),
                'browser_download_url': item.get('browser_download_url'),
                'size': item.get('size') or 0,
            }
            for item in assets
            if isinstance(item, dict)
        ],
    }


def fetch_latest_release(timeout=12):
    response = requests.get(
        app_version.GITHUB_LATEST_API,
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': _USER_AGENT,
            'X-GitHub-Api-Version': '2022-11-28',
        },
        timeout=timeout,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return parse_latest_release(response.json())


def _cache_is_fresh(now=None):
    import time
    now = time.time() if now is None else now
    checked = app_config.get_app_update_checked_at()
    return checked > 0 and (now - checked) < CHECK_INTERVAL_S


def check_for_app_update(force=False):
    """Compara la versión local con la última de GitHub. No registra URLs."""
    local = current_version()
    kind = install_kind()
    cached = app_config.get_app_update_cache()
    remote = cached if (cached and not force and _cache_is_fresh()) else None
    error = ''
    if remote is None:
        try:
            remote = fetch_latest_release()
        except Exception as exc:
            error = str(exc) or 'No se pudo consultar GitHub.'
            remote = cached
        else:
            if remote:
                app_config.set_app_update_cache(remote)
    if not remote:
        return {
            'local': local,
            'remote': '',
            'newer': False,
            'kind': kind,
            'asset': None,
            'url': app_version.GITHUB_RELEASES_URL,
            'error': error or 'No hay lanzamientos publicados.',
        }
    asset = pick_release_asset(remote.get('assets'), kind)
    return {
        'local': local,
        'remote': remote.get('version') or '',
        'newer': is_newer_version(remote.get('version'), local),
        'kind': kind,
        'asset': asset,
        'url': remote.get('url') or app_version.GITHUB_RELEASES_URL,
        'error': error,
    }


def download_release_asset(url, filename, dest_dir=None, timeout=60):
    name = safe_asset_filename(filename)
    if not name:
        raise ValueError('Nombre de paquete no válido.')
    folder = dest_dir or tempfile.gettempdir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with requests.get(
        url,
        headers={'User-Agent': _USER_AGENT, 'Accept': 'application/octet-stream'},
        stream=True,
        timeout=timeout,
    ) as response:
        response.raise_for_status()
        try:
            total = int(response.headers.get('Content-Length') or 0)
        except (TypeError, ValueError):
            total = 0
        if total > MAX_ASSET_BYTES:
            raise ValueError('El paquete es demasiado grande.')
        written = 0
        with open(path, 'wb') as handle:
            for chunk in response.iter_content(chunk_size=256 * 1024):
                if not chunk:
                    continue
                written += len(chunk)
                if written > MAX_ASSET_BYTES:
                    handle.close()
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    raise ValueError('El paquete es demasiado grande.')
                handle.write(chunk)
    if not os.path.isfile(path) or os.path.getsize(path) < 1024:
        raise ValueError('La descarga está vacía o incompleta.')
    return path


def launch_windows_installer(path):
    if os.name == 'nt':
        os.startfile(path)  # noqa: S606 — instalador local recién descargado
        return
    subprocess.Popen(['cmd.exe', '/c', 'start', '', path], close_fds=True)


def install_debian_package(path):
    try:
        completed = subprocess.run(
            ['pkexec', 'dpkg', '-i', path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=300,
        )
    except FileNotFoundError:
        return False, 'pkexec'
    except subprocess.TimeoutExpired:
        return False, 'timeout'
    if completed.returncode == 0:
        return True, ''
    output = (completed.stdout or b'').decode('utf-8', errors='replace').strip()
    return False, output.splitlines()[-1] if output else f'Código {completed.returncode}'


def start_startup_update_check(root, quit_app=None):
    if not app_config.get_check_app_updates():
        return
    _start_check(root, quit_app=quit_app, force=False, silent_if_current=True)


def start_manual_update_check(root, quit_app=None, status_var=None):
    if status_var is not None:
        try:
            status_var.set(plain_ui_line('Buscando actualizaciones…'))
        except tk.TclError:
            pass
    _start_check(
        root,
        quit_app=quit_app,
        force=True,
        silent_if_current=False,
        status_var=status_var,
    )


def _start_check(root, quit_app=None, force=False, silent_if_current=True, status_var=None):
    global _busy
    if _busy:
        if not silent_if_current:
            try:
                messagebox.showinfo('Actualización', 'Ya hay una comprobación en curso.', parent=root)
            except tk.TclError:
                pass
        return
    _busy = True

    def work():
        global _busy
        try:
            result = check_for_app_update(force=force)
        except Exception as exc:
            result = {
                'local': current_version(),
                'remote': '',
                'newer': False,
                'kind': install_kind(),
                'asset': None,
                'url': app_version.GITHUB_RELEASES_URL,
                'error': str(exc) or 'Error desconocido.',
            }
        try:
            root.after(
                0,
                lambda: _on_check_done(root, result, quit_app, silent_if_current, status_var),
            )
        except tk.TclError:
            _busy = False

    threading.Thread(target=work, daemon=True, name='app-update-check').start()


def _on_check_done(root, result, quit_app, silent_if_current, status_var=None):
    global _busy
    _busy = False
    try:
        if not root.winfo_exists():
            return
    except tk.TclError:
        return
    if status_var is not None:
        try:
            if result.get('error') and not result.get('remote'):
                status_var.set('No se pudo buscar actualizaciones')
            elif result.get('newer'):
                status_var.set(f'Hay una versión nueva ({result.get("remote")})')
            else:
                status_var.set(f'Ya tienes la última versión ({result.get("local") or current_version()})')
        except tk.TclError:
            pass
    if result.get('error') and not result.get('remote'):
        if not silent_if_current:
            messagebox.showerror(
                'Actualización',
                'No se pudo comprobar si hay una versión nueva.\nComprueba la red e inténtalo más tarde.',
                parent=root,
            )
        return
    if not result.get('newer'):
        if not silent_if_current:
            messagebox.showinfo(
                'Actualización',
                f'Ya tienes la última versión ({result.get("local") or current_version()}).',
                parent=root,
            )
        return
    if not app_config.get_check_app_updates() and silent_if_current:
        return
    show_update_dialog(root, result, quit_app=quit_app)


def show_update_dialog(root, result, quit_app=None):
    global _dialog
    if _dialog is not None:
        try:
            if _dialog.winfo_exists():
                _dialog.lift()
                _dialog.focus_force()
                return _dialog
        except tk.TclError:
            _dialog = None

    local = result.get('local') or current_version()
    remote = result.get('remote') or ''
    kind = result.get('kind') or install_kind()
    asset = result.get('asset')
    page = result.get('url') or app_version.GITHUB_RELEASES_URL
    can_install = kind in ('windows', 'deb') and bool(asset)

    window = tk.Toplevel(root)
    window.title('Nueva versión')
    setup_resizable_dialog(window, 460, 280, 420, 240)
    window.transient(root)
    style_window(window)
    set_window_icon(window)
    _dialog = window

    frame = ttk.Frame(window, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    bind_wraplength(frame, padding=40)

    ttk.Label(frame, text='Hay una versión nueva', style='PageTitle.TLabel').pack(anchor=tk.W)
    ttk.Label(
        frame,
        text=f'Tienes {local}. En GitHub está {remote}.',
        style='Muted.TLabel',
    ).pack(anchor=tk.W, pady=(4, 10))

    if kind == 'source':
        detail = (
            'Estás usando el código fuente: abre la página de lanzamientos para '
            'bajar el paquete o actualizar el repositorio. El instalador no se aplica encima del código.'
        )
        action_label = 'Abrir lanzamientos'
    elif can_install:
        package = asset.get('name') if asset else ''
        detail = (
            f'Se descargará {package} y se instalará encima de esta copia. '
            'Preferencias, cookies y favoritos se conservan.'
        )
        action_label = 'Actualizar'
    else:
        detail = (
            'Hay una versión nueva, pero en este lanzamiento no está el paquete de tu sistema. '
            'Ábrelo en el navegador.'
        )
        action_label = 'Abrir lanzamientos'

    ttk.Label(frame, text=detail, wraplength=400, justify=tk.LEFT).pack(anchor=tk.W)
    status = tk.StringVar(value='')
    ttk.Label(frame, textvariable=status, style='Muted.TLabel', wraplength=400).pack(
        anchor=tk.W, pady=(12, 0)
    )

    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X, side=tk.BOTTOM, pady=(16, 0))

    def close():
        global _dialog
        if _dialog is window:
            _dialog = None
        window.destroy()

    def disable_notices():
        app_config.set_check_app_updates(False)
        close()

    def later():
        close()

    def open_page():
        webbrowser.open_new(page)
        close()

    def apply_update():
        if kind == 'source' or not can_install:
            open_page()
            return
        for child in (update_btn, later_btn, skip_btn):
            try:
                child.configure(state=tk.DISABLED)
            except tk.TclError:
                pass
        status.set(plain_ui_line('Descargando el paquete…'))

        def work():
            try:
                path = download_release_asset(asset['url'], asset['name'])
                error = ''
            except Exception as exc:
                path = ''
                error = str(exc) or 'No se pudo descargar.'

            def done():
                if error or not path:
                    status.set('')
                    for child in (update_btn, later_btn, skip_btn):
                        try:
                            child.configure(state=tk.NORMAL)
                        except tk.TclError:
                            pass
                    messagebox.showerror(
                        'Actualización',
                        'No se pudo descargar el paquete.\nComprueba la red e inténtalo de nuevo.',
                        parent=window,
                    )
                    return
                if kind == 'windows':
                    try:
                        launch_windows_installer(path)
                    except OSError:
                        status.set('')
                        for child in (update_btn, later_btn, skip_btn):
                            try:
                                child.configure(state=tk.NORMAL)
                            except tk.TclError:
                                pass
                        messagebox.showerror(
                            'Actualización',
                            'No se pudo abrir el instalador. Prueba a ejecutarlo a mano desde la carpeta temporal.',
                            parent=window,
                        )
                        return
                    close()
                    if callable(quit_app):
                        quit_app()
                    return
                status.set(plain_ui_line('Instalando el paquete (pide confirmación de administrador)…'))
                window.update_idletasks()

                def install():
                    ok, detail = install_debian_package(path)

                    def after_install():
                        if ok:
                            messagebox.showinfo(
                                'Actualización',
                                'Se instaló la versión nueva. Cierra el programa y ábrelo otra vez '
                                '(comando kidneysm3u) para cargar el código actualizado.',
                                parent=window,
                            )
                            close()
                            return
                        status.set('')
                        for child in (update_btn, later_btn, skip_btn):
                            try:
                                child.configure(state=tk.NORMAL)
                            except tk.TclError:
                                pass
                        messagebox.showerror(
                            'Actualización',
                            'No se pudo instalar el .deb.\n'
                            f'Puedes instalarlo a mano:\nsudo dpkg -i {path}',
                            parent=window,
                        )

                    try:
                        window.after(0, after_install)
                    except tk.TclError:
                        pass

                threading.Thread(target=install, daemon=True, name='app-update-deb').start()

            try:
                window.after(0, done)
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True, name='app-update-download').start()

    update_btn = ttk.Button(buttons, text=action_label, style='Accent.TButton', command=apply_update)
    update_btn.pack(side=tk.LEFT)
    later_btn = ttk.Button(buttons, text='Más tarde', command=later)
    later_btn.pack(side=tk.LEFT, padx=(8, 0))
    skip_btn = ttk.Button(buttons, text='No avisarme', command=disable_notices)
    skip_btn.pack(side=tk.RIGHT)

    window.protocol('WM_DELETE_WINDOW', close)
    window.bind('<Escape>', lambda event: close())
    return window
