import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from app_paths import resource_dir
from ui_theme import style_window, set_window_icon, center_window, get_font
from ui_layout import setup_resizable_dialog

def show_keyboard_shortcuts(root):
    shortcuts_window = tk.Toplevel(root)
    shortcuts_window.title('Atajos de Teclado')
    setup_resizable_dialog(shortcuts_window, 540, 640, 420, 400)
    shortcuts_window.transient(root)
    shortcuts_window.grab_set()
    style_window(shortcuts_window)
    set_window_icon(shortcuts_window)

    main_frame = ttk.Frame(shortcuts_window, padding=24)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Cargar y mostrar el logo
    try:
        # Intentar diferentes ubicaciones posibles del logo
        possible_paths = [
            os.path.join(resource_dir(), 'img', 'logo.png'),
        ]
        
        logo_path = None
        for path in possible_paths:
            if os.path.isfile(path):
                logo_path = path
                break
                
        if logo_path:
            # Usar PIL para compatibilidad multiplataforma
            logo_image = Image.open(logo_path)
            # Redimensionar el logo a un tamaño adecuado
            logo_image = logo_image.resize((100, 120), Image.Resampling.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = ttk.Label(main_frame, image=logo_photo)
            logo_label.image = logo_photo  # Mantener una referencia
            logo_label.pack(pady=(0, 20))
        else:
            print("No se pudo encontrar el archivo logo.png")
    except Exception as e:
        print(f"Error al cargar el logo: {e}")
        # Mostrar un label con texto en caso de error
        ttk.Label(
            main_frame,
            text="[Logo no disponible]",
            font=get_font(10),
            foreground='gray'
        ).pack(pady=(0, 20))

    # Título
    title_label = ttk.Label(
        main_frame,
        text='Atajos de teclado',
        style='PageTitle.TLabel',
    )
    title_label.pack(pady=(0, 8))
    ttk.Label(
        main_frame,
        text='Controles del reproductor y de la lista',
        style='Muted.TLabel',
    ).pack(pady=(0, 16))

    # Frame para la lista de atajos
    shortcuts_frame = ttk.Frame(main_frame)
    shortcuts_frame.pack(fill=tk.BOTH, expand=True)
    shortcuts_frame.columnconfigure(0, weight=1)
    shortcuts_frame.rowconfigure(0, weight=1)

    tree = ttk.Treeview(shortcuts_frame, show='tree')
    tree.grid(row=0, column=0, sticky='nsew')

    scrollbar = ttk.Scrollbar(shortcuts_frame, orient='vertical', command=tree.yview)
    scrollbar.grid(row=0, column=1, sticky='ns')
    tree.configure(yscrollcommand=scrollbar.set)

    shortcuts = [
        ("Reproducción", [
            ("Espacio", "Reproducir/Pausar"),
            ("Clic en el vídeo", "Reproducir/Pausar"),
            ("F1", "Pantalla Completa"),
            ("M", "Silenciar/Activar sonido"),
            ("←", "Retroceder 2 segundos"),
            ("→", "Avanzar 2 segundos"),
            ("ESC", "Cancelar el zap o salir de pantalla completa")
        ]),
        ("Botones de Control", [
            ("|◀◀", "Retroceder 10 segundos"),
            ("◀", "Retroceder 2 segundos"),
            ("▶❚", "Reproducir/Pausar"),
            ("▶", "Avanzar 2 segundos"),
            ("▶▶|", "Avanzar 10 segundos"),
            ("■", "Detener reproducción"),
            ("● Grabar", "Iniciar o detener grabación (se pone rojo)"),
            ("PiP", "Canal en recuadro (Esc o doble clic para cerrar)"),
            ("Altavoz", "Silenciar/Activar sonido"),
            ("Esquinas", "Alternar pantalla completa"),
            ("≡", "Mostrar/Ocultar lista de canales")
        ]),
        ("Favoritos", [
            ("Ctrl + S", "Añadir a favoritos (también desde la búsqueda)"),
            ("Ctrl + D", "Eliminar de favoritos"),
            ("★ Añadir", "Guardar el canal seleccionado (junto al buscador)"),
            ("★ Favoritos", "Mostrar lista de favoritos"),
            ("Exportar / Importar", "Llevar los favoritos a otro equipo (JSON o M3U)"),
            ("Todos", "Mostrar todos los canales")
        ]),
        ("Guía EPG", [
            ("G", "Abrir la parrilla"),
            ("Guía", "Botón de la lista lateral"),
            ("Mostrar logos de canal", "Menú Guía EPG o Preferencias")
        ]),
        ("Twitch", [
            ("C", "Ver u ocultar el chat (solo en directos)"),
            ("Ver chat…", "Menú Twitch: ventana flotante de chat en vivo")
        ]),
        ("Zap (cambiar de canal)", [
            ("0–9", "Número del canal (el de la lista visible)"),
            ("Enter", "Ir ya a ese canal (si no, espera ~1 s)"),
            ("Retroceso", "Borrar el último dígito"),
            ("Esc", "Cancelar el número")
        ]),
        ("Historial", [
            ("Historial", "IPTV y YouTube: últimos y seguir viendo")
        ]),
        ("General", [
            ("Alt + F4", "Cerrar ventana"),
            ("Barra de volumen", "Ajustar volumen del reproductor"),
            ("Barra de progreso", "Ver y cambiar posición (YouTube y VOD)")
        ])
    ]

    for category, items in shortcuts:
        category_id = tree.insert("", "end", text=category, open=True)
        for key, action in items:
            tree.insert(category_id, "end", text=f"{key}: {action}")

    # Botón de cerrar
    close_button = ttk.Button(
        main_frame,
        text='Cerrar',
        style='Accent.TButton',
        command=shortcuts_window.destroy,
    )
    close_button.pack(pady=(16, 0))
