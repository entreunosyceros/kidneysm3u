import tkinter as tk
from tkinter import ttk
import webbrowser
from PIL import Image, ImageTk

def show_about(root):
    # Crear ventana About
    about_window = tk.Toplevel(root)
    about_window.title('Acerca de')
    about_window.geometry('500x500')
    about_window.resizable(False, False)
    about_window.transient(root)
    about_window.grab_set()

    # Centrar la ventana
    about_window.update_idletasks()
    width = about_window.winfo_width()
    height = about_window.winfo_height()
    x = (about_window.winfo_screenwidth() // 2) - (width // 2)
    y = (about_window.winfo_screenheight() // 2) - (height // 2)
    about_window.geometry(f'{width}x{height}+{x}+{y}')

    # Frame principal
    main_frame = ttk.Frame(about_window, padding='20')
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Título
    title_label = ttk.Label(main_frame, text='Riñones M3U/M3U8', 
                          font=('Helvetica', 16, 'bold'))
    title_label.pack(pady=(0, 10))

    # Cargar y mostrar imagen
    try:
        image = Image.open('img/logo.png')
        image = image.resize((125, 150), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        image_label = ttk.Label(main_frame, image=photo)
        image_label.image = photo  # Mantener referencia
        image_label.pack(pady=(0, 20))
    except:
        # Si no se encuentra la imagen, mostrar un mensaje
        ttk.Label(main_frame, text="[Logo no disponible]").pack(pady=(0, 20))

    # Descripción
    description = """Esta aplicación permite procesar y filtrar archivos M3U, 
    comúnmente utilizados para listas de reproducción de medios. 
    Permite filtrar canales específicos y reproducirlos 
    directamente desde la interfaz. También permite reproducir y buscar vídeos y listas de Youtube."""
    
    desc_label = ttk.Label(main_frame, text=description, wraplength=400, 
                         justify='center')
    desc_label.pack(pady=(0, 20))

    # Enlace a GitHub
    github_url = "https://github.com/sapoclay/kidneysm3u"
    github_link = ttk.Label(main_frame, text="Visitar repositorio en GitHub",
                          foreground='blue', cursor='hand2')
    github_link.pack(pady=(0, 20))
    github_link.bind('<Button-1>', lambda e: webbrowser.open_new(github_url))

    # Botón cerrar
    ttk.Button(main_frame, text='Cerrar', 
              command=about_window.destroy).pack(pady=(0, 10))