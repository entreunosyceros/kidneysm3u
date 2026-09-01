"""Lista lateral del reproductor: grupos por group-title, pestañas o desplegable."""

import time
import tkinter as tk
from tkinter import ttk

from display_text import plain_display_text, truncate_ui_text
from ui_theme import get_colors, get_font

VIRTUAL_MIN = 2500
CHUNK = 200
ROW_HEIGHT = 26
UNGROUPED = 'Sin grupo'
ALL_GROUPS = ''
TAB_MAX_GROUPS = 8


def _group_buckets(groups):
    """Uso interno: group buckets."""
    order = []
    buckets = {}
    for index, group in enumerate(groups):
        key = (group or '').strip() or UNGROUPED
        if key not in buckets:
            order.append(key)
            buckets[key] = []
        buckets[key].append(index)
    return order, buckets


def _short_label(name, limit=22):
    """Uso interno: short label."""
    return truncate_ui_text(name, limit, UNGROUPED)


class ChannelSidebar:
    """Clase que representa channelsidebar."""
    def __init__(self, parent):
        """Inicializa ChannelSidebar."""
        self.outer = ttk.Frame(parent)
        self.outer.pack(fill=tk.BOTH, expand=True, padx=8)

        self.picker_frame = ttk.Frame(self.outer)
        self._tab_bar = ttk.Frame(self.picker_frame)
        combo_row = ttk.Frame(self.picker_frame)
        combo_row.pack(fill=tk.X)
        ttk.Label(combo_row, text='Grupo', style='Muted.TLabel').pack(side=tk.LEFT, padx=(0, 8))
        self.picker = ttk.Combobox(combo_row, state='readonly')
        self.picker.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.picker.bind('<<ComboboxSelected>>', self._on_combo)
        self._back_btn = ttk.Button(combo_row, text='← Grupos', command=self.show_all_groups)
        self._combo_row = combo_row

        self._body = ttk.Frame(self.outer)
        self._body.pack(fill=tk.BOTH, expand=True)
        self.scrollbar = ttk.Scrollbar(self._body, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree = ttk.Treeview(
            self._body,
            show='tree',
            selectmode='browse',
            takefocus=True,
        )
        self.tree.column('#0', width=220, minwidth=80, stretch=True)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.mode = 'flat'
        self.channels = []
        self.groups = []
        self._order = []
        self._buckets = {}
        self._active_group = ALL_GROUPS
        self._view_indices = None
        self._virtual_start = 0
        self._pool = 0
        self._selected = None
        self._loaded_groups = set()
        self._group_items = {}
        self._fill_job = None
        self._rebuild_gen = 0
        self._combo_keys = []
        self._tab_keys = []
        self._tab_buttons = []
        self._updating_picker = False
        self._ignore_play_until = 0
        self._zap_numbers = {}
        self.on_view_change = None
        self.now_text = None
        self.row_image = None
        self.is_favorite = None

        self.tree.bind('<<TreeviewOpen>>', self._on_open)
        self.tree.bind('<<TreeviewClose>>', self._on_close)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Configure>', self._on_configure)
        self.tree.bind('<Button-1>', self._on_press, add='+')
        self.tree.bind('<Button-4>', self._on_wheel)
        self.tree.bind('<Button-5>', self._on_wheel)
        self.tree.bind('<MouseWheel>', self._on_wheel)
        self._apply_tags()
        self._use_native_scroll()

    def _apply_tags(self):
        """Uso interno: apply tags."""
        colors = get_colors()
        try:
            self.tree.tag_configure(
                'group',
                font=get_font(9, 'bold'),
                foreground=colors['accent'],
                background=colors.get('surface_alt') or colors['list_bg'],
            )
        except tk.TclError:
            pass

    def refresh_theme(self):
        """Refresca theme."""
        self._apply_tags()

    def ignore_play(self):
        """Ignore play."""
        return time.time() < self._ignore_play_until

    def _block_play_briefly(self):
        """Uso interno: block play briefly."""
        self._ignore_play_until = time.time() + 0.4

    def _cancel_fill(self):
        """Uso interno: cancel fill."""
        self._rebuild_gen += 1
        job = self._fill_job
        self._fill_job = None
        if job:
            try:
                self.tree.after_cancel(job)
            except tk.TclError:
                pass

    def _clear_tree(self):
        """Uso interno: clear árbol."""
        self._cancel_fill()
        try:
            children = self.tree.get_children()
            if children:
                self.tree.delete(*children)
        except tk.TclError:
            pass
        self._loaded_groups.clear()
        self._group_items = {}
        self._pool = 0

    def _use_native_scroll(self):
        """Uso interno: use native scroll."""
        try:
            self.scrollbar.configure(command=self.tree.yview)
            self.tree.configure(yscrollcommand=self.scrollbar.set)
        except tk.TclError:
            pass

    def _use_virtual_scroll(self):
        """Uso interno: use virtual scroll."""
        try:
            self.scrollbar.configure(command=self._virtual_scroll)
            self.tree.configure(yscrollcommand='')
        except tk.TclError:
            pass
        self._sync_virtual_scrollbar()

    def rebuild(self, channels, groups=None):
        """Rebuild."""
        previous = self._active_group
        self.channels = list(channels or [])
        if groups is None or len(groups) != len(self.channels):
            self.groups = [''] * len(self.channels)
        else:
            self.groups = list(groups)
        self._selected = None
        self._virtual_start = 0
        self._clear_tree()
        self._order, self._buckets = _group_buckets(self.groups)
        if previous and previous in self._buckets:
            self._active_group = previous
        else:
            self._active_group = ALL_GROUPS
        self._sync_picker()
        self._render()
        self._notify_view_change()

    def show_all_groups(self):
        """Muestra all groups."""
        self.set_active_group(ALL_GROUPS)

    def set_active_group(self, name):
        """Establece active group."""
        key = ALL_GROUPS if name in (None, ALL_GROUPS) else name
        if key not in (ALL_GROUPS,) and key not in self._buckets:
            key = ALL_GROUPS
        if key == self._active_group and self.tree.get_children():
            self._sync_picker_selection()
            return
        self._active_group = key
        self._block_play_briefly()
        self._selected = None
        self._virtual_start = 0
        self._clear_tree()
        self._sync_picker_selection()
        self._render()
        self._notify_view_change()

    def _notify_view_change(self):
        """Uso interno: notify view change."""
        callback = self.on_view_change
        if callable(callback):
            callback()

    def current_indices(self):
        """Current indices."""
        if self.mode == 'catalog':
            return []
        if self._view_indices is not None:
            return list(self._view_indices)
        return list(range(len(self.channels)))

    def _row_text(self, index):
        """Uso interno: row text."""
        if index is None or not (0 <= index < len(self.channels)):
            return ''
        name = plain_display_text(self.channels[index][0])
        getter = self.now_text
        extra = getter(index) if callable(getter) else ''
        extra = plain_display_text(extra)
        mark = ''
        if callable(self.is_favorite):
            try:
                if self.is_favorite(index):
                    mark = '★ '
            except Exception:
                mark = ''
        title = f'{mark}{name}'
        number = self._visible_number(index)
        if number is not None:
            title = f'{number}  {title}'
        if extra:
            return f'{title}  ·  {extra}'
        return title

    def _visible_number(self, index):
        """Uso interno: visible number."""
        return (self._zap_numbers or {}).get(index)

    def _refresh_zap_numbers(self):
        """Uso interno: refresh zap numbers."""
        mapping = {}
        if self.mode != 'catalog':
            indices = self.current_indices()
            if not indices:
                indices = list(range(len(self.channels)))
            mapping = {index: offset + 1 for offset, index in enumerate(indices)}
        self._zap_numbers = mapping

    def _image_for(self, index):
        """Uso interno: image for."""
        getter = self.row_image
        if not callable(getter):
            return None
        try:
            return getter(index)
        except Exception:
            return None

    def _item_kwargs(self, index):
        """Uso interno: item kwargs."""
        kwargs = {'text': self._row_text(index)}
        image = self._image_for(index)
        if image is not None:
            kwargs['image'] = image
        else:
            kwargs['image'] = ''
        return kwargs

    def refresh_rows(self):
        """Refresca rows."""
        if self.mode == 'virtual':
            self._refresh_virtual()
            return
        if self.mode == 'catalog':
            return

        def walk(parent=''):
            """Walk."""
            try:
                items = list(self.tree.get_children(parent))
            except tk.TclError:
                return
            for iid in items:
                index = self._index_from_iid(iid)
                if index is not None:
                    try:
                        self.tree.item(iid, **self._item_kwargs(index))
                    except tk.TclError:
                        continue
                walk(iid)

        walk()

    def _has_groups(self):
        """Uso interno: has groups."""
        return len(self.channels) >= 2 and len(self._order) >= 2

    def _sync_picker(self):
        """Uso interno: sync picker."""
        if not self._has_groups():
            self._active_group = ALL_GROUPS
            try:
                self.picker_frame.pack_forget()
            except tk.TclError:
                pass
            return
        try:
            self.picker_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 6), before=self._body)
        except tk.TclError:
            self.picker_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 6))
        if len(self._order) <= TAB_MAX_GROUPS:
            self._show_tabs()
            self._combo_row.pack_forget()
        else:
            self._hide_tabs()
            self._combo_row.pack(fill=tk.X)
            self._fill_combo()
        self._sync_picker_selection()

    def _hide_tabs(self):
        """Uso interno: hide tabs."""
        for btn in self._tab_buttons:
            try:
                btn.destroy()
            except tk.TclError:
                pass
        self._tab_buttons = []
        self._tab_keys = []
        try:
            self._tab_bar.pack_forget()
        except tk.TclError:
            pass

    def _show_tabs(self):
        """Uso interno: show tabs."""
        self._hide_tabs()
        self._tab_bar.pack(side=tk.TOP, fill=tk.X, pady=(0, 6))
        self._tab_bar.columnconfigure(0, weight=1, uniform='group_tab')
        self._tab_bar.columnconfigure(1, weight=1, uniform='group_tab')
        total = len(self.channels)
        keys = [ALL_GROUPS] + list(self._order)
        for index, key in enumerate(keys):
            if key == ALL_GROUPS:
                text = f'Todos ({total})'
            else:
                text = f'{_short_label(key, 16)} ({len(self._buckets.get(key) or [])})'
            btn = ttk.Button(
                self._tab_bar,
                text=text,
                style='Compact.TButton',
                command=lambda k=key: self.set_active_group(k),
            )
            row, column = divmod(index, 2)
            padx = (0, 4) if column == 0 else (0, 0)
            btn.grid(row=row, column=column, sticky='ew', padx=padx, pady=(0, 4))
            self._tab_buttons.append(btn)
            self._tab_keys.append(key)

    def _fill_combo(self):
        """Uso interno: fill combo."""
        self._updating_picker = True
        try:
            values = [f'Todos los grupos ({len(self.channels)})']
            keys = [ALL_GROUPS]
            for name in self._order:
                values.append(f'{name} ({len(self._buckets[name])})')
                keys.append(name)
            self._combo_keys = keys
            self.picker['values'] = values
        finally:
            self._updating_picker = False

    def _sync_picker_selection(self):
        """Uso interno: sync picker selection."""
        self._updating_picker = True
        try:
            inside = bool(self._active_group)
            if inside:
                try:
                    self._back_btn.pack(side=tk.LEFT, padx=(8, 0))
                except tk.TclError:
                    pass
            else:
                self._back_btn.pack_forget()
            if self._combo_keys:
                try:
                    index = self._combo_keys.index(self._active_group)
                except ValueError:
                    index = 0
                values = list(self.picker.cget('values') or ())
                if 0 <= index < len(values):
                    self.picker.set(values[index])
            for key, btn in zip(self._tab_keys, self._tab_buttons):
                try:
                    btn.configure(style='Accent.TButton' if key == self._active_group else 'TButton')
                except tk.TclError:
                    pass
        finally:
            self._updating_picker = False

    def _on_combo(self, event=None):
        """Callback interno para combo."""
        if self._updating_picker:
            return
        try:
            index = self.picker.current()
        except tk.TclError:
            return
        if 0 <= index < len(self._combo_keys):
            self.set_active_group(self._combo_keys[index])

    def _render(self):
        """Uso interno: render."""
        if self._has_groups() and not self._active_group:
            self.mode = 'catalog'
            self._view_indices = None
            self._refresh_zap_numbers()
            self._use_native_scroll()
            self._build_catalog()
            return
        if self._active_group and self._active_group in self._buckets:
            self._view_indices = list(self._buckets[self._active_group])
        else:
            self._view_indices = None
        count = self._view_count()
        if count >= VIRTUAL_MIN:
            self.mode = 'virtual'
            self._refresh_zap_numbers()
            self._use_virtual_scroll()
            self._refresh_virtual()
            return
        self.mode = 'flat'
        self._refresh_zap_numbers()
        self._use_native_scroll()
        self._fill_flat(0, self._rebuild_gen)

    def _view_count(self):
        """Uso interno: view count."""
        if self._view_indices is not None:
            return len(self._view_indices)
        return len(self.channels)

    def _index_at_row(self, row):
        """Uso interno: index at row."""
        if self._view_indices is not None:
            if 0 <= row < len(self._view_indices):
                return self._view_indices[row]
            return None
        if 0 <= row < len(self.channels):
            return row
        return None

    def _build_catalog(self):
        """Uso interno: build catalog."""
        self._group_items = {}
        for offset, name in enumerate(self._order):
            gid = f'g:{offset}'
            indices = self._buckets[name]
            self._group_items[gid] = indices
            label = f'{name}  ·  {len(indices)}'
            try:
                self.tree.insert('', 'end', iid=gid, text=label, tags=('group',), open=False)
            except tk.TclError:
                return

    def _build_groups(self, order, buckets):
        """Uso interno: build groups."""
        self._build_catalog()

    def _fill_flat(self, start, gen):
        """Uso interno: fill flat."""
        if gen != self._rebuild_gen:
            return
        total = self._view_count()
        end = min(total, start + CHUNK)
        for row in range(start, end):
            index = self._index_at_row(row)
            if index is None:
                continue
            try:
                self.tree.insert('', 'end', iid=f'c:{index}', **self._item_kwargs(index))
            except tk.TclError:
                return
        if end < total:
            self._fill_job = self.tree.after(1, lambda: self._fill_flat(end, gen))
        else:
            self._fill_job = None

    def _group_iid(self, iid):
        """Uso interno: group iid."""
        if not iid:
            return None
        if iid.endswith(':ph'):
            try:
                iid = self.tree.parent(iid)
            except tk.TclError:
                return None
        if iid.startswith('g:'):
            return iid
        return None

    def _on_press(self, event):
        """Callback interno para press."""
        gid = self.group_at(event)
        if not gid:
            return
        name = self._group_name(gid)
        if name is None:
            return
        self.set_active_group(name)
        return 'break'

    def _group_name(self, gid):
        """Uso interno: group name."""
        indices = self._group_items.get(gid) or []
        if not indices:
            return None
        index = indices[0]
        if 0 <= index < len(self.groups):
            return (self.groups[index] or '').strip() or UNGROUPED
        return None

    def _on_select(self, event=None):
        """Callback interno para select."""
        try:
            selection = self.tree.selection()
        except tk.TclError:
            return
        if not selection:
            return
        index = self._index_from_iid(selection[0])
        if index is not None:
            self._selected = index

    def _on_open(self, event=None):
        """Callback interno para open."""
        iid = self._group_iid(self.tree.focus())
        if not iid:
            return
        name = self._group_name(iid)
        if name is not None:
            self.set_active_group(name)

    def _on_close(self, event=None):
        """Callback interno para close."""
        iid = self._group_iid(self.tree.focus())
        if not iid:
            return
        self.tree.after_idle(lambda group=iid: self._unload_group(group))

    def _load_group(self, gid):
        """Uso interno: load group."""
        name = self._group_name(gid)
        if name is not None:
            self.set_active_group(name)

    def _unload_group(self, gid):
        """Uso interno: unload group."""
        if gid not in self._loaded_groups:
            return
        try:
            if not self.tree.exists(gid) or self.tree.item(gid, 'open'):
                return
            for child in self.tree.get_children(gid):
                self.tree.delete(child)
            self.tree.insert(gid, 'end', iid=f'{gid}:ph', text='...')
        except tk.TclError:
            return
        self._loaded_groups.discard(gid)

    def _fill_group(self, gid, indices, start, gen):
        """Uso interno: fill group."""
        if gen != self._rebuild_gen or gid not in self._loaded_groups:
            return
        end = min(len(indices), start + CHUNK)
        for pos in range(start, end):
            index = indices[pos]
            try:
                self.tree.insert(gid, 'end', iid=f'c:{index}', **self._item_kwargs(index))
            except tk.TclError:
                return
        if end < len(indices):
            self._fill_job = self.tree.after(1, lambda: self._fill_group(gid, indices, end, gen))
        else:
            self._fill_job = None

    def toggle_group(self, gid):
        """Alterna group."""
        name = self._group_name(gid)
        if name is not None:
            self.set_active_group(name)

    def _visible_rows(self):
        """Uso interno: visible rows."""
        try:
            height = max(ROW_HEIGHT, int(self.tree.winfo_height() or 0))
        except tk.TclError:
            height = ROW_HEIGHT * 12
        return max(8, height // ROW_HEIGHT + 1)

    def _on_configure(self, event=None):
        """Callback interno para configure."""
        if self.mode == 'virtual':
            self._refresh_virtual()

    def _on_wheel(self, event):
        """Callback interno para wheel."""
        if self.mode != 'virtual':
            return
        delta = -3
        if getattr(event, 'num', None) == 5 or getattr(event, 'delta', 0) < 0:
            delta = 3
        self._move_virtual(delta)
        return 'break'

    def _virtual_scroll(self, *args):
        """Uso interno: virtual scroll."""
        n = self._view_count()
        vis = self._visible_rows()
        max_start = max(0, n - vis)
        if not args:
            return
        if args[0] == 'moveto':
            try:
                self._virtual_start = int(float(args[1]) * max_start)
            except (TypeError, ValueError, IndexError):
                return
        elif args[0] == 'scroll':
            try:
                amount = int(args[1])
            except (TypeError, ValueError, IndexError):
                return
            unit = args[2] if len(args) > 2 else 'units'
            step = vis - 1 if unit == 'pages' else 3
            self._virtual_start += amount * step
        self._virtual_start = max(0, min(max_start, self._virtual_start))
        self._refresh_virtual()

    def _move_virtual(self, delta):
        """Uso interno: move virtual."""
        n = self._view_count()
        vis = self._visible_rows()
        max_start = max(0, n - vis)
        self._virtual_start = max(0, min(max_start, self._virtual_start + delta))
        self._refresh_virtual()

    def _sync_virtual_scrollbar(self):
        """Uso interno: sync virtual scrollbar."""
        n = max(1, self._view_count())
        vis = min(self._visible_rows(), n)
        start = self._virtual_start / n
        end = (self._virtual_start + vis) / n
        try:
            self.scrollbar.set(start, min(1.0, end))
        except tk.TclError:
            pass

    def _refresh_virtual(self):
        """Uso interno: refresh virtual."""
        n = self._view_count()
        vis = self._visible_rows()
        max_start = max(0, n - vis)
        self._virtual_start = max(0, min(max_start, self._virtual_start))
        need = vis if n else 0
        for row in range(need):
            view_row = self._virtual_start + row
            index = self._index_at_row(view_row)
            kwargs = self._item_kwargs(index) if index is not None else {'text': '', 'image': ''}
            iid = f'v:{row}'
            try:
                if self.tree.exists(iid):
                    self.tree.item(iid, **kwargs)
                else:
                    self.tree.insert('', 'end', iid=iid, **kwargs)
            except tk.TclError:
                return
        for row in range(need, self._pool):
            iid = f'v:{row}'
            try:
                if self.tree.exists(iid):
                    self.tree.delete(iid)
            except tk.TclError:
                break
        self._pool = need
        self._sync_virtual_scrollbar()
        self._paint_virtual_selection()

    def _paint_virtual_selection(self):
        """Uso interno: paint virtual selection."""
        if self._selected is None:
            try:
                self.tree.selection_remove(self.tree.selection())
            except tk.TclError:
                pass
            return
        row = self._virtual_row_of(self._selected)
        iid = f'v:{row}'
        try:
            if row is not None and 0 <= row < self._pool and self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.focus(iid)
            else:
                self.tree.selection_remove(self.tree.selection())
        except tk.TclError:
            pass

    def _virtual_row_of(self, index):
        """Uso interno: virtual row of."""
        if self._view_indices is not None:
            try:
                view_row = self._view_indices.index(index)
            except ValueError:
                return None
        else:
            view_row = index
        return view_row - self._virtual_start

    def _index_from_iid(self, iid):
        """Uso interno: index from iid."""
        if not iid:
            return None
        if iid.startswith('c:'):
            try:
                return int(iid.split(':', 1)[1])
            except ValueError:
                return None
        if iid.startswith('v:'):
            try:
                row = int(iid.split(':', 1)[1])
            except ValueError:
                return None
            return self._index_at_row(self._virtual_start + row)
        return None

    def index_at(self, event):
        """Index at."""
        try:
            iid = self.tree.identify_row(event.y)
        except tk.TclError:
            return None
        return self._index_from_iid(iid)

    def group_at(self, event):
        """Group at."""
        try:
            iid = self.tree.identify_row(event.y)
        except tk.TclError:
            return None
        return self._group_iid(iid)

    def name_at(self, event):
        """Name at."""
        try:
            iid = self.tree.identify_row(event.y)
        except tk.TclError:
            return None
        if not iid:
            return None
        try:
            bbox = self.tree.bbox(iid)
        except tk.TclError:
            bbox = None
        if bbox:
            x, y, width, height = bbox
            if not (y <= event.y < y + height):
                return None
        index = self._index_from_iid(iid)
        if index is not None and 0 <= index < len(self.channels):
            return self.channels[index][0]
        try:
            text = self.tree.item(iid, 'text') or None
        except tk.TclError:
            return None
        if text and '  ·  ' in text:
            return text.split('  ·  ', 1)[0]
        return text

    def selected_index(self):
        """Selected index."""
        if self.mode == 'virtual':
            return self._selected
        try:
            selection = self.tree.selection()
        except tk.TclError:
            return None
        if not selection:
            return None
        return self._index_from_iid(selection[0])

    def select(self, index):
        """Select."""
        if index is None or not (0 <= index < len(self.channels)):
            self._selected = None
            try:
                self.tree.selection_remove(self.tree.selection())
            except tk.TclError:
                pass
            return
        if self.mode == 'catalog':
            group = (self.groups[index] or '').strip() or UNGROUPED
            self.set_active_group(group)
        self._selected = index
        if self.mode == 'virtual':
            self.see(index)
            self._paint_virtual_selection()
            return
        iid = f'c:{index}'
        if self._view_indices is not None and index not in self._view_indices:
            group = (self.groups[index] or '').strip() or UNGROUPED
            self.set_active_group(group)
        try:
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.tree.see(iid)
        except tk.TclError:
            pass

    def see(self, index):
        """See."""
        if index is None or not (0 <= index < len(self.channels)):
            return
        if self.mode == 'catalog':
            group = (self.groups[index] or '').strip() or UNGROUPED
            self.set_active_group(group)
        if self._view_indices is not None and index not in self._view_indices:
            group = (self.groups[index] or '').strip() or UNGROUPED
            self.set_active_group(group)
        if self.mode == 'virtual':
            vis = self._visible_rows()
            if self._view_indices is not None:
                try:
                    abs_row = self._view_indices.index(index)
                except ValueError:
                    return
            else:
                abs_row = index
            if abs_row < self._virtual_start:
                self._virtual_start = abs_row
            elif abs_row >= self._virtual_start + vis:
                self._virtual_start = abs_row - vis + 1
            self._refresh_virtual()
            return
        iid = f'c:{index}'
        try:
            if self.tree.exists(iid):
                self.tree.see(iid)
        except tk.TclError:
            pass

    def _expand_for_index(self, index):
        """Uso interno: expand for index."""
        if not (0 <= index < len(self.groups)):
            return
        group = (self.groups[index] or '').strip() or UNGROUPED
        self.set_active_group(group)

    def set_item_name(self, index, name):
        """Establece item name."""
        if not (0 <= index < len(self.channels)):
            return
        clean = plain_display_text(name, name)
        self.channels[index] = (clean, self.channels[index][1])
        iid = f'c:{index}'
        try:
            if self.tree.exists(iid):
                self.tree.item(iid, **self._item_kwargs(index))
                return
        except tk.TclError:
            return
        if self.mode == 'virtual':
            row = self._virtual_row_of(index)
            if row is not None and 0 <= row < self._pool:
                try:
                    self.tree.item(f'v:{row}', **self._item_kwargs(index))
                except tk.TclError:
                    pass

    def clear(self):
        """Clear."""
        self.channels = []
        self.groups = []
        self._order = []
        self._buckets = {}
        self._active_group = ALL_GROUPS
        self._view_indices = None
        self._selected = None
        self._virtual_start = 0
        self.mode = 'flat'
        self._clear_tree()
        self._use_native_scroll()
        try:
            self.picker_frame.pack_forget()
        except tk.TclError:
            pass
