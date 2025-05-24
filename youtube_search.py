import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import yt_dlp
import requests
import webbrowser
import threading
import os
import re
from datetime import datetime, timedelta

class YouTubeSearchDialog:
    def __init__(self, parent, play_callback, load_playlist_callback=None):
        self.parent = parent
        self.play_callback = play_callback
        self.load_playlist_callback = load_playlist_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Buscar en YouTube")
        self.window.geometry("700x500")
        self.create_widgets()

    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Frame de búsqueda
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.bind('<Return>', lambda e: self.search())

        search_btn = ttk.Button(search_frame, text="Buscar", command=self.search)
        search_btn.pack(side=tk.LEFT, padx=5)

        # Frame de filtros
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Filtro por tipo de contenido
        ttk.Label(filter_frame, text="Tipo:").pack(side=tk.LEFT, padx=(0, 2))
        self.type_var = tk.StringVar(value="Vídeos")
        type_combobox = ttk.Combobox(
            filter_frame, textvariable=self.type_var,
            values=["Vídeos", "Listas de reproducción", "Canales"],
            width=15, state="readonly"
        )
        type_combobox.pack(side=tk.LEFT, padx=(0, 10))
        
        # Filtro por fecha
        ttk.Label(filter_frame, text="Fecha:").pack(side=tk.LEFT, padx=(0, 2))
        self.date_var = tk.StringVar(value="Cualquier fecha")
        date_combobox = ttk.Combobox(
            filter_frame, textvariable=self.date_var,
            values=["Cualquier fecha", "Hoy", "Esta semana", "Este mes", "Este año"],
            width=15, state="readonly"
        )
        date_combobox.pack(side=tk.LEFT, padx=(0, 10))
        
        # Filtro por duración
        ttk.Label(filter_frame, text="Duración:").pack(side=tk.LEFT, padx=(0, 2))
        self.duration_var = tk.StringVar(value="Cualquier duración")
        duration_combobox = ttk.Combobox(
            filter_frame, textvariable=self.duration_var,
            values=["Cualquier duración", "Corto (<4 min)", "Medio (4-20 min)", "Largo (>20 min)"],
            width=15, state="readonly"
        )
        duration_combobox.pack(side=tk.LEFT, padx=(0, 10))
        
        # Filtro por orden
        ttk.Label(filter_frame, text="Ordenar por:").pack(side=tk.LEFT, padx=(0, 2))
        self.sort_var = tk.StringVar(value="Relevancia")
        sort_combobox = ttk.Combobox(
            filter_frame, textvariable=self.sort_var,
            values=["Relevancia", "Fecha", "Vistas", "Valoración"],
            width=15, state="readonly"
        )
        sort_combobox.pack(side=tk.LEFT)
        
        # Spinbox para seleccionar el número de resultados
        results_frame = ttk.Frame(main_frame)
        results_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(results_frame, text="Número de resultados:").pack(side=tk.LEFT, padx=(0, 2))
        self.results_count = tk.IntVar(value=10)
        results_spinbox = tk.Spinbox(
            results_frame, from_=1, to=100, textvariable=self.results_count, width=4
        )
        results_spinbox.pack(side=tk.LEFT)
        
        # Frame para la lista de resultados y barra de desplazamiento
        results_list_frame = ttk.Frame(main_frame)
        results_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(results_list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox con resultados
        self.results_listbox = tk.Listbox(results_list_frame, yscrollcommand=scrollbar.set, font=("Arial", 10))
        self.results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.results_listbox.yview)
        
        # Configurar el menú contextual para la lista de resultados
        self.results_listbox.bind('<Double-Button-1>', self.play_selected)
        self.results_listbox.bind('<Button-3>', self.show_context_menu)
        
        # Frame de botones
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        play_btn = ttk.Button(button_frame, text="Reproducir", command=self.play_selected)
        play_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        download_btn = ttk.Button(button_frame, text="Descargar", command=self.download_selected)
        download_btn.pack(side=tk.LEFT, padx=5)
        
        close_btn = ttk.Button(button_frame, text="Cerrar", command=self.window.destroy)
        close_btn.pack(side=tk.RIGHT)
        
        self.results = []
        self.result_types = []
        self.result_details = []  # Para almacenar detalles adicionales como duración

    def search(self):
        query = self.search_var.get().strip()
        if not query:
            messagebox.showinfo("Info", "Introduce un término de búsqueda.")
            return
        
        self.results_listbox.delete(0, tk.END)
        self.results = []
        self.result_types = []
        self.result_details = []
        
        # Aplicar filtros a la consulta
        search_query = query
        
        # Filtro de fecha
        date_filter = self.date_var.get()
        date_query = ""
        if date_filter == "Hoy":
            date_query = " after:today"
        elif date_filter == "Esta semana":
            date_query = f" after:{(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')}"
        elif date_filter == "Este mes":
            date_query = f" after:{(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')}"
        elif date_filter == "Este año":
            date_query = f" after:{(datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')}"
        
        # Filtro de duración
        duration_filter = self.duration_var.get()
        duration_query = ""
        if duration_filter == "Corto (<4 min)":
            duration_query = " short"
        elif duration_filter == "Medio (4-20 min)":
            duration_query = " medium"
        elif duration_filter == "Largo (>20 min)":
            duration_query = " long"
        
        # Aplicar filtros a la consulta
        if self.type_var.get() == "Vídeos":
            search_query += date_query + duration_query
        elif self.type_var.get() == "Listas de reproducción":
            search_query += " playlist" + date_query
        # NO añadir nada para canales, solo buscar el nombre
        try:
            tipo = self.type_var.get()
            max_results = min(max(self.results_count.get(), 1), 100)
            
            # Configurar opciones de yt-dlp
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'skip_download': True,
                'force_generic_extractor': False,
            }
            
            # Aplicar ordenación
            sort_option = self.sort_var.get()
            if sort_option == "Fecha":
                search_url = f"ytsearch{max_results}:{search_query}"
                ydl_opts['dateafter'] = 'today'
            elif sort_option == "Vistas":
                search_url = f"ytsearch{max_results}:{search_query}"
                ydl_opts['format'] = 'best'
                ydl_opts['extractor_args'] = {'youtube': {'sort_by': 'view_count'}}
            elif sort_option == "Valoración":
                search_url = f"ytsearch{max_results}:{search_query}"
                ydl_opts['format'] = 'best'
                ydl_opts['extractor_args'] = {'youtube': {'sort_by': 'rating'}}
            else:  # Relevancia (por defecto)
                search_url = f"ytsearch{max_results}:{search_query}"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
                found_playlist = False
                for entry in info.get('entries', []):
                    title = entry.get('title', 'Sin título')
                    duration = entry.get('duration')
                    duration_str = self.format_duration(duration) if duration else ""
                    if tipo == "Listas de reproducción":
                        # Detectar listas de reproducción reales
                        if (entry.get('ie_key') == 'YoutubePlaylist') or (entry.get('playlist_id')):
                            playlist_id = entry.get('playlist_id') or entry.get('id')
                            url = f"https://www.youtube.com/playlist?list={playlist_id}"
                            self.result_types.append("playlist")
                            self.results.append(url)
                            self.result_details.append({
                                'title': title,
                                'id': playlist_id,
                                'duration': duration
                            })
                            self.results_listbox.insert(tk.END, f"📑 {title}")
                            found_playlist = True
                    elif tipo == "Vídeos":
                        url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                        self.result_types.append("video")
                        self.results.append(url)
                        self.result_details.append({
                            'title': title,
                            'id': entry.get('id'),
                            'duration': duration
                        })
                        display_text = f"▶️ {title}"
                        if duration_str:
                            display_text += f" [{duration_str}]"
                        self.results_listbox.insert(tk.END, display_text)
                    elif tipo == "Canales":
                        # Solo mostrar el canal principal, no vídeos del canal
                        channel_id = entry.get('channel_id') or entry.get('uploader_id') or entry.get('id')
                        if channel_id:
                            url = f"https://www.youtube.com/channel/{channel_id}"
                            self.result_types.append("channel")
                            self.results.append(url)
                            self.result_details.append({
                                'title': title,
                                'id': channel_id
                            })
                            self.results_listbox.insert(tk.END, f"📺 {title}")
                        # No mostrar vídeos del canal en este modo
                if tipo == "Listas de reproducción" and not found_playlist:
                    messagebox.showinfo("Info", "No se encontraron listas de reproducción con ese nombre.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo realizar la búsqueda: {e}")

    def format_duration(self, seconds):
        """Formatea la duración en segundos a formato HH:MM:SS o MM:SS"""
        if not seconds:
            return ""
        
        try:
            seconds = int(seconds)
            if seconds < 3600:  # Menos de una hora
                return f"{seconds // 60}:{seconds % 60:02d}"
            else:
                return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
        except:
            return ""

    def show_context_menu(self, event):
        """Muestra el menú contextual al hacer clic derecho en un elemento"""
        selection = self.results_listbox.nearest(event.y)
        if 0 <= selection < len(self.results):
            self.results_listbox.selection_clear(0, tk.END)
            self.results_listbox.selection_set(selection)
            self.results_listbox.activate(selection)
            
            context_menu = tk.Menu(self.window, tearoff=0)
            tipo = self.result_types[selection]
            
            if tipo == "video":
                context_menu.add_command(label="Reproducir", command=self.play_selected)
                context_menu.add_command(label="Descargar", command=self.download_selected)
                context_menu.add_separator()
                context_menu.add_command(label="Abrir en navegador", 
                                        command=lambda: webbrowser.open_new(self.results[selection]))
            elif tipo == "playlist":
                context_menu.add_command(label="Cargar lista", command=self.play_selected)
                context_menu.add_separator()
                context_menu.add_command(label="Abrir en navegador", 
                                        command=lambda: webbrowser.open_new(self.results[selection]))
            elif tipo == "channel":
                context_menu.add_command(label="Abrir en navegador", 
                                        command=lambda: webbrowser.open_new(self.results[selection]))
            
            context_menu.tk_popup(event.x_root, event.y_root)

    def play_selected(self, event=None):
        selection = self.results_listbox.curselection()
        if selection:
            index = selection[0]
            url = self.results[index]
            tipo = self.result_types[index] if hasattr(self, 'result_types') else "video"
            if tipo == "video":
                self.play_callback(url)
                self.window.destroy()
            elif tipo == "playlist":
                self.load_playlist_videos(url)
                self.window.destroy()
            elif tipo == "channel":
                webbrowser.open_new(url)
                self.window.destroy()

    def download_selected(self):
        """Descarga el vídeo seleccionado"""
        selection = self.results_listbox.curselection()
        if not selection:
            messagebox.showinfo("Info", "Selecciona un vídeo para descargar.")
            return
        
        index = selection[0]
        tipo = self.result_types[index]
        url = self.results[index]
        
        if tipo != "video":
            messagebox.showinfo("Info", "Solo se pueden descargar vídeos individuales.")
            return
        
        # Obtener información del vídeo
        try:
            title = self.result_details[index]['title']
            # Limpiar el título para usarlo como nombre de archivo
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            
            # Pedir al usuario dónde guardar el archivo
            filepath = filedialog.asksaveasfilename(
                title="Guardar vídeo",
                initialfile=safe_title,
                filetypes=[("Todos los archivos", "*.*")]
            )
            
            if not filepath:
                return  # Usuario canceló
                
            # Iniciar la descarga en un hilo separado
            download_thread = threading.Thread(
                target=self._execute_download, 
                args=(url, filepath, title)
            )
            download_thread.start()
            
            messagebox.showinfo("Descarga iniciada", 
                               f"Iniciando descarga de '{title}'. Se te notificará cuando termine.")
                
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar la descarga: {str(e)}")

    def _execute_download(self, url, filepath, title):
        """Ejecuta la descarga del vídeo de YouTube."""
        try:
            ydl_opts = {
                'format': 'best',  # Mejor formato disponible
                'outtmpl': filepath,
                'quiet': False,
                'noplaylist': True,
                'noprogress': False,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
                }
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            # Notificar al usuario en el hilo principal
            self.window.after(0, lambda: messagebox.showinfo(
                "Descarga completada", 
                f"'{title}' descargado en:\n{filepath}"
            ))
            
        except Exception as e:
            # Capturar el error y mostrarlo
            error_message = str(e)
            self.window.after(0, lambda msg=error_message: messagebox.showerror(
                "Error de descarga", 
                f"No se pudo descargar '{title}':\n{msg}\n\nPosibles soluciones:\n"
                f"1. Verifica que el enlace sea accesible\n"
                f"2. Prueba con otro vídeo\n"
                f"3. Comprueba tu conexión a internet"
            ))
            
            # Intentar eliminar archivo parcial si existe
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass  # No hacer nada si no se puede borrar

    def load_playlist_videos(self, playlist_url):
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'skip_download': True,
                'force_generic_extractor': False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                videos = info.get('entries', [])
                if not videos:
                    messagebox.showinfo("Info", "No se encontraron vídeos en la playlist.")
                    return
                # Prepara la lista de canales (nombre, url)
                channels = []
                for video in videos:
                    title = video.get('title', 'Sin título')
                    video_url = f"https://www.youtube.com/watch?v={video.get('id')}"
                    channels.append((title, video_url))
                # Llama al callback del reproductor para cargar los vídeos como canales
                if self.load_playlist_callback:
                    self.load_playlist_callback(channels)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo obtener la playlist: {e}")