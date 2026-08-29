"""Ventana de preferencias: tema, volumen, descargas, cookies y sesión."""

import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

import app_config
import subtitle_style
from ui_theme import apply_theme, get_colors, style_window, set_window_icon, center_window

COOKIE_LABELS = (
    ('auto', 'Automático (el que tenga sesión)'),
    ('firefox', 'Firefox'),
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
    window.geometry('560x760')
    window.minsize(480, 460)
    window.transient(parent)
    style_window(window)
    set_window_icon(window)
    center_window(window, 560, 760)
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
    light_var = tk.BooleanVar(value=app_config.get_light_mode())
    hw_decode_var = tk.BooleanVar(value=app_config.get_light_mode_hw_decode())
    cpu_var = tk.BooleanVar(value=app_config.get_show_cpu_monitor())
    updates_var = tk.BooleanVar(value=app_config.get_check_app_updates())
    sub_cfg = app_config.get_subtitle_style()
    sub_size_var = tk.StringVar(value=str(sub_cfg['subtitle_size']))
    sub_color_var = tk.StringVar(value=sub_cfg['subtitle_color'])
    sub_outline_var = tk.StringVar(value=str(sub_cfg['subtitle_outline']))
    sub_outline_color_var = tk.StringVar(value=sub_cfg['subtitle_outline_color'])
    sub_bg_color_var = tk.StringVar(value=sub_cfg['subtitle_bg_color'])
    sub_text_op_label = tk.StringVar()
    sub_bg_op_label = tk.StringVar()
    sub_margin_label = tk.StringVar()
    sub_delay_label = tk.StringVar()

    colors = get_colors()
    shell = ttk.Frame(window, padding=(16, 16, 12, 12))
    shell.pack(fill=tk.BOTH, expand=True)

    ttk.Label(shell, text='Preferencias', style='PageTitle.TLabel').pack(anchor=tk.W)
    ttk.Label(
        shell,
        text='Tema, logos, reproducción, subtítulos, descargas, actualizaciones, sesión de YouTube y yt-dlp',
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

    performance = ttk.LabelFrame(main, text=' MODO LIGERO ', padding=12)
    performance.pack(fill=tk.X, pady=(0, 10))
    ttk.Checkbutton(
        performance,
        text='Modo ligero (equipos justos o listas enormes)',
        variable=light_var,
        style='Card.TCheckbutton',
    ).pack(anchor=tk.W)
    hw_decode_check = ttk.Checkbutton(
        performance,
        text='Usar GPU para IPTV si VLC puede (solo en modo ligero)',
        variable=hw_decode_var,
        style='Card.TCheckbutton',
    )
    hw_decode_check.pack(anchor=tk.W, pady=(8, 0))
    ttk.Checkbutton(
        performance,
        text='Mostrar monitor de CPU (muestreo cada ~8 s)',
        variable=cpu_var,
        style='Card.TCheckbutton',
    ).pack(anchor=tk.W, pady=(8, 0))

    cache_row = ttk.Frame(performance, style='Card.TFrame')
    cache_row.pack(fill=tk.X, pady=(10, 0))

    def clear_logo_cache():
        import logo_cache
        removed = logo_cache.clear_cache()
        messagebox.showinfo(
            'Caché de logos',
            f'Se eliminaron {removed} miniaturas de epg_cache/.',
            parent=window,
        )

    ttk.Button(cache_row, text='Limpiar caché de logos…', command=clear_logo_cache).pack(side=tk.LEFT)
    ttk.Label(
        performance,
        text='Desactiva logos, aligera EPG y YouTube, no restaura listas M3U enormes al abrir y reduce la caché de descargas. La línea de EPG bajo la búsqueda no se muestra.',
        style='CardMuted.TLabel',
        wraplength=500,
    ).pack(anchor=tk.W, pady=(8, 0))

    def _sync_light_opts(*_args):
        state = 'normal' if light_var.get() else 'disabled'
        try:
            hw_decode_check.configure(state=state)
        except tk.TclError:
            pass

    light_var.trace_add('write', _sync_light_opts)
    _sync_light_opts()

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

    subs = ttk.LabelFrame(main, text=' SUBTÍTULOS ', padding=12)
    subs.pack(fill=tk.X, pady=(0, 10))

    def _paint_swatch(swatch, var):
        try:
            swatch.configure(bg=var.get())
        except tk.TclError:
            swatch.configure(bg='#FFFFFF')

    def _color_row(parent, text, var):
        row = ttk.Frame(parent, style='Card.TFrame')
        row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(row, text=text, style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 12))
        swatch = tk.Frame(
            row,
            width=36,
            height=20,
            bg=var.get(),
            highlightthickness=1,
            highlightbackground=colors['border'],
        )
        swatch.pack(side=tk.LEFT, padx=(0, 8))
        swatch.pack_propagate(False)

        def pick():
            _rgb, chosen = colorchooser.askcolor(color=var.get(), parent=window, title=text)
            if chosen:
                var.set(subtitle_style.normalize_hex_color(chosen, var.get()))
                _paint_swatch(swatch, var)

        ttk.Button(row, text='Elegir', command=pick).pack(side=tk.RIGHT)
        swatch.bind('<Button-1>', lambda _e: pick())
        return swatch

    size_row = ttk.Frame(subs, style='Card.TFrame')
    size_row.pack(fill=tk.X)
    ttk.Label(size_row, text='Tamaño', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 12))
    for value, label in subtitle_style.SUBTITLE_SIZES:
        ttk.Radiobutton(size_row, text=label, variable=sub_size_var, value=str(value)).pack(
            side=tk.LEFT, padx=(0, 8)
        )

    _color_row(subs, 'Color del texto', sub_color_var)

    text_op_row = ttk.Frame(subs, style='Card.TFrame')
    text_op_row.pack(fill=tk.X)
    ttk.Label(text_op_row, text='Opacidad del texto', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(text_op_row, textvariable=sub_text_op_label, style='CardMuted.TLabel', width=6).pack(side=tk.RIGHT)

    def _on_text_op(value):
        try:
            sub_text_op_label.set(f'{int(float(value))} %')
        except (TypeError, ValueError):
            pass

    text_op_scale = ttk.Scale(subs, from_=20, to=100, command=_on_text_op)
    text_op_scale.set(subtitle_style.opacity_percent(sub_cfg['subtitle_opacity']))
    text_op_scale.pack(fill=tk.X, pady=(4, 10))
    _on_text_op(text_op_scale.get())

    outline_row = ttk.Frame(subs, style='Card.TFrame')
    outline_row.pack(fill=tk.X)
    ttk.Label(outline_row, text='Contorno', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 12))
    for value, label in subtitle_style.SUBTITLE_OUTLINES:
        ttk.Radiobutton(outline_row, text=label, variable=sub_outline_var, value=str(value)).pack(
            side=tk.LEFT, padx=(0, 8)
        )
    _color_row(subs, 'Color del contorno', sub_outline_color_var)
    _color_row(subs, 'Color de fondo', sub_bg_color_var)

    bg_op_row = ttk.Frame(subs, style='Card.TFrame')
    bg_op_row.pack(fill=tk.X)
    ttk.Label(bg_op_row, text='Transparencia del fondo', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(bg_op_row, textvariable=sub_bg_op_label, style='CardMuted.TLabel', width=6).pack(side=tk.RIGHT)

    def _on_bg_op(value):
        try:
            percent = int(float(value))
        except (TypeError, ValueError):
            return
        if percent <= 0:
            sub_bg_op_label.set('nada')
        else:
            sub_bg_op_label.set(f'{percent} %')

    bg_op_scale = ttk.Scale(subs, from_=0, to=100, command=_on_bg_op)
    bg_op_scale.set(subtitle_style.opacity_percent(sub_cfg['subtitle_bg_opacity']))
    bg_op_scale.pack(fill=tk.X, pady=(4, 10))
    _on_bg_op(bg_op_scale.get())

    margin_row = ttk.Frame(subs, style='Card.TFrame')
    margin_row.pack(fill=tk.X)
    ttk.Label(margin_row, text='Margen inferior', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(margin_row, textvariable=sub_margin_label, style='CardMuted.TLabel', width=6).pack(side=tk.RIGHT)

    def _on_margin(value):
        try:
            sub_margin_label.set(f'{int(float(value))} px')
        except (TypeError, ValueError):
            pass

    margin_scale = ttk.Scale(subs, from_=0, to=150, command=_on_margin)
    margin_scale.set(sub_cfg['subtitle_margin'])
    margin_scale.pack(fill=tk.X, pady=(4, 10))
    _on_margin(margin_scale.get())

    delay_row = ttk.Frame(subs, style='Card.TFrame')
    delay_row.pack(fill=tk.X)
    ttk.Label(delay_row, text='Retraso', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 12))
    ttk.Label(delay_row, textvariable=sub_delay_label, style='CardMuted.TLabel', width=8).pack(side=tk.RIGHT)

    def _on_delay(value):
        try:
            tenths = int(round(float(value)))
        except (TypeError, ValueError):
            return
        sub_delay_label.set(subtitle_style.delay_label(tenths))

    delay_scale = ttk.Scale(subs, from_=-50, to=50, command=_on_delay)
    delay_scale.set(sub_cfg['subtitle_delay_ds'])
    delay_scale.pack(fill=tk.X, pady=(4, 0))
    _on_delay(delay_scale.get())
    ttk.Label(
        subs,
        text='Solo cambia subtítulos de texto (SRT y YouTube). Los de imagen del propio canal no se pueden restilar. VLC usa una paleta fija de colores (se aproxima la más cercana). El margen inferior no lo admite VLC 3; el retraso sí al reproducir. En YouTube se recarga el vídeo al guardar; en IPTV se recarga el canal en curso al guardar.',
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

    updates = ttk.LabelFrame(main, text=' ACTUALIZACIONES ', padding=12)
    updates.pack(fill=tk.X, pady=(0, 10))
    ttk.Checkbutton(
        updates,
        text='Avisar si hay una versión nueva al abrir el programa',
        variable=updates_var,
        style='Card.TCheckbutton',
    ).pack(anchor=tk.W)
    ttk.Label(
        updates,
        text='Consulta GitHub Releases (como mucho una vez al día). Si hay paquete para tu sistema, puedes instalarlo desde el aviso. Quien usa el código fuente solo recibe el enlace. También está en Ayuda → Buscar actualizaciones.',
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
        text='Lo fiable es Firefox con sesión en YouTube: ciérralo y pulsa Reexportar cookies. Automático prueba Firefox y, si el sistema lo permite, otros navegadores. En Windows, Chrome, Brave y Edge cifran las cookies y no se pueden leer.',
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
        try:
            sub_size = int(sub_size_var.get())
        except (TypeError, ValueError):
            sub_size = 0
        try:
            sub_outline = int(sub_outline_var.get())
        except (TypeError, ValueError):
            sub_outline = 1
        try:
            text_pct = int(float(text_op_scale.get()))
        except (TypeError, ValueError, tk.TclError):
            text_pct = 100
        try:
            bg_pct = int(float(bg_op_scale.get()))
        except (TypeError, ValueError, tk.TclError):
            bg_pct = 0
        try:
            sub_margin = int(float(margin_scale.get()))
        except (TypeError, ValueError, tk.TclError):
            sub_margin = 0
        try:
            sub_delay = int(round(float(delay_scale.get())))
        except (TypeError, ValueError, tk.TclError):
            sub_delay = 0
        sub_payload = subtitle_style.normalize_subtitle_style({
            'subtitle_size': sub_size,
            'subtitle_color': sub_color_var.get(),
            'subtitle_opacity': subtitle_style.percent_to_opacity(text_pct),
            'subtitle_outline': sub_outline,
            'subtitle_outline_color': sub_outline_color_var.get(),
            'subtitle_bg_color': sub_bg_color_var.get(),
            'subtitle_bg_opacity': subtitle_style.percent_to_opacity(bg_pct),
            'subtitle_margin': sub_margin,
            'subtitle_delay_ds': sub_delay,
        })
        payload = {
            'theme': 'dark' if theme_var.get() == 'dark' else 'light',
            'volume': volume,
            'download_dir': folder,
            'cookie_browser': cookie_key,
            'remember_last_list': bool(remember_var.get()),
            'show_channel_logos': bool(logos_var.get()),
            'light_mode': bool(light_var.get()),
            'light_mode_hw_decode': bool(hw_decode_var.get()),
            'show_cpu_monitor': bool(cpu_var.get()),
            'check_app_updates': bool(updates_var.get()),
            'youtube_quality': app_config.normalize_youtube_quality(quality),
            'iptv_buffer': app_config.normalize_iptv_buffer_profile(buffer_var.get()),
        }
        payload.update(sub_payload)
        app_config.save(payload)
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
