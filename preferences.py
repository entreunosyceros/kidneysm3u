"""Ventana de preferencias: tema, volumen, descargas, cookies y sesión."""

import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import app_config
from ui_theme import apply_theme, get_colors, style_window, set_window_icon, center_window

COOKIE_LABELS = (
    ('auto', 'Automático (el que tenga sesión)'),
    ('firefox', 'Firefox'),
    ('chrome', 'Chrome'),
    ('chromium', 'Chromium'),
    ('brave', 'Brave'),
    ('edge', 'Edge'),
)

_YT_DLP_UPDATING = False


def yt_dlp_installed_version():
    try:
        from yt_dlp.version import __version__
        return str(__version__ or '').strip()
    except Exception:
        return ''


def yt_dlp_upgrade_cmd(python=None):
    return [
        python or sys.executable,
        '-m', 'pip',
        'install',
        '--upgrade',
        '--disable-pip-version-check',
        'yt-dlp[default]',
    ]


def parse_yt_dlp_pip_result(output, returncode=0):
    text = output or ''
    lower = text.lower()
    if returncode:
        if 'externally-managed-environment' in lower:
            return False, 'externally-managed'
        if 'permission denied' in lower:
            return False, 'permission'
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        return False, '\n'.join(lines[-8:]) or f'pip salió con código {returncode}'
    match = re.search(r'Successfully installed[^\n]*yt-dlp-([0-9][0-9A-Za-z.\-]+)', text)
    if match:
        return True, match.group(1)
    if 'yt-dlp' in lower and re.search(r'already (up-to-date|satisfied)', text, re.I):
        return True, 'already'
    return True, ''


def run_yt_dlp_upgrade(timeout=180):
    try:
        completed = subprocess.run(
            yt_dlp_upgrade_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, 'timeout'
    except OSError as exc:
        return False, str(exc)
    output = (completed.stdout or b'').decode('utf-8', errors='replace')
    return parse_yt_dlp_pip_result(output, completed.returncode)


def yt_dlp_update_message(ok, detail):
    current = yt_dlp_installed_version()
    if ok and detail == 'already':
        version = current or 'instalada'
        return True, f'Ya tienes la última versión ({version}).'
    if ok:
        version = detail or current or 'actualizado'
        return True, (
            f'Se instaló yt-dlp {version}.\n'
            'Cierra el programa y ábrelo otra vez para que cargue.'
        )
    if detail == 'externally-managed':
        return False, (
            'Este Python no deja instalar paquetes (entorno del sistema).\n'
            'Arranca con python3 run_app.py para usar el entorno .venv.'
        )
    if detail == 'permission':
        return False, (
            'No hay permiso para instalar yt-dlp.\n'
            'Arranca con python3 run_app.py o instálalo a mano en el entorno virtual.'
        )
    if detail == 'timeout':
        return False, 'La actualización tardó demasiado. Comprueba la red e inténtalo de nuevo.'
    return False, f'No se pudo actualizar.\n{detail or "Error desconocido."}'


def start_yt_dlp_upgrade(parent, on_done=None, busy_widgets=None):
    global _YT_DLP_UPDATING
    if _YT_DLP_UPDATING:
        messagebox.showinfo('yt-dlp', 'Ya hay una actualización en curso.', parent=parent)
        return
    _YT_DLP_UPDATING = True
    for widget in busy_widgets or ():
        try:
            widget.configure(state='disabled')
        except tk.TclError:
            pass

    def work():
        ok, detail = run_yt_dlp_upgrade()

        def finish():
            global _YT_DLP_UPDATING
            _YT_DLP_UPDATING = False
            for widget in busy_widgets or ():
                try:
                    widget.configure(state='normal')
                except tk.TclError:
                    pass
            success, text = yt_dlp_update_message(ok, detail)
            try:
                if success:
                    messagebox.showinfo('yt-dlp', text, parent=parent)
                else:
                    messagebox.showerror('yt-dlp', text, parent=parent)
            except tk.TclError:
                pass
            if on_done:
                on_done(ok, detail)

        try:
            parent.after(0, finish)
        except tk.TclError:
            _YT_DLP_UPDATING = False

    threading.Thread(target=work, daemon=True, name='yt-dlp-upgrade').start()


def _tk_root(widget):
    try:
        return widget.nametowidget('.')
    except tk.TclError:
        return widget.winfo_toplevel()


def show_preferences(parent, on_apply=None):
    root = _tk_root(parent)
    existing = getattr(root, '_prefs_window', None)
    if existing:
        try:
            if existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                return existing
        except tk.TclError:
            pass

    window = tk.Toplevel(parent)
    window.title('Preferencias')
    window.geometry('560x680')
    window.minsize(480, 420)
    window.transient(parent)
    style_window(window)
    set_window_icon(window)
    center_window(window, 560, 680)
    root._prefs_window = window

    theme_var = tk.StringVar(value=app_config.get_theme())
    volume_var = tk.IntVar(value=app_config.get_volume())
    volume_label_var = tk.StringVar(value=f'{volume_var.get()} %')
    download_var = tk.StringVar(value=app_config.get_download_dir())
    quality_var = tk.StringVar(value=str(app_config.get_youtube_quality()))
    buffer_var = tk.StringVar(value=app_config.get_iptv_buffer())
    cookie_var = tk.StringVar(value=app_config.get_cookie_browser())
    remember_var = tk.BooleanVar(value=app_config.get_remember_last_list())
    logos_var = tk.BooleanVar(value=app_config.get_show_channel_logos())

    colors = get_colors()
    shell = ttk.Frame(window, padding=(16, 16, 12, 12))
    shell.pack(fill=tk.BOTH, expand=True)

    ttk.Label(shell, text='Preferencias', style='PageTitle.TLabel').pack(anchor=tk.W)
    ttk.Label(
        shell,
        text='Tema, logos, reproducción, descargas, sesión de YouTube y yt-dlp',
        style='Muted.TLabel',
    ).pack(anchor=tk.W, pady=(0, 10))

    body = ttk.Frame(shell)
    body.pack(fill=tk.BOTH, expand=True)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)

    canvas = tk.Canvas(body, bg=colors['bg'], highlightthickness=0, bd=0)
    scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.grid(row=0, column=0, sticky='nsew')
    scroll.grid(row=0, column=1, sticky='ns', padx=(4, 0))

    main = ttk.Frame(canvas, padding=(0, 0, 8, 4))
    main_id = canvas.create_window((0, 0), window=main, anchor='nw')
    _syncing = {'on': False}
    _last_wrap = {'value': 0}

    def _sync_scroll(_event=None):
        if _syncing['on']:
            return
        _syncing['on'] = True
        try:
            width = max(1, int(canvas.winfo_width()))
            canvas.itemconfigure(main_id, width=width)
            wrap = max(240, width - 36)
            if wrap != _last_wrap['value']:
                _last_wrap['value'] = wrap

                def _walk(widget):
                    for child in widget.winfo_children():
                        try:
                            if int(child.cget('wraplength') or 0) > 0:
                                child.configure(wraplength=wrap)
                        except (tk.TclError, TypeError, ValueError):
                            pass
                        _walk(child)

                _walk(main)
            canvas.configure(scrollregion=canvas.bbox('all') or (0, 0, 0, 0))
        except tk.TclError:
            pass
        finally:
            _syncing['on'] = False

    def _on_wheel(event):
        if getattr(event, 'num', None) == 5:
            steps = 1
        elif getattr(event, 'num', None) == 4:
            steps = -1
        else:
            delta = getattr(event, 'delta', 0) or 0
            if not delta:
                return
            steps = int(-delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        canvas.yview_scroll(steps, 'units')
        return 'break'

    def _bind_wheel(widget):
        widget.bind('<MouseWheel>', _on_wheel)
        widget.bind('<Button-4>', _on_wheel)
        widget.bind('<Button-5>', _on_wheel)
        for child in widget.winfo_children():
            _bind_wheel(child)

    main.bind('<Configure>', _sync_scroll)
    canvas.bind('<Configure>', _sync_scroll)

    appearance = ttk.LabelFrame(main, text=' APARIENCIA ', padding=12)
    appearance.pack(fill=tk.X, pady=(0, 10))
    theme_row = ttk.Frame(appearance, style='Card.TFrame')
    theme_row.pack(fill=tk.X)
    ttk.Label(theme_row, text='Tema', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 16))
    ttk.Radiobutton(theme_row, text='Oscuro', variable=theme_var, value='dark').pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(theme_row, text='Claro', variable=theme_var, value='light').pack(side=tk.LEFT)
    ttk.Checkbutton(
        appearance,
        text='Mostrar logos de canal',
        variable=logos_var,
        style='Card.TCheckbutton',
    ).pack(anchor=tk.W, pady=(10, 0))
    ttk.Label(
        appearance,
        text='Miniaturas de tvg-logo en la lista y en la parrilla. En listas grandes desactívalo: la lista se pinta antes y no se descargan imágenes.',
        style='CardMuted.TLabel',
        wraplength=500,
    ).pack(anchor=tk.W, pady=(6, 0))

    playback = ttk.LabelFrame(main, text=' REPRODUCCIÓN ', padding=12)
    playback.pack(fill=tk.X, pady=(0, 10))
    vol_row = ttk.Frame(playback, style='Card.TFrame')
    vol_row.pack(fill=tk.X)
    ttk.Label(vol_row, text='Volumen por defecto', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(vol_row, textvariable=volume_label_var, style='CardMuted.TLabel', width=6).pack(side=tk.RIGHT)

    def _on_volume(value):
        try:
            volume_label_var.set(f'{int(float(value))} %')
        except (TypeError, ValueError):
            pass

    volume_scale = ttk.Scale(
        playback,
        from_=0,
        to=100,
        command=_on_volume,
    )
    volume_scale.set(volume_var.get())
    volume_scale.pack(fill=tk.X, pady=(8, 10))

    quality_row = ttk.Frame(playback, style='Card.TFrame')
    quality_row.pack(fill=tk.X)
    ttk.Label(quality_row, text='Calidad YouTube', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 16))
    ttk.Radiobutton(quality_row, text='360p', variable=quality_var, value='360').pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(quality_row, text='720p', variable=quality_var, value='720').pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(quality_row, text='1080p', variable=quality_var, value='1080').pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(quality_row, text='Mejor', variable=quality_var, value='0').pack(side=tk.LEFT)
    ttk.Label(
        playback,
        text='Tope de altura al pedir el stream. «Mejor» usa la resolución más alta que VLC pueda abrir. Si cambias la calidad con un vídeo de YouTube en marcha, se recarga desde el segundo actual.',
        style='CardMuted.TLabel',
        wraplength=500,
    ).pack(anchor=tk.W, pady=(8, 0))

    buffer_row = ttk.Frame(playback, style='Card.TFrame')
    buffer_row.pack(fill=tk.X, pady=(12, 0))
    ttk.Label(buffer_row, text='Buffer IPTV', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 16))
    ttk.Radiobutton(buffer_row, text='Rápido', variable=buffer_var, value='fast').pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(buffer_row, text='Equilibrado', variable=buffer_var, value='balanced').pack(side=tk.LEFT, padx=(0, 10))
    ttk.Radiobutton(buffer_row, text='Estable', variable=buffer_var, value='stable').pack(side=tk.LEFT)
    ttk.Label(
        playback,
        text='Caché de VLC al ver un canal. Equilibrado deja ~5 s en MPEG-TS y ~8 s en HLS (canales FHD). Rápido reduce la espera; Estable aguanta mejor los microcortes. El siguiente canal ya usa el valor nuevo.',
        style='CardMuted.TLabel',
        wraplength=500,
    ).pack(anchor=tk.W, pady=(8, 0))

    session = ttk.LabelFrame(main, text=' SESIÓN ', padding=12)
    session.pack(fill=tk.X, pady=(0, 10))
    ttk.Checkbutton(
        session,
        text='Recordar la última lista al abrir el reproductor',
        variable=remember_var,
        style='Card.TCheckbutton',
    ).pack(anchor=tk.W)
    ttk.Label(
        session,
        text='Si está desactivado, el reproductor abre la lista vacía. Las listas recientes del menú se siguen guardando.',
        style='CardMuted.TLabel',
        wraplength=500,
    ).pack(anchor=tk.W, pady=(6, 0))

    downloads = ttk.LabelFrame(main, text=' DESCARGAS ', padding=12)
    downloads.pack(fill=tk.X, pady=(0, 10))
    dest_row = ttk.Frame(downloads, style='Card.TFrame')
    dest_row.pack(fill=tk.X)
    ttk.Entry(dest_row, textvariable=download_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

    def browse_dir():
        folder = filedialog.askdirectory(
            parent=window,
            title='Carpeta de descargas',
            initialdir=download_var.get() or app_config.suggested_download_dir(),
        )
        if folder:
            download_var.set(folder)

    ttk.Button(dest_row, text='Examinar', command=browse_dir).pack(side=tk.RIGHT)
    ttk.Label(
        downloads,
        text='Se usa como carpeta inicial al guardar vídeos, audio o descargas por URL.',
        style='CardMuted.TLabel',
        wraplength=500,
    ).pack(anchor=tk.W, pady=(8, 0))

    cookies = ttk.LabelFrame(main, text=' COOKIES DE YOUTUBE ', padding=12)
    cookies.pack(fill=tk.X, pady=(0, 10))
    cookie_row = ttk.Frame(cookies, style='Card.TFrame')
    cookie_row.pack(fill=tk.X)
    ttk.Label(cookie_row, text='Navegador', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 12))
    cookie_combo = ttk.Combobox(
        cookie_row,
        state='readonly',
        width=32,
        values=[label for _key, label in COOKIE_LABELS],
    )
    labels_by_key = {key: label for key, label in COOKIE_LABELS}
    keys_by_label = {label: key for key, label in COOKIE_LABELS}
    cookie_combo.set(labels_by_key.get(cookie_var.get(), labels_by_key['auto']))
    cookie_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
    ttk.Label(
        cookies,
        text='Automático prueba Firefox primero. En Windows usa Firefox (Chrome y Edge suelen cifrar las cookies y no se pueden leer). Cierra el navegador si el archivo está bloqueado.',
        style='CardMuted.TLabel',
        wraplength=500,
    ).pack(anchor=tk.W, pady=(8, 0))

    tools = ttk.LabelFrame(main, text=' YT-DLP ', padding=12)
    tools.pack(fill=tk.X, pady=(0, 10))
    ytdlp_row = ttk.Frame(tools, style='Card.TFrame')
    ytdlp_row.pack(fill=tk.X)
    version_var = tk.StringVar()

    def _refresh_ytdlp_version(_ok=None, _detail=None):
        if _ok and _detail and _detail not in ('already',):
            version_var.set(f'Versión instalada: {_detail} (reinicia el programa)')
            return
        version = yt_dlp_installed_version()
        version_var.set(f'Versión instalada: {version}' if version else 'yt-dlp no está instalado')

    _refresh_ytdlp_version()
    ttk.Label(ytdlp_row, textvariable=version_var, style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 12))
    update_btn = ttk.Button(ytdlp_row, text='Actualizar yt-dlp')
    update_btn.configure(
        command=lambda: start_yt_dlp_upgrade(
            window,
            on_done=_refresh_ytdlp_version,
            busy_widgets=(update_btn,),
        )
    )
    update_btn.pack(side=tk.RIGHT)
    ttk.Label(
        tools,
        text='YouTube cambia el extractor a menudo. Si deja de reproducir, buscar o descargar, actualiza yt-dlp y reinicia el programa. No sustituye a «Reexportar cookies».',
        style='CardMuted.TLabel',
        wraplength=500,
    ).pack(anchor=tk.W, pady=(8, 0))

    buttons = ttk.Frame(shell)
    buttons.pack(fill=tk.X, pady=(12, 0))

    def close():
        if getattr(root, '_prefs_window', None) is window:
            root._prefs_window = None
        window.destroy()

    def save():
        folder = download_var.get().strip()
        if folder and not os.path.isdir(folder):
            messagebox.showerror(
                'Carpeta de descargas',
                'Esa carpeta no existe. Elige otra con Examinar.',
                parent=window,
            )
            return
        cookie_key = keys_by_label.get(cookie_combo.get(), 'auto')
        try:
            quality = int(quality_var.get())
        except (TypeError, ValueError):
            quality = 720
        try:
            volume = max(0, min(100, int(float(volume_scale.get()))))
        except (TypeError, ValueError, tk.TclError):
            volume = app_config.get_volume()
        app_config.save({
            'theme': 'dark' if theme_var.get() == 'dark' else 'light',
            'volume': volume,
            'download_dir': folder,
            'cookie_browser': cookie_key,
            'remember_last_list': bool(remember_var.get()),
            'show_channel_logos': bool(logos_var.get()),
            'youtube_quality': app_config.normalize_youtube_quality(quality),
            'iptv_buffer': app_config.normalize_iptv_buffer_profile(buffer_var.get()),
        })
        close()
        apply_theme(root, app_config.get_theme() == 'dark')
        if on_apply:
            on_apply()

    ttk.Button(buttons, text='Guardar', style='Accent.TButton', command=save).pack(side=tk.LEFT)
    ttk.Button(buttons, text='Cancelar', command=close).pack(side=tk.RIGHT)

    _bind_wheel(canvas)
    _bind_wheel(main)
    window.after_idle(_sync_scroll)

    window.protocol('WM_DELETE_WINDOW', close)
    window.bind('<Escape>', lambda e: close())
    try:
        window.grab_set()
    except tk.TclError:
        pass
    return window
