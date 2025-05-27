import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import yt_dlp
import os
import re
import requests
from urllib.parse import unquote

class DownloadManager:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("Descargar URL")
        self.window.geometry("600x400")
        self.window.resizable(True, True)
        
        # Variables
        self.url = tk.StringVar()
        self.output_path = tk.StringVar()
        self.filename = tk.StringVar()
        self.is_downloading = False
        
        self.create_widgets()
        
    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URL
        url_frame = ttk.LabelFrame(main_frame, text="URL a descargar", padding="5")
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Entry(url_frame, textvariable=self.url).pack(fill=tk.X, padx=5, pady=5)
        
        # Carpeta de destino
        dest_frame = ttk.LabelFrame(main_frame, text="Carpeta de destino", padding="5")
        dest_frame.pack(fill=tk.X, pady=(0, 10))
        
        dest_entry = ttk.Entry(dest_frame, textvariable=self.output_path)
        dest_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        ttk.Button(dest_frame, text="Buscar", command=self.browse_output).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Nombre del archivo
        name_frame = ttk.LabelFrame(main_frame, text="Nombre del archivo", padding="5")
        name_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Entry(name_frame, textvariable=self.filename).pack(fill=tk.X, padx=5, pady=5)
        
        # Barra de progreso
        self.progress_frame = ttk.LabelFrame(main_frame, text="Progreso", padding="5")
        self.progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress = ttk.Progressbar(self.progress_frame, length=300, mode='determinate')
        self.progress.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.progress_label.pack(pady=5)
        
        # Botones
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        self.download_button = ttk.Button(buttons_frame, text="Descargar", command=self.start_download)
        self.download_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(buttons_frame, text="Cancelar", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)
        
    def browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_path.set(folder)
            
    def start_download(self):
        if not self.url.get():
            messagebox.showerror("Error", "Por favor, introduce una URL")
            return
            
        if not self.output_path.get():
            messagebox.showerror("Error", "Por favor, selecciona una carpeta de destino")
            return
            
        if not self.filename.get():
            # Intentar obtener el título del video
            try:
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(self.url.get(), download=False)
                    # Eliminar caracteres no válidos para nombres de archivo en Windows y Linux
                    suggested_name = re.sub(r'[\\/*?:"<>|]', "", info.get('title', 'video'))
                    # Limitar la longitud del nombre para evitar problemas en algunos sistemas de archivos
                    suggested_name = suggested_name[:200]  # Longitud máxima razonable
                    self.filename.set(suggested_name)
            except Exception as e:
                print(f"Error al obtener información del video: {e}")
                self.filename.set('video')
        
        self.download_button.configure(state='disabled')
        threading.Thread(target=self._download, daemon=True).start()
        
    def _download(self):
        try:
            # Asegurar que el nombre del archivo tenga una extensión válida
            filename = self.filename.get()
            # Lista de extensiones comunes por tipo de archivo
            media_extensions = ['.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.wav', '.flv', '.avi', '.mov']
            playlist_extensions = ['.m3u', '.m3u8']
            text_extensions = ['.txt', '.srt', '.vtt']
            common_extensions = ['.pdf', '.zip', '.rar', '.json', '.xml']
            all_extensions = media_extensions + playlist_extensions + text_extensions + common_extensions
            
            # Verificar si la URL contiene una extensión
            url_path = unquote(self.url.get().split('?')[0])
            url_ext = os.path.splitext(url_path)[1].lower()
            
            # Si no hay extensión en el nombre del archivo pero sí en la URL, sugerirla
            if not os.path.splitext(filename)[1] and url_ext:
                # Preguntar al usuario si desea usar la extensión de la URL
                if messagebox.askyesno("Extensión de archivo", 
                                     f"¿Desea usar la extensión {url_ext} para el archivo?"):
                    filename += url_ext
            # Para URLs de YouTube, sugerir .mp4 si no hay extensión
            elif not os.path.splitext(filename)[1] and any(ext in self.url.get().lower() 
                                                         for ext in ['youtube.com', 'youtu.be']):
                if messagebox.askyesno("Extensión de archivo", 
                                     "¿Desea guardar el archivo con extensión .mp4?"):
                    filename += '.mp4'
            
            # Normalizar la ruta para el sistema operativo actual
            output_template = os.path.normpath(os.path.join(self.output_path.get(), filename))
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    # Calcular porcentaje
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    if total > 0:
                        downloaded = d.get('downloaded_bytes', 0)
                        percentage = (downloaded / total) * 100
                        speed = d.get('speed', 0)
                        if speed:
                            speed_str = f" - {self._format_speed(speed)}"
                        else:
                            speed_str = ""
                        self.window.after(0, self._update_progress, percentage, f"{d['_percent_str']}{speed_str}")
                        
            # Determinar si es una URL de YouTube o similar
            is_youtube = any(domain in self.url.get().lower() 
                           for domain in ['youtube.com', 'youtu.be', 'vimeo.com'])

            if is_youtube:
                # Configuración para descargas de YouTube y plataformas similares
                ydl_opts = {
                    'format': 'best',
                    'outtmpl': output_template,
                    'progress_hooks': [progress_hook],
                    'windowsfilenames': True,
                    'ignoreerrors': True,
                    'no_warnings': True,
                    'quiet': True,
                    'extract_flat': False,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([self.url.get()])
            else:
                # Para otros tipos de archivos, usar requests
                try:
                    # Realizar la solicitud con stream=True para archivos grandes
                    response = requests.get(self.url.get(), stream=True)
                    response.raise_for_status()
                    
                    # Obtener el tamaño total si está disponible
                    total_length = response.headers.get('content-length')
                    
                    if total_length is not None:
                        total_length = int(total_length)
                        dl = 0
                        
                        with open(output_template, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    dl += len(chunk)
                                    f.write(chunk)
                                    if total_length > 0:
                                        done = int(100 * dl / total_length)
                                        self.window.after(0, self._update_progress, 
                                                        done, f"{done}% - {self._format_speed(dl/30)}")
                    else:
                        # Si no hay content-length, guardar sin progreso
                        with open(output_template, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    
                except requests.RequestException as e:
                    raise Exception(f"Error al descargar el archivo: {str(e)}")
            
            self.window.after(0, self._download_complete)
            
        except Exception as e:
            self.window.after(0, self._show_error, str(e))
        
    def _update_progress(self, percentage, percent_str):
        self.progress['value'] = percentage
        self.progress_label.configure(text=f"Descargando: {percent_str}")
        
    def _download_complete(self):
        self.progress['value'] = 100
        self.progress_label.configure(text="¡Descarga completada!")
        messagebox.showinfo("Éxito", "La descarga se ha completado correctamente")
        self.window.destroy()
        
    def _show_error(self, error):
        self.download_button.configure(state='normal')
        messagebox.showerror("Error", f"Error durante la descarga:\n{error}")
        
    def _format_speed(self, speed):
        """Formatea la velocidad de descarga en una cadena legible"""
        if speed is None:
            return "? KB/s"
        if speed < 1024:
            return f"{speed:.0f} B/s"
        elif speed < 1024*1024:
            return f"{speed/1024:.1f} KB/s"
        else:
            return f"{speed/(1024*1024):.1f} MB/s"
