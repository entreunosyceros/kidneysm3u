import os
import tkinter as tk
from tkinter import ttk
import webbrowser
from PIL import Image, ImageTk
from app_paths import resource_dir
from ui_theme import style_window, set_window_icon, center_window, get_colors, get_font
from app_version import __version__ as APP_VERSION

def show_about(root):
    about_window = tk.Toplevel(root)
    about_window.title('Acerca de')
    about_window.geometry('520x580')
    about_window.resizable(False, False)
    about_window.transient(root)
    about_window.grab_set()
    style_window(about_window)
    set_window_icon(about_window)
    center_window(about_window, 520, 580)

    main_frame = ttk.Frame(about_window, padding=28)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text='Kidneys M3U/M3U8', style='PageTitle.TLabel').pack(pady=(0, 4))
    ttk.Label(
        main_frame,
        text=f'Versión {APP_VERSION}',
        style='Muted.TLabel',
    ).pack(pady=(0, 4))
    ttk.Label(
        main_frame,
        text='Listas IPTV, YouTube y descargas en el escritorio',
        style='Muted.TLabel',
    ).pack(pady=(0, 16))

    try:
        image = Image.open(os.path.join(resource_dir(), 'img', 'logo.png'))
        image = image.resize((110, 132), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        image_label = ttk.Label(main_frame, image=photo)
        image_label.image = photo
        image_label.pack(pady=(0, 18))
    except Exception:
        ttk.Label(main_frame, text="[Logo no disponible]", style='Muted.TLabel').pack(pady=(0, 18))

    description = (
        "Procesa y filtra archivos M3U, reproduce canales y vídeos, "
        "busca en YouTube y gestiona descargas desde una sola interfaz."
    )
    ttk.Label(main_frame, text=description, wraplength=420, justify='center').pack(pady=(0, 18))

    colors = get_colors()
    github_url = "https://github.com/entreunosyceros/kidneysm3u"
    github_link = tk.Label(
        main_frame,
        text="Visitar repositorio en GitHub",
        fg=colors['accent'],
        bg=colors['bg'],
        cursor='hand2',
        font=get_font(10),
    )
    github_link.pack(pady=(0, 24))
    github_link.bind('<Button-1>', lambda e: webbrowser.open_new(github_url))

    ttk.Button(
        main_frame,
        text='Cerrar',
        style='Accent.TButton',
        command=about_window.destroy,
    ).pack()
