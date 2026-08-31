"""Explorar VODs recientes de un canal de Twitch."""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

import app_config
from display_text import plain_display_text, plain_ui_line
from twitch_player import (
    fetch_twitch_channel_vods,
    normalize_twitch_channel_input,
    probe_twitch_channel_live,
    twitch_auth_blocked,
    twitch_auth_help,
)
from ui_clipboard import ask_string
from ui_theme import center_window, get_colors, set_window_icon, style_listbox, style_window


def _format_duration(seconds):
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        return ''
    if seconds <= 0:
        return ''
    return app_config.format_iptv_clock(seconds)


def _vod_line(item):
    title = plain_display_text(item.get('title') or 'Twitch', 'Twitch')
    duration = _format_duration(item.get('duration'))
    if duration:
        return plain_ui_line(f'{title}  ·  {duration}')
    return title


def open_twitch_channel_browser(player, channel=None):
    if not getattr(player, 'window', None):
        return None
    if channel is None:
        channel = ask_string(
            player.window,
            'VODs de un canal',
            'Nombre del canal de Twitch (p. ej. shroud) o URL del canal:',
        )
    channel = normalize_twitch_channel_input(channel)
    if not channel:
        return None
    existing = getattr(player, '_twitch_channel_browser', None)
    if existing is not None:
        try:
            if existing.window.winfo_exists():
                existing.load_channel(channel)
                existing.window.deiconify()
                existing.window.lift()
                return existing
        except tk.TclError:
            pass
    browser = TwitchChannelBrowser(player, channel)
    player._twitch_channel_browser = browser
    return browser


class TwitchChannelBrowser:
    def __init__(self, player, channel):
        self.player = player
        self.channel = channel
        self._videos = []
        self._live = None
        self._load_gen = 0

        window = tk.Toplevel(player.window)
        window.title(f'Twitch · {channel}')
        window.geometry('760x560')
        window.minsize(560, 420)
        style_window(window)
        set_window_icon(window)
        center_window(window, 760, 560)
        window.transient(player.window)
        self.window = window

        top = ttk.Frame(window, padding=(12, 10, 12, 6))
        top.pack(fill=tk.X)
        ttk.Label(top, text='VODs del canal', style='PageTitle.TLabel').pack(side=tk.LEFT)
        ttk.Button(top, text='Cerrar', command=self.close).pack(side=tk.RIGHT)
        ttk.Button(top, text='Actualizar', command=self._reload).pack(side=tk.RIGHT, padx=(0, 8))

        self.channel_var = tk.StringVar(value=channel)
        search_row = ttk.Frame(window, padding=(12, 0, 12, 8))
        search_row.pack(fill=tk.X)
        self._search_row = search_row
        ttk.Label(search_row, text='Canal', style='Card.TLabel').pack(side=tk.LEFT, padx=(0, 8))
        entry = ttk.Entry(search_row, textvariable=self.channel_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(search_row, text='Buscar', command=self._search).pack(side=tk.LEFT)
        entry.bind('<Return>', lambda _e: self._search())

        self.live_frame = ttk.Frame(window, padding=(12, 0, 12, 8))
        self.live_frame.pack(fill=tk.X)
        self.live_frame.pack_forget()
        self.live_label = ttk.Label(self.live_frame, style='Card.TLabel', wraplength=700)
        self.live_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.live_button = ttk.Button(
            self.live_frame,
            text='Ver directo',
            style='Accent.TButton',
            command=self._play_live,
        )
        self.live_button.pack(side=tk.RIGHT)

        self.status_var = tk.StringVar(value=plain_ui_line('Cargando…'))
        ttk.Label(
            window,
            textvariable=self.status_var,
            style='Muted.TLabel',
            wraplength=700,
        ).pack(anchor=tk.W, padx=12, pady=(0, 8))

        body = ttk.Frame(window, padding=(12, 0, 12, 12))
        body.pack(fill=tk.BOTH, expand=True)
        list_frame = ttk.Frame(body)
        list_frame.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.listbox = tk.Listbox(
            list_frame,
            activestyle='none',
            highlightthickness=0,
            yscrollcommand=scroll.set,
        )
        style_listbox(self.listbox)
        scroll.config(command=self.listbox.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind('<Double-Button-1>', self._play_selected)
        self.listbox.bind('<Return>', self._play_selected)

        buttons = ttk.Frame(window, padding=(12, 0, 12, 12))
        buttons.pack(fill=tk.X)
        ttk.Button(
            buttons,
            text='Reproducir VOD',
            style='Accent.TButton',
            command=self._play_selected,
        ).pack(side=tk.LEFT)

        window.protocol('WM_DELETE_WINDOW', self.close)
        self.load_channel(channel)

    def close(self):
        if getattr(self.player, '_twitch_channel_browser', None) is self:
            self.player._twitch_channel_browser = None
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _set_status(self, text):
        self.status_var.set(plain_ui_line(text))

    def _search(self):
        channel = normalize_twitch_channel_input(self.channel_var.get())
        if not channel:
            messagebox.showinfo('Twitch', 'Introduce un nombre de canal válido.', parent=self.window)
            return
        self.load_channel(channel)

    def _reload(self):
        self.load_channel(self.channel)

    def load_channel(self, channel):
        channel = normalize_twitch_channel_input(channel)
        if not channel:
            return
        self.channel = channel
        self.channel_var.set(channel)
        self._load_gen += 1
        gen = self._load_gen
        self._set_status(f'Cargando VODs de {channel}…')
        self.live_frame.pack_forget()
        self._live = None
        try:
            self.listbox.delete(0, tk.END)
        except tk.TclError:
            pass
        try:
            self.window.title(f'Twitch · {channel}')
        except tk.TclError:
            pass

        def work():
            err = None
            live = None
            videos = []
            channel_name = channel
            try:
                live = probe_twitch_channel_live(channel)
                videos, channel_name = fetch_twitch_channel_vods(channel, limit=30)
            except Exception as exc:
                err = exc

            def done():
                if gen != self._load_gen:
                    return
                if err:
                    handler = getattr(self.player, 'twitch_handler', None)
                    if handler:
                        handler.mark_session_from_error(err)
                    if twitch_auth_blocked(err):
                        messagebox.showerror(
                            'Twitch',
                            twitch_auth_help(),
                            parent=self.window,
                        )
                    else:
                        messagebox.showerror(
                            'Twitch',
                            f'No se pudieron cargar los VOD del canal.\n\n{err}',
                            parent=self.window,
                        )
                    self._set_status('Error al cargar el canal.')
                    return
                self._live = live
                self._videos = videos
                display_name = plain_display_text(channel_name or channel, channel)
                if live and live.get('live'):
                    title = plain_display_text(live.get('title') or display_name, display_name)
                    self.live_label.configure(
                        text=plain_ui_line(
                            f'En directo ahora: {title} ({display_name})'
                        ),
                    )
                    self.live_frame.pack(fill=tk.X, padx=12, pady=(0, 8), after=self._search_row)
                else:
                    self.live_frame.pack_forget()
                try:
                    self.listbox.delete(0, tk.END)
                except tk.TclError:
                    return
                for item in videos:
                    self.listbox.insert(tk.END, _vod_line(item))
                if videos:
                    self._set_status(
                        f'{len(videos)} VOD recientes de {display_name}. '
                        'Doble clic para reproducir.'
                    )
                elif live and live.get('live'):
                    self._set_status(
                        f'{display_name} está en directo; no hay VOD recientes listados.'
                    )
                else:
                    self._set_status(f'No hay VOD recientes visibles para {display_name}.')

            try:
                self.window.after(0, done)
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _play_live(self):
        live = self._live or {}
        url = live.get('url') or f'https://www.twitch.tv/{self.channel}'
        title = plain_display_text(live.get('title') or self.channel, self.channel)
        play = getattr(self.player, 'play_twitch_url', None)
        if play:
            play(url, title=title)

    def _play_selected(self, _event=None):
        try:
            index = self.listbox.curselection()[0]
        except IndexError:
            messagebox.showinfo('Twitch', 'Selecciona un VOD de la lista.', parent=self.window)
            return
        if index < 0 or index >= len(self._videos):
            return
        item = self._videos[index]
        play = getattr(self.player, 'play_twitch_url', None)
        if play:
            play(item['url'], title=item.get('title') or 'Twitch')
