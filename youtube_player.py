import yt_dlp
import re
import webbrowser
import os
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
 
class YouTubeHandler:
    def __init__(self, video_player):
        self.video_player = video_player
        
    def prompt_youtube_url(self, url=None):
        if url is None:
            url = simpledialog.askstring("Cargar YouTube", "Introduce la URL del video de YouTube:")
        if url:
            self.play_youtube_url(url)

    def play_youtube_url(self, url, force_pulse=False, show_progress=False, is_sequential=False):
        """Reproduce un vídeo de YouTube usando VLC si es posible. Permite forzar salida de audio pulse."""
        try:
            # Exportar cookies automáticamente antes de reproducir (ignorar error si falta browser_cookie3)
            try:
                self.export_cookies_from_browser()
            except Exception as e:
                print(f"[YouTubeHandler] No se pudieron exportar cookies: {e}")
            # Extraer el ID del vídeo de YouTube
            video_id = self.extract_youtube_id(url)
            if not video_id:
                messagebox.showerror("Error", "No se pudo extraer el ID del vídeo de YouTube")
                return
            # Limpiar el frame de video si hay contenido previo
            for widget in self.video_player.video_frame.winfo_children():
                widget.destroy()
            # Obtener la mejor URL compatible para VLC
            vlc_url = self.get_best_vlc_url(url)
            if vlc_url:
                print(f"[YouTubeHandler] Reproduciendo URL VLC: {vlc_url}")
                # Reproducir el vídeo en el reproductor VLC integrado
                self.video_player.play_video_url(vlc_url, force_pulse=force_pulse, show_progress=show_progress)
            else:
                # Mostrar error explícito además del frame negro y botón
                messagebox.showerror(
                    "Error de reproducción de YouTube",
                    "No se pudo reproducir el vídeo de YouTube en VLC.\n\nPuedes intentar abrirlo en el navegador."
                )
                # Si no se puede obtener la URL, mostrar mensaje y botón para abrir en navegador
                info_frame = tk.Frame(self.video_player.video_frame, bg="black")
                info_frame.pack(fill=tk.BOTH, expand=True)
                title_label = tk.Label(
                    info_frame,
                    text="No se pudo reproducir el vídeo en VLC",
                    font=("Arial", 16, "bold"),
                    bg="black",
                    fg="white"
                )
                title_label.pack(pady=(50, 10))
                open_button = tk.Button(
                    info_frame,
                    text="Abrir en navegador",
                    font=("Arial", 12),
                    command=lambda: self.open_in_browser(url),
                    padx=10,
                    pady=5
                )
                open_button.pack(pady=20)
        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar el vídeo: {str(e)}")
            self.open_in_browser(url)

    def extract_youtube_id(self, url):
        """Extrae el ID del video de YouTube de la URL"""
        if match := re.search(r'(?:v=|/v/|youtu\.be/)([^"&?/\s]{11})', url):
            return match.group(1)
        return None

    def load_playlist(self, playlist_url):
        """Carga todos los vídeos de una playlist de YouTube."""
        try:
            # Exportar cookies automáticamente antes de cargar la playlist
            self.export_cookies_from_browser()
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
                    return None
                channels = []
                for video in videos:
                    title = video.get('title', 'Sin título')
                    video_url = f"https://www.youtube.com/watch?v={video.get('id')}"
                    channels.append((title, video_url))
                return channels
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo obtener la playlist: {e}")
            return None
           
    def download_youtube_video(self, url=None):
        """Permite al usuario descargar un vídeo de YouTube."""
        if url is None:
            url = simpledialog.askstring("Descargar vídeo de YouTube", "Introduce la URL del video de YouTube:")
        
        if not url:
            return
            
        try:
            # Primero obtenemos información del vídeo para mostrar el título
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get('title', 'video')
                
            # Limpiamos el título para usarlo como nombre de archivo
            safe_title = re.sub(r'[\\/*?:"<>|]', "", video_title)
            
            # Pedimos al usuario dónde guardar el archivo
            filepath = filedialog.asksaveasfilename(
                title="Guardar vídeo",
                initialfile=safe_title,
                filetypes=[("Archivos MP4", "*.mp4"), ("Todos los archivos", "*.*")]
            )
            
            if not filepath:
                return  # Usuario canceló
                
            # Aseguramos que el archivo tenga extensión .mp4
            if not filepath.lower().endswith('.mp4'):
                filepath += '.mp4'
                
            # Iniciamos la descarga en un hilo separado
            download_thread = threading.Thread(
                target=self._execute_download, 
                args=(url, filepath, video_title)
            )
            download_thread.daemon = True  # El hilo terminará cuando el programa principal termine
            download_thread.start()
            
            messagebox.showinfo("Descarga iniciada", 
                               f"Iniciando descarga de '{video_title}'.\nSe te notificará cuando termine.")
                
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
            self.video_player.window.after(0, lambda: messagebox.showinfo(
                "Descarga completada", 
                f"'{title}' descargado en:\n{filepath}"
            ))
            
        except Exception as e:
            # Capturar el error y mostrarlo
            error_message = str(e)
            self.video_player.window.after(0, lambda msg=error_message: messagebox.showerror(
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


    def get_best_vlc_url(self, youtube_url):
        """Obtiene la mejor URL compatible con VLC para un video de YouTube, usando cookies si están disponibles."""
        import re
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': (
                'bestvideo[ext=mp4][vcodec^=avc1][height<=720][fps<=30][protocol^=http][container=mp4][format_id!*=dash][format_id!*=hls]'
                '+bestaudio[ext=m4a][protocol^=http][container=m4a][format_id!*=dash][format_id!*=hls]/'
                'best[ext=mp4][height<=720][fps<=30][protocol^=http][container=mp4][format_id!*=dash][format_id!*=hls]/'
                'best'
            ),
            'merge_output_format': 'mp4',
            'noplaylist': True,
            'skip_download': True,
        }
        cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                print("[yt-dlp] Formatos disponibles:")
                for f in info.get('formats', []):
                    print(f"  - id: {f.get('format_id')}, ext: {f.get('ext')}, vcodec: {f.get('vcodec')}, acodec: {f.get('acodec')}, protocol: {f.get('protocol')}, container: {f.get('container')}, format_note: {f.get('format_note')}, url: {f.get('url')}")
                # 1. Filtro estricto
                def is_vlc_compatible_strict(f):
                    if not f.get('url'):
                        return False
                    if f.get('ext') != 'mp4':
                        return False
                    if not f.get('vcodec', '').startswith('avc1'):
                        return False
                    if f.get('height', 0) > 720:
                        return False
                    if f.get('fps', 30) > 30:
                        return False
                    if not f.get('protocol', '').startswith('http'):
                        return False
                    if 'dash' in (f.get('format_id') or '').lower():
                        return False
                    if 'hls' in (f.get('format_id') or '').lower():
                        return False
                    if f.get('fragment_base_url') or f.get('fragments'):
                        return False
                    if re.search(r'(\.m3u8|\.mpd|\.ism|\.f4m|\.ts)(\?|$)', f.get('url')):
                        return False
                    if f.get('acodec', 'none') in ('none', ''):
                        return False
                    if f.get('vcodec', 'none') in ('none', ''):
                        return False
                    if f.get('format_note', '').lower() in ('audio only', 'video only'):
                        return False
                    if f.get('container', '') != 'mp4':
                        return False
                    if f.get('acodec', '') not in ('aac', 'mp4a'):
                        return False
                    if f.get('ext', '') == 'webm':
                        return False
                    return True
                compatibles = [f for f in info.get('formats', []) if is_vlc_compatible_strict(f)]
                if compatibles:
                    best = max(compatibles, key=lambda f: f.get('height', 0))
                    print(f"[yt-dlp] URL compatible seleccionada (estricto): {best['url']}")
                    return best['url']
                print("[yt-dlp] No se encontró stream compatible estricto. Probando filtro relajado...")
                # 2. Filtro relajado: permitir cualquier mp4/avc1 <=720p con audio+video juntos
                def is_vlc_compatible_relaxed(f):
                    if not f.get('url'):
                        return False
                    if f.get('ext') != 'mp4':
                        return False
                    if not f.get('vcodec', '').startswith('avc1'):
                        return False
                    if f.get('height', 0) > 720:
                        return False
                    if f.get('fps', 30) > 30:
                        return False
                    if not f.get('protocol', '').startswith('http'):
                        return False
                    if 'dash' in (f.get('format_id') or '').lower():
                        return False
                    if 'hls' in (f.get('format_id') or '').lower():
                        return False
                    if f.get('fragment_base_url') or f.get('fragments'):
                        return False
                    if re.search(r'(\.m3u8|\.mpd|\.ism|\.f4m|\.ts)(\?|$)', f.get('url')):
                        return False
                    if f.get('acodec', 'none') in ('none', ''):
                        return False
                    if f.get('vcodec', 'none') in ('none', ''):
                        return False
                    if f.get('format_note', '').lower() in ('audio only', 'video only'):
                        return False
                    if f.get('ext', '') == 'webm':
                        return False
                    return True
                compatibles_relaxed = [f for f in info.get('formats', []) if is_vlc_compatible_relaxed(f)]
                if compatibles_relaxed:
                    best = max(compatibles_relaxed, key=lambda f: f.get('height', 0))
                    print(f"[yt-dlp] URL compatible seleccionada (relajado): {best['url']}")
                    print("[ADVERTENCIA] Se usó un stream menos estricto. Puede haber problemas de audio/video.")
                    return best['url']
                print("[yt-dlp] No se encontró stream compatible ni siquiera en modo relajado.")
        except Exception as e:
            print(f"Error al obtener la URL compatible para VLC: {e}")
        return None

    def open_in_browser(self, url):
        """Abre una URL de YouTube en el navegador predeterminado."""
        try:
            webbrowser.open_new(url)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el navegador: {e}")

    def export_cookies_from_browser(self, output_path=None):
        """Exporta automáticamente las cookies de YouTube desde el navegador predeterminado usando browser-cookie3."""
        try:
            import browser_cookie3
            if output_path is None:
                output_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
            # Intenta obtener cookies de los navegadores más comunes
            cookies = None
            try:
                cookies = browser_cookie3.load(domain_name='youtube.com')
            except Exception:
                pass
            if not cookies:
                # Prueba navegadores específicos
                for loader in [browser_cookie3.chrome, browser_cookie3.firefox, browser_cookie3.edge, browser_cookie3.opera]:
                    try:
                        cookies = loader(domain_name='youtube.com')
                        if cookies:
                            break
                    except Exception:
                        continue
            if not cookies:
                raise Exception("No se pudieron extraer cookies de ningún navegador compatible. Asegúrate de tener sesión iniciada en YouTube.")
            # Escribir cookies en formato Netscape
            from http.cookiejar import MozillaCookieJar
            cj = MozillaCookieJar(output_path)
            # Añadir cookies extraídas
            for c in cookies:
                cj.set_cookie(c)
            cj.save(ignore_discard=True, ignore_expires=True)
            return output_path
        except ImportError:
            messagebox.showerror("Error", "Falta el módulo browser-cookie3. Instálalo con: pip install browser-cookie3")
            return None
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron exportar las cookies del navegador: {e}")
            return None