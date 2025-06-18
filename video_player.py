import os
import psutil
from favorites_manager import FavoritesManager
import vlc
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import sys
import requests
import re
import threading
import yt_dlp
import traceback
from youtube_player import YouTubeHandler
from youtube_search import YouTubeSearchDialog

# Clase Tooltip para mostrar información al pasar el ratón
class Tooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text, x=None, y=None):
        """Muestra el tooltip con el texto dado, cerca del puntero del ratón"""
        if self.tipwindow or not text:
            return
        # Si no se pasan coordenadas, usar la posición actual del puntero
        if x is None or y is None:
            x = self.widget.winfo_pointerx() + 20
            y = self.widget.winfo_pointery() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "9", "normal"))
        label.pack(ipadx=4)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

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
        self.empty_menu = None  # Menú vacío para ocultar en fullscreen
        self.volume = 50
        self.favorites = []
        self.all_channels = []
        self.is_seeking = False 
        self.update_time_job = None  # Inicializar para evitar errores al cerrar

        # Inicializar el manejador de YouTube
        self.youtube_handler = YouTubeHandler(self)

        # Inicializar el manejador de favoritos
        self.favorites_manager = FavoritesManager(self)

        self.create_window()
        self.load_favorites()
        self.setup_mouse_tracking()
        self.setup_keyboard_shortcuts()

        # Nuevas variables para reproducción secuencial
        self.is_sequential_playback = False
        self.current_playlist_index = None

    def create_window(self):
        self.window = tk.Toplevel()
        self.window.title('Reproductor Vídeos')
        self.window.geometry('1100x750')

        self.create_menu()

        # Frame principal
        self.main_frame = ttk.Frame(self.window)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame de canales con ancho inicial
        self.channels_frame = ttk.Frame(self.main_frame, width=300)  # Ancho inicial de 300 píxeles
        self.channels_frame.pack_propagate(False)  # Evita que el frame se ajuste automáticamente
        self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Estilo para el sizer
        style = ttk.Style()
        style.configure('Sizer.TFrame', background='gray75')
        
        # Frame separador (sizer)
        self.sizer = ttk.Frame(self.main_frame, width=5, cursor='sb_h_double_arrow', style='Sizer.TFrame')
        self.sizer.pack(side=tk.LEFT, fill=tk.Y)

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

        # Tooltip para los elementos de la lista (solo al seleccionar)
        self.listbox_tooltip = Tooltip(self.channels_listbox)
        self.channels_listbox.bind('<<ListboxSelect>>', self.on_listbox_select)
        self.channels_listbox.bind('<FocusOut>', lambda e: self.listbox_tooltip.hidetip())
        # Ya no se usa el tooltip con el ratón

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
        
        # NO agregar eventos de movimiento de mouse que reinician constantemente el timer
        # Solo usar eventos de clic intencionales

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
            # SOLUCIÓN TIMEOUT: Solo eventos de clic intencionales, no <Enter> ni <Motion>
            # que causaban reinicio constante del timer de 3 segundos
            btn.bind('<Button-1>', self.on_control_interact)
        self.add_volume_control()
        #self.setup_performance_monitoring()
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
        # Atajos generales
        self.window.bind('<space>', lambda e: self.toggle_play())
        self.window.bind('<F1>', lambda e: self.toggle_fullscreen())
        self.window.bind('<m>', lambda e: self.toggle_mute())
        self.window.bind('<Left>', lambda e: self.seek_relative(-2))
        self.window.bind('<Right>', lambda e: self.seek_relative(2))
        
        # Atajos para favoritos
        self.window.bind('<Control-s>', self.handle_add_favorite)
        self.window.bind('<Control-d>', self.handle_remove_favorite)
        
        # Asegurarse de que el listbox también recibe los eventos
        self.channels_listbox.bind('<Control-s>', self.handle_add_favorite)
        self.channels_listbox.bind('<Control-d>', self.handle_remove_favorite)

    def setup_mouse_tracking(self):
        # Eliminar eventos de hover para mostrar/ocultar controles
        # self.video_frame.bind('<Enter>', self.on_mouse_enter)
        # self.video_frame.bind('<Leave>', self.on_mouse_leave)
        # self.controls_frame.bind('<Enter>', self.on_mouse_enter)
        # self.controls_frame.bind('<Leave>', self.on_mouse_leave)

        # Nuevo: mostrar controles solo al hacer clic en pantalla completa
        def on_video_click(event=None):
            if self.is_fullscreen:
                self.show_controls_and_menu()
        self.video_frame.bind('<Button-1>', on_video_click)

        # Eventos para el sizer
        self.sizer = ttk.Frame(self.main_frame, width=5, cursor='sb_h_double_arrow')
        self.sizer.pack(side=tk.LEFT, fill=tk.Y)
        self.sizer.bind('<Button-1>', self.start_resize)
        self.sizer.bind('<B1-Motion>', self.do_resize)
        self.sizer.bind('<ButtonRelease-1>', self.stop_resize)
        self.resize_active = False
        self.last_x = 0

    # Eliminar la lógica de hover de controles
    def on_mouse_enter(self, event=None):
        pass  # Ya no se usa para mostrar controles

    def on_mouse_leave(self, event=None):
        pass  # Ya no se usa para ocultar controles

    def hide_controls_and_menu(self):
        """Oculta controles y menú superior juntos (solo en fullscreen el menú)."""
        if self.controls_visible:
            self.controls_frame.pack_forget()
            self.controls_visible = False
        # Ocultar menú superior solo si estamos en fullscreen
        if self.is_fullscreen:
            self.window.config(menu="")
        # Cancelar temporizador si existe
        if self.hide_controls_timer:
            self.window.after_cancel(self.hide_controls_timer)
            self.hide_controls_timer = None

    def show_controls_and_menu(self):
        """Muestra controles y menú superior juntos."""
        if not self.controls_visible:
            self.controls_frame.pack(fill=tk.X, pady=5)
            self.controls_visible = True
        
        # Mostrar menú solo si estamos en fullscreen
        if self.is_fullscreen:
            self.window.config(menu=self.menubar)
            # Siempre reiniciar el timeout cuando se muestran controles en fullscreen
            self.reset_hide_controls_timer()
        else:
            self.window.config(menu=self.menubar)
            # No activar timeout fuera de fullscreen

    def enter_fullscreen(self):
        self.window.attributes('-fullscreen', True)
        self.is_fullscreen = True
        self.window.config(menu="")  # Ocultar menú superior
        if self.channels_frame_visible:
            self.channels_frame.pack_forget()
            self.sizer.pack_forget()  # Ocultar también el sizer
        else:
            # Por si acaso el sizer quedó visible
            self.sizer.pack_forget()
        self.hide_controls_and_menu()  # Ocultar controles y menú al entrar en fullscreen

    def exit_fullscreen(self):
        self.window.attributes('-fullscreen', False)
        self.is_fullscreen = False
        self.window.config(menu=self.menubar)
        if self.channels_frame_visible:
            self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)
            self.sizer.pack(side=tk.LEFT, fill=tk.Y)
        if self.hide_controls_timer:
            self.window.after_cancel(self.hide_controls_timer)
            self.hide_controls_timer = None
        self.show_controls_and_menu()

    def reset_hide_controls_timer(self):
        """
        Reinicia el temporizador para ocultar controles y menú en pantalla completa.
        
        SOLUCIÓN AL TIMEOUT: Este método implementa el timeout de 3 segundos que
        oculta automáticamente el menú y controles en fullscreen. Solo se activa
        con interacciones intencionales (clics), no con movimientos de mouse.
        """
        if self.hide_controls_timer:
            self.window.after_cancel(self.hide_controls_timer)
            self.hide_controls_timer = None
        if self.is_fullscreen:
            self.hide_controls_timer = self.window.after(3000, self.hide_controls_and_menu)

    def on_control_interact(self, event=None):
        """
        Manejador para cualquier interacción con los controles en fullscreen.
        
        SOLUCIÓN AL TIMEOUT: Solo se activa con clics intencionales, no con
        movimientos de mouse, permitiendo que el timeout de 3 segundos funcione.
        """
        if self.is_fullscreen:
            self.reset_hide_controls_timer()

    # Frame de configuración de audio
    def add_volume_control(self):
        self.volume_scale = ttk.Scale(
            self.controls_frame, from_=0, to=100,
            orient='horizontal', command=self.set_volume
        )
        self.volume_scale.set(self.volume)
        self.volume_scale.pack(side=tk.LEFT, padx=5)
        
        # SOLUCIÓN TIMEOUT: Solo clics en control de volumen, no <Motion>
        # que causaba reinicio constante del timer
        self.volume_scale.bind('<Button-1>', self.on_control_interact)
        self.volume_scale.bind('<ButtonRelease-1>', self.on_control_interact)

    def set_volume(self, value):
        """Establece el volumen del reproductor"""
        try:
            if self.player:
                self.volume = int(float(value))
                self.player.audio_set_volume(self.volume)
            # Reiniciar timer si estamos en fullscreen
            if self.is_fullscreen:
                self.reset_hide_controls_timer()
        except Exception as e:
            print(f"Error al ajustar el volumen: {e}")

    def toggle_mute(self):
        self.player.audio_toggle_mute()

    def toggle_fullscreen(self, event=None):
        if not self.is_fullscreen:
            self.enter_fullscreen()
        else:
            self.exit_fullscreen()

    def close(self):
        """Cierra la ventana y libera recursos."""
        try:
            # Desactivar los manejadores de eventos
            if hasattr(self, 'video_frame') and self.video_frame:
                try:
                    self.video_frame.unbind('<Enter>')
                    self.video_frame.unbind('<Leave>')
                except tk.TclError:
                    pass
                    
            if hasattr(self, 'controls_frame') and self.controls_frame:
                try:
                    self.controls_frame.unbind('<Enter>')
                    self.controls_frame.unbind('<Leave>')
                except tk.TclError:
                    pass

            # Guardar datos y limpiar temporizadores
            self.save_favorites()
            self.stop_update_time()  # Detener temporizador de actualización

            # Liberar recursos de VLC
            self._cleanup_vlc_player()

            # Destruir la ventana y limpiar referencias
            if self.window:
                try:
                    self.window.destroy()
                except tk.TclError:
                    pass
                finally:
                    self.window = None
                    self.video_frame = None
                    self.controls_frame = None
                    self.channels_frame = None
                    self.sizer = None
                    
        except Exception as e:
            print(f"Error durante el cierre del reproductor: {e}")

    def _cleanup_vlc_player(self):
        """Limpia de forma segura el reproductor VLC y sus event managers."""
        try:
            # Limpiar event manager antes de liberar el reproductor
            if hasattr(self, '_current_event_manager') and self._current_event_manager:
                try:
                    self._current_event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                    self._current_event_manager = None
                except Exception as e:
                    print(f"Error al limpiar event manager: {e}")
            
            # Detener y liberar reproductor
            if self.player:
                try:
                    if self.player.is_playing():
                        self.player.stop()
                    # Esperar un poco para que VLC termine completamente
                    import time
                    time.sleep(0.1)
                    self.player.release()
                except Exception as e:
                    print(f"Error al liberar reproductor: {e}")
                finally:
                    self.player = None
        except Exception as e:
            print(f"Error en limpieza VLC: {e}")

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

    
    def restore_all_channels(self):
        self.channels = self.all_channels.copy()
        self.channels_listbox.delete(0, tk.END)
        for channel in self.channels:
            self.channels_listbox.insert(tk.END, channel[0])

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

    def load_m3u_file(self, filename):
        """Carga un archivo M3U local y procesa sus canales."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            self._process_m3u_content(content)
            messagebox.showinfo("Éxito", f"Lista M3U cargada correctamente: {len(self.channels)} canales encontrados")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el archivo M3U: {e}")

    def load_m3u_url(self, url):
        """Carga una lista M3U desde una URL y procesa sus canales."""
        try:
            import urllib.request
            with urllib.request.urlopen(url) as response:
                content = response.read().decode('utf-8')
            self._process_m3u_content(content)
            messagebox.showinfo("Éxito", f"Lista M3U cargada correctamente: {len(self.channels)} canales encontrados")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la URL M3U: {e}")

    def _process_m3u_content(self, content):
        """Procesa el contenido de un archivo M3U y carga los canales."""
        lines = content.strip().split('\n')
        self.channels.clear()
        self.all_channels.clear()
        self.channels_listbox.delete(0, tk.END)
        
        i = 0
        while i < len(lines):
            if lines[i].startswith('#EXTINF:'):
                if i + 1 < len(lines) and not lines[i + 1].startswith('#'):
                    # Extraer nombre del canal de la línea EXTINF
                    extinf_line = lines[i]
                    url_line = lines[i + 1].strip()
                    
                    # Extraer el nombre del canal
                    if ',' in extinf_line:
                        name = extinf_line.split(',', 1)[1].strip()
                    else:
                        name = url_line
                    
                    # Añadir canal a las listas
                    self.channels.append((name, url_line))
                    self.all_channels.append((name, url_line))
                    self.channels_listbox.insert(tk.END, name)
                    i += 2
                else:
                    i += 1
            else:
                i += 1

    def prompt_youtube_playlist(self):
        """Solicita URL de playlist de YouTube y la carga."""
        playlist_url = simpledialog.askstring("Cargar Playlist de YouTube", "Introduce la URL de la playlist de YouTube:")
        if playlist_url:
            self.load_youtube_playlist(playlist_url)

    def load_youtube_playlist(self, playlist_url):
        """Carga todos los vídeos de una playlist de YouTube y los muestra en la lista de canales."""
        try:
            import yt_dlp
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
                
                messagebox.showinfo("Éxito", f"Playlist cargada: {len(videos)} vídeos")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la playlist: {e}")

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
            # Limpiar reproductor anterior de forma segura
            self._cleanup_vlc_player()

            # Crear un nuevo reproductor
            self.player = self.instance.media_player_new()
            
            # Configurar el administrador de eventos si es una reproducción secuencial
            if self.is_sequential_playback:
                self.setup_event_manager()
                
            self.show_controls_and_menu()
            if "youtube.com" in url or "youtu.be" in url:
                # Pasar el flag de reproducción secuencial al youtube_handler
                self.youtube_handler.play_youtube_url(
                    url, 
                    force_pulse=True, 
                    show_progress=True,
                    is_sequential=self.is_sequential_playback
                )
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

    def play_video_url(self, url, force_pulse=False, show_progress=False, is_sequential=False):
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
            
            # Configurar event manager si es reproducción secuencial
            if is_sequential and not hasattr(self, '_current_event_manager'):
                self.setup_event_manager()
            
            media = self.instance.media_new(url)
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
        """Actualiza el tiempo de reproducción y la barra de progreso."""
        if self.player and self.player.is_playing():
            try:
                length = self.player.get_length()
                if length > 0:  # Asegurarse de que el video tiene duración
                    # Solo actualizar la barra si no se está arrastrando
                    if not self.is_seeking and self.progress_frame.winfo_ismapped():
                        time = self.player.get_time()
                        position = (time / length) * 100
                        self.progress_bar.set(position)
            except Exception as e:
                print(f"Error actualizando tiempo: {e}")
        self.update_time_job = self.window.after(1000, self.update_time)

    def adjust_video_settings(self):
        """Ajusta la configuración del video para optimizar la reproducción"""
        if self.player:
            # Cambiamos True por una cadena vacía "" para desactivar o "yadif" para activar
            self.player.video_set_deinterlace("") 
            self.player.audio_set_volume(self.volume)

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
        try:
            # Usar método de limpieza segura
            self._cleanup_vlc_player()
            # Ocultar la barra de progreso
            self.hide_progress_bar()
        except Exception as e:
            print(f"Error al detener la reproducción: {e}")
        
        self.stop_update_time()
        # Resetear el estado de reproducción secuencial
        self.is_sequential_playback = False
        self.current_playlist_index = None

    def show_youtube_progress_bar(self):
        """Muestra y configura la barra de progreso para videos de YouTube."""
        self.progress_frame.pack(fill=tk.X, padx=5, pady=2)
        self.progress_bar.set(0)
        # Habilitamos la barra y permitimos búsqueda
        self.progress_bar.state(['!disabled'])
        # Configura el comando para el seek
        self.progress_bar.configure(command=self.seek_to_position)
        # Bindings para el arrastre - solo eventos de clic, no movimiento
        self.progress_bar.bind('<Button-1>', self.start_seek)
        self.progress_bar.bind('<ButtonRelease-1>', self.end_seek)

    def hide_progress_bar(self):
        self.progress_frame.pack_forget()

    def on_listbox_motion(self, event):
        """Muestra un tooltip con el nombre del canal al pasar el ratón"""
        index = self.channels_listbox.nearest(event.y)
        if 0 <= index < len(self.channels):
            name = self.channels[index][0]
            # Usar coordenadas absolutas del puntero
            x = self.channels_listbox.winfo_pointerx() + 20
            y = self.channels_listbox.winfo_pointery() + 10
            self.listbox_tooltip.showtip(name, x, y)
        else:
            self.listbox_tooltip.hidetip()

    def on_listbox_select(self, event):
        """Muestra un tooltip con el nombre del canal seleccionado justo debajo del ítem seleccionado"""
        self.listbox_tooltip.hidetip()  # Oculta cualquier tooltip anterior
        selection = self.channels_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.channels):
                name = self.channels[index][0]
                bbox = self.channels_listbox.bbox(index)
                if bbox:
                    x, y, width, height = bbox
                    abs_x = self.channels_listbox.winfo_rootx() + x
                    abs_y = self.channels_listbox.winfo_rooty() + y + height
                    self.listbox_tooltip.showtip(name, abs_x, abs_y)
                else:
                    self.listbox_tooltip.showtip(name)
        else:
            self.listbox_tooltip.hidetip()

    def start_seek(self, event):
        """Inicia el proceso de seek manual."""
        self.is_seeking = True
        # Reiniciar el timer del menú si estamos en fullscreen
        if self.is_fullscreen:
            self.reset_hide_controls_timer()

    def end_seek(self, event):
        """Finaliza el proceso de seek manual."""
        self.is_seeking = False
        # Reiniciar el timer del menú si estamos en fullscreen
        if self.is_fullscreen:
            self.reset_hide_controls_timer()

    def seek_to_position(self, value):
        """Realiza el seek a una posición específica."""
        if not self.is_seeking or not self.player:
            return
        try:
            position = float(value) / 100.0
            length = self.player.get_length()
            if length > 0:
                target_time = int(position * length)
                self.player.set_time(target_time)
        except Exception as e:
            print(f"Error en seek: {e}")

    def handle_add_favorite(self, event=None):
        """Manejador para el atajo de teclado Ctrl+S"""
        self.add_to_favorites()
        return "break"  # Evita que el evento se propague

    def handle_remove_favorite(self, event=None):
        """Manejador para el atajo de teclado Ctrl+D"""
        self.remove_from_favorites()
        return "break"  # Evita que el evento se propague

    def play_from_here(self, start_index):
        """Reproduce todos los videos de la lista desde el índice especificado."""
        print(f"Iniciando reproducción secuencial desde índice {start_index}")
        
        # Detener cualquier reproducción actual y limpiar el estado
        self.stop()
        
        # Esperar un momento antes de iniciar la nueva reproducción
        def start_playback():
            print("Configurando reproducción secuencial")
            self.is_sequential_playback = True
            self.current_playlist_index = start_index
            self.select_and_play_channel(start_index)
            
        # Usar delay para asegurar que todo se detuvo correctamente
        self.window.after(500, start_playback)

    def select_and_play_channel(self, index):
        """Selecciona y reproduce un canal del listado."""
        try:
            print(f"\n=== Seleccionando y reproduciendo canal {index} ===")
            if 0 <= index < len(self.channels):
                # Detener cualquier reproducción actual
                if self.player:
                    if self.player.is_playing():
                        print("Deteniendo reproducción actual")
                        self.player.stop()
                    print("Liberando reproductor actual")
                    self.player.release()
                    self.player = None
                
                # Actualizar selección visual
                print("Actualizando selección visual")
                self.channels_listbox.selection_clear(0, tk.END)
                self.channels_listbox.selection_set(index)
                self.channels_listbox.activate(index)
                self.channels_listbox.see(index)
                
                # Crear nuevo reproductor y reproducir
                print("Iniciando reproducción")
                self.play_channel(index)
            else:
                print(f"Índice {index} fuera de rango (max: {len(self.channels)-1})")
        except Exception as e:
            print(f"Error en select_and_play_channel: {e}")
            import traceback
            print(traceback.format_exc())

    def _safe_on_media_end(self, event):
        """Cuando termina un vídeo, reproduce el siguiente si estamos en modo secuencial."""
        try:
            print("\n=== MediaPlayerEndReached ===")
            print(f"Estado actual: {self.player.get_state() if self.player else 'No hay reproductor'}")
            print(f"Reproducción secuencial: {self.is_sequential_playback}")
            print(f"Índice actual: {self.current_playlist_index}")
            
            if not self.player:
                print("No hay reproductor activo")
                return
                
            if not self.is_sequential_playback:
                print("Reproducción secuencial desactivada")
                return
                
            if self.current_playlist_index is None:
                print("Índice actual es None")
                return
                
            # Obtener el índice actual y el siguiente
            current_index = self.current_playlist_index
            next_index = current_index + 1
            
            print(f"\nProcesando transición de vídeo {current_index} -> {next_index}")
            
            # Verificar si hay más videos por reproducir
            if next_index < len(self.channels):
                print(f"Preparando reproducción del vídeo {next_index}")
                
                def play_next():
                    try:
                        print("\n=== Iniciando reproducción del siguiente vídeo ===")
                        # Detener reproducción actual
                        if self.player and self.player.is_playing():
                            self.player.stop()
                            print("Reproducción anterior detenida")
                            
                        # Limpiar event manager
                        if hasattr(self, '_current_event_manager') and self._current_event_manager:
                            try:
                                self._current_event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                                self._current_event_manager = None
                                print("Event manager limpiado")
                            except Exception as e:
                                print(f"Error al limpiar event manager: {e}")
                        
                        # Actualizar índice
                        self.current_playlist_index = next_index
                        print(f"Índice actualizado a {next_index}")
                        
                        # Reproducir siguiente vídeo
                        self.select_and_play_channel(next_index)
                        print("Reproducción iniciada")
                    except Exception as e:
                        print(f"Error al reproducir siguiente vídeo: {e}")
                
                # Usar delay más largo para asegurar que el vídeo anterior se ha detenido
                self.window.after(500, play_next)
                print("Reproducción programada con delay de 500ms")
            else:
                print("\nFin de la playlist alcanzado")
                self.is_sequential_playback = False
                self.current_playlist_index = None
                self._current_event_manager = None
                
        except Exception as e:
            print(f"Error en _safe_on_media_end: {e}")
            import traceback
            print(traceback.format_exc())

    def setup_event_manager(self):
        """Configura el event manager de VLC para manejar el fin de reproducción."""
        if not self.player:
            print("No hay reproductor disponible para configurar eventos")
            return

        print("Configurando event manager")

        # Limpiar cualquier event manager existente
        if hasattr(self, '_current_event_manager') and self._current_event_manager:
            try:
                self._current_event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                self._current_event_manager = None
                print("Event manager anterior limpiado")
            except Exception as e:
                print(f"Error al limpiar event manager anterior: {e}")

        try:
            # Verificar que el reproductor sigue válido
            if not self.player:
                print("No hay reproductor válido para configurar eventos")
                return
                
            # Crear un nuevo event manager
            event_manager = self.player.event_manager()
            
            # Configurar el callback para el fin de reproducción
            event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._safe_on_media_end)
            
            # Guardar la referencia al event manager actual
            self._current_event_manager = event_manager
            
            print(f"Event manager configurado exitosamente para índice {self.current_playlist_index}")

        except Exception as e:
            print(f"Error al configurar event manager: {e}")
            self.is_sequential_playback = False
            self.current_playlist_index = None
            self._current_event_manager = None

    def remove_channel(self, index):
        """Elimina un canal específico de la lista."""
        try:
            if 0 <= index < len(self.channels):
                del self.channels[index]
                del self.all_channels[index]
                self.channels_listbox.delete(index)
        except Exception as e:
            print(f"Error al eliminar canal: {e}")

    def clear_channel_list(self):
        """Limpia toda la lista de canales."""
        try:
            self.channels.clear()
            self.all_channels.clear()
            self.channels_listbox.delete(0, tk.END)
        except Exception as e:
            print(f"Error al limpiar la lista: {e}")

    def add_to_favorites(self):
        """Añade el canal seleccionado a favoritos"""
        selection = self.channels_listbox.curselection()
        if not selection:
            messagebox.showinfo("Información", "Por favor, selecciona un canal primero")
            return
        selected_index = selection[0]
        channel = self.channels[selected_index]
        if channel not in self.favorites:
            self.favorites.append(channel)
            self.save_favorites()
            messagebox.showinfo("Éxito", f"Canal '{channel[0]}' añadido a favoritos")
        else:
            messagebox.showinfo("Información", f"El canal '{channel[0]}' ya está en favoritos")

    def remove_from_favorites(self):
        """Elimina el canal seleccionado de favoritos"""
        selection = self.channels_listbox.curselection()
        if not selection:
            messagebox.showinfo("Información", "Por favor, selecciona un canal primero")
            return
        selected_index = selection[0]
        channel = self.channels[selected_index]
        if channel in self.favorites:
            self.favorites.remove(channel)
            self.save_favorites()
            messagebox.showinfo("Éxito", f"Canal '{channel[0]}' eliminado de favoritos")
        else:
            messagebox.showinfo("Información", f"El canal '{channel[0]}' no estaba en favoritos")

    def show_channel_context_menu(self, event):
        selection = self.channels_listbox.nearest(event.y)
        if selection < 0 or selection >= len(self.channels):
            return
        self.channels_listbox.selection_clear(0, tk.END)
        self.channels_listbox.selection_set(selection)
        self.channels_listbox.activate(selection)
        menu = tk.Menu(self.window, tearoff=0)
        menu.add_command(label="Reproducir desde aquí", command=lambda: self.play_from_here(selection))
        menu.add_separator()
        menu.add_command(label="Añadir a Favoritos", command=self.add_to_favorites)
        menu.add_command(label="Eliminar de Favoritos", command=self.remove_from_favorites)
        menu.add_separator()
        menu.add_command(label="Descargar", command=lambda: self.download_channel(selection))
        menu.add_command(label="Eliminar canal", command=lambda: self.remove_channel(selection))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def toggle_playlist(self):
        """Muestra u oculta la lista de canales y el sizer"""
        if self.channels_frame_visible:
            self.channels_frame.pack_forget()
            self.sizer.pack_forget()
        else:
            self.channels_frame.pack(side=tk.LEFT, fill=tk.Y)
            self.sizer.pack(side=tk.LEFT, fill=tk.Y)
        self.channels_frame_visible = not self.channels_frame_visible
        self.window.update_idletasks()

    def start_resize(self, event):
        self.resize_active = True
        self.last_x = event.x_root

    def do_resize(self, event):
        if not self.resize_active:
            return
        delta = event.x_root - self.last_x
        new_width = self.channels_frame.winfo_width() + delta
        # Limitar el ancho mínimo y máximo
        if 200 <= new_width <= 600:
            self.channels_frame.configure(width=new_width)
        self.last_x = event.x_root

    def stop_resize(self, event):
        self.resize_active = False

