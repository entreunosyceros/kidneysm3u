import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import os

def show_keyboard_shortcuts(root):
    # Crear ventana de atajos
    shortcuts_window = tk.Toplevel(root)
    shortcuts_window.title('Atajos de Teclado')
    shortcuts_window.geometry('500x500')
    shortcuts_window.transient(root)
    shortcuts_window.grab_set()

    # Frame principal con padding
    main_frame = ttk.Frame(shortcuts_window, padding='20')
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Cargar y mostrar el logo
    try:
        # Intentar diferentes ubicaciones posibles del logo
        possible_paths = [
            os.path.join(os.path.dirname(__file__), 'img', 'logo.png'),  # Ruta relativa
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'img', 'logo.png'),  # Ruta absoluta
            os.path.join(os.path.dirname(__file__), '..', 'img', 'logo.png'),  # Un nivel arriba
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
            font=('Arial', 10),
            foreground='gray'
        ).pack(pady=(0, 20))

    # Título
    title_label = ttk.Label(
        main_frame, 
        text='Atajos de Teclado Disponibles',
        font=('Arial', 12, 'bold')
    )
    title_label.pack(pady=(0, 20))

    # Frame para la lista de atajos
    shortcuts_frame = ttk.Frame(main_frame)
    shortcuts_frame.pack(fill=tk.BOTH, expand=True)

    # Lista de atajos
    shortcuts = [
        ("Reproducción", [
            ("Espacio", "Reproducir/Pausar"),
            ("F1", "Pantalla Completa"),
            ("M", "Silenciar/Activar sonido"),
            ("←", "Retroceder 2 segundos"),
            ("→", "Avanzar 2 segundos"),
            ("ESC", "Salir de pantalla completa")
        ]),
        ("Botones de Control", [
            ("⏮⏮", "Retroceder 10 segundos"),
            ("⏮", "Retroceder 2 segundos"),
            ("⏯", "Reproducir/Pausar"),
            ("⏭", "Avanzar 2 segundos"),
            ("⏭⏭", "Avanzar 10 segundos"),
            ("⏹", "Detener reproducción"),
            ("🔊", "Silenciar/Activar sonido"),
            ("⛶", "Alternar pantalla completa"),
            ("≡", "Mostrar/Ocultar lista de canales")
        ]),
        ("Favoritos", [
            ("Ctrl + S", "Añadir a favoritos"),
            ("Ctrl + D", "Eliminar de favoritos"),
            ("⭐", "Mostrar lista de favoritos"),
            ("📺", "Mostrar todos los canales")
        ]),
        ("General", [
            ("Alt + F4", "Cerrar ventana"),
            ("Barra de volumen", "Ajustar volumen del reproductor"),
            ("Barra de progreso", "Ver y cambiar posición del video (solo YouTube)")
        ])
    ]

    # Crear la lista usando un Treeview
    tree = ttk.Treeview(shortcuts_frame, show='tree')
    tree.pack(fill=tk.BOTH, expand=True, padx=(0, 10))  # Añadir padding derecho para la scrollbar

    # Añadir scrollbar superpuesta
    scrollbar = ttk.Scrollbar(shortcuts_frame, orient="vertical", command=tree.yview)
    scrollbar.place(relx=1, rely=0, relheight=1, anchor='ne')
    tree.configure(yscrollcommand=scrollbar.set)
    
    # Estilo para la scrollbar superpuesta
    style = ttk.Style()
    style.configure("Vertical.TScrollbar", borderwidth=0)
    scrollbar.configure(style="Vertical.TScrollbar")

    # Insertar atajos en el Treeview
    for category, items in shortcuts:
        category_id = tree.insert("", "end", text=category)
        for key, action in items:
            tree.insert(category_id, "end", text=f"{key}: {action}")

    # Botón de cerrar
    close_button = ttk.Button(
        main_frame, 
        text='Cerrar',
        command=shortcuts_window.destroy
    )
    close_button.pack(pady=(20, 0))
