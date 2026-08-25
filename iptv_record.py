"""Grabación local del stream actual con ffmpeg (-c copy). Sin nube ni DRM."""

import os
import re
import shutil
import subprocess
import time
import tkinter as tk
from tkinter import ttk, messagebox

from m3u_parse import IPTV_USER_AGENT
from ui_theme import center_window, get_colors, set_window_icon, style_window
import app_config


def _safe_filename(name):
    text = re.sub(r'[\\/*?:"<>|]', '', name or 'canal').strip() or 'canal'
    return text[:80]


def _ffmpeg_copy_cmd(ffmpeg, source, dest, headers=None):
    cmd = [
        ffmpeg, '-hide_banner', '-loglevel', 'error',
        '-user_agent', IPTV_USER_AGENT,
        '-reconnect', '1', '-reconnect_streamed', '1',
        '-reconnect_delay_max', '5',
    ]
    if headers:
        block = ''.join(f'{key}: {value}\r\n' for key, value in headers.items() if value)
        if block:
            cmd.extend(['-headers', block])
    ext = os.path.splitext(dest)[1].lower()
    mux = 'matroska' if ext == '.mkv' else 'mpegts'
    cmd.extend(['-i', source, '-c', 'copy', '-f', mux, dest])
    return cmd


def default_recording_path(name, folder=None, when=None, ext='.ts'):
    folder = folder or app_config.get_download_dir() or app_config.suggested_download_dir()
    when = when or time.strftime('%Y%m%d-%H%M%S')
    ext = ext if str(ext).startswith('.') else f'.{ext}'
    return os.path.join(folder, f'{_safe_filename(name)}_{when}{ext}')


class StreamRecorder:
    def __init__(self, player):
        self.player = player
        self.proc = None
        self.path = ''
        self.name = ''
        self.started = 0

    def is_recording(self):
        proc = self.proc
        return bool(proc) and proc.poll() is None

    def current_source(self):
        player = self.player
        if getattr(player, '_playing_youtube', False):
            handler = getattr(player, 'youtube_handler', None)
            url = getattr(handler, '_direct_url', '') or ''
            headers = dict(getattr(handler, '_direct_headers', None) or {})
            title = getattr(handler, '_loading_title_text', '') or 'YouTube'
            return url, headers, title
        url = (getattr(player, '_iptv_source_url', '') or '').strip()
        name = getattr(player, '_iptv_retry_name', '') or 'canal'
        return url, {}, name

    def start(self, dest):
        if self.is_recording():
            return False, 'Ya hay una grabación en curso.'
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            return False, 'Instala ffmpeg para grabar (sudo apt install ffmpeg).'
        source, headers, name = self.current_source()
        if not source:
            return False, 'No hay un stream que se pueda copiar ahora.'
        if source.startswith('http://127.0.0.1'):
            return False, 'Este relevo local no se graba; prueba el canal original.'
        dest = os.path.abspath(dest)
        folder = os.path.dirname(dest)
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            return False, str(exc)
        cmd = _ffmpeg_copy_cmd(ffmpeg, source, dest, headers=headers or None)
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            return False, str(exc)
        self.path = dest
        self.name = name
        self.started = time.time()
        print(f"[Grabar] Copiando stream → {os.path.basename(dest)}")
        return True, dest

    def stop(self):
        proc = self.proc
        self.proc = None
        if not proc:
            return self.path
        try:
            proc.terminate()
        except OSError:
            pass
        try:
            proc.wait(timeout=4)
        except Exception:
            try:
                proc.kill()
            except OSError:
                pass
        path = self.path
        elapsed = max(0, int(time.time() - (self.started or time.time())))
        print(f"[Grabar] Fin ({elapsed}s) {os.path.basename(path or '')}")
        return path


def show_recordings(player):
    existing = getattr(player, '_recordings_win', None)
    if existing is not None:
        try:
            if existing.window.winfo_exists():
                existing.window.deiconify()
                existing.window.lift()
                existing.refresh()
                return existing
        except tk.TclError:
            pass
    return RecordingsWindow(player)


class RecordingsWindow:
    def __init__(self, player):
        self.player = player
        player._recordings_win = self
        colors = get_colors()
        window = tk.Toplevel(player.window)
        window.title('Grabaciones')
        window.geometry('560x380')
        window.minsize(420, 280)
        style_window(window)
        set_window_icon(window)
        center_window(window, 560, 380)
        window.transient(player.window)
        self.window = window
        self._paths = {}

        top = ttk.Frame(window, padding=(12, 10, 12, 6))
        top.pack(fill=tk.X)
        ttk.Label(top, text='Grabaciones', style='PageTitle.TLabel').pack(side=tk.LEFT)
        ttk.Button(top, text='Cerrar', command=self.close).pack(side=tk.RIGHT)
        ttk.Label(
            window,
            text='Copia local del stream (ffmpeg -c copy). No descifra DRM ni sube nada.',
            style='Muted.TLabel',
            wraplength=520,
        ).pack(anchor=tk.W, padx=12, pady=(0, 8))

        body = ttk.Frame(window, padding=(12, 0, 12, 12))
        body.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(body, columns=('status',), show='tree headings', selectmode='browse')
        self.tree.heading('#0', text='Archivo', anchor=tk.W)
        self.tree.heading('status', text='Estado', anchor=tk.W)
        self.tree.column('#0', width=360, stretch=True)
        self.tree.column('status', width=120, stretch=False)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.tag_configure('empty', foreground=colors['text_muted'])
        self.tree.bind('<Double-Button-1>', self._play_selected)

        buttons = ttk.Frame(window, padding=(12, 0, 12, 12))
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text='Grabar lo actual', style='Accent.TButton', command=self._record_current).pack(side=tk.LEFT)
        ttk.Button(buttons, text='Detener', command=self._stop).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text='Reproducir', command=self._play_selected).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text='Carpeta', command=self._open_folder).pack(side=tk.RIGHT)

        window.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()

    def close(self):
        if getattr(self.player, '_recordings_win', None) is self:
            self.player._recordings_win = None
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def refresh(self):
        if not self.player._widget_exists(self.window):
            return
        try:
            self.tree.delete(*self.tree.get_children())
        except tk.TclError:
            return
        self._paths = {}
        recorder = getattr(self.player, '_stream_recorder', None)
        items = list(getattr(self.player, '_recordings', None) or [])
        if recorder and recorder.is_recording() and recorder.path:
            items = [{'name': recorder.name, 'path': recorder.path, 'live': True}] + [
                item for item in items if item.get('path') != recorder.path
            ]
        if not items:
            self.tree.insert('', 'end', iid='empty', text='Aún no hay grabaciones', values=('',), tags=('empty',))
            return
        for index, item in enumerate(items):
            iid = str(index)
            path = item.get('path') or ''
            self._paths[iid] = path
            status = 'Grabando' if item.get('live') else 'Listo'
            self.tree.insert('', 'end', iid=iid, text=item.get('name') or os.path.basename(path), values=(status,))

    def _record_current(self):
        start = getattr(self.player, 'start_stream_recording', None)
        if start:
            start()
        self.refresh()

    def _stop(self):
        stop = getattr(self.player, 'stop_stream_recording', None)
        if stop:
            stop()
        self.refresh()

    def _selected_path(self):
        try:
            selection = self.tree.selection()
        except tk.TclError:
            return ''
        if not selection:
            return ''
        return self._paths.get(selection[0], '')

    def _play_selected(self, event=None):
        path = self._selected_path()
        if not path or not os.path.isfile(path):
            return
        play = getattr(self.player, 'play_video_url', None)
        if play:
            play(path, show_progress=True, local_file=True, fail_after_s=20)

    def _open_folder(self):
        path = self._selected_path() or app_config.get_download_dir()
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if not folder:
            return
        try:
            subprocess.Popen(['xdg-open', folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            messagebox.showinfo('Carpeta', folder, parent=self.window)
