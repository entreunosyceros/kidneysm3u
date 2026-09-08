"""Búsqueda de canales Kick (directos y offline) + VODs del coincidente exacto."""

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest
import json

import app_config
from display_text import plain_display_text, plain_ui_line
from kick_browse import open_kick_channel_browser
from kick_player import (
    _kick_api_headers,
    fetch_kick_channel_vods,
    normalize_kick_channel_input,
    probe_kick_channel_live,
)
from ui_theme import set_window_icon, style_listbox, style_window
from ui_layout import bind_wraplength, setup_resizable_dialog

KICK_SEARCH_URL = 'https://kick.com/api/search'


def _format_duration(seconds):
    """Formatea duración."""
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        return ''
    if seconds <= 0:
        return ''
    return app_config.format_iptv_clock(seconds)


def _format_viewers(count):
    """Formatea espectadores."""
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


def _search_get(query):
    """GET api/search de Kick."""
    params = urlparse.urlencode({'searched_word': plain_display_text(query, '').strip()})
    url = f'{KICK_SEARCH_URL}?{params}'
    req = urlrequest.Request(url, headers=_kick_api_headers(), method='GET')
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urlerror.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'HTTP {exc.code}: {detail[:240]}') from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f'No se pudo contactar con Kick: {exc.reason}') from exc


def _parse_channel_item(item):
    """Normaliza un canal de la API de búsqueda."""
    if not item or not isinstance(item, dict):
        return None
    slug = plain_display_text(item.get('slug') or '', '').strip().lower()
    if not slug:
        return None
    user = item.get('user') or {}
    display = plain_display_text(user.get('username') or slug, slug)
    followers = item.get('followersCount')
    if followers is None:
        followers = item.get('followers_count')
    try:
        followers = int(followers or 0)
    except (TypeError, ValueError):
        followers = 0
    if item.get('isLive'):
        return {
            'kind': 'live',
            'login': slug,
            'title': display,
            'url': f'https://kick.com/{slug}',
            'viewers': 0,
            'followers': followers,
        }
    return {
        'kind': 'channel',
        'login': slug,
        'title': display,
        'url': f'https://kick.com/{slug}',
        'followers': followers,
    }


def _parse_vod_item(item, channel_slug):
    """Normaliza un VOD ya parseado por fetch_kick_channel_vods."""
    if not item:
        return None
    slug = plain_display_text(channel_slug or '', '').strip().lower()
    return {
        'kind': 'vod',
        'login': slug,
        'title': plain_display_text(item.get('title') or '', 'VOD'),
        'url': item.get('url') or '',
        'duration': item.get('duration'),
    }


def _merge_result(results, seen, item):
    """Añade resultado sin duplicar por (kind, url)."""
    if not item or not item.get('url'):
        return
    key = (item.get('kind'), item.get('url'))
    if key in seen:
        return
    seen.add(key)
    results.append(item)


def search_kick(query, limit=20):
    """Busca canales (live/offline) y VODs del slug exacto. Devuelve lista normalizada."""
    from ttl_cache import get_cached, put_cached

    text = plain_display_text(query, '').strip()
    if not text:
        return []
    limit = max(5, min(int(limit or 20), 40))
    cache_key = f'kick:search:{limit}:{text.lower()}'
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    data = _search_get(text) or {}
    results = []
    seen = set()
    for raw in (data.get('channels') or [])[:limit]:
        _merge_result(results, seen, _parse_channel_item(raw))

    exact = normalize_kick_channel_input(text)
    if exact:
        live = None
        try:
            live = probe_kick_channel_live(exact)
        except Exception:
            live = None
        if live and live.get('live'):
            enriched = {
                'kind': 'live',
                'login': exact,
                'title': live.get('title') or exact,
                'url': live.get('url') or f'https://kick.com/{exact}',
                'viewers': int(live.get('viewers') or 0),
            }
            # Preferir el enriquecido al genérico de búsqueda
            for index, item in enumerate(results):
                if item.get('kind') == 'live' and item.get('login') == exact:
                    results[index] = enriched
                    break
            else:
                _merge_result(results, seen, enriched)
        try:
            videos, channel_name = fetch_kick_channel_vods(exact, limit=min(10, limit))
            slug = plain_display_text(channel_name or exact, exact).lower()
            for video in videos:
                _merge_result(results, seen, _parse_vod_item(video, slug))
        except Exception as exc:
            print(f'[Kick] Búsqueda: no se listaron VOD de {exact}: {exc}')

    live_items = [item for item in results if item.get('kind') == 'live']
    channel_items = [item for item in results if item.get('kind') == 'channel']
    vod_items = [item for item in results if item.get('kind') == 'vod']
    live_items.sort(key=lambda item: int(item.get('viewers') or 0), reverse=True)
    channel_items.sort(key=lambda item: int(item.get('followers') or 0), reverse=True)
    merged = live_items + channel_items + vod_items
    put_cached(cache_key, merged, ttl=180)
    return merged


def kick_search_label(item):
    """Etiqueta legible para un resultado de búsqueda."""
    item = item or {}
    kind = item.get('kind')
    title = plain_display_text(item.get('title') or '', 'Kick')
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


def open_kick_search(player):
    """Abre el diálogo de búsqueda Kick."""
    if not getattr(player, 'window', None):
        return None
    existing = getattr(player, '_kick_search', None)
    if existing is not None:
        try:
            if existing.window.winfo_exists():
                existing.window.deiconify()
                existing.window.lift()
                existing.search_entry.focus_set()
                return existing
        except tk.TclError:
            pass
    dialog = KickSearchDialog(player)
    player._kick_search = dialog
    return dialog


class KickSearchDialog:
    """Diálogo Buscar en Kick."""

    def __init__(self, player):
        """Inicializa KickSearchDialog."""
        self.player = player
        self._results = []
        self._search_gen = 0

        window = tk.Toplevel(player.window)
        window.title('Buscar en Kick')
        setup_resizable_dialog(window, 820, 620, 640, 480)
        style_window(window)
        set_window_icon(window)
        window.transient(player.window)
        self.window = window

        shell = ttk.Frame(window, padding=(16, 14, 16, 12))
        shell.pack(fill=tk.BOTH, expand=True)
        bind_wraplength(shell, padding=40)
        ttk.Label(shell, text='Buscar en Kick', style='PageTitle.TLabel').pack(anchor=tk.W)
        ttk.Label(
            shell,
            text=(
                'Canales en directo, canales offline y, si el término coincide con un slug, '
                'VOD recientes de ese canal. Doble clic para reproducir.'
            ),
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
        """Cierra el diálogo."""
        if getattr(self.player, '_kick_search', None) is self:
            self.player._kick_search = None
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def _set_loading(self, active, message=''):
        """Muestra u oculta la barra de progreso."""
        if message:
            self.status_var.set(plain_ui_line(message))
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
        """Lanza la búsqueda en segundo plano."""
        query = (self.search_var.get() or '').strip()
        if not query:
            messagebox.showinfo('Kick', 'Introduce un término de búsqueda.', parent=self.window)
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
            """Work."""
            err = None
            items = []
            try:
                items = search_kick(query, limit=20)
            except Exception as exc:
                err = exc

            def done():
                """Done."""
                if gen != self._search_gen:
                    return
                self._set_loading(False)
                if err:
                    messagebox.showerror(
                        'Kick',
                        f'No se pudo completar la búsqueda.\n\n{err}',
                        parent=self.window,
                    )
                    self.status_var.set('Error en la búsqueda.')
                    return
                self._results = items
                for item in items:
                    self.listbox.insert(tk.END, kick_search_label(item))
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
        """Resultado seleccionado o None."""
        try:
            index = self.listbox.curselection()[0]
        except IndexError:
            return None
        if index < 0 or index >= len(self._results):
            return None
        return self._results[index]

    def _play_selected(self, _event=None):
        """Reproduce el resultado seleccionado."""
        item = self._selected_item()
        if not item:
            messagebox.showinfo('Kick', 'Selecciona un resultado.', parent=self.window)
            return
        play = getattr(self.player, 'play_kick_url', None)
        if not play:
            return
        play(item['url'], title=item.get('title') or item.get('login') or 'Kick')

    def _open_channel_vods(self):
        """Abre VODs del canal del resultado seleccionado."""
        item = self._selected_item()
        if not item:
            messagebox.showinfo('Kick', 'Selecciona un canal o directo.', parent=self.window)
            return
        login = normalize_kick_channel_input(item.get('login') or item.get('url'))
        if not login:
            messagebox.showinfo('Kick', 'Este resultado no tiene canal asociado.', parent=self.window)
            return
        open_kick_channel_browser(self.player, login)
