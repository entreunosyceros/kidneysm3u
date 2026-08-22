import yt_dlp
import re
import webbrowser
import os
import shutil
import sys
import subprocess
import tempfile
import threading
import time
import atexit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog


YT_TEMP_PREFIX = 'kidneys_yt_'


def cleanup_youtube_temp_dirs(keep=None):
    """Borra las copias temporales de reproducción para que no se amontonen."""
    temp_root = tempfile.gettempdir()
    keep_path = os.path.abspath(keep) if keep else None
    try:
        for name in os.listdir(temp_root):
            if not name.startswith(YT_TEMP_PREFIX):
                continue
            path = os.path.join(temp_root, name)
            if keep_path and os.path.abspath(path) == keep_path:
                continue
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


atexit.register(cleanup_youtube_temp_dirs)


def detect_js_runtimes():
    """Runtimes JS que yt-dlp puede usar para los retos de YouTube."""
    runtimes = {}
    for name, binary in (
        ('deno', 'deno'),
        ('node', 'node'),
        ('bun', 'bun'),
        ('quickjs', 'qjs'),
    ):
        path = shutil.which(binary)
        if path:
            runtimes[name] = {'path': path}
    if 'quickjs' not in runtimes:
        path = shutil.which('quickjs')
        if path:
            runtimes['quickjs'] = {'path': path}
    return runtimes


def _merge_extractor_args(base, extra):
    merged = {}
    for source in (base, extra):
        if not source:
            continue
        for key, value in source.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def youtube_ydl_opts(**extra):
    """Opciones comunes de yt-dlp: runtime JS + cookies de navegador/archivo."""
    extra_extractor = extra.pop('extractor_args', None)
    opts = {
        'quiet': True,
        'no_warnings': False,
        'nocheckcertificate': True,
        'noplaylist': True,
        'geo_bypass_country': 'ES',
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) '
                'Gecko/20100101 Firefox/125.0'
            ),
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        },
        'remote_components': {'ejs:github'},
    }
    runtimes = detect_js_runtimes()
    if runtimes:
        opts['js_runtimes'] = runtimes
        print("[yt-dlp] Runtimes JS: " + ", ".join(f"{n}={info.get('path')}" for n, info in runtimes.items()))
    else:
        print("[yt-dlp] No se encontró Deno ni Node. YouTube puede bloquear la extracción.")

    cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
    browser = extra.pop('cookie_browser', None)
    use_cookiefile = extra.pop('use_cookiefile', True)
    if browser:
        opts['cookiesfrombrowser'] = (browser,)
    elif use_cookiefile and os.path.exists(cookies_path):
        opts['cookiefile'] = cookies_path

    opts.update(extra)
    opts['extractor_args'] = _merge_extractor_args(
        {'youtube': {'lang': ['es']}},
        extra_extractor,
    )
    return opts


def preferred_youtube_browser():
    """Elige un navegador que tenga cookies de YouTube, si es posible."""
    try:
        import browser_cookie3
    except ImportError:
        return 'firefox'
    loaders = (
        ('firefox', getattr(browser_cookie3, 'firefox', None)),
        ('chrome', getattr(browser_cookie3, 'chrome', None)),
        ('chromium', getattr(browser_cookie3, 'chromium', None)),
        ('brave', getattr(browser_cookie3, 'brave', None)),
        ('edge', getattr(browser_cookie3, 'edge', None)),
    )
    for name, loader in loaders:
        if not loader:
            continue
        try:
            cookies = loader(domain_name='youtube.com')
            if cookies and any(True for _ in cookies):
                return name
        except Exception:
            continue
    return 'firefox'
 
class _GrowingTSHandler(BaseHTTPRequestHandler):
    """Sirve un MPEG-TS que ffmpeg sigue escribiendo."""

    def log_message(self, format, *args):
        return

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-Type', 'video/MP2T')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()

    def do_GET(self):
        path = self.server.ts_path
        self.send_response(200)
        self.send_header('Content-Type', 'video/MP2T')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'close')
        self.end_headers()
        pos = 0
        idle = 0.0
        try:
            while idle < 45:
                try:
                    size = os.path.getsize(path) if os.path.exists(path) else 0
                except OSError:
                    size = 0
                if size > pos:
                    with open(path, 'rb') as fh:
                        fh.seek(pos)
                        data = fh.read(size - pos)
                    if data:
                        self.wfile.write(data)
                        pos += len(data)
                        idle = 0.0
                        continue
                procs = getattr(self.server, 'yt_procs', [])
                finished = procs and all(p.poll() is not None for p in procs)
                if finished and size <= pos:
                    break
                time.sleep(0.05)
                idle += 0.05
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


class YouTubeHandler:
    def __init__(self, video_player):
        self.video_player = video_player
        self._yt_procs = []
        self._yt_tmpdir = None
        self._yt_server = None
        cleanup_youtube_temp_dirs()

    def stop_pipeline(self):
        server = self._yt_server
        self._yt_server = None
        if server:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
        for proc in self._yt_procs:
            try:
                proc.terminate()
            except Exception:
                pass
        for proc in self._yt_procs:
            try:
                proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._yt_procs = []
        current = self._yt_tmpdir
        self._yt_tmpdir = None
        if current and os.path.isdir(current):
            shutil.rmtree(current, ignore_errors=True)
        cleanup_youtube_temp_dirs()
        
    def prompt_youtube_url(self, url=None):
        if url is None:
            url = simpledialog.askstring("Cargar YouTube", "Introduce la URL del video de YouTube:")
        if url:
            self.play_youtube_url(url)

    def play_youtube_url(self, url, force_pulse=False, show_progress=False, is_sequential=False):
        """Reproduce un vídeo de YouTube dentro del reproductor integrado."""
        try:
            try:
                self.export_cookies_from_browser(silent=True)
            except Exception as e:
                print(f"[YouTubeHandler] No se pudieron exportar cookies: {e}")

            video_id = self.extract_youtube_id(url)
            if not video_id:
                messagebox.showerror("Error", "No se pudo extraer el ID del vídeo de YouTube")
                return

            self._show_status("Obteniendo vídeo de YouTube…")
            self.stop_pipeline()
            stream = self.get_best_vlc_url(url)
            if stream and self._stream_ok_for_vlc(stream):
                print(f"[YouTubeHandler] Reproduciendo en el reproductor: {stream['url'][:80]}…")
                self._clear_video_surface()

                def fallback():
                    print("[YouTubeHandler] VLC no pudo abrir el stream directo; retransmitiendo con yt-dlp")
                    if not self._play_via_pipe(url, force_pulse, show_progress, is_sequential, duration=stream.get('duration')):
                        self._show_playback_error(url)

                self.video_player.play_video_url(
                    stream['url'],
                    force_pulse=force_pulse,
                    show_progress=show_progress,
                    is_sequential=is_sequential,
                    http_headers=stream.get('headers'),
                    duration_s=stream.get('duration'),
                    on_fail=fallback,
                )
                return

            if stream:
                print("[YouTubeHandler] El stream directo no es compatible con VLC; retransmitiendo con yt-dlp")
            duration = (stream or {}).get('duration')
            if self._play_via_pipe(url, force_pulse, show_progress, is_sequential, duration=duration):
                return

            self._show_playback_error(url)
        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar el vídeo: {str(e)}")
            self.open_in_browser(url)

    def _clear_video_surface(self):
        for widget in self.video_player.video_frame.winfo_children():
            widget.destroy()

    def _show_status(self, text):
        from ui_theme import get_colors, get_font
        self._clear_video_surface()
        colors = get_colors()
        info_frame = tk.Frame(self.video_player.video_frame, bg=colors['bg'])
        info_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            info_frame,
            text=text,
            font=get_font(12),
            bg=colors['bg'],
            fg=colors['text'],
        ).pack(expand=True)
        self.video_player.window.update_idletasks()

    def _show_playback_error(self, url):
        from ui_theme import get_colors, get_font
        self._clear_video_surface()
        colors = get_colors()
        info_frame = tk.Frame(self.video_player.video_frame, bg=colors['bg'])
        info_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            info_frame,
            text="No se pudo reproducir el vídeo",
            font=get_font(16, 'bold'),
            bg=colors['bg'],
            fg=colors['text'],
        ).pack(pady=(50, 10))
        tk.Label(
            info_frame,
            text="YouTube bloquea el acceso directo. Abre el vídeo en el navegador o revisa que ffmpeg esté instalado.",
            font=get_font(10),
            bg=colors['bg'],
            fg=colors['text_muted'],
            wraplength=520,
            justify='center',
        ).pack(pady=(0, 16))
        tk.Button(
            info_frame,
            text="Abrir en navegador",
            font=get_font(10),
            command=lambda: self.open_in_browser(url),
            padx=12,
            pady=6,
            bg=colors['surface_alt'],
            fg=colors['text'],
            activebackground=colors['border'],
            activeforeground=colors['text'],
            relief=tk.FLAT,
        ).pack(pady=10)

    def _stream_ok_for_vlc(self, stream):
        url = (stream or {}).get('url') or ''
        if 'rqh=1' in url:
            return False
        if 'googlevideo.com/videoplayback' in url and 'c=WEB' in url:
            return False
        return bool(url)

    def _play_via_pipe(self, youtube_url, force_pulse, show_progress, is_sequential, duration=None):
        """Retransmite el vídeo con yt-dlp (+ ffmpeg) a un MPEG-TS y lo abre en VLC."""
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            return self._play_via_download(youtube_url, force_pulse, show_progress, is_sequential, duration=duration)

        self.stop_pipeline()
        self._show_status("Preparando vídeo…")
        tmpdir = tempfile.mkdtemp(prefix='kidneys_yt_')
        ts_path = os.path.join(tmpdir, 'stream.ts')
        self._yt_tmpdir = tmpdir

        ytdlp_cmd = self._ytdlp_argv(youtube_url)
        ffmpeg_cmd = [
            ffmpeg, '-hide_banner', '-loglevel', 'error',
            '-fflags', '+genpts',
            '-i', 'pipe:0',
            '-c', 'copy', '-bsf:v', 'h264_mp4toannexb',
            '-f', 'mpegts', ts_path,
        ]

        def producer():
            try:
                ytdlp = subprocess.Popen(ytdlp_cmd, stdout=subprocess.PIPE)
                ffproc = subprocess.Popen(
                    ffmpeg_cmd, stdin=ytdlp.stdout, stderr=subprocess.PIPE
                )
                ytdlp.stdout.close()
                self._yt_procs = [ytdlp, ffproc]
                if self._yt_server:
                    self._yt_server.yt_procs = self._yt_procs
                ff_err = ffproc.communicate()[1]
                ytdlp.wait()
                if ffproc.returncode not in (0, -15, None) and ff_err:
                    print(f"[ffmpeg] {ff_err.decode('utf-8', errors='replace')[-1500:]}")
            except Exception as exc:
                print(f"[YouTubeHandler] Error en la retransmisión: {exc}")

        server = ThreadingHTTPServer(('127.0.0.1', 0), _GrowingTSHandler)
        server.ts_path = ts_path
        server.yt_procs = []
        self._yt_server = server
        threading.Thread(target=server.serve_forever, daemon=True).start()
        stream_url = f'http://127.0.0.1:{server.server_address[1]}/stream.ts'
        threading.Thread(target=producer, daemon=True).start()

        def wait_and_play():
            min_bytes = 64 * 1024
            deadline = time.time() + 75
            while time.time() < deadline:
                try:
                    if os.path.exists(ts_path) and os.path.getsize(ts_path) >= min_bytes:
                        break
                except OSError:
                    pass
                dead = self._yt_procs and all(p.poll() is not None for p in self._yt_procs)
                if dead:
                    self.video_player.window.after(
                        0, lambda: self._show_playback_error(youtube_url)
                    )
                    return
                time.sleep(0.2)
            else:
                print("[YouTubeHandler] ffmpeg no generó datos a tiempo; descargando el archivo")
                self.video_player.window.after(0, lambda: self._play_via_download(
                    youtube_url, force_pulse, show_progress, is_sequential, duration=duration
                ))
                return

            def start_player():
                size = os.path.getsize(ts_path)
                print(f"[YouTubeHandler] Reproduciendo stream local ({size} bytes) {stream_url}")
                self._clear_video_surface()
                self.video_player.play_video_url(
                    stream_url,
                    force_pulse=force_pulse,
                    show_progress=show_progress,
                    is_sequential=is_sequential,
                    local_file=True,
                    fail_after_s=25,
                    duration_s=duration,
                    on_fail=lambda: self._show_playback_error(youtube_url),
                )

            self.video_player.window.after(0, start_player)

        threading.Thread(target=wait_and_play, daemon=True).start()
        print(f"[YouTubeHandler] Retransmitiendo a {ts_path}")
        return True

    def _play_via_download(self, youtube_url, force_pulse, show_progress, is_sequential, duration=None):
        """Si no hay ffmpeg, descarga a un temporal y luego reproduce en VLC."""
        self.stop_pipeline()
        self._show_status("Descargando vídeo para reproducirlo…")
        tmpdir = tempfile.mkdtemp(prefix='kidneys_yt_')
        self._yt_tmpdir = tmpdir
        outtmpl = os.path.join(tmpdir, 'video.%(ext)s')

        def work():
            try:
                opts = youtube_ydl_opts(
                    outtmpl=outtmpl,
                    format='best[ext=mp4][acodec!=none][vcodec!=none]/best',
                    quiet=True,
                )
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)
                    path = ydl.prepare_filename(info)
                if not path or not os.path.exists(path):
                    raise FileNotFoundError('No se descargó el archivo')
                self.video_player.window.after(
                    0,
                    lambda: self.video_player.play_video_url(
                        path,
                        force_pulse=force_pulse,
                        show_progress=show_progress,
                        is_sequential=is_sequential,
                        duration_s=duration or info.get('duration'),
                    ),
                )
            except Exception as exc:
                print(f"[YouTubeHandler] Descarga para reproducción fallida: {exc}")
                self.video_player.window.after(0, lambda: self._show_playback_error(youtube_url))

        threading.Thread(target=work, daemon=True).start()
        return True

    def _ytdlp_argv(self, youtube_url):
        cmd = [
            sys.executable, '-m', 'yt_dlp', youtube_url,
            '-o', '-',
            '-f', 'best[ext=mp4][acodec!=none][vcodec!=none]/best[acodec!=none][vcodec!=none]/best',
            '--no-playlist', '--newline',
            '--sleep-interval', '0',
            '--max-sleep-interval', '0',
            '--sleep-requests', '0',
            '--extractor-args', 'youtube:lang=es',
            '--geo-bypass-country', 'ES',
            '--remote-components', 'ejs:github',
        ]
        cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if os.path.exists(cookies_path):
            cmd.extend(['--cookies', cookies_path])
        else:
            browser = preferred_youtube_browser()
            if browser:
                cmd.extend(['--cookies-from-browser', browser])
        runtimes = detect_js_runtimes()
        for name in ('node', 'deno', 'bun', 'quickjs'):
            if name in runtimes and runtimes[name].get('path'):
                cmd.extend(['--js-runtimes', f"{name}:{runtimes[name]['path']}"])
        return cmd

    def extract_youtube_id(self, url):
        """Extrae el ID del video de YouTube de la URL"""
        if match := re.search(r'(?:v=|/v/|/shorts/|youtu\.be/)([^"&?/\s]{11})', url):
            return match.group(1)
        return None

    def load_playlist(self, playlist_url):
        """Carga todos los vídeos de una playlist de YouTube."""
        try:
            # Exportar cookies automáticamente antes de cargar la playlist
            self.export_cookies_from_browser()
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
            with yt_dlp.YoutubeDL(youtube_ydl_opts(skip_download=True)) as ydl:
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
            ydl_opts = youtube_ydl_opts(
                format='best',
                outtmpl=filepath,
                quiet=False,
                noprogress=False,
            )
            
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
        """Obtiene una URL de stream que VLC pueda reproducir dentro de la ventana."""
        format_sel = (
            'best[ext=mp4][acodec!=none][vcodec!=none]/'
            'best[acodec!=none][vcodec!=none]/'
            'best'
        )
        attempts = [
            # Sin cookies: permite clientes android/ios, cuyas URLs VLC suele abrir
            youtube_ydl_opts(
                use_cookiefile=False,
                skip_download=True,
                extractor_args={'youtube': {'player_client': ['android', 'ios', 'web']}},
                format=format_sel,
            ),
        ]
        browser = preferred_youtube_browser()
        cookie_clients = {'youtube': {'player_client': ['tv', 'web', 'mweb']}}
        if browser:
            attempts.append(youtube_ydl_opts(
                cookie_browser=browser,
                use_cookiefile=False,
                skip_download=True,
                extractor_args=cookie_clients,
                format=format_sel,
            ))
        attempts.append(youtube_ydl_opts(
            skip_download=True,
            extractor_args=cookie_clients,
            format=format_sel,
        ))

        last_error = None
        for ydl_opts in attempts:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=False)
                stream = self._pick_playable_stream(info)
                if stream:
                    stream['headers'] = self._headers_for_vlc(stream.get('headers'))
                    stream['duration'] = info.get('duration')
                    return stream
            except Exception as e:
                last_error = e
                print(f"Error al obtener la URL compatible para VLC: {e}")
                continue
        if last_error:
            print(f"[yt-dlp] Ningún intento de extracción funcionó: {last_error}")
        return None

    def _headers_for_vlc(self, headers):
        merged = dict(headers or {})
        cookie = merged.get('Cookie') or merged.get('cookie') or self._cookie_header_from_file()
        if cookie:
            merged['Cookie'] = cookie
        merged.setdefault('Referer', 'https://www.youtube.com/')
        merged.setdefault('Origin', 'https://www.youtube.com')
        return merged

    def _cookie_header_from_file(self):
        path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if not os.path.exists(path):
            return None
        parts = []
        try:
            with open(path, encoding='utf-8') as handle:
                for line in handle:
                    if not line.strip() or line.startswith('#'):
                        continue
                    fields = line.rstrip('\n').split('\t')
                    if len(fields) < 7:
                        continue
                    domain, name, value = fields[0], fields[5], fields[6]
                    if 'youtube' in domain or 'google' in domain:
                        parts.append(f'{name}={value}')
        except OSError:
            return None
        return '; '.join(parts) if parts else None

    def _pick_playable_stream(self, info):
        formats = list(info.get('formats') or [])
        headers = dict(info.get('http_headers') or {})

        def protocol_of(fmt):
            return (fmt.get('protocol') or '').lower()

        def is_playable(fmt):
            if not fmt.get('url'):
                return False
            if fmt.get('vcodec', 'none') in ('none', '', None):
                return False
            proto = protocol_of(fmt)
            if 'dash' in proto or proto == 'http_dash_segments':
                return False
            if fmt.get('fragment_base_url') and 'm3u8' not in proto:
                return False
            return True

        def is_progressive(fmt):
            acodec = fmt.get('acodec') or 'none'
            vcodec = fmt.get('vcodec') or 'none'
            return acodec not in ('none', '') and vcodec not in ('none', '')

        def is_hls(fmt):
            proto = protocol_of(fmt)
            url = fmt.get('url') or ''
            return 'm3u8' in proto or '.m3u8' in url

        progressive = [f for f in formats if is_playable(f) and is_progressive(f) and not is_hls(f)]
        hls = [f for f in formats if is_playable(f) and is_hls(f)]
        mp4_prog = [
            f for f in progressive
            if (f.get('ext') == 'mp4' or str(f.get('vcodec', '')).startswith('avc1'))
            and (f.get('height') or 0) <= 720
        ]
        other_prog = [f for f in progressive if f not in mp4_prog]
        candidates = []
        for group, score_base in ((hls, 4000), (mp4_prog, 2000), (other_prog, 1000)):
            for fmt in group:
                url = fmt.get('url') or ''
                score = score_base + (fmt.get('height') or 0)
                # rqh=1 en clientes WEB suele devolver HTTP 403 en VLC
                if 'rqh=1' in url:
                    score -= 5000
                candidates.append((score, fmt))

        usable = [item for item in candidates if item[0] > 0]
        ranked = usable or candidates
        if ranked:
            _, best = max(ranked, key=lambda item: item[0])
            fmt_headers = dict(best.get('http_headers') or headers)
            print(
                f"[yt-dlp] Stream: id={best.get('format_id')} ext={best.get('ext')} "
                f"vcodec={best.get('vcodec')} acodec={best.get('acodec')} "
                f"proto={best.get('protocol')} height={best.get('height')}"
            )
            return {'url': best['url'], 'headers': fmt_headers}

        url = info.get('url')
        if url:
            print("[yt-dlp] Usando URL seleccionada por yt-dlp")
            return {'url': url, 'headers': headers}
        return None

    def open_in_browser(self, url):
        """Abre una URL de YouTube en el navegador predeterminado."""
        try:
            webbrowser.open_new(url)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el navegador: {e}")

    def export_cookies_from_browser(self, output_path=None, silent=False):
        """Exporta automáticamente las cookies de YouTube desde el navegador predeterminado usando browser-cookie3."""
        def _error(message):
            if silent:
                print(f"[YouTubeHandler] {message}")
            else:
                messagebox.showerror("Error", message)

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
            _error("Falta el módulo browser-cookie3. Instálalo con: pip install browser-cookie3")
            return None
        except Exception as e:
            _error(f"No se pudieron exportar las cookies del navegador: {e}")
            return None