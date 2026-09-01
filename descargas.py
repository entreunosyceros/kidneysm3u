"""Módulo de descargas."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import yt_dlp
import os
import re
import sys
import subprocess
import pathlib
import requests
from urllib.parse import unquote
from ui_theme import style_window, set_window_icon, center_window, style_listbox, style_menu_tree
from ui_layout import bind_wraplength, setup_resizable_dialog, walk_wraplength
import app_config
from display_text import truncate_ui_text


def download_history_label(item, max_len=72):
    """Descarga historial label."""
    name = str((item or {}).get('name') or '').strip()
    url = str((item or {}).get('url') or '').strip()
    shown = name or url.split('#')[0].split('?')[0] or url
    return truncate_ui_text(shown, max_len)


def resolve_downloaded_path(planned):
    """Resolve downloaded path."""
    planned = os.path.abspath(planned or '')
    if planned and os.path.isfile(planned):
        return planned
    folder = os.path.dirname(planned)
    stem = os.path.splitext(os.path.basename(planned))[0]
    if not folder or not stem or not os.path.isdir(folder):
        return planned
    matches = []
    try:
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if name.startswith(stem) and os.path.isfile(path):
                matches.append(path)
    except OSError:
        return planned
    if not matches:
        return planned
    matches.sort(key=os.path.getmtime, reverse=True)
    return matches[0]


def reveal_in_file_manager(path):
    """Abre el gestor de archivos del sistema y, si puede, selecciona el fichero."""
    path = os.path.abspath(path or '')
    if not path:
        return False
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if not folder or not os.path.isdir(folder):
        return False
    try:
        if sys.platform.startswith('win'):
            if os.path.isfile(path):
                subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
            else:
                subprocess.Popen(['explorer', os.path.normpath(folder)])
            return True
        if sys.platform == 'darwin':
            cmd = ['open', '-R', path] if os.path.isfile(path) else ['open', folder]
            subprocess.Popen(cmd)
            return True
        if os.path.isfile(path):
            uri = pathlib.Path(path).resolve().as_uri()
            try:
                result = subprocess.run(
                    [
                        'dbus-send', '--session', '--type=method_call',
                        '--dest=org.freedesktop.FileManager1',
                        '/org/freedesktop/FileManager1',
                        'org.freedesktop.FileManager1.ShowItems',
                        f'array:string:{uri}',
                        'string:',
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                )
                if result.returncode == 0:
                    return True
            except (OSError, subprocess.TimeoutExpired):
                pass
        subprocess.Popen(
            ['xdg-open', folder],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False

class DownloadManager:
    """Clase que representa downloadmanager."""
    def __init__(self, parent):
        """Inicializa DownloadManager."""
        self.window = tk.Toplevel(parent)
        self.window.title("Descargar URL")
        from ui_layout import setup_resizable_dialog
        setup_resizable_dialog(self.window, 640, 700, 520, 600)
        style_window(self.window)
        set_window_icon(self.window)
        self.url = tk.StringVar()
        self.output_path = tk.StringVar(value=app_config.get_download_dir())
        self.filename = tk.StringVar()
        self.open_folder_var = tk.BooleanVar(value=app_config.get_open_folder_after_download())
        self.is_downloading = False
        
        self.create_widgets()
        
    def create_widgets(self):
        """Crea widgets."""
        buttons_frame = ttk.Frame(self.window, padding=(20, 0, 20, 16))
        buttons_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.download_button = ttk.Button(
            buttons_frame, text="Descargar", style='Accent.TButton', command=self.start_download
        )
        self.download_button.pack(side=tk.LEFT)
        ttk.Button(buttons_frame, text="Cancelar", command=self.window.destroy).pack(side=tk.RIGHT)

        main_frame = ttk.Frame(self.window, padding=(20, 20, 20, 12))
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text='Descargar URL', style='PageTitle.TLabel').pack(anchor=tk.W)
        ttk.Label(
            main_frame,
            text='YouTube, listas y archivos directos',
            style='Muted.TLabel',
            wraplength=500,
        ).pack(anchor=tk.W, pady=(0, 16))
        bind_wraplength(main_frame, padding=40)
        
        url_frame = ttk.LabelFrame(main_frame, text=" URL ", padding=10)
        url_frame.pack(fill=tk.X, pady=(0, 12))
        self.url_combo = ttk.Combobox(url_frame, textvariable=self.url)
        self.url_combo.pack(fill=tk.X)
        self.url_combo.bind('<<ComboboxSelected>>', self._on_recent_url)

        recent_frame = ttk.LabelFrame(main_frame, text=" ÚLTIMAS DESCARGAS ", padding=10)
        recent_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        list_row = ttk.Frame(recent_frame, style='Card.TFrame')
        list_row.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(list_row)
        self.recent_list = tk.Listbox(
            list_row,
            activestyle='dotbox',
            exportselection=False,
            yscrollcommand=scroll.set,
        )
        self.recent_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.recent_list.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        style_listbox(self.recent_list)
        self.recent_list.bind('<<ListboxSelect>>', self._on_recent_select)
        self.recent_list.bind('<Double-Button-1>', self._on_recent_double)
        self.recent_list.bind('<Button-3>', self._on_recent_menu)
        self.recent_list.bind('<Control-c>', self._copy_recent_url)
        self.recent_list.bind('<Control-Insert>', self._copy_recent_url)
        self.recent_list.bind('<Control-v>', self._paste_url)
        self.recent_list.bind('<Shift-Insert>', self._paste_url)
        self.recent_list.bind('<Return>', self._redownload_item)
        self.recent_empty = ttk.Label(
            recent_frame,
            text='Aún no hay descargas recientes. Las URLs se recuerdan al descargar.',
            style='CardMuted.TLabel',
        )
        self._recent_items = []
        self._refresh_recent()
        
        dest_frame = ttk.LabelFrame(main_frame, text=" CARPETA DE DESTINO ", padding=10)
        dest_frame.pack(fill=tk.X, pady=(0, 12))
        dest_row = ttk.Frame(dest_frame, style='Card.TFrame')
        dest_row.pack(fill=tk.X)
        dest_entry = ttk.Entry(dest_row, textvariable=self.output_path)
        dest_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(dest_row, text="Examinar", command=self.browse_output).pack(side=tk.RIGHT)
        ttk.Checkbutton(
            dest_frame,
            text='Al terminar, abrir el gestor de archivos y mostrar el archivo',
            variable=self.open_folder_var,
            command=self._persist_open_folder,
            style='Card.TCheckbutton',
        ).pack(anchor=tk.W, pady=(10, 0))
        
        name_frame = ttk.LabelFrame(main_frame, text=" NOMBRE DEL ARCHIVO ", padding=10)
        name_frame.pack(fill=tk.X, pady=(0, 12))
        ttk.Entry(name_frame, textvariable=self.filename).pack(fill=tk.X)
        
        self.progress_frame = ttk.LabelFrame(main_frame, text=" PROGRESO ", padding=10)
        self.progress_frame.pack(fill=tk.X, pady=(0, 12))
        self.progress = ttk.Progressbar(self.progress_frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0, 6))
        self.progress_label = ttk.Label(self.progress_frame, text="", style='CardMuted.TLabel')
        self.progress_label.pack(anchor=tk.W)

    def _refresh_recent(self):
        """Uso interno: refresh recent."""
        items = app_config.download_url_history()
        self._recent_items = items
        combo = getattr(self, 'url_combo', None)
        listing = getattr(self, 'recent_list', None)
        empty = getattr(self, 'recent_empty', None)
        urls = [item['url'] for item in items]
        if combo is not None:
            try:
                combo.configure(values=urls)
            except tk.TclError:
                pass
        if listing is None:
            return
        self._filling_recent = True
        try:
            listing.delete(0, tk.END)
            for item in items:
                listing.insert(tk.END, download_history_label(item))
        except tk.TclError:
            pass
        self._filling_recent = False
        if empty is not None:
            if items:
                empty.configure(
                    text='Doble clic para volver a descargar. Clic derecho o Ctrl+C copia la URL; Ctrl+V la pega arriba.',
                )
            else:
                empty.configure(
                    text='Aún no hay descargas recientes. Las URLs se recuerdan al descargar.',
                )
            empty.pack(anchor=tk.W, pady=(8, 0))

    def _apply_recent_item(self, item):
        """Uso interno: apply recent item."""
        if not item:
            return
        url = item.get('url') or ''
        self.url.set(url)
        name = (item.get('name') or '').strip()
        if name:
            self.filename.set(name)

    def _on_recent_url(self, event=None):
        """Callback interno para recent URL."""
        url = (self.url.get() or '').strip()
        for item in self._recent_items:
            if item.get('url') == url:
                self._apply_recent_item(item)
                return

    def _on_recent_select(self, event=None):
        """Callback interno para recent select."""
        if getattr(self, '_filling_recent', False):
            return
        listing = getattr(self, 'recent_list', None)
        if listing is None:
            return
        selection = listing.curselection()
        if not selection:
            return
        index = selection[0]
        if 0 <= index < len(self._recent_items):
            self._apply_recent_item(self._recent_items[index])

    def _recent_index_from_event(self, event=None, from_mouse=False):
        """Uso interno: recent index from event."""
        listing = getattr(self, 'recent_list', None)
        if listing is None:
            return None
        index = None
        if from_mouse and event is not None:
            try:
                index = listing.nearest(event.y)
            except tk.TclError:
                index = None
        if index is None:
            selection = listing.curselection()
            index = selection[0] if selection else None
        if index is None:
            return None
        if 0 <= index < len(self._recent_items):
            return index
        return None

    def _select_recent_index(self, index):
        """Uso interno: select recent index."""
        listing = getattr(self, 'recent_list', None)
        if listing is None or index is None:
            return
        try:
            listing.selection_clear(0, tk.END)
            listing.selection_set(index)
            listing.activate(index)
            listing.see(index)
        except tk.TclError:
            pass

    def _redownload_item(self, event=None, from_mouse=False):
        """Uso interno: redownload item."""
        index = self._recent_index_from_event(event, from_mouse=from_mouse)
        if index is None:
            return 'break'
        self._select_recent_index(index)
        self._apply_recent_item(self._recent_items[index])
        self.start_download()
        return 'break'

    def _on_recent_double(self, event=None):
        """Callback interno para recent double."""
        return self._redownload_item(event, from_mouse=True)

    def _copy_recent_url(self, event=None):
        """Uso interno: copy recent URL."""
        from_mouse = event is not None and getattr(event, 'num', None) in (1, 2, 3)
        index = self._recent_index_from_event(event, from_mouse=from_mouse)
        if index is None:
            return 'break'
        self._select_recent_index(index)
        url = (self._recent_items[index].get('url') or '').strip()
        if not url:
            return 'break'
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(url)
        except tk.TclError:
            pass
        return 'break'

    def _paste_url(self, event=None):
        """Uso interno: paste URL."""
        try:
            text = (self.window.clipboard_get() or '').strip()
        except tk.TclError:
            return 'break'
        if text:
            self.url.set(text)
            try:
                self.url_combo.focus_set()
                self.url_combo.icursor(tk.END)
            except tk.TclError:
                pass
        return 'break'

    def _on_recent_menu(self, event):
        """Callback interno para recent menu."""
        index = self._recent_index_from_event(event, from_mouse=True)
        if index is None:
            return
        self._select_recent_index(index)
        self._apply_recent_item(self._recent_items[index])
        menu = tk.Menu(self.window, tearoff=0)
        style_menu_tree(menu)
        menu.add_command(label='Copiar URL', command=self._copy_recent_url)
        menu.add_command(label='Descargar de nuevo', command=self.start_download)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass
        return 'break'
        
    def browse_output(self):
        """Browse output."""
        folder = filedialog.askdirectory(
            parent=self.window,
            title='Carpeta de destino',
            initialdir=self.output_path.get() or app_config.get_download_dir(),
        )
        if folder:
            self.output_path.set(folder)

    def _persist_open_folder(self):
        """Uso interno: persist open folder."""
        app_config.set_open_folder_after_download(bool(self.open_folder_var.get()))
            
    def start_download(self):
        """Inicia download."""
        if str(self.download_button.cget('state')) == 'disabled':
            return
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
            except Exception:
                self.filename.set('video')

        app_config.remember_download_url(self.url.get().strip(), self.filename.get().strip())
        self._refresh_recent()
        
        self.download_button.configure(state='disabled')
        threading.Thread(target=self._download, daemon=True).start()
        
    def _download(self):
        """Uso interno: download."""
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
                """Progress hook."""
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
                
                saved = output_template
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(self.url.get(), download=True)
                    try:
                        if info and info.get('entries'):
                            entry = next((item for item in info['entries'] if item), None)
                            if entry:
                                saved = ydl.prepare_filename(entry)
                        elif info:
                            saved = ydl.prepare_filename(info)
                    except Exception:
                        saved = output_template
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
                    saved = output_template
                                    
                except requests.RequestException as e:
                    raise Exception(f"Error al descargar el archivo: {str(e)}")
            
            saved = resolve_downloaded_path(saved)
            self.window.after(0, lambda path=saved: self._download_complete(path))
            
        except Exception as e:
            self.window.after(0, self._show_error, str(e))
        
    def _update_progress(self, percentage, percent_str):
        """Uso interno: update progress."""
        self.progress['value'] = percentage
        self.progress_label.configure(text=f"Descargando: {percent_str}")
        
    def _download_complete(self, path=''):
        """Uso interno: download complete."""
        self.progress['value'] = 100
        self.progress_label.configure(text="¡Descarga completada!")
        app_config.remember_download_url(self.url.get().strip(), self.filename.get().strip())
        self._persist_open_folder()
        opened = False
        if self.open_folder_var.get() and path:
            opened = reveal_in_file_manager(path)
        location = path or self.output_path.get()
        text = "La descarga se ha completado correctamente."
        if location:
            text += f"\n\n{location}"
        if self.open_folder_var.get() and location and not opened:
            text += "\n\nNo se pudo abrir el gestor de archivos."
        messagebox.showinfo("Éxito", text, parent=self.window)
        self.window.destroy()
        
    def _show_error(self, error):
        """Uso interno: show error."""
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
