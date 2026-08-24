import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import yt_dlp
import requests
import webbrowser
import threading
import os
import re
import subprocess
from datetime import datetime, timedelta
from urllib.parse import quote, quote_plus
from youtube_player import youtube_ydl_opts
from ui_theme import style_window, style_listbox, style_menu_tree, set_window_icon, center_window


def _hashtag_slug(query):
    text = (query or '').strip().lstrip('#')
    return re.sub(r'[^\w]+', '', text, flags=re.UNICODE)


def _is_youtube_short(entry):
    if not entry:
        return False
    for key in ('url', 'original_url', 'webpage_url'):
        if '/shorts/' in str(entry.get(key) or ''):
            return True
    return False


def _fill_short_titles(entries):
    missing = [entry for entry in entries if not (entry.get('title') or '').strip()]
    if not missing:
        return

    def fetch(entry):
        video_id = entry.get('id')
        try:
            response = requests.get(
                'https://www.youtube.com/oembed',
                params={'url': f'https://www.youtube.com/watch?v={video_id}', 'format': 'json'},
                timeout=6,
            )
            if response.ok:
                entry['title'] = (response.json().get('title') or '').strip() or video_id
                return
        except Exception:
            pass
        entry['title'] = video_id

    workers = [threading.Thread(target=fetch, args=(entry,), daemon=True) for entry in missing]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=8)


def _search_youtube_shorts(query, max_results, extra_query=''):
    """Busca Shorts reales: pestaña /hashtag/.../shorts y filtro de búsqueda."""
    seen = set()
    found = []
    fetch_limit = max(max_results + 10, 20)
    sources = []
    slugs = []
    full_slug = _hashtag_slug(query)
    if full_slug:
        slugs.append(full_slug)
    for word in re.findall(r'\w+', (query or '').lstrip('#'), flags=re.UNICODE):
        word_slug = _hashtag_slug(word)
        if word_slug and word_slug not in slugs:
            slugs.append(word_slug)
    for slug in slugs:
        sources.append((f'https://www.youtube.com/hashtag/{quote(slug)}/shorts', True))
    search_text = (query + extra_query).strip()
    sources.append((
        f'https://www.youtube.com/results?search_query={quote_plus(search_text)}&sp=EgIQCQ%3D%3D',
        False,
    ))

    for url, from_shorts_tab in sources:
        if len(found) >= max_results:
            break
        ydl_opts = youtube_ydl_opts(
            extract_flat='in_playlist',
            skip_download=True,
            force_generic_extractor=False,
            noplaylist=False,
            playlistend=fetch_limit,
            use_cookiefile=False,
        )
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as err:
            print(f"[Shorts] No se pudo leer una fuente ({err})")
            continue
        for entry in info.get('entries') or []:
            if not entry or not entry.get('id'):
                continue
            if not from_shorts_tab and not _is_youtube_short(entry):
                continue
            video_id = entry['id']
            if video_id in seen:
                continue
            seen.add(video_id)
            found.append(entry)
            if len(found) >= max_results:
                break

    print(f"[Shorts] {len(found)}/{max_results} resultados")
    _fill_short_titles(found)
    return found


class YouTubeSearchDialog:
    def __init__(self, parent, play_callback, load_playlist_callback=None):
        self.parent = parent
        self.play_callback = play_callback
        self.load_playlist_callback = load_playlist_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Buscar en YouTube")
        self.window.geometry("780x560")
        self.window.minsize(640, 420)
        style_window(self.window)
        set_window_icon(self.window)
        center_window(self.window, 780, 560)
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.window, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text='Buscar en YouTube', style='PageTitle.TLabel').pack(anchor=tk.W)
        ttk.Label(
            main_frame,
            text='Vídeos, Shorts, listas de reproducción y canales',
            style='Muted.TLabel',
        ).pack(anchor=tk.W, pady=(0, 12))
        
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.bind('<Return>', lambda e: self.search())
        search_entry.focus_set()

        ttk.Button(search_frame, text="Buscar", style='Accent.TButton', command=self.search).pack(side=tk.LEFT, padx=(8, 0))

        # Frame de filtros
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Filtro por tipo de contenido
        ttk.Label(filter_frame, text="Tipo:").pack(side=tk.LEFT, padx=(0, 2))
        self.type_var = tk.StringVar(value="Vídeos")
        type_combobox = ttk.Combobox(
            filter_frame, textvariable=self.type_var,
            values=["Vídeos", "Shorts", "Listas de reproducción", "Canales"],
            width=15, state="readonly"
        )
        type_combobox.pack(side=tk.LEFT, padx=(0, 10))
        type_combobox.bind('<<ComboboxSelected>>', self._on_type_change)
        
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
        self.duration_combobox = ttk.Combobox(
            filter_frame, textvariable=self.duration_var,
            values=["Cualquier duración", "Corto (<4 min)", "Medio (4-20 min)", "Largo (>20 min)"],
            width=15, state="readonly"
        )
        self.duration_combobox.pack(side=tk.LEFT, padx=(0, 10))
        
        # Filtro por orden
        ttk.Label(filter_frame, text="Ordenar por:").pack(side=tk.LEFT, padx=(0, 2))
        self.sort_var = tk.StringVar(value="Relevancia")
        sort_combobox = ttk.Combobox(
            filter_frame, textvariable=self.sort_var,
            values=["Relevancia", "Fecha", "Vistas", "Valoración"],
            width=15, state="readonly"
        )
        sort_combobox.pack(side=tk.LEFT)

        # Frame para la lista de resultados
        results_frame = ttk.Frame(main_frame)
        results_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(results_frame, text="Número de resultados:").pack(side=tk.LEFT, padx=(0, 2))
        self.results_count = tk.IntVar(value=10)
        results_spinbox = ttk.Spinbox(
            results_frame, from_=1, to=100, textvariable=self.results_count, width=4
        )
        results_spinbox.pack(side=tk.LEFT)
        
        # Frame para la lista de resultados y barra de desplazamiento
        results_list_frame = ttk.Frame(main_frame)
        results_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(results_list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.results_listbox = tk.Listbox(results_list_frame, yscrollcommand=scrollbar.set)
        self.results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        style_listbox(self.results_listbox)
        scrollbar.config(command=self.results_listbox.yview)
        
        # Configurar el menú contextual
        self.results_listbox.bind('<Double-Button-1>', self.play_selected)
        self.results_listbox.bind('<Button-3>', self.show_context_menu)

        # Barra de progreso
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_frame.pack(fill=tk.X, pady=(5, 10))
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='indeterminate')
        
        # Frame de botones
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        play_btn = ttk.Button(button_frame, text="Reproducir", style='Accent.TButton', command=self.play_selected)
        play_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        download_video_btn = ttk.Button(button_frame, text="Descargar Vídeo+Audio", 
                                      command=lambda: self.download_selected(False))
        download_video_btn.pack(side=tk.LEFT, padx=5)
        
        download_audio_btn = ttk.Button(button_frame, text="Descargar SOLO Audio", 
                                      command=lambda: self.download_selected(True))
        download_audio_btn.pack(side=tk.LEFT, padx=5)
        
        close_btn = ttk.Button(button_frame, text="Cerrar", command=self.window.destroy)
        close_btn.pack(side=tk.RIGHT)
        
        self.results = []
        self.result_types = []
        self.result_details = []

    def _on_type_change(self, event=None):
        shorts = self.type_var.get() == "Shorts"
        self.duration_combobox.configure(state='disabled' if shorts else 'readonly')
        if shorts:
            self.duration_var.set("Cualquier duración")

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

    def check_ffmpeg(self):
        """Verifica si FFmpeg está instalado en el sistema."""
        try:
            result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def search(self):
        query = self.search_var.get().strip()
        if not query:
            messagebox.showinfo("Info", "Introduce un término de búsqueda.")
            return
        
        self.results_listbox.delete(0, tk.END)
        self.results = []
        self.result_types = []
        self.result_details = []
        
        self.progress_bar.pack(fill=tk.X, expand=True)
        self.progress_bar.start(10)
        
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
        
        # Aplicar filtros según el tipo
        tipo = self.type_var.get()
        if tipo == "Vídeos":
            search_query += date_query + duration_query
        elif tipo == "Shorts":
            search_query += date_query
        elif tipo == "Listas de reproducción":
            search_query += " playlist" + date_query

        def perform_search():
            try:
                try:
                    max_results = int(self.results_count.get())
                except (tk.TclError, TypeError, ValueError):
                    max_results = 10
                max_results = min(max(max_results, 1), 100)
                if tipo == "Shorts":
                    shorts = _search_youtube_shorts(query, max_results, extra_query=date_query)

                    def update_shorts_ui():
                        if not shorts:
                            messagebox.showinfo("Info", "No se encontraron Shorts con esa búsqueda.")
                            self.progress_bar.stop()
                            self.progress_bar.pack_forget()
                            return
                        for entry in shorts:
                            title = (entry.get('title') or '').strip() or entry.get('id')
                            duration = entry.get('duration')
                            duration_str = self.format_duration(duration) if duration else ""
                            self.result_types.append("video")
                            self.results.append(f"https://www.youtube.com/shorts/{entry.get('id')}")
                            self.result_details.append({
                                'title': title,
                                'id': entry.get('id'),
                                'duration': duration,
                            })
                            display_text = f"[Short] {title}"
                            if duration_str:
                                display_text += f" [{duration_str}]"
                            self.results_listbox.insert(tk.END, display_text)
                        self.progress_bar.stop()
                        self.progress_bar.pack_forget()

                    self.window.after(0, update_shorts_ui)
                    return

                ydl_opts = youtube_ydl_opts(
                    extract_flat=True,
                    skip_download=True,
                    force_generic_extractor=False,
                    noplaylist=False,
                    playlistend=max_results + 5,
                )

                query_q = quote_plus(search_query)
                if tipo == "Listas de reproducción":
                    sp = "EgIQAw%3D%3D"
                elif tipo == "Canales":
                    sp = "EgIQAg%3D%3D"
                else:
                    sp = "EgIQAQ%3D%3D"
                search_url = (
                    f"https://www.youtube.com/results?search_query={query_q}"
                    f"&hl=es&gl=ES&sp={sp}"
                )

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(search_url, download=False)
                    results_count = 0
                    found_playlist = False
                    
                    def update_ui():
                        nonlocal results_count, found_playlist
                        for entry in info.get('entries') or []:
                            if not entry or results_count >= max_results:
                                break
                                
                            title = entry.get('title', 'Sin título')
                            duration = entry.get('duration')
                            duration_str = self.format_duration(duration) if duration else ""
                            
                            if tipo == "Listas de reproducción":
                                playlist_id = None
                                if entry.get('url') and 'list=' in entry.get('url'):
                                    playlist_id = re.search(r'list=([^&]+)', entry.get('url'))
                                    if playlist_id:
                                        playlist_id = playlist_id.group(1)
                                        playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
                                        self.result_types.append("playlist")
                                        self.results.append(playlist_url)
                                        self.result_details.append({
                                            'title': title,
                                            'id': playlist_id,
                                            'duration': duration
                                        })
                                        self.results_listbox.insert(tk.END, f"[Lista] {title}")
                                        found_playlist = True
                                        results_count += 1
                            elif tipo == "Vídeos":
                                if entry.get('id'):
                                    url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                                    self.result_types.append("video")
                                    self.results.append(url)
                                    self.result_details.append({
                                        'title': title,
                                        'id': entry.get('id'),
                                        'duration': duration
                                    })
                                    display_text = f"[Vídeo] {title}"
                                    if duration_str:
                                        display_text += f" [{duration_str}]"
                                    self.results_listbox.insert(tk.END, display_text)
                                    results_count += 1
                            
                            elif tipo == "Canales":
                                channel_id = entry.get('channel_id') or entry.get('uploader_id') or entry.get('id')
                                if channel_id:
                                    url = f"https://www.youtube.com/channel/{channel_id}"
                                    self.result_types.append("channel")
                                    self.results.append(url)
                                    self.result_details.append({
                                        'title': title,
                                        'id': channel_id
                                    })
                                    self.results_listbox.insert(tk.END, f"[Canal] {title}")
                                    results_count += 1
                        
                        if tipo == "Listas de reproducción" and not found_playlist:
                            messagebox.showinfo("Info", "No se encontraron listas de reproducción con ese nombre.")

                        self.progress_bar.stop()
                        self.progress_bar.pack_forget()
                    
                    self.window.after(0, update_ui)
                    
            except Exception as e:
                def show_error():
                    messagebox.showerror("Error", f"No se pudo realizar la búsqueda: {e}")
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
                
                self.window.after(0, show_error)

        threading.Thread(target=perform_search, daemon=True).start()

    def show_context_menu(self, event):
        """Muestra el menú contextual al hacer clic derecho en un elemento"""
        selection = self.results_listbox.nearest(event.y)
        if 0 <= selection < len(self.results):
            self.results_listbox.selection_clear(0, tk.END)
            self.results_listbox.selection_set(selection)
            self.results_listbox.activate(selection)
            
            context_menu = tk.Menu(self.window, tearoff=0)
            style_menu_tree(context_menu)
            tipo = self.result_types[selection]
            
            if tipo == "video":
                context_menu.add_command(label="Reproducir", command=self.play_selected)
                context_menu.add_command(label="Descargar vídeo", command=lambda: self.download_selected(False))
                context_menu.add_command(label="Descargar audio", command=lambda: self.download_selected(True))
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
                label = self.results_listbox.get(index)
                self.play_callback(url, title=label)
                self.window.destroy()
            elif tipo == "playlist":
                self.load_playlist_videos(url)
                self.window.destroy()
            elif tipo == "channel":
                webbrowser.open_new(url)
                self.window.destroy()

    def download_selected(self, audio_only=False):
        """Descarga el vídeo seleccionado o solo su audio"""
        if audio_only and not self.check_ffmpeg():
            messagebox.showerror("Error", "FFmpeg no está instalado. Para descargar audio necesitas instalar FFmpeg:\n\nEn Ubuntu/Debian: sudo apt install ffmpeg\nEn Fedora: sudo dnf install ffmpeg")
            return

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
        
        try:
            title = self.result_details[index]['title']
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            
            file_types = [("Archivos MP3", "*.mp3")] if audio_only else [("Archivos MP4", "*.mp4")]
            default_ext = ".mp3" if audio_only else ".mp4"
            
            filepath = filedialog.asksaveasfilename(
                title="Guardar " + ("audio" if audio_only else "vídeo"),
                initialfile=safe_title + default_ext,
                defaultextension=default_ext,
                filetypes=file_types + [("Todos los archivos", "*.*")]
            )
            
            if not filepath:
                return
                
            download_thread = threading.Thread(
                target=self._execute_download, 
                args=(url, filepath, title, audio_only)
            )
            download_thread.start()
            
            tipo_descarga = "audio" if audio_only else "vídeo"
            messagebox.showinfo("Descarga iniciada", 
                              f"Iniciando descarga del {tipo_descarga} de '{title}'. Se te notificará cuando termine.")
                
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar la descarga: {str(e)}")

    def _execute_download(self, url, filepath, title, audio_only=False):
        """Ejecuta la descarga del vídeo de YouTube."""
        try:
            ydl_opts = youtube_ydl_opts(
                format='bestaudio/best' if audio_only else 'best',
                outtmpl=filepath,
                quiet=False,
                noprogress=False,
            )
            
            if audio_only:
                ydl_opts.update({
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            self.window.after(0, lambda: messagebox.showinfo(
                "Descarga completada", 
                f"'{title}' descargado en:\n{filepath}"
            ))
            
        except Exception as e:
            error_message = str(e)
            self.window.after(0, lambda msg=error_message: messagebox.showerror(
                "Error de descarga", 
                f"No se pudo descargar '{title}':\n{msg}\n\nPosibles soluciones:\n"
                f"1. Verifica que el enlace sea accesible\n"
                f"2. Prueba con otro vídeo\n"
                f"3. Comprueba tu conexión a internet"
            ))
            
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass

    def load_playlist_videos(self, playlist_url):
        try:
            ydl_opts = youtube_ydl_opts(
                extract_flat=True,
                skip_download=True,
                force_generic_extractor=False,
                noplaylist=False,
            )
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                videos = info.get('entries', [])
                if not videos:
                    messagebox.showinfo("Info", "No se encontraron vídeos en la playlist.")
                    return
                channels = []
                for video in videos:
                    title = video.get('title', 'Sin título')
                    video_url = f"https://www.youtube.com/watch?v={video.get('id')}"
                    channels.append((title, video_url))
                if self.load_playlist_callback:
                    self.load_playlist_callback(channels)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo obtener la playlist: {e}")


