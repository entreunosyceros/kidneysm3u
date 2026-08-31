"""Búsqueda de canales, directos y VODs de Twitch vía GraphQL (sin navegador)."""

import json
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib import error as urlerror
from urllib import request as urlrequest

import app_config
from display_text import plain_display_text, plain_ui_line
from twitch_browse import open_twitch_channel_browser
from twitch_player import (
    _cookie_header_from_twitch_file,
    normalize_twitch_channel_input,
    twitch_auth_blocked,
    twitch_auth_help,
)
from ui_theme import center_window, get_colors, set_window_icon, style_listbox, style_window

TWITCH_GQL_URL = 'https://gql.twitch.tv/gql'
TWITCH_GQL_CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'
SEARCH_RESULTS_HASH = 'f6c2575aee4418e8a616e03364d8bcdbf0b10a5c87b59f523569dacc963e8da5'
SEARCH_OPERATION = 'SearchResultsPage_SearchResults'


def _format_duration(seconds):
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        return ''
    if seconds <= 0:
        return ''
    return app_config.format_iptv_clock(seconds)


def _format_viewers(count):
    try:
        count = int(count or 0)
    except (TypeError, ValueError):
        return ''
    if count <= 0:
        return ''
    if count >= 1_000_000:
        return f'{count / 1_000_000:.1f}M espectadores'
    if count >= 1_000:
        return f'{count / 1_000:.1f}k espectadores'
    return f'{count} espectadores'


def _gql_headers():
    headers = {
        'Client-ID': TWITCH_GQL_CLIENT_ID,
        'Content-Type': 'application/json',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) '
            'Gecko/20100101 Firefox/125.0'
        ),
    }
    cookie = _cookie_header_from_twitch_file()
    if cookie:
        headers['Cookie'] = cookie
    return headers


def _gql_post(payload):
    body = json.dumps(payload).encode('utf-8')
    req = urlrequest.Request(TWITCH_GQL_URL, data=body, headers=_gql_headers(), method='POST')
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urlerror.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'HTTP {exc.code}: {detail[:240]}') from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f'No se pudo contactar con Twitch: {exc.reason}') from exc


def _search_payload(query, target_index, limit):
    limit = max(5, min(int(limit or 15), 30))
    return [{
        'operationName': SEARCH_OPERATION,
        'variables': {
            'platform': 'web',
            'query': plain_display_text(query, '').strip(),
            'includeIsDJ': True,
            'options': {
                'targets': [{'index': target_index, 'limit': limit}],
                'shouldSkipDiscoveryControl': False,
            },
        },
        'extensions': {
            'persistedQuery': {
                'version': 1,
                'sha256Hash': SEARCH_RESULTS_HASH,
            },
        },
    }]


def _search_block(payload):
    raw = _gql_post(payload)
    if isinstance(raw, list):
        block = raw[0] if raw else {}
    else:
        block = raw or {}
    data = (block.get('data') or {}).get('searchFor')
    if not data:
        errors = block.get('errors') or []
        if errors:
            messages = '; '.join(str(item.get('message') or item) for item in errors[:3])
            raise RuntimeError(messages or 'Búsqueda de Twitch fallida')
        return {}
    return data


def _channel_stream_title(item):
    stream = item.get('stream') or {}
    settings = item.get('broadcastSettings') or {}
    return plain_display_text(
        settings.get('title') or stream.get('title') or item.get('displayName') or item.get('login') or '',
        '',
    )


def _parse_live_channel(item):
    login = plain_display_text(item.get('login') or '', '').strip()
    if not login:
        return None
    stream = item.get('stream') or {}
    if not stream:
        return None
    title = _channel_stream_title(item)
    return {
        'kind': 'live',
        'login': login,
        'title': title or login,
        'url': f'https://www.twitch.tv/{login}',
        'viewers': int(stream.get('viewersCount') or 0),
    }


def _parse_offline_channel(item):
    login = plain_display_text(item.get('login') or '', '').strip()
    if not login:
        return None
    if item.get('stream'):
        return None
    display = plain_display_text(item.get('displayName') or login, login)
    followers = ((item.get('followers') or {}).get('totalCount'))
    return {
        'kind': 'channel',
        'login': login,
        'title': display,
        'url': f'https://www.twitch.tv/{login}',
        'followers': int(followers or 0),
    }


def _parse_related_live(item):
    stream = item.get('stream') or {}
    broadcaster = stream.get('broadcaster') or {}
    login = plain_display_text(broadcaster.get('login') or '', '').strip()
    if not login:
        return None
    settings = broadcaster.get('broadcastSettings') or {}
    title = plain_display_text(settings.get('title') or broadcaster.get('displayName') or login, login)
    return {
        'kind': 'live',
        'login': login,
        'title': title,
        'url': f'https://www.twitch.tv/{login}',
        'viewers': int(stream.get('viewersCount') or 0),
    }


def _parse_vod(item):
    vod_id = str(item.get('id') or '').strip()
    if not vod_id:
        return None
    owner = item.get('owner') or {}
    login = plain_display_text(owner.get('login') or '', '').strip()
    title = plain_display_text(item.get('title') or '', f'VOD {vod_id}')
    return {
        'kind': 'vod',
        'login': login,
        'title': title,
        'url': f'https://www.twitch.tv/videos/{vod_id}',
        'duration': item.get('lengthSeconds'),
        'view_count': int(item.get('viewCount') or 0),
    }


def _merge_result(results, seen, item):
    if not item:
        return
    key = (item.get('kind'), item.get('url'))
    if key in seen:
        return
    seen.add(key)
    results.append(item)


def search_twitch(query, limit=15):
    """Busca canales, directos y VODs. Devuelve lista normalizada."""
    text = plain_display_text(query, '').strip()
    if not text:
        return []
    limit = max(5, min(int(limit or 15), 30))
    results = []
    seen = set()

    channel_data = _search_block(_search_payload(text, 'CHANNEL', limit))
    for edge in ((channel_data.get('channels') or {}).get('edges') or []):
        item = edge.get('item') or {}
        live = _parse_live_channel(item)
        if live:
            _merge_result(results, seen, live)
        else:
            _merge_result(results, seen, _parse_offline_channel(item))
    for edge in ((channel_data.get('relatedLiveChannels') or {}).get('edges') or []):
        _merge_result(results, seen, _parse_related_live(edge.get('item') or {}))

    video_data = _search_block(_search_payload(text, 'VOD', limit))
    for edge in ((video_data.get('videos') or {}).get('edges') or []):
        _merge_result(results, seen, _parse_vod(edge.get('item') or {}))

    live_items = [item for item in results if item.get('kind') == 'live']
    channel_items = [item for item in results if item.get('kind') == 'channel']
    vod_items = [item for item in results if item.get('kind') == 'vod']
    live_items.sort(key=lambda item: int(item.get('viewers') or 0), reverse=True)
    channel_items.sort(key=lambda item: item.get('title') or item.get('login') or '')
    return live_items + channel_items + vod_items


def twitch_search_label(item):
    item = item or {}
    kind = item.get('kind')
    title = plain_display_text(item.get('title') or '', 'Twitch')
    login = plain_display_text(item.get('login') or '', '')
    if kind == 'live':
        viewers = _format_viewers(item.get('viewers'))
        base = f'Directo · {login}'
        if title and title.lower() != login.lower():
            base = f'{base} — {title}'
        return plain_ui_line(f'{base}  ·  {viewers}' if viewers else base)
    if kind == 'channel':
        followers = int(item.get('followers') or 0)
        suffix = f'  ·  {followers:,} seguidores'.replace(',', '.') if followers > 0 else ''
        return plain_ui_line(f'Canal · {title}{suffix}')
    if kind == 'vod':
        duration = _format_duration(item.get('duration'))
        prefix = f'VOD · {login} — ' if login else 'VOD · '
        line = f'{prefix}{title}'
        if duration:
            line = f'{line}  ·  {duration}'
        return plain_ui_line(line)
    return title


def open_twitch_search(player):
    if not getattr(player, 'window', None):
        return None
    existing = getattr(player, '_twitch_search', None)
    if existing is not None:
        try:
            if existing.window.winfo_exists():
                existing.window.deiconify()
                existing.window.lift()
                existing.search_entry.focus_set()
                return existing
        except tk.TclError:
            pass
    dialog = TwitchSearchDialog(player)
    player._twitch_search = dialog
    return dialog


class TwitchSearchDialog:
    def __init__(self, player):
        self.player = player
        self._results = []
        self._search_gen = 0

        window = tk.Toplevel(player.window)
        window.title('Buscar en Twitch')
        window.geometry('820x620')
        window.minsize(640, 480)
        style_window(window)
        set_window_icon(window)
        center_window(window, 820, 620)
        window.transient(player.window)
        self.window = window

        shell = ttk.Frame(window, padding=(16, 14, 16, 12))
        shell.pack(fill=tk.BOTH, expand=True)
        ttk.Label(shell, text='Buscar en Twitch', style='PageTitle.TLabel').pack(anchor=tk.W)
        ttk.Label(
            shell,
            text='Canales en directo, canales offline y VODs recientes. Doble clic para reproducir en el reproductor.',
            style='Muted.TLabel',
            wraplength=760,
        ).pack(anchor=tk.W, pady=(0, 10))

        search_row = ttk.Frame(shell)
        search_row.pack(fill=tk.X, pady=(0, 8))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind('<Return>', lambda _e: self.search())
        ttk.Button(search_row, text='Buscar', style='Accent.TButton', command=self.search).pack(
            side=tk.LEFT, padx=(8, 0),
        )

        self.status_var = tk.StringVar(value='Introduce un término y pulsa Buscar.')
        ttk.Label(shell, textvariable=self.status_var, style='Muted.TLabel', wraplength=760).pack(
            anchor=tk.W, pady=(0, 8),
        )

        self.progress = ttk.Progressbar(shell, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=(0, 8))
        self.progress.pack_forget()

        list_frame = ttk.Frame(shell)
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

        buttons = ttk.Frame(shell)
        buttons.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(buttons, text='Reproducir', style='Accent.TButton', command=self._play_selected).pack(
            side=tk.LEFT,
        )
        ttk.Button(buttons, text='VODs del canal', command=self._open_channel_vods).pack(
            side=tk.LEFT, padx=(8, 0),
        )
        ttk.Button(buttons, text='Cerrar', command=self.close).pack(side=tk.RIGHT)

        window.protocol('WM_DELETE_WINDOW', self.close)
        self.search_entry.focus_set()

    def close(self):
        if getattr(self.player, '_twitch_search', None) is self:
            self.player._twitch_search = None
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _set_loading(self, active, message=''):
        if message:
            self.status_var.set(message)
        if active:
            self.progress.pack(fill=tk.X, pady=(0, 8))
            self.progress.start(10)
        else:
            try:
                self.progress.stop()
                self.progress.pack_forget()
            except tk.TclError:
                pass

    def search(self):
        query = (self.search_var.get() or '').strip()
        if not query:
            messagebox.showinfo('Twitch', 'Introduce un término de búsqueda.', parent=self.window)
            return
        self._search_gen += 1
        gen = self._search_gen
        self._set_loading(True, f'Buscando «{query}»…')
        try:
            self.listbox.delete(0, tk.END)
        except tk.TclError:
            return
        self._results = []

        def work():
            err = None
            items = []
            try:
                items = search_twitch(query, limit=20)
            except Exception as exc:
                err = exc

            def done():
                if gen != self._search_gen:
                    return
                self._set_loading(False)
                if err:
                    handler = getattr(self.player, 'twitch_handler', None)
                    if handler:
                        handler.mark_session_from_error(err)
                    if twitch_auth_blocked(err):
                        messagebox.showerror('Twitch', twitch_auth_help(), parent=self.window)
                    else:
                        messagebox.showerror(
                            'Twitch',
                            f'No se pudo completar la búsqueda.\n\n{err}',
                            parent=self.window,
                        )
                    self.status_var.set('Error en la búsqueda.')
                    return
                self._results = items
                for item in items:
                    self.listbox.insert(tk.END, twitch_search_label(item))
                if not items:
                    self.status_var.set(f'Sin resultados para «{query}».')
                    return
                live_count = sum(1 for item in items if item.get('kind') == 'live')
                channel_count = sum(1 for item in items if item.get('kind') == 'channel')
                vod_count = sum(1 for item in items if item.get('kind') == 'vod')
                parts = []
                if live_count:
                    parts.append(f'{live_count} en directo')
                if channel_count:
                    parts.append(f'{channel_count} canales')
                if vod_count:
                    parts.append(f'{vod_count} VOD')
                summary = ', '.join(parts)
                self.status_var.set(
                    plain_ui_line(f'{len(items)} resultados ({summary}). Doble clic para reproducir.'),
                )

            try:
                self.window.after(0, done)
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True).start()

    def _selected_item(self):
        try:
            index = self.listbox.curselection()[0]
        except IndexError:
            return None
        if index < 0 or index >= len(self._results):
            return None
        return self._results[index]

    def _play_selected(self, _event=None):
        item = self._selected_item()
        if not item:
            messagebox.showinfo('Twitch', 'Selecciona un resultado.', parent=self.window)
            return
        play = getattr(self.player, 'play_twitch_url', None)
        if not play:
            return
        play(item['url'], title=item.get('title') or item.get('login') or 'Twitch')

    def _open_channel_vods(self):
        item = self._selected_item()
        if not item:
            messagebox.showinfo('Twitch', 'Selecciona un canal o directo.', parent=self.window)
            return
        login = normalize_twitch_channel_input(item.get('login') or item.get('url'))
        if not login:
            messagebox.showinfo('Twitch', 'Este resultado no tiene canal asociado.', parent=self.window)
            return
        open_twitch_channel_browser(self.player, login)
