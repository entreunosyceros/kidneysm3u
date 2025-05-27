import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ttkthemes import ThemedStyle
import os
import subprocess
import json
from video_player import VideoPlayer
from about import show_about
from keyboard import show_keyboard_shortcuts
from tkinterdnd2 import DND_FILES, TkinterDnD
import webbrowser

class M3UProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title('Kidneys M3U/M3U8')
        self.root.geometry('800x300')
        
        # Configurar el estilo
        self.style = ThemedStyle(self.root)
        self.style.set_theme("arc")
        
        # Importar el gestor de descargas
        from descargas import DownloadManager
        self.download_manager = None
        
        # Variables
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.search_pattern = tk.StringVar(value='tvg-name="ES')
        self.patterns_list = ['tvg-name="ES"', 'group-title="', 'tvg-logo="']
        self.last_output_folder = None
        self.channels = []
        self.video_player = None
        self.tema_oscuro = False
        self.save_mode = tk.StringVar(value="w") 
        
        # Configuración inicial
        self.create_menu()
        self.create_widgets()
        self.load_config()
        self.setup_drag_drop()
    
    def create_menu(self):
        menubar = tk.Menu(self.root)
        
        # Menú Archivo
        archivo_menu = tk.Menu(menubar, tearoff=0)
        archivo_menu.add_command(label="Cambiar Tema", command=self.toggle_tema)
        archivo_menu.add_command(label="Descargar", command=self.open_download_manager)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="Salir", command=self.root.quit)
        
        # Menú Procesar
        procesar_menu = tk.Menu(menubar, tearoff=0)
        procesar_menu.add_command(label="Establecer archivo de entrada M3U", command=self.browse_input)
        procesar_menu.add_command(label="Cargar URL como archivo de entrada M3U", command=self.load_url)
        procesar_menu.add_command(label="Establecer archivo de salida", command=self.browse_output)
        procesar_menu.add_separator()
        procesar_menu.add_command(label="Procesar archivo", command=self.process_file)
        
        # Menú Ordenar (Nuevo)
        ordenar_menu = tk.Menu(menubar, tearoff=0)
        ordenar_menu.add_command(label="Ordenar lista M3U", command=self.open_sorter)
        
        # Menú Reproducir
        reproducir_menu = tk.Menu(menubar, tearoff=0)
        reproducir_menu.add_command(label="Abrir Reproductor", command=self.open_player)
        reproducir_menu.add_separator()
        reproducir_menu.add_command(label="Cargar URL", command=self.load_url)
        reproducir_menu.add_command(label="Cargar Archivo Local", command=self.load_local_file)
        
        # Menú Enlaces (Nuevo)
        enlaces_menu = tk.Menu(menubar, tearoff=0)
        enlaces_menu.add_command(label="Gestionar Enlaces", command=self.open_enlaces_manager)
        
        # Añadir separador
        enlaces_menu.add_separator()
        
        # Cargar y añadir enlaces guardados
        self.actualizar_menu_enlaces(enlaces_menu)
        
        menubar.add_cascade(label="Archivo", menu=archivo_menu)
        menubar.add_cascade(label="Procesar", menu=procesar_menu)
        menubar.add_cascade(label="Ordenar", menu=ordenar_menu)
        menubar.add_cascade(label="Reproducir", menu=reproducir_menu)
        menubar.add_cascade(label="Enlaces", menu=enlaces_menu)
        menubar.add_command(label="About", command=lambda: show_about(self.root))
        menubar.add_command(label="Ayuda", command=lambda: show_keyboard_shortcuts(self.root))
        
        self.root.config(menu=menubar)

    def open_sorter(self):
        filename = filedialog.askopenfilename(filetypes=[("Archivos M3U", "*.m3u")])
        if filename:
            from m3u_sorter import M3USorter
            M3USorter(self.root, filename)
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding='10')
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        
        # Widgets de entrada/salida
        ttk.Label(main_frame, text='Archivo M3U de entrada:').grid(row=0, column=0, sticky=tk.E, padx=5)
        ttk.Entry(main_frame, textvariable=self.input_file, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(main_frame, text='Buscar', command=self.browse_input).grid(row=0, column=2, padx=5)
        
        ttk.Label(main_frame, text='Archivo de salida:').grid(row=1, column=0, sticky=tk.E, padx=5)
        ttk.Entry(main_frame, textvariable=self.output_file, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(main_frame, text='Buscar', command=self.browse_output).grid(row=1, column=2, padx=5)
        
        # Radiobuttons para modo de guardado
        save_mode_frame = ttk.Frame(main_frame)
        save_mode_frame.grid(row=2, column=1, sticky=tk.W, pady=(0, 5))
        ttk.Label(save_mode_frame, text="Modo de guardado:").pack(side=tk.LEFT)
        ttk.Radiobutton(save_mode_frame, text="Sobrescribir", variable=self.save_mode, value="w").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(save_mode_frame, text="Añadir al final", variable=self.save_mode, value="a").pack(side=tk.LEFT, padx=5)
        
        # Patrón de búsqueda 
        pattern_frame = ttk.Frame(main_frame)
        pattern_frame.grid(row=4, column=1, sticky=(tk.W, tk.E))
        ttk.Label(main_frame, text='Patrón de búsqueda:').grid(row=4, column=0, sticky=tk.E, padx=5)
        ttk.Entry(pattern_frame, textvariable=self.search_pattern, width=43).grid(row=0, column=0, padx=5)
        ttk.Button(pattern_frame, text='Editar', command=self.edit_pattern).grid(row=0, column=1, padx=5)
        
        # Barra de progreso y botones 
        self.progress = ttk.Progressbar(main_frame, length=400, mode='determinate')
        self.progress.grid(row=5, column=0, columnspan=3, pady=20, padx=5)
        
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=6, column=0, columnspan=3, pady=10)
        
        ttk.Button(buttons_frame, text='Procesar', command=self.process_file).pack(side=tk.LEFT, padx=5)
        self.stop_processing = False
        self.stop_button = ttk.Button(buttons_frame, text='Parar', command=self.stop_process, state='disabled')
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.open_folder_button = ttk.Button(buttons_frame, text='Abrir carpeta', command=self.open_output_folder, state='disabled')
        self.open_folder_button.pack(side=tk.LEFT, padx=5)
        self.play_button = ttk.Button(buttons_frame, text='Reproducir', command=self.open_player, state='disabled')
        self.play_button.pack(side=tk.LEFT, padx=5)
    
        for child in main_frame.winfo_children():
            child.grid_configure(pady=5)
    
    def edit_pattern(self):
        pattern_window = tk.Toplevel(self.root)
        pattern_window.title('Editar Patrón de Búsqueda')
        pattern_window.geometry('400x300')
        pattern_window.transient(self.root)
        pattern_window.grab_set()

        edit_frame = ttk.Frame(pattern_window, padding='10')
        edit_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(edit_frame, text='Patrones predefinidos:').pack(fill=tk.X, pady=(0, 5))
        patterns_frame = ttk.Frame(edit_frame)
        patterns_frame.pack(fill=tk.X, pady=5)

        buttons_container = ttk.Frame(patterns_frame)
        buttons_container.pack(expand=True)
        for pattern in self.patterns_list:
            ttk.Button(buttons_container, text=pattern, command=lambda p=pattern: self.set_pattern(p, pattern_window)).pack(side=tk.LEFT, padx=2)

        ttk.Label(edit_frame, text='Patrón personalizado:').pack(fill=tk.X, pady=(10, 5))
        custom_pattern = ttk.Entry(edit_frame, width=40)
        custom_pattern.insert(0, self.search_pattern.get())
        custom_pattern.pack(pady=5)

        buttons_frame = ttk.Frame(edit_frame)
        buttons_frame.pack(side=tk.BOTTOM, pady=10)
        ttk.Button(buttons_frame, text='Aplicar', command=lambda: self.apply_custom_pattern(custom_pattern.get(), pattern_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text='Cancelar', command=pattern_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def set_pattern(self, pattern, window):
        self.search_pattern.set(pattern)
        window.destroy()
    
    def apply_custom_pattern(self, pattern, window):
        self.search_pattern.set(pattern)
        window.destroy()

    def browse_input(self):
        filename = filedialog.askopenfilename(filetypes=[("Archivos M3U", "*.m3u")])
        if filename:
            self.input_file.set(filename)
    
    def browse_output(self):
        filename = filedialog.asksaveasfilename(defaultextension=".m3u", filetypes=[("Archivos M3U", "*.m3u")])
        if filename:
            self.output_file.set(filename)
    
    def open_output_folder(self):
        if self.last_output_folder:
            folder = os.path.dirname(self.last_output_folder)
            if os.name == 'nt':  # Windows
                subprocess.run(['explorer', folder])
            elif os.name == 'posix':
                import sys
                if sys.platform == 'darwin':  # macOS
                    subprocess.run(['open', folder])
                else:  # Linux y otros
                    subprocess.run(['xdg-open', folder])
    

    def process_file(self):
        if not self.input_file.get():
            messagebox.showerror('Error', 'Por favor, seleccione un archivo de entrada')
            return
        if not self.output_file.get():
            messagebox.showerror('Error', 'Por favor, seleccione un archivo de salida')
            return

        mode = self.save_mode.get()  # Usar el valor del radiobutton
        self.stop_processing = False
        self.stop_button['state'] = 'normal'
        try:
            self.channels = []
            self.progress['value'] = 0
            self.root.update()

            file_size = os.path.getsize(self.input_file.get())
            bytes_processed = 0
            buffer = []
            buffer_size = 2000  # Número de pares de líneas a acumular antes de escribir
            update_interval = 2000  # Actualizar la barra de progreso cada N líneas
            lines_since_update = 0

            with open(self.input_file.get(), 'r', encoding='utf-8') as infile, \
                 open(self.output_file.get(), mode, encoding='utf-8') as outfile:

                if mode == 'w':
                    outfile.write('#EXTM3U\n')

                line1 = None
                for line in infile:
                    if self.stop_processing:
                        break
                    bytes_processed += len(line.encode('utf-8'))
                    lines_since_update += 1

                    if line.startswith('#EXTINF'):
                        line1 = line
                    elif line1 is not None:
                        if self.search_pattern.get() in line1:
                            buffer.append(line1)
                            buffer.append(line)
                            self.channels.append((line1.strip(), line.strip()))
                        line1 = None

                    # Escribir buffer y actualizar progreso cada cierto número de líneas
                    if len(buffer) >= buffer_size * 2:
                        outfile.writelines(buffer)
                        buffer.clear()
                    if lines_since_update >= update_interval:
                        self.progress['value'] = (bytes_processed / file_size) * 100
                        self.root.update()
                        lines_since_update = 0

                # Escribir lo que quede en el buffer antes de salir
                if buffer:
                    outfile.writelines(buffer)

            self.last_output_folder = self.output_file.get()
            self.open_folder_button['state'] = 'normal'
            self.play_button['state'] = 'normal'
            self.progress['value'] = 100
            self.root.update()
            if self.stop_processing:
                messagebox.showinfo('Parado', 'El proceso de filtrado fue detenido por el usuario. El archivo contiene los datos filtrados hasta ese momento.')
            else:
                messagebox.showinfo('Éxito', 'Archivo procesado correctamente')

        except Exception as e:
            messagebox.showerror('Error', f'Error al procesar el archivo: {str(e)}')
        finally:
            self.stop_button['state'] = 'disabled'

    def stop_process(self):
        self.stop_processing = True

    def load_url(self):
        if not self.video_player:
            self.video_player = VideoPlayer()
        
        url = tk.simpledialog.askstring("Cargar URL", "Introduce la URL de la lista M3U:")
        if url:
            self.video_player.load_m3u_url(url)
            self.video_player.run()

    def load_local_file(self):
        if not self.video_player:
            self.video_player = VideoPlayer()
        # Usar askopenfilename correctamente para seleccionar archivos
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Selecciona un archivo M3U o M3U8",
            filetypes=[("Archivos M3U/M3U8", "*.m3u *.m3u8"), ("Todos los archivos", "*")]
        )
        if filename:
            self.video_player.load_m3u_file(filename)
            self.video_player.run()

    def open_player(self):
        if not self.video_player:
            self.video_player = VideoPlayer()
        if self.channels:
            self.video_player.load_m3u_file(self.output_file.get())
        self.video_player.run()

    def close_player(self):
        if self.video_player:
            self.video_player.close()
            self.video_player = None

    def toggle_tema(self):
        self.tema_oscuro = not self.tema_oscuro
        self.style.set_theme("equilux" if self.tema_oscuro else "arc")

    def setup_drag_drop(self):
        # Drag & Drop multiplataforma usando tkinterdnd2
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)
    
    def handle_drop(self, event):
        file_path = event.data
        if file_path.lower().endswith('.m3u'):
            self.input_file.set(file_path)
    
    def load_config(self):
        try:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = self.get_default_config()
    
    def get_default_config(self):
        return {
            'theme': 'arc',
            'language': 'es',
            'recent_files': [],
            'patterns': self.patterns_list
        }

    def open_enlaces_manager(self):
        from enlaces import EnlacesManager
        self.enlaces_manager = EnlacesManager(self.root)
        self.enlaces_manager.window.transient(self.root)
        self.enlaces_manager.window.grab_set()
        self.root.wait_window(self.enlaces_manager.window)
        # Actualizar menú después de cerrar el gestor
        menu_bar = self.root.nametowidget(self.root.cget("menu"))
        for i in range(menu_bar.index('end') + 1):
            if menu_bar.type(i) == 'cascade':
                if menu_bar.entrycget(i, 'label') == 'Enlaces':
                    enlaces_menu = menu_bar.nametowidget(menu_bar.entrycget(i, 'menu'))
                    self.actualizar_menu_enlaces(enlaces_menu)
                    break

    def actualizar_menu_enlaces(self, menu):

        last_index = menu.index(tk.END)
        if last_index is not None:
            for i in range(2, last_index + 1):
                menu.delete(2)
        
        # Cargar enlaces
        try:
            with open('enlaces.json', 'r', encoding='utf-8') as f:
                enlaces = json.load(f)
                for nombre, url in enlaces.items():
                    menu.add_command(label=nombre, command=lambda u=url: webbrowser.open(u))
        except:
            pass

    def open_download_manager(self):
        """Abre la ventana del gestor de descargas"""
        from descargas import DownloadManager
        self.download_manager = DownloadManager(self.root)
        self.download_manager.window.transient(self.root)
        self.download_manager.window.grab_set()
        self.root.wait_window(self.download_manager.window)
        self.download_manager = None

if __name__ == '__main__':
    root = TkinterDnD.Tk() 
    app = M3UProcessor(root)
    root.mainloop()