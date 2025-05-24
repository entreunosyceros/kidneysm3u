import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import vlc
import requests
import json
import re
import yt_dlp
from urllib.parse import parse_qs, urlparse
from youtube_player import YouTubeHandler
from youtube_search import YouTubeSearchDialog
import os
import threading 
import psutil
 
class VideoPlayer:
    def __init__(self):
        self.window = None
        self.instance = vlc.Instance(
            "--avcodec-hw=none",  # Forzar decodificación por software
            "--aout=alsa",        # Forzar salida de audio ALSA
            "--audio-resampler=soxr", # Resampler de audio
            "--network-caching=3000",
            "--live-caching=3000",
            "--file-caching=3000",
            "--sout-mux-caching=3000",
            "--no-ts-trust-pcr"
        )
        self.player = self.instance.media_player_new()
        self.channels = []
        self.current_channel = None
        self.channels_listbox = None
        self.channels_frame_visible = True
        self.is_fullscreen = False
        self.controls_visible = True
        self.hide_controls_timer = None
        self.volume = 50
        self.favorites = []
        self.all_channels = []
        self.is_seeking = False 
        self.update_time_job = None  # Inicializar para evitar errores al cerrar

        # Inicializar el manejador de YouTube
        self.youtube_handler = YouTubeHandler(self)

        self.create_window()
        self.load_favorites()
        self.setup_mouse_tracking()
        self.setup_keyboard_shortcuts()

    def create_window(self):
        self.window = tk.Toplevel()
        self.window.title('Reproductor Vídeos')
        self.window.geometry('800x600')

        self.create_menu()

        # Frame principal
        self.main_frame = ttk.Frame(self.window)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame de canales
        self.channels_frame = ttk.Frame(self.main_frame)
        self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)

        # Botones de favoritos
        favorites_buttons_frame = ttk.Frame(self.channels_frame)
        favorites_buttons_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        ttk.Button(favorites_buttons_frame, text="⭐ Favoritos", command=self.show_favorites).pack(side=tk.LEFT, padx=2)
        ttk.Button(favorites_buttons_frame, text="📺 Todos", command=self.restore_all_channels).pack(side=tk.LEFT, padx=2)

        # Búsqueda
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_channels)
        self.search_entry = ttk.Entry(self.channels_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.channels_listbox = tk.Listbox(self.channels_frame, width=30, yscrollcommand=None)
        self.channels_listbox.pack(side=tk.LEFT, fill=tk.Y)
        self.channels_listbox.bind('<Double-Button-1>', self.play_selected)
        self.channels_listbox.bind('<Button-3>', self.show_channel_context_menu)

        scrollbar = ttk.Scrollbar(self.channels_frame, orient=tk.VERTICAL, command=self.channels_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.channels_listbox.config(yscrollcommand=scrollbar.set)

        # Frame de reproductor
        self.player_frame = ttk.Frame(self.main_frame)
        self.player_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.video_frame = ttk.Frame(self.player_frame)
        self.video_frame.pack(fill=tk.BOTH, expand=True)

        # Controles
        self.controls_frame = ttk.Frame(self.player_frame)
        self.controls_frame.pack(fill=tk.X, pady=5)

        # Barra de progreso (solo visible para YouTube)
        self.progress_frame = ttk.Frame(self.controls_frame)
        self.progress_bar = ttk.Scale(
            self.progress_frame,
            from_=0,
            to=100,
            orient='horizontal',
            command=None,  # No permitir seek
            state='disabled'  # Deshabilitada
        )
        self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_frame.pack_forget()  # Oculta por defecto

        # Botones de control
        controls_buttons_frame = ttk.Frame(self.controls_frame)
        controls_buttons_frame.pack(side=tk.TOP, fill=tk.X)
        buttons_info = [
            ("⏮⏮", lambda: self.seek_relative(-10)),
            ("⏮", lambda: self.seek_relative(-2)),
            ("⏯", self.toggle_play),
            ("⏭", lambda: self.seek_relative(2)),
            ("⏭⏭", lambda: self.seek_relative(10)),
            ("⏹", self.stop),
            ("🔊", self.toggle_mute),
            ("⛶", self.toggle_fullscreen),
            ("≡", self.toggle_playlist)
        ]
        for text, command in buttons_info:
            btn = ttk.Button(controls_buttons_frame, text=text, command=command)
            btn.pack(side=tk.LEFT, padx=5)
        self.add_volume_control()
        # self.setup_performance_monitoring()
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind('<Escape>', lambda e: self.exit_fullscreen())

    def setup_performance_monitoring(self):
        """Inicia el monitoreo de recursos"""
        self.cpu_label = ttk.Label(self.controls_frame, text="CPU: 0%")
        self.cpu_label.pack(side=tk.RIGHT, padx=5)
        self.update_performance_stats()

    def update_performance_stats(self):
        """Actualiza las estadísticas de rendimiento"""
        cpu_percent = psutil.cpu_percent()
        self.cpu_label.config(text=f"CPU: {cpu_percent}%")
        self.window.after(1000, self.update_performance_stats)
        
    def create_menu(self):
        self.menubar = tk.Menu(self.window)

        reproducir_menu = tk.Menu(self.menubar, tearoff=0)
        reproducir_menu.add_command(label="Cargar URL", command=self.prompt_url)
        reproducir_menu.add_command(label="Cargar Archivo Local", command=self.prompt_file)
        reproducir_menu.add_separator()
        reproducir_menu.add_command(label="Cerrar Reproductor", command=self.close)

        youtube_menu = tk.Menu(self.menubar, tearoff=0)
        youtube_menu.add_command(label="Cargar URL de YouTube", command=self.youtube_handler.prompt_youtube_url)
        youtube_menu.add_command(label="Descargar vídeo de YouTube", command=self.youtube_handler.download_youtube_video)
        youtube_menu.add_command(label="Buscar en YouTube", command=self.open_youtube_search)
        # NUEVO: Añadir opción para cargar playlist
        youtube_menu.add_command(label="Cargar Playlist de YouTube", command=self.prompt_youtube_playlist)
        favoritos_menu = tk.Menu(self.menubar, tearoff=0)
        favoritos_menu.add_command(label="Mostrar Favoritos", command=self.show_favorites)
        favoritos_menu.add_command(label="Añadir a Favoritos", command=self.add_to_favorites)
        favoritos_menu.add_command(label="Eliminar de Favoritos", command=self.remove_from_favorites)

        self.menubar.add_cascade(label="Reproducir", menu=reproducir_menu)
        self.menubar.add_cascade(label="Youtube", menu=youtube_menu)
        self.menubar.add_cascade(label="Favoritos", menu=favoritos_menu)
        self.window.config(menu=self.menubar)

    def setup_keyboard_shortcuts(self):
        self.window.bind('<space>', lambda e: self.toggle_play())
        self.window.bind('<f>', lambda e: self.toggle_fullscreen())
        self.window.bind('<m>', lambda e: self.toggle_mute())
        self.window.bind('<Control-s>', lambda e: self.add_to_favorites())
        self.window.bind('<Left>', lambda e: self.seek_relative(-2))  # Retroceder 2 segundos
        self.window.bind('<Right>', lambda e: self.seek_relative(2))  # Avanzar 2 segundos

    def setup_mouse_tracking(self):
        for widget in [self.window, self.video_frame, self.controls_frame, self.player_frame]:
            widget.bind('<Motion>', self.on_mouse_move)

    def on_mouse_move(self, event=None):
        if self.is_fullscreen:
            self.show_controls()
            self.reset_hide_controls_timer()

    def show_controls(self):
        if not self.controls_visible:
            self.controls_frame.pack(side=tk.BOTTOM, fill=tk.X)
            self.controls_visible = True

    def hide_controls(self):
        if self.controls_visible and self.is_fullscreen:
            self.controls_frame.pack_forget()
            self.controls_visible = False

    def toggle_playlist(self):
        if self.channels_frame_visible:
            self.channels_frame.pack_forget()
        else:
            self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.channels_frame_visible = not self.channels_frame_visible
        self.window.update_idletasks()

    def load_m3u_file(self, filename):
        """Carga un archivo M3U local."""
        try:
            # Asegurarse de que la ventana existe
            if not self.window:
                self.create_window()
            
            # Limpiar la lista actual
            self.channels.clear()
            self.channels_listbox.delete(0, tk.END)
            
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            name = ""
            self.all_channels.clear()
            for line in lines:
                line = line.strip()
                if line.startswith('#EXTINF:'):
                    name = line.split(',')[-1]
                elif line and not line.startswith('#'):
                    self.channels.append((name, line))
                    self.all_channels.append((name, line))
                    self.channels_listbox.insert(tk.END, name)
                    
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar el archivo: {str(e)}")

    def load_m3u_url(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            self.channels.clear()
            self.channels_listbox.delete(0, tk.END)
            self._parse_m3u(response.text.splitlines())
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar la URL: {e}")

    def _parse_m3u(self, lines):
        name = ""
        self.all_channels.clear()
        for line in lines:
            line = line.strip()
            if line.startswith('#EXTINF:'):
                name = line.split(',')[-1]
            elif line and not line.startswith('#'):
                self.channels.append((name, line))
                self.all_channels.append((name, line))
                self.channels_listbox.insert(tk.END, name)

    def filter_channels(self, *args):
        search_term = self.search_var.get().lower()
        self.channels.clear()
        self.channels_listbox.delete(0, tk.END)
        
        for name, url in self.all_channels:
            if search_term in name.lower():
                self.channels.append((name, url))
                self.channels_listbox.insert(tk.END, name)

    def seek_relative(self, seconds):
        """Avanza o retrocede el video en segundos"""
        if self.player and self.player.is_playing():
            current_time = self.player.get_time()
            new_time = current_time + (seconds * 1000)  # Convertir a milisegundos
            
            # Asegurarse de que no vamos más allá de los límites del video
            if new_time < 0:
                new_time = 0
            elif new_time > self.player.get_length():
                new_time = self.player.get_length()
                
            self.player.set_time(int(new_time))

    def adjust_video_settings(self):
        """Ajusta la configuración del video para optimizar la reproducción"""
        if self.player:
            # Cambiamos True por una cadena vacía "" para desactivar o "yadif" para activar
            self.player.video_set_deinterlace("") 
            self.player.audio_set_volume(self.volume)

    def prompt_url(self):
        url = simpledialog.askstring("Cargar URL", "Introduce la URL de la lista M3U:")
        if url:
            self.load_m3u_url(url)

    def prompt_file(self):
        filename = filedialog.askopenfilename(
            title="Selecciona un archivo M3U o M3U8",
            filetypes=[("Archivos M3U/M3U8", "*.m3u *.m3u8"), ("Todos los archivos", "*")],
            parent=self.window
        )
        if filename:
            self.load_m3u_file(filename)

    def prompt_youtube_playlist(self):
        playlist_url = simpledialog.askstring("Cargar Playlist de YouTube", "Introduce la URL de la playlist de YouTube:")
        if playlist_url:
            self.load_youtube_playlist(playlist_url)

    def load_youtube_playlist(self, playlist_url):
        """
        Carga todos los vídeos de una playlist de YouTube y los muestra en la lista de canales.
        """
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

                self.channels.clear()
                self.channels_listbox.delete(0, tk.END)
                self.all_channels.clear()
                for video in videos:
                    title = video.get('title', 'Sin título')
                    video_url = f"https://www.youtube.com/watch?v={video.get('id')}"
                    self.channels.append((title, video_url))
                    self.all_channels.append((title, video_url))
                    self.channels_listbox.insert(tk.END, title)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo obtener la playlist: {e}")

    def play_selected(self, event=None):
        """Reproduce el canal seleccionado de la lista al hacer doble clic."""
        selection = self.channels_listbox.curselection()
        if selection:
            index = selection[0]
            self.play_channel(index)
    def play_channel(self, index):
        if 0 <= index < len(self.channels):
            name, url = self.channels[index]
            if self.instance is None:
                self.instance = vlc.Instance(
                    "--avcodec-hw=none",
                    "--aout=alsa",
                    "--audio-resampler=soxr",
                    "--network-caching=3000",
                    "--live-caching=3000",
                    "--file-caching=3000",
                    "--sout-mux-caching=3000",
                    "--no-ts-trust-pcr"
                )
            if self.player is None:
                self.player = self.instance.media_player_new()
            self.show_controls_and_menu()
            if "youtube.com" in url or "youtu.be" in url:
                self.youtube_handler.play_youtube_url(url)
                return
            try:
                if self.player.is_playing():
                    self.player.stop()
                media = self.instance.media_new(url)
                media.add_option('network-caching=3000')
                media.add_option('live-caching=3000')
                media.add_option('file-caching=3000')
                media.add_option('sout-mux-caching=3000')
                media.add_option('no-ts-trust-pcr')
                media.add_option('avcodec-hw=none')
                media.add_option('aout=alsa')
                media.add_option('audio-resampler=soxr')
                self.player.set_media(media)
                self.player.play()
                import sys
                if sys.platform.startswith('win'):
                    self.player.set_hwnd(self.video_frame.winfo_id())
                elif sys.platform.startswith('linux'):
                    self.player.set_xwindow(self.video_frame.winfo_id())
                elif sys.platform == 'darwin':
                    self.player.set_nsobject(self.video_frame.winfo_id())
                self.adjust_video_settings()
                self.start_update_time()  # Restaurar lógica de actualización periódica
                print("[AUDIO] Reproducción iniciada con aout=alsa y audio-resampler=soxr")
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                messagebox.showerror("Error de reproducción", f"No se pudo reproducir el canal '{name}'.\n\nError: {e}")

    def play_video_url(self, url, force_pulse=False, show_progress=False):
        try:
            if self.player is None:
                self.player = self.instance.media_player_new()
            if self.player.is_playing():
                self.player.stop()
            self.show_controls_and_menu()
            if show_progress:
                self.show_youtube_progress_bar()
            else:
                self.hide_progress_bar()
            media = self.instance.media_new(
                url,
                "input-repeat=1"
            )
            media.add_option('network-caching=3000')
            media.add_option('live-caching=3000')
            media.add_option('file-caching=3000')
            media.add_option('sout-mux-caching=3000')
            media.add_option('no-ts-trust-pcr')
            media.add_option('avcodec-hw=none')
            if force_pulse:
                media.add_option('aout=pulse')
                print("[AUDIO] Forzando salida de audio: pulse (YouTube)")
            else:
                media.add_option('aout=alsa')
                print("[AUDIO] Forzando salida de audio: alsa (M3U)")
            media.add_option('audio-resampler=soxr')
            media.add_option('codec=avcodec')
            media.add_option('http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0')
            self.player.set_media(media)
            self.player.play()
            self.window.update_idletasks()
            self.video_frame.update_idletasks()
            import sys
            if sys.platform.startswith('win'):
                self.player.set_hwnd(self.video_frame.winfo_id())
            elif sys.platform.startswith('linux'):
                self.player.set_xwindow(self.video_frame.winfo_id())
            elif sys.platform == 'darwin':
                self.player.set_nsobject(self.video_frame.winfo_id())
            self.adjust_video_settings()
            self.start_update_time()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo reproducir el vídeo: {e}")

    def start_update_time(self):
        """Inicia la actualización periódica de tiempo de reproducción (sin barra de progreso visible)."""
        self.stop_update_time()  # Detener cualquier temporizador previo
        self.update_time()  # Llamada inicial

    def stop_update_time(self):
        if self.update_time_job:
            try:
                self.window.after_cancel(self.update_time_job)
            except Exception:
                pass
            self.update_time_job = None

    def update_time(self):
        """Actualiza el tiempo de reproducción internamente para mantener el stream activo."""
        if self.player and self.player.is_playing():
            # Solo consulta el tiempo, no actualiza ninguna barra
            _ = self.player.get_time()
            _ = self.player.get_length()
        self.update_time_job = self.window.after(1000, self.update_time)

    def close(self):
        """Cierra la ventana y libera recursos."""
        try:
            self.save_favorites()
            self.stop_update_time()  # Detener temporizador de actualización
            if self.player:
                try:
                    if self.player.is_playing():
                        self.player.stop()
                    self.player.release()
                except Exception:
                    pass
                finally:
                    self.player = None
            if self.instance:
                try:
                    self.instance.release()
                except Exception:
                    pass
                finally:
                    self.instance = None
            if self.window:
                try:
                    self.window.destroy()
                except tk.TclError:
                    pass
                finally:
                    self.window = None
        except Exception as e:
            print(f"Error durante el cierre del reproductor: {e}")

    def toggle_mute(self):
        self.player.audio_toggle_mute()

    def toggle_fullscreen(self, event=None):
        if not self.is_fullscreen:
            self.enter_fullscreen()
        else:
            self.exit_fullscreen()

    def reset_hide_controls_timer(self):
        """Reinicia el temporizador para ocultar controles y menú en pantalla completa."""
        if self.hide_controls_timer:
            self.window.after_cancel(self.hide_controls_timer)
            self.hide_controls_timer = None
        self.show_controls_and_menu()
        # Oculta controles y menú tras 3 segundos de inactividad
        self.hide_controls_timer = self.window.after(3000, self.hide_controls_and_menu)

    def hide_controls_and_menu(self):
        """Oculta controles y menú superior en pantalla completa."""
        if self.is_fullscreen:
            self.hide_controls()
            self.window.config(menu="")  # Cambiado de None a ""

    def show_controls_and_menu(self):
        """Muestra controles y menú superior."""
        self.show_controls()
        self.window.config(menu=self.menubar)

    def enter_fullscreen(self):
        self.window.attributes('-fullscreen', True)
        self.is_fullscreen = True
        self.window.config(menu="")  # Cambiado de None a ""
        if self.channels_frame_visible:
            self.channels_frame.pack_forget()
        self.reset_hide_controls_timer()

    def exit_fullscreen(self):
        self.window.attributes('-fullscreen', False)
        self.is_fullscreen = False
        self.window.config(menu=self.menubar)
        if not self.channels_frame_visible:
            self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)
        if self.hide_controls_timer:
            self.window.after_cancel(self.hide_controls_timer)
            self.hide_controls_timer = None
        self.show_controls_and_menu()

    def add_volume_control(self):
        self.volume_scale = ttk.Scale(
            self.controls_frame, from_=0, to=100,
            orient='horizontal', command=self.set_volume
        )
        self.volume_scale.set(self.volume)
        self.volume_scale.pack(side=tk.LEFT, padx=5)

    def add_to_favorites(self):
        selection = self.channels_listbox.curselection()
        if selection:
            index = selection[0]
            channel = self.channels[index]
            if channel not in self.favorites:
                self.favorites.append(channel)
                self.save_favorites()

    def save_favorites(self):
        try:
            with open('favoritos.json', 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron guardar los favoritos: {e}")

    def load_favorites(self):
        try:
            with open('favoritos.json', 'r', encoding='utf-8') as f:
                self.favorites = json.load(f)
        except FileNotFoundError:
            self.favorites = []
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los favoritos: {e}")

    def run(self):
        if not self.window:
            # Reinicializar el reproductor VLC si es necesario
            if not self.player or not self.instance:
                self.instance = vlc.Instance(
                    "--no-xlib",
                    "--avcodec-hw=any",
                    "--network-caching=3000",
                    "--live-caching=3000",
                    "--file-caching=3000",
                    "--sout-mux-caching=3000",
                    "--clock-jitter=0",
                    "--clock-synchro=0",
                    "--no-drop-late-frames",
                    "--no-skip-frames",
                    "--vout=any"
                )
                self.player = self.instance.media_player_new()
                self.volume = 50
            self.create_window()
        else:
            try:
                self.window.deiconify()
                self.window.lift()
                self.window.focus_force()
            except tk.TclError:
                # Si la ventana fue destruida, reinicializar todo
                self.window = None
                self.player = None
                self.instance = None
                self.run()

    def set_volume(self, value):
        """Establece el volumen del reproductor"""
        try:
            if self.player:
                self.volume = int(float(value))
                self.player.audio_set_volume(self.volume)
        except Exception as e:
            print(f"Error al ajustar el volumen: {e}")

    def show_favorites(self):
        if not self.favorites:
            messagebox.showinfo("Favoritos", "Por el momento no hay favoritos añadidos.")
            return
        self.temp_channels = self.channels.copy()
        self.channels.clear()
        self.channels_listbox.delete(0, tk.END)
        
        for channel in self.favorites:
            self.channels.append(channel)
            self.channels_listbox.insert(tk.END, channel[0])
    
    def remove_from_favorites(self):
        selection = self.channels_listbox.curselection()
        if selection:
            index = selection[0]
            channel = self.channels[index]
            if channel in self.favorites:
                self.favorites.remove(channel)
                self.save_favorites()
                messagebox.showinfo("Éxito", "Canal eliminado de favoritos")
    
    def restore_all_channels(self):
        self.channels = self.all_channels.copy()
        self.channels_listbox.delete(0, tk.END)
        for channel in self.channels:
            self.channels_listbox.insert(tk.END, channel[0])

    def show_channel_context_menu(self, event):
        context_menu = tk.Menu(self.window, tearoff=0)
        try: # Añadir manejo de errores por si el índice no es válido
            index = self.channels_listbox.nearest(event.y)
            if index < 0 or index >= len(self.channels): # Verificar índice válido
                 return 
            self.channels_listbox.selection_clear(0, tk.END)
            self.channels_listbox.selection_set(index)
            channel = self.channels[index]
            
            if channel in self.favorites:
                context_menu.add_command(label="Eliminar de Favoritos", command=self.remove_from_favorites)
            else:
                context_menu.add_command(label="Añadir a Favoritos", command=self.add_to_favorites)
            
            context_menu.add_command(label="Reproducir", command=self.play_selected)
            # Añadir opción de descarga
            context_menu.add_command(label="Descargar", command=lambda idx=index: self.download_channel(idx)) 
            context_menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
             print(f"Error al mostrar menú contextual: {e}") # Mejor depuración

    def check_available_formats(self, url):
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                print("Formatos disponibles:")
                for f in formats:
                    print(f"Format ID: {f['format_id']}, Ext: {f['ext']}, Codec: {f.get('vcodec', '?')}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al verificar formatos: {str(e)}")

    def prompt_youtube_url(self):
        """Delega la solicitud de URL de YouTube al manejador centralizado"""
        self.youtube_handler.prompt_youtube_url()

    def add_channel_to_list(self, name, url):
        """Añade un canal o vídeo individual a la lista de la izquierda y a all_channels."""
        self.channels.append((name, url))
        self.all_channels.append((name, url))
        self.channels_listbox.insert(tk.END, name)

    def play_youtube_url(self, url):
        """Delega la reproducción de YouTube al manejador centralizado, forzando salida pulse y añade a la lista si no está."""
        # Obtener título del vídeo antes de reproducir
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', url)
        except Exception:
            title = url
        # Añadir a la lista si no está
        if (title, url) not in self.all_channels:
            self.add_channel_to_list(title, url)
        self.youtube_handler.play_youtube_url(url, force_pulse=True, show_progress=True)

    def cargar_videos_playlist(self, canales):
        """Carga los vídeos de una playlist de YouTube como canales en el listado."""
        self.channels = canales
        self.all_channels = canales.copy()
        self.channels_listbox.delete(0, tk.END)
        for nombre, url in canales:
            self.channels_listbox.insert(tk.END, nombre)

    def download_channel(self, index):
        """Inicia la descarga del canal seleccionado en un hilo separado."""
        if 0 <= index < len(self.channels):
            name, url = self.channels[index]
            
            # Expresión regular simple para verificar extensiones de video comunes o URL de YouTube
            is_youtube = 'youtube.com' in url or 'youtu.be' in url
            is_direct_video = re.search(r'\.(mkv|mp4|avi|mov|flv|ogg|webm)$', url, re.IGNORECASE)

            if not is_youtube and not is_direct_video:
                messagebox.showinfo("Descarga no soportada", "La descarga solo está soportada para URLs de YouTube o enlaces directos a archivos de vídeo (mkv, mp4, etc.).")
                return

            # Pedir al usuario la ubicación de guardado
            # Sugerir nombre de archivo basado en el nombre del canal
            suggested_filename = re.sub(r'[\\/*?:"<>|]', "", name)  # Limpiar nombre de archivo
            filepath = filedialog.asksaveasfilename(
                title="Guardar vídeo",
                initialfile=suggested_filename,
                filetypes=[("Todos los archivos", "*.*")]
            )

            if not filepath:
                return 

            # Iniciar la descarga en un hilo para no bloquear la UI
            download_thread = threading.Thread(target=self._execute_download, args=(url, filepath, name))
            download_thread.start()
            messagebox.showinfo("Descarga iniciada", f"Iniciando descarga de '{name}'. Se te notificará cuando termine.")

    def _execute_download(self, url, filepath, name):
        """Ejecuta la descarga usando yt-dlp sin conversión a MP4."""
        try:
            # Opciones de yt-dlp simplificadas sin conversión
            ydl_opts = {
                'format': 'best',  # Descargar el mejor formato disponible
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

            # Mensaje de éxito en el hilo principal
            self.window.after(0, lambda: messagebox.showinfo("Descarga completada", f"'{name}' descargado en:\n{filepath}"))

        except Exception as e:
            # Capturar el mensaje de error
            error_message = str(e)
            # Usar el mensaje capturado en la lambda
            self.window.after(0, lambda msg=error_message: messagebox.showerror("Error de descarga", 
                f"No se pudo descargar '{name}':\n{msg}\n\nPosibles soluciones:\n"
                f"1. Verifica que el enlace sea accesible\n"
                f"2. Prueba con otro enlace de vídeo\n"
                f"3. Comprueba tu conexión a internet"))
            
            # Intentar eliminar archivo parcial si existe
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass # No hacer nada si no se puede borrar

    def open_youtube_search(self):
        """Abre la ventana de búsqueda de YouTube."""
        # Asegúrate de que load_playlist_callback se pasa correctamente
        search_dialog = YouTubeSearchDialog(self.window, self.play_youtube_url, self.load_playlist_callback)

    def load_playlist_callback(self, channels_list):
         """Callback para cargar vídeos de una playlist en la lista principal."""
         if channels_list:
             self.channels.clear()
             self.channels_listbox.delete(0, tk.END)
             self.all_channels = channels_list.copy() # Actualizar all_channels también
             for name, url in channels_list:
                 self.channels.append((name, url))
                 self.channels_listbox.insert(tk.END, name)
             messagebox.showinfo("Playlist cargada", f"Se cargaron {len(channels_list)} vídeos de la playlist.")

    def toggle_play(self):
        """Alterna entre reproducir y pausar el vídeo actual."""
        if self.player:
            if self.player.is_playing():
                self.player.pause()
            else:
                self.player.play()

    def stop(self):
        """Detiene la reproducción del vídeo actual y reinicia el estado del reproductor."""
        if self.player:
            try:
                if self.player.is_playing():
                    self.player.stop()
            except Exception:
                pass
        self.stop_update_time()

    def show_youtube_progress_bar(self):
        self.progress_frame.pack(fill=tk.X, padx=5, pady=2)
        self.progress_bar.set(0)
        self.progress_bar.state(['disabled'])

    def hide_progress_bar(self):
        self.progress_frame.pack_forget()
