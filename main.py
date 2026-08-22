import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import json
from video_player import VideoPlayer
from about import show_about
from keyboard import show_keyboard_shortcuts
from docs_viewer import show_documentation
from tkinterdnd2 import DND_FILES, TkinterDnD
import webbrowser
from bandejaSistema import IconoBandeja
from ui_theme import (
    apply_theme, get_colors, style_window, style_menu_tree,
    set_window_icon, center_window,
)
import app_config

class M3UProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title('Kidneys M3U/M3U8')
        self.root.geometry('900x620')
        self.root.minsize(780, 540)
        
        self.download_manager = None
        
        # Variables
        self.input_file = tk.StringVar()
        self.output_file = tk.StringVar()
        self.search_pattern = tk.StringVar(value='tvg-name="ES')
        self.patterns_list = ['tvg-name="ES"', 'group-title="', 'tvg-logo="']
        self.last_output_folder = None
        self.channels = []
        self.video_player = None
        self.tema_oscuro = True
        self.save_mode = tk.StringVar(value="w")
        self.status_var = tk.StringVar(value='Listo · Arrastra un archivo M3U o selecciónalo')
        self.config = self.get_default_config()
        
        # Configuración inicial
        self.load_config()
        apply_theme(self.root, self.tema_oscuro)
        set_window_icon(self.root)
        if not app_config.apply_geometry(self.root, 'main', '900x620'):
            center_window(self.root, 900, 620)
        self._geometry_save_job = None
        self.root.bind('<Configure>', self._on_window_configure)
        
        self.create_menu()
        self.create_widgets()
        self.setup_drag_drop()
        
        # Inicializar el icono de la bandeja del sistema
        self.icono_bandeja = IconoBandeja(self.root)
    
    def create_menu(self):
        menubar = tk.Menu(self.root)
        
        # Menú Archivo
        archivo_menu = tk.Menu(menubar, tearoff=0)
        archivo_menu.add_command(label="Cambiar Tema", command=self.toggle_tema)
        archivo_menu.add_command(label="Descargar", command=self.open_download_manager)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="Salir", command=self.quit_app)
        
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
        reproducir_menu.add_separator()
        self.recientes_menu = tk.Menu(reproducir_menu, tearoff=0)
        reproducir_menu.add_cascade(label="Listas recientes", menu=self.recientes_menu)
        
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
        ayuda_menu = tk.Menu(menubar, tearoff=0)
        ayuda_menu.add_command(label="Atajos de teclado", command=lambda: show_keyboard_shortcuts(self.root))
        ayuda_menu.add_command(label="Documentación", command=lambda: show_documentation(self.root))
        menubar.add_cascade(label="Ayuda", menu=ayuda_menu)
        
        self.menubar = menubar
        self.root.config(menu=menubar)
        style_menu_tree(menubar)
        self._refresh_recent_menu()

    def open_sorter(self):
        filename = filedialog.askopenfilename(filetypes=[("Archivos M3U", "*.m3u")])
        if filename:
            from m3u_sorter import M3USorter
            M3USorter(self.root, filename)
    
    def create_widgets(self):
        colors = get_colors()

        header = ttk.Frame(self.root, style='Header.TFrame', padding=(28, 20))
        header.pack(fill=tk.X)

        title_col = ttk.Frame(header, style='Header.TFrame')
        title_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(title_col, text='Kidneys M3U', style='Title.TLabel').pack(anchor=tk.W)
        ttk.Label(
            title_col,
            text='Filtra, reproduce y gestiona listas IPTV y YouTube',
            style='Subtitle.TLabel',
        ).pack(anchor=tk.W, pady=(4, 0))

        self.theme_button = ttk.Button(
            header,
            text=self._theme_button_label(),
            style='Ghost.TButton',
            command=self.toggle_tema,
        )
        self.theme_button.pack(side=tk.RIGHT)

        ttk.Separator(self.root, orient='horizontal').pack(fill=tk.X)

        status = ttk.Frame(self.root, style='Status.TFrame', padding=(24, 10))
        status.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(status, textvariable=self.status_var, style='Status.TLabel').pack(side=tk.LEFT)
        ttk.Separator(self.root, orient='horizontal').pack(fill=tk.X, side=tk.BOTTOM)

        body = ttk.Frame(self.root, padding=24)
        body.pack(fill=tk.BOTH, expand=True)

        files_card = ttk.LabelFrame(body, text=' ARCHIVOS ', padding=16)
        files_card.pack(fill=tk.X, pady=(0, 14))
        files_card.columnconfigure(1, weight=1)

        ttk.Label(files_card, text='Entrada M3U', style='Card.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 12), pady=6
        )
        ttk.Entry(files_card, textvariable=self.input_file).grid(
            row=0, column=1, sticky=(tk.W, tk.E), pady=6
        )
        ttk.Button(files_card, text='Examinar', command=self.browse_input).grid(
            row=0, column=2, padx=(10, 0), pady=6
        )

        ttk.Label(files_card, text='Salida', style='Card.TLabel').grid(
            row=1, column=0, sticky=tk.W, padx=(0, 12), pady=6
        )
        ttk.Entry(files_card, textvariable=self.output_file).grid(
            row=1, column=1, sticky=(tk.W, tk.E), pady=6
        )
        ttk.Button(files_card, text='Examinar', command=self.browse_output).grid(
            row=1, column=2, padx=(10, 0), pady=6
        )

        save_mode_frame = ttk.Frame(files_card, style='Card.TFrame')
        save_mode_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(8, 4))
        ttk.Label(save_mode_frame, text='Modo de guardado', style='CardMuted.TLabel').pack(
            side=tk.LEFT, padx=(0, 12)
        )
        ttk.Radiobutton(
            save_mode_frame, text='Sobrescribir', variable=self.save_mode, value='w'
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(
            save_mode_frame, text='Añadir al final', variable=self.save_mode, value='a'
        ).pack(side=tk.LEFT)

        self.drop_zone = tk.Frame(
            files_card,
            bg=colors['drop_bg'],
            highlightbackground=colors['drop_border'],
            highlightcolor=colors['drop_border'],
            highlightthickness=1,
        )
        self.drop_zone.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(12, 2))
        self.drop_label = tk.Label(
            self.drop_zone,
            text='Arrastra un archivo .m3u aquí',
            bg=colors['drop_bg'],
            fg=colors['text_muted'],
            pady=14,
        )
        self.drop_label.pack(fill=tk.X)

        filter_card = ttk.LabelFrame(body, text=' FILTRO ', padding=16)
        filter_card.pack(fill=tk.X, pady=(0, 14))
        filter_card.columnconfigure(1, weight=1)

        ttk.Label(filter_card, text='Patrón de búsqueda', style='Card.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 12)
        )
        ttk.Entry(filter_card, textvariable=self.search_pattern).grid(
            row=0, column=1, sticky=(tk.W, tk.E)
        )
        ttk.Button(filter_card, text='Editar', command=self.edit_pattern).grid(
            row=0, column=2, padx=(10, 0)
        )

        progress_card = ttk.LabelFrame(body, text=' PROGRESO ', padding=16)
        progress_card.pack(fill=tk.X, pady=(0, 14))
        self.progress = ttk.Progressbar(progress_card, mode='determinate')
        self.progress.pack(fill=tk.X)

        buttons_frame = ttk.Frame(body)
        buttons_frame.pack(fill=tk.X, pady=(4, 0))

        ttk.Button(
            buttons_frame, text='Procesar', style='Accent.TButton', command=self.process_file
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.stop_processing = False
        self.stop_button = ttk.Button(
            buttons_frame, text='Parar', style='Danger.TButton',
            command=self.stop_process, state='disabled',
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 8))
        self.open_folder_button = ttk.Button(
            buttons_frame, text='Abrir carpeta', command=self.open_output_folder, state='disabled'
        )
        self.open_folder_button.pack(side=tk.LEFT, padx=(0, 8))
        self.play_button = ttk.Button(
            buttons_frame, text='Reproducir', command=self.open_player, state='disabled'
        )
        self.play_button.pack(side=tk.LEFT)
    
    def edit_pattern(self):
        pattern_window = tk.Toplevel(self.root)
        pattern_window.title('Editar Patrón de Búsqueda')
        pattern_window.geometry('460x340')
        pattern_window.transient(self.root)
        pattern_window.grab_set()
        style_window(pattern_window)
        set_window_icon(pattern_window)
        center_window(pattern_window, 460, 340)

        edit_frame = ttk.Frame(pattern_window, padding=20)
        edit_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(edit_frame, text='Patrones predefinidos', style='Muted.TLabel').pack(fill=tk.X, pady=(0, 8))
        patterns_frame = ttk.Frame(edit_frame)
        patterns_frame.pack(fill=tk.X, pady=5)

        for pattern in self.patterns_list:
            ttk.Button(
                patterns_frame,
                text=pattern,
                command=lambda p=pattern: self.set_pattern(p, pattern_window),
            ).pack(fill=tk.X, pady=3)

        ttk.Label(edit_frame, text='Patrón personalizado', style='Muted.TLabel').pack(fill=tk.X, pady=(16, 8))
        custom_pattern = ttk.Entry(edit_frame)
        custom_pattern.insert(0, self.search_pattern.get())
        custom_pattern.pack(fill=tk.X, pady=(0, 16))
        custom_pattern.focus_set()

        buttons_frame = ttk.Frame(edit_frame)
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(
            buttons_frame,
            text='Aplicar',
            style='Accent.TButton',
            command=lambda: self.apply_custom_pattern(custom_pattern.get(), pattern_window),
        ).pack(side=tk.LEFT)
        ttk.Button(buttons_frame, text='Cancelar', command=pattern_window.destroy).pack(side=tk.LEFT, padx=8)
    
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
            self.status_var.set(f'Archivo de entrada: {os.path.basename(filename)}')
    
    def browse_output(self):
        filename = filedialog.asksaveasfilename(defaultextension=".m3u", filetypes=[("Archivos M3U", "*.m3u")])
        if filename:
            self.output_file.set(filename)
            self.status_var.set(f'Archivo de salida: {os.path.basename(filename)}')
    
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
        self.status_var.set('Procesando archivo…')
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
                        stripped = line.strip()
                        if not stripped or stripped.startswith('#'):
                            continue
                        if self.search_pattern.get() in line1:
                            buffer.append(line1)
                            buffer.append(line if line.endswith('\n') else line + '\n')
                            self.channels.append((line1.strip(), stripped))
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
                self.status_var.set('Proceso detenido · El archivo contiene los datos filtrados hasta ese momento')
                messagebox.showinfo('Parado', 'El proceso de filtrado fue detenido por el usuario. El archivo contiene los datos filtrados hasta ese momento.')
            else:
                self.status_var.set(f'Completado · {len(self.channels)} canales coincidentes')
                messagebox.showinfo('Éxito', 'Archivo procesado correctamente')

        except Exception as e:
            self.status_var.set('Error al procesar el archivo')
            messagebox.showerror('Error', f'Error al procesar el archivo: {str(e)}')
        finally:
            self.stop_button['state'] = 'disabled'

    def stop_process(self):
        self.stop_processing = True

    def _ensure_player(self):
        if self.video_player is None or not getattr(self.video_player, 'is_alive', lambda: False)():
            self.video_player = VideoPlayer()
        return self.video_player

    def load_url(self):
        url = tk.simpledialog.askstring("Cargar URL", "Introduce la URL de la lista M3U:")
        if url:
            player = self._ensure_player()
            player.run()
            player.load_m3u_url(url)
            self._refresh_recent_menu()

    def load_local_file(self):
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Selecciona un archivo M3U o M3U8",
            filetypes=[("Archivos M3U/M3U8", "*.m3u *.m3u8"), ("Todos los archivos", "*")]
        )
        if filename:
            player = self._ensure_player()
            player.run()
            player.load_m3u_file(filename)
            self._refresh_recent_menu()

    def open_player(self):
        player = self._ensure_player()
        player.run()
        output = self.output_file.get()
        if self.channels and output and os.path.isfile(output):
            player.load_m3u_file(output, notify=False)
            player.restore_last_channel()
        elif not player.channels:
            player.restore_session()
        self._refresh_recent_menu()

    def close_player(self):
        if self.video_player:
            self.video_player.close()
            self.video_player = None

    def quit_app(self):
        self._save_window_geometry()
        self.save_config()
        self.close_player()
        from youtube_player import cleanup_youtube_temp_dirs
        cleanup_youtube_temp_dirs()
        self.root.quit()
        self.root.destroy()

    def _on_window_configure(self, event=None):
        if event and event.widget is not self.root:
            return
        if self._geometry_save_job:
            try:
                self.root.after_cancel(self._geometry_save_job)
            except Exception:
                pass
        self._geometry_save_job = self.root.after(500, self._save_window_geometry)

    def _save_window_geometry(self):
        self._geometry_save_job = None
        geometry = app_config.capture_geometry(self.root)
        if geometry:
            app_config.remember_window('main', geometry)

    def _refresh_recent_menu(self):
        menu = getattr(self, 'recientes_menu', None)
        if menu is None:
            return
        menu.delete(0, tk.END)
        recent = app_config.load().get('recent_files') or []
        if not recent:
            menu.add_command(label='(vacío)', state='disabled')
            return
        for path in recent:
            label = path if path.lower().startswith('http') else os.path.basename(path)
            if len(label) > 60:
                label = label[:57] + '…'
            menu.add_command(label=label, command=lambda p=path: self._open_recent(p))
        style_menu_tree(menu)

    def _open_recent(self, path):
        player = self._ensure_player()
        player.run()
        if str(path).lower().startswith('http'):
            player.load_m3u_url(path, notify=False)
        elif os.path.isfile(path):
            player.load_m3u_file(path, notify=False)
        else:
            messagebox.showinfo('Lista reciente', 'Ese archivo ya no existe.')
            return
        player.restore_last_channel()
        self._refresh_recent_menu()

    def _theme_button_label(self):
        return 'Tema claro' if self.tema_oscuro else 'Tema oscuro'

    def _refresh_native_chrome(self):
        colors = get_colors()
        style_window(self.root)
        style_menu_tree(getattr(self, 'menubar', None))
        if hasattr(self, 'theme_button'):
            self.theme_button.configure(text=self._theme_button_label())
        if hasattr(self, 'drop_zone'):
            self.drop_zone.configure(
                bg=colors['drop_bg'],
                highlightbackground=colors['drop_border'],
                highlightcolor=colors['drop_border'],
            )
            self.drop_label.configure(bg=colors['drop_bg'], fg=colors['text_muted'])

    def toggle_tema(self):
        self.tema_oscuro = not self.tema_oscuro
        apply_theme(self.root, self.tema_oscuro)
        self._refresh_native_chrome()
        self.save_config()

    def setup_drag_drop(self):
        # Drag & Drop multiplataforma usando tkinterdnd2
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)
        try:
            self.root.dnd_bind('<<DragEnter>>', self.on_drag_enter)
            self.root.dnd_bind('<<DragLeave>>', self.on_drag_leave)
        except tk.TclError:
            pass

    def on_drag_enter(self, event):
        colors = get_colors()
        self.drop_zone.configure(highlightbackground=colors['accent'], highlightcolor=colors['accent'])
        self.drop_label.configure(fg=colors['accent'], text='Suelta el archivo para cargarlo')
        return event.action

    def on_drag_leave(self, event):
        self._reset_drop_zone()
        return event.action

    def _reset_drop_zone(self):
        colors = get_colors()
        self.drop_zone.configure(
            highlightbackground=colors['drop_border'],
            highlightcolor=colors['drop_border'],
        )
        self.drop_label.configure(fg=colors['text_muted'], text='Arrastra un archivo .m3u aquí')

    def handle_drop(self, event):
        file_path = event.data.strip()
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]
        self._reset_drop_zone()
        if file_path.lower().endswith('.m3u') or file_path.lower().endswith('.m3u8'):
            self.input_file.set(file_path)
            self.status_var.set(f'Archivo de entrada: {os.path.basename(file_path)}')
        else:
            self.status_var.set('Solo se aceptan archivos .m3u / .m3u8')
    
    def load_config(self):
        self.config = app_config.load()
        theme = self.config.get('theme', 'dark')
        self.tema_oscuro = theme in ('dark', 'equilux')
        if 'patterns' in self.config:
            self.patterns_list = self.config['patterns']

    def save_config(self):
        self.config = app_config.save({
            'theme': 'dark' if self.tema_oscuro else 'light',
            'patterns': self.patterns_list,
        })
    
    def get_default_config(self):
        return {
            'theme': 'dark',
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
        style_menu_tree(menu)

    def open_download_manager(self):
        """Abre la ventana del gestor de descargas"""
        from descargas import DownloadManager
        self.download_manager = DownloadManager(self.root)
        self.download_manager.window.transient(self.root)
        self.download_manager.window.grab_set()
        self.root.wait_window(self.download_manager.window)
        self.download_manager = None

def main():
    """Función principal para iniciar la aplicación"""
    try:
        root = TkinterDnD.Tk() 
        app = M3UProcessor(root)
        root.mainloop()
        return 0
    except Exception as e:
        print(f"Error al iniciar la aplicación: {e}")
        return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())