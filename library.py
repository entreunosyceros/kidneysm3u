"""Biblioteca unificada: favoritos e historial IPTV / YouTube / Twitch / Kick."""

import tkinter as tk
from tkinter import messagebox, ttk

import app_config
from display_text import plain_display_text, plain_ui_line
from favorites_manager import favorite_name, favorite_url
from ui_layout import bind_tree_stretch, bind_wraplength, setup_resizable_dialog
from ui_theme import get_colors, set_window_icon, style_window

SOURCES = ('all', 'iptv', 'youtube', 'twitch', 'kick')
SECTIONS = ('all', 'favorites', 'continue', 'history')

SOURCE_LABELS = {
    'all': 'Todas',
    'iptv': 'IPTV',
    'youtube': 'YouTube',
    'twitch': 'Twitch',
    'kick': 'Kick',
}
SECTION_LABELS = {
    'all': 'Todo',
    'favorites': 'Favoritos',
    'continue': 'Seguir viendo',
    'history': 'Historial',
}
BUCKET_LABELS = {
    'favorite': 'Favorito',
    'continue': 'Seguir viendo',
    'history': 'Historial',
}


def source_from_url(url):
    """Detecta la fuente a partir de la URL."""
    text = (url or '').strip()
    if not text:
        return 'iptv'
    lower = text.lower()
    if app_config._is_youtube_url(text):
        return 'youtube'
    if 'twitch.tv' in lower:
        return 'twitch'
    if 'kick.com' in lower:
        return 'kick'
    return 'iptv'


def _progress_text(item, source):
    """Texto de posición para la columna."""
    try:
        seconds = int((item or {}).get('s') or 0)
    except (TypeError, ValueError):
        seconds = 0
    try:
        duration = int((item or {}).get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0
    kind = str((item or {}).get('kind') or '').lower()
    if source == 'youtube':
        min_s = app_config.YT_RESUME_MIN_S
    else:
        min_s = app_config.IPTV_RESUME_MIN_S
        if source in ('twitch', 'kick') and kind and kind != 'vod':
            return ''
        if source == 'iptv' and kind and kind != 'vod' and seconds < min_s:
            return ''
    if seconds < min_s:
        return ''
    stamp = app_config.format_iptv_clock(seconds)
    if duration > 0:
        return f'{stamp} / {app_config.format_iptv_clock(duration)}'
    return stamp


def _entry(
    *,
    bucket,
    source,
    name,
    url,
    item_id='',
    progress='',
    updated=0,
    kind='',
):
    """Crea un ítem normalizado de biblioteca."""
    return {
        'bucket': bucket,
        'source': source,
        'name': plain_display_text(name, source.title()),
        'url': (url or '').strip(),
        'id': str(item_id or '').strip(),
        'progress': progress or '',
        'updated': int(updated or 0),
        'kind': kind or '',
    }


def _history_entries(bucket, source, items):
    """Convierte entradas de historial/continuar en ítems de biblioteca."""
    out = []
    for item in items or ():
        url = (item.get('url') or '').strip()
        if not url:
            continue
        out.append(_entry(
            bucket=bucket,
            source=source,
            name=item.get('name') or SOURCE_LABELS.get(source, source),
            url=url,
            item_id=item.get('id') or '',
            progress=_progress_text(item, source),
            updated=item.get('updated') or item.get('at') or 0,
            kind=item.get('kind') or '',
        ))
    return out


def collect_library_items(favorites=None, section='all', source='all', query=''):
    """Agrega favoritos + seguir viendo + historial con filtros."""
    section = section if section in SECTIONS else 'all'
    source = source if source in SOURCES else 'all'
    needle = plain_display_text(query, '').strip().lower()
    items = []

    if section in ('all', 'favorites'):
        for raw in favorites or ():
            url = favorite_url(raw)
            if not url:
                continue
            src = source_from_url(url)
            if source != 'all' and src != source:
                continue
            items.append(_entry(
                bucket='favorite',
                source=src,
                name=favorite_name(raw) or SOURCE_LABELS.get(src, src),
                url=url,
            ))

    continue_map = {
        'iptv': app_config.iptv_continue_watching,
        'youtube': app_config.youtube_continue_watching,
        'twitch': app_config.twitch_continue_watching,
        'kick': app_config.kick_continue_watching,
    }
    history_map = {
        'iptv': app_config.iptv_history,
        'youtube': app_config.youtube_history,
        'twitch': app_config.twitch_history,
        'kick': app_config.kick_history,
    }

    if section in ('all', 'continue'):
        for src, loader in continue_map.items():
            if source != 'all' and src != source:
                continue
            items.extend(_history_entries('continue', src, loader()))

    if section in ('all', 'history'):
        continue_urls = {
            item['url']
            for item in items
            if item.get('bucket') == 'continue' and item.get('url')
        }
        for src, loader in history_map.items():
            if source != 'all' and src != source:
                continue
            for entry in _history_entries('history', src, loader()):
                # En "Todo", no duplicar la misma URL que ya está en Seguir viendo
                if section == 'all' and entry['url'] in continue_urls:
                    continue
                items.append(entry)

    if needle:
        filtered = []
        for item in items:
            hay = ' '.join([
                item.get('name') or '',
                item.get('url') or '',
                SOURCE_LABELS.get(item.get('source'), ''),
                BUCKET_LABELS.get(item.get('bucket'), ''),
            ]).lower()
            if needle in hay:
                filtered.append(item)
        items = filtered

    def sort_key(item):
        bucket_rank = {'continue': 0, 'favorite': 1, 'history': 2}.get(item.get('bucket'), 9)
        updated = int(item.get('updated') or 0)
        return (bucket_rank, -updated, (item.get('name') or '').lower())

    items.sort(key=sort_key)
    return items


def library_row_label(item):
    """Etiqueta corta para listados simples."""
    item = item or {}
    source = SOURCE_LABELS.get(item.get('source'), '')
    bucket = BUCKET_LABELS.get(item.get('bucket'), '')
    name = item.get('name') or 'Sin nombre'
    return plain_ui_line(f'{bucket} · {source} — {name}')


def remove_library_item(player, item):
    """Quita un ítem de favoritos o historial según el bucket."""
    item = item or {}
    url = item.get('url') or ''
    bucket = item.get('bucket')
    source = item.get('source')
    if bucket == 'favorite':
        remover = getattr(player, 'remove_favorite_entry', None)
        if remover:
            remover(item.get('name') or '', url)
        return True
    if source == 'youtube':
        video_id = item.get('id') or ''
        if not video_id and url:
            found = app_config.youtube_history_item_by_url(url) or {}
            video_id = found.get('id') or ''
        app_config.remove_youtube_history(video_id)
        return True
    if source == 'twitch':
        app_config.remove_twitch_history(url)
        return True
    if source == 'kick':
        app_config.remove_kick_history(url)
        return True
    if source == 'iptv':
        app_config.remove_iptv_history(url)
        return True
    return False


def play_library_item(player, item):
    """Reproduce un ítem de la biblioteca."""
    item = item or {}
    url = item.get('url') or ''
    if not url:
        return
    name = item.get('name') or ''
    source = item.get('source') or source_from_url(url)
    if source == 'youtube':
        play = getattr(player, 'play_youtube_url', None)
        if play:
            play(url, title=name or 'YouTube', add_to_list=False)
        return
    if source == 'twitch':
        play = getattr(player, 'play_twitch_url', None)
        if play:
            play(url, title=name or 'Twitch', add_to_list=False)
        return
    if source == 'kick':
        play = getattr(player, 'play_kick_url', None)
        if play:
            play(url, title=name or 'Kick', add_to_list=False)
        return
    play = getattr(player, 'play_history_url', None)
    if play:
        play(url)


def open_library(player, section='all', source='all'):
    """Abre (o reutiliza) la ventana de biblioteca."""
    if not getattr(player, 'window', None):
        return None
    existing = getattr(player, '_library_window', None)
    if existing is not None:
        try:
            if existing.window.winfo_exists():
                existing.set_filters(section=section, source=source)
                existing.window.deiconify()
                existing.window.lift()
                existing.refresh()
                return existing
        except tk.TclError:
            pass
    return LibraryWindow(player, section=section, source=source)


class LibraryWindow:
    """Ventana Biblioteca con filtros por sección y fuente."""

    def __init__(self, player, section='all', source='all'):
        """Inicializa LibraryWindow."""
        self.player = player
        player._library_window = self
        self._entries = {}
        self._section = section if section in SECTIONS else 'all'
        self._source = source if source in SOURCES else 'all'

        colors = get_colors()
        window = tk.Toplevel(player.window)
        window.title('Biblioteca')
        setup_resizable_dialog(window, 900, 620, 640, 420)
        style_window(window)
        set_window_icon(window)
        window.transient(player.window)
        self.window = window

        top = ttk.Frame(window, padding=(12, 10, 12, 6))
        top.pack(fill=tk.X)
        ttk.Label(top, text='Biblioteca', style='PageTitle.TLabel').pack(side=tk.LEFT)
        ttk.Button(top, text='Cerrar', command=self.close).pack(side=tk.RIGHT)
        ttk.Button(top, text='Actualizar', command=self.refresh).pack(side=tk.RIGHT, padx=(0, 8))

        ttk.Label(
            window,
            text=(
                'Favoritos e historial de IPTV, YouTube, Twitch y Kick en un solo sitio. '
                'Filtra por sección y fuente; doble clic para reproducir.'
            ),
            style='Muted.TLabel',
            wraplength=860,
        ).pack(anchor=tk.W, padx=12, pady=(0, 8))
        bind_wraplength(window, padding=24)

        filters = ttk.Frame(window, padding=(12, 0, 12, 8))
        filters.pack(fill=tk.X)
        ttk.Label(filters, text='Sección', style='Card.TLabel').pack(side=tk.LEFT)
        self.section_var = tk.StringVar(value=SECTION_LABELS[self._section])
        section_box = ttk.Combobox(
            filters,
            textvariable=self.section_var,
            values=[SECTION_LABELS[key] for key in SECTIONS],
            state='readonly',
            width=14,
        )
        section_box.pack(side=tk.LEFT, padx=(6, 16))
        section_box.bind('<<ComboboxSelected>>', lambda _e: self._on_filter_change())

        ttk.Label(filters, text='Fuente', style='Card.TLabel').pack(side=tk.LEFT)
        self.source_var = tk.StringVar(value=SOURCE_LABELS[self._source])
        source_box = ttk.Combobox(
            filters,
            textvariable=self.source_var,
            values=[SOURCE_LABELS[key] for key in SOURCES],
            state='readonly',
            width=12,
        )
        source_box.pack(side=tk.LEFT, padx=(6, 16))
        source_box.bind('<<ComboboxSelected>>', lambda _e: self._on_filter_change())

        ttk.Label(filters, text='Buscar', style='Card.TLabel').pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filters, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        search_entry.bind('<KeyRelease>', lambda _e: self._schedule_refresh())
        search_entry.bind('<Return>', lambda _e: self.refresh())
        self._search_job = None

        self.status_var = tk.StringVar(value='')
        ttk.Label(
            window,
            textvariable=self.status_var,
            style='Muted.TLabel',
            wraplength=860,
        ).pack(anchor=tk.W, padx=12, pady=(0, 6))

        body = ttk.Frame(window, padding=(12, 0, 12, 12))
        body.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            body,
            columns=('title', 'source', 'bucket', 'progress'),
            show='headings',
            selectmode='browse',
        )
        self.tree.heading('title', text='Título', anchor=tk.W)
        self.tree.heading('source', text='Fuente', anchor=tk.W)
        self.tree.heading('bucket', text='Tipo', anchor=tk.W)
        self.tree.heading('progress', text='Posición', anchor=tk.W)
        self.tree.column('title', width=380, stretch=True)
        self.tree.column('source', width=90, stretch=False)
        self.tree.column('bucket', width=120, stretch=False)
        self.tree.column('progress', width=140, stretch=False)
        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bind_tree_stretch(self.tree, stretch_columns=('title',))
        self.tree.tag_configure('favorite', foreground=colors.get('accent') or colors.get('text'))
        self.tree.bind('<Double-Button-1>', self._play_selected)
        self.tree.bind('<Return>', self._play_selected)

        buttons = ttk.Frame(window, padding=(12, 0, 12, 12))
        buttons.pack(fill=tk.X)
        ttk.Button(
            buttons,
            text='Reproducir',
            style='Accent.TButton',
            command=self._play_selected,
        ).pack(side=tk.LEFT)
        ttk.Button(buttons, text='Quitar', command=self._remove_selected).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            buttons,
            text='Mostrar favoritos en lista',
            command=self._show_favorites_sidebar,
        ).pack(side=tk.LEFT, padx=(8, 0))

        window.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()

    def close(self):
        """Cierra la ventana."""
        if getattr(self.player, '_library_window', None) is self:
            self.player._library_window = None
        try:
            self.window.destroy()
        except tk.TclError:
            pass

    def set_filters(self, section=None, source=None):
        """Ajusta filtros sin recrear la ventana."""
        if section in SECTIONS:
            self._section = section
            self.section_var.set(SECTION_LABELS[section])
        if source in SOURCES:
            self._source = source
            self.source_var.set(SOURCE_LABELS[source])

    def _label_to_key(self, labels, value, default):
        """Resuelve etiqueta visible → clave interna."""
        for key, label in labels.items():
            if label == value:
                return key
        return default

    def _on_filter_change(self):
        """Combobox cambiados."""
        self._section = self._label_to_key(SECTION_LABELS, self.section_var.get(), 'all')
        self._source = self._label_to_key(SOURCE_LABELS, self.source_var.get(), 'all')
        self.refresh()

    def _schedule_refresh(self):
        """Debounce de la búsqueda de biblioteca."""
        job = getattr(self, '_search_job', None)
        if job:
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass
        try:
            self._search_job = self.window.after(180, self.refresh)
        except tk.TclError:
            self._search_job = None

    def refresh(self):
        """Recarga la lista según filtros."""
        self._search_job = None
        try:
            if not self.window.winfo_exists():
                return
            self.tree.delete(*self.tree.get_children())
        except tk.TclError:
            return
        self._entries = {}
        favorites = getattr(self.player, 'favorites', None) or []
        items = collect_library_items(
            favorites=favorites,
            section=self._section,
            source=self._source,
            query=self.search_var.get(),
        )
        for index, item in enumerate(items):
            iid = f'lib:{index}'
            self._entries[iid] = item
            tags = ('favorite',) if item.get('bucket') == 'favorite' else ()
            self.tree.insert(
                '',
                'end',
                iid=iid,
                values=(
                    item.get('name') or 'Sin nombre',
                    SOURCE_LABELS.get(item.get('source'), ''),
                    BUCKET_LABELS.get(item.get('bucket'), ''),
                    item.get('progress') or '',
                ),
                tags=tags,
            )
        if items:
            self.status_var.set(
                plain_ui_line(f'{len(items)} elementos. Doble clic para reproducir.'),
            )
        else:
            self.status_var.set('No hay elementos con estos filtros.')

    def _selected_item(self):
        """Ítem seleccionado o None."""
        try:
            selection = self.tree.selection()
        except tk.TclError:
            return None
        if not selection:
            return None
        return self._entries.get(selection[0])

    def _play_selected(self, _event=None):
        """Reproduce la selección."""
        item = self._selected_item()
        if not item:
            messagebox.showinfo('Biblioteca', 'Selecciona un elemento.', parent=self.window)
            return
        play_library_item(self.player, item)
        refresh = getattr(self.player, '_refresh_history_ui', None)
        if refresh:
            refresh()

    def _remove_selected(self):
        """Quita favorito o entrada de historial."""
        item = self._selected_item()
        if not item:
            return
        label = library_row_label(item)
        if not messagebox.askyesno(
            'Biblioteca',
            f'¿Quitar de la biblioteca?\n\n{label}',
            parent=self.window,
        ):
            return
        remove_library_item(self.player, item)
        self.refresh()
        refresh = getattr(self.player, '_refresh_history_ui', None)
        if refresh:
            refresh()

    def _show_favorites_sidebar(self):
        """Abre la vista de favoritos en la barra lateral."""
        show = getattr(self.player, 'show_favorites', None)
        if show:
            show()
