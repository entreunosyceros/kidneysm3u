"""Atajos de teclado: diálogo completo y overlay breve en el reproductor."""

import os
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

import app_config
from app_paths import resource_dir
from ui_layout import setup_resizable_dialog, wraplength_for
from ui_theme import get_colors, get_font, set_window_icon, style_window

SHORTCUT_CATEGORIES = (
    ('Reproducción', (
        ('Espacio', 'Reproducir/Pausar'),
        ('Clic en el vídeo', 'Reproducir/Pausar'),
        ('F11', 'Pantalla completa'),
        ('M', 'Silenciar/Activar sonido'),
        ('←', 'Retroceder 2 segundos'),
        ('→', 'Avanzar 2 segundos'),
        ('ESC', 'Cancelar el zap o salir de pantalla completa'),
    )),
    ('Ayuda', (
        ('F1', 'Atajos rápidos en el reproductor'),
        ('?', 'Atajos rápidos en el reproductor'),
    )),
    ('Lista de canales', (
        ('Ctrl + F', 'Buscar en el grupo activo'),
    )),
    ('Botones de Control', (
        ('|◀◀', 'Retroceder 10 segundos'),
        ('◀', 'Retroceder 2 segundos'),
        ('▶❚', 'Reproducir/Pausar'),
        ('▶', 'Avanzar 2 segundos'),
        ('▶▶|', 'Avanzar 10 segundos'),
        ('■', 'Detener reproducción'),
        ('● Grabar', 'Iniciar o detener grabación (se pone rojo)'),
        ('PiP', 'Canal en recuadro (Esc o doble clic para cerrar)'),
        ('Altavoz', 'Silenciar/Activar sonido'),
        ('Esquinas', 'Alternar pantalla completa'),
        ('≡', 'Mostrar/Ocultar lista de canales'),
    )),
    ('Favoritos', (
        ('Ctrl + S', 'Añadir a favoritos (también desde la búsqueda)'),
        ('Ctrl + D', 'Eliminar de favoritos'),
        ('★ Añadir', 'Guardar el canal seleccionado (junto al buscador)'),
        ('★ Favoritos', 'Mostrar lista de favoritos'),
        ('Exportar / Importar', 'Llevar los favoritos a otro equipo (JSON o M3U)'),
        ('Todos', 'Mostrar todos los canales'),
    )),
    ('Guía EPG', (
        ('G', 'Abrir la parrilla'),
        ('Guía', 'Botón de la lista lateral'),
        ('Mostrar logos de canal', 'Menú Guía EPG o Preferencias'),
    )),
    ('Twitch', (
        ('C', 'Ver u ocultar el chat (solo en directos)'),
        ('Ver chat…', 'Menú Twitch: ventana flotante de chat en vivo'),
    )),
    ('Zap (cambiar de canal)', (
        ('0–9', 'Número del canal (el de la lista visible)'),
        ('Enter', 'Ir ya a ese canal (si no, espera ~1 s)'),
        ('Retroceso', 'Borrar el último dígito'),
        ('Esc', 'Cancelar el número'),
    )),
    ('Historial', (
        ('Historial', 'IPTV y YouTube: últimos y seguir viendo'),
    )),
    ('General', (
        ('Alt + F4', 'Cerrar ventana'),
        ('Barra de volumen', 'Ajustar volumen del reproductor'),
        ('Barra de progreso', 'Ver y cambiar posición (YouTube y VOD)'),
    )),
)

PLAYER_QUICK_HINTS = (
    ('Espacio', 'Reproducir / pausar'),
    ('F11', 'Pantalla completa'),
    ('M', 'Silenciar'),
    ('← / →', '±2 segundos'),
    ('G', 'Guía EPG'),
    ('Ctrl + S', 'Añadir favorito'),
    ('0–9 + Enter', 'Zap de canal'),
    ('F1 / ?', 'Ver atajos'),
)

OVERLAY_AUTO_HIDE_MS = 12000

# <?> no es portable en Tk (falla en Linux). Probamos variantes válidas.
QUESTION_MARK_BIND_SEQUENCES = (
    '<Key-question>',
    '<KeyPress-question>',
    '<Shift-slash>',
    '<Shift-KeyPress-slash>',
)


def bind_question_mark_help(widget, handler, *, add=False):
    """Enlaza ? para atajos; ignora secuencias que Tk rechace en este sistema."""
    kwargs = {'add': '+'} if add else {}
    for sequence in QUESTION_MARK_BIND_SEQUENCES:
        try:
            widget.bind(sequence, handler, **kwargs)
        except tk.TclError:
            pass


def _widget_exists(widget):
    if widget is None:
        return False
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


def _overlay_parent(player):
    """Devuelve (marco contenedor, marco vídeo) para colocar el overlay."""
    player_frame = getattr(player, 'player_frame', None)
    video = getattr(player, 'video_frame', None)
    if _widget_exists(player_frame):
        return player_frame, video if _widget_exists(video) else None
    if _widget_exists(video):
        return video, None
    main = getattr(player, 'main_frame', None)
    if _widget_exists(main):
        return main, None
    window = getattr(player, 'window', None)
    return window, None


def hide_player_shortcuts_overlay(player):
    """Cierra el overlay breve de atajos en el reproductor."""
    job = getattr(player, '_shortcuts_overlay_hide_job', None)
    player._shortcuts_overlay_hide_job = None
    if job and _widget_exists(getattr(player, 'window', None)):
        try:
            player.window.after_cancel(job)
        except tk.TclError:
            pass
    frame = getattr(player, '_shortcuts_overlay', None)
    player._shortcuts_overlay = None
    if frame is not None:
        try:
            frame.destroy()
        except tk.TclError:
            pass


def shortcuts_overlay_visible(player):
    """True si el overlay de atajos está visible."""
    frame = getattr(player, '_shortcuts_overlay', None)
    return _widget_exists(frame)


def show_player_shortcuts_overlay(player, *, first_time=False, mark_seen=None):
    """Muestra un panel breve sobre el vídeo con los atajos más usados."""
    if shortcuts_overlay_visible(player):
        return
    parent, video = _overlay_parent(player)
    window = getattr(player, 'window', None)
    if not _widget_exists(parent) or not _widget_exists(window):
        return

    hide_player_shortcuts_overlay(player)
    colors = get_colors()

    overlay = tk.Frame(parent, bg='#000000', highlightthickness=0)
    try:
        if _widget_exists(video):
            overlay.place(in_=video, relx=0, rely=0, relwidth=1, relheight=1)
            try:
                overlay.lift(video)
            except tk.TclError:
                overlay.tkraise()
        else:
            overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            overlay.tkraise()
    except tk.TclError:
        try:
            overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            overlay.tkraise()
        except tk.TclError:
            return
    player._shortcuts_overlay = overlay

    card = tk.Frame(
        overlay,
        bg=colors['surface'],
        highlightbackground=colors['border'],
        highlightthickness=1,
    )
    card.place(relx=0.5, rely=0.5, anchor='center', relwidth=0.88, relheight=0.78)

    title = tk.Label(
        card,
        text='Atajos de teclado',
        bg=colors['surface'],
        fg=colors['text'],
        font=get_font(12, weight='bold'),
    )
    title.pack(anchor=tk.W, padx=18, pady=(14, 4))

    subtitle = tk.Label(
        card,
        text='Pulsa F1 o ? para volver a ver este panel',
        bg=colors['surface'],
        fg=colors['text_muted'],
        font=get_font(9),
    )
    subtitle.pack(anchor=tk.W, padx=18, pady=(0, 10))

    body = tk.Frame(card, bg=colors['surface'])
    if first_time:
        tk.Label(
            card,
            text='Consejo: se muestra una sola vez al abrir el reproductor.',
            bg=colors['surface'],
            fg=colors['text_muted'],
            font=get_font(9),
        ).pack(anchor=tk.W, padx=18, pady=(0, 6))

    body.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 8))

    for row, (key, action) in enumerate(PLAYER_QUICK_HINTS):
        line = tk.Frame(body, bg=colors['surface'])
        line.pack(fill=tk.X, pady=2)
        tk.Label(
            line,
            text=key,
            width=14,
            anchor=tk.W,
            bg=colors['surface'],
            fg=colors['accent'],
            font=get_font(10, weight='bold'),
        ).pack(side=tk.LEFT)
        tk.Label(
            line,
            text=action,
            anchor=tk.W,
            bg=colors['surface'],
            fg=colors['text'],
            font=get_font(10),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    footer = tk.Frame(card, bg=colors['surface'])
    footer.pack(fill=tk.X, padx=18, pady=(4, 14))

    def dismiss(mark=True):
        if mark and mark_seen:
            mark_seen()
        hide_player_shortcuts_overlay(player)

    def open_full():
        dismiss(mark=False)
        show_keyboard_shortcuts(window)

    ttk.Button(
        footer,
        text='Ver todos los atajos',
        command=open_full,
    ).pack(side=tk.LEFT)
    ttk.Button(
        footer,
        text='Entendido',
        style='Accent.TButton',
        command=dismiss,
    ).pack(side=tk.RIGHT)

    overlay.bind('<Button-1>', lambda e: dismiss(), add='+')
    card.bind('<Button-1>', lambda e: 'break')

    def sync_wrap(event=None):
        try:
            width = max(220, card.winfo_width())
            subtitle.configure(wraplength=wraplength_for(width, padding=36, min_wrap=160))
        except tk.TclError:
            pass

    card.bind('<Configure>', sync_wrap, add='+')
    window.after_idle(sync_wrap)

    player._shortcuts_overlay_hide_job = window.after(
        OVERLAY_AUTO_HIDE_MS,
        lambda: dismiss(mark=bool(mark_seen)),
    )
    if mark_seen:
        mark_seen()


def toggle_player_shortcuts_overlay(player, *, mark_seen=None):
    """Alterna el overlay breve de atajos."""
    if shortcuts_overlay_visible(player):
        hide_player_shortcuts_overlay(player)
        return
    show_player_shortcuts_overlay(player, mark_seen=mark_seen)


def show_keyboard_shortcuts(root):
    """Abre el diálogo completo de atajos de teclado."""
    shortcuts_window = tk.Toplevel(root)
    shortcuts_window.title('Atajos de Teclado')
    setup_resizable_dialog(shortcuts_window, 540, 640, 420, 400)
    shortcuts_window.transient(root)
    shortcuts_window.grab_set()
    style_window(shortcuts_window)
    set_window_icon(shortcuts_window)

    main_frame = ttk.Frame(shortcuts_window, padding=24)
    main_frame.pack(fill=tk.BOTH, expand=True)

    try:
        logo_path = os.path.join(resource_dir(), 'img', 'logo.png')
        if os.path.isfile(logo_path):
            logo_image = Image.open(logo_path)
            logo_image = logo_image.resize((100, 120), Image.Resampling.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = ttk.Label(main_frame, image=logo_photo)
            logo_label.image = logo_photo
            logo_label.pack(pady=(0, 20))
    except Exception:
        ttk.Label(
            main_frame,
            text='[Logo no disponible]',
            font=get_font(10),
            foreground='gray',
        ).pack(pady=(0, 20))

    ttk.Label(main_frame, text='Atajos de teclado', style='PageTitle.TLabel').pack(pady=(0, 8))
    ttk.Label(
        main_frame,
        text='Controles del reproductor y de la lista',
        style='Muted.TLabel',
    ).pack(pady=(0, 16))

    shortcuts_frame = ttk.Frame(main_frame)
    shortcuts_frame.pack(fill=tk.BOTH, expand=True)
    shortcuts_frame.columnconfigure(0, weight=1)
    shortcuts_frame.rowconfigure(0, weight=1)

    tree = ttk.Treeview(shortcuts_frame, show='tree')
    tree.grid(row=0, column=0, sticky='nsew')
    scrollbar = ttk.Scrollbar(shortcuts_frame, orient='vertical', command=tree.yview)
    scrollbar.grid(row=0, column=1, sticky='ns')
    tree.configure(yscrollcommand=scrollbar.set)

    for category, items in SHORTCUT_CATEGORIES:
        category_id = tree.insert('', 'end', text=category, open=True)
        for key, action in items:
            tree.insert(category_id, 'end', text=f'{key}: {action}')

    ttk.Button(
        main_frame,
        text='Cerrar',
        style='Accent.TButton',
        command=shortcuts_window.destroy,
    ).pack(pady=(16, 0))
