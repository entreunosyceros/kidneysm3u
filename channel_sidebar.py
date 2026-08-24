"""Lista lateral del reproductor: grupos bajo demanda y vista virtual."""

import tkinter as tk
from tkinter import ttk

from ui_theme import get_colors, get_font

VIRTUAL_MIN = 2500
CHUNK = 200
ROW_HEIGHT = 26
UNGROUPED = 'Sin grupo'


def _group_buckets(groups):
    order = []
    buckets = {}
    for index, group in enumerate(groups):
        key = (group or '').strip() or UNGROUPED
        if key not in buckets:
            order.append(key)
            buckets[key] = []
        buckets[key].append(index)
    return order, buckets


class ChannelSidebar:
    def __init__(self, parent, scrollbar):
        self.scrollbar = scrollbar
        self.tree = ttk.Treeview(
            parent,
            show='tree',
            selectmode='browse',
            takefocus=True,
        )
        self.tree.column('#0', width=220, minwidth=80, stretch=True)
        self.mode = 'flat'
        self.channels = []
        self.groups = []
        self._virtual_start = 0
        self._pool = 0
        self._selected = None
        self._loaded_groups = set()
        self._group_items = {}
        self._fill_job = None
        self._rebuild_gen = 0
        self.tree.bind('<<TreeviewOpen>>', self._on_open)
        self.tree.bind('<<TreeviewClose>>', self._on_close)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Configure>', self._on_configure)
        self.tree.bind('<Button-4>', self._on_wheel)
        self.tree.bind('<Button-5>', self._on_wheel)
        self.tree.bind('<MouseWheel>', self._on_wheel)
        self._apply_tags()
        self._use_native_scroll()

    def _apply_tags(self):
        colors = get_colors()
        try:
            self.tree.tag_configure('group', font=get_font(9, 'bold'), foreground=colors['text_muted'])
        except tk.TclError:
            pass

    def refresh_theme(self):
        self._apply_tags()

    def _cancel_fill(self):
        self._rebuild_gen += 1
        job = self._fill_job
        self._fill_job = None
        if job:
            try:
                self.tree.after_cancel(job)
            except tk.TclError:
                pass

    def _clear_tree(self):
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
        try:
            self.scrollbar.configure(command=self.tree.yview)
            self.tree.configure(yscrollcommand=self.scrollbar.set)
        except tk.TclError:
            pass

    def _use_virtual_scroll(self):
        try:
            self.scrollbar.configure(command=self._virtual_scroll)
            self.tree.configure(yscrollcommand='')
        except tk.TclError:
            pass
        self._sync_virtual_scrollbar()

    def rebuild(self, channels, groups=None):
        self.channels = list(channels or [])
        if groups is None or len(groups) != len(self.channels):
            self.groups = [''] * len(self.channels)
        else:
            self.groups = list(groups)
        self._selected = None
        self._virtual_start = 0
        self._clear_tree()
        count = len(self.channels)
        order, buckets = _group_buckets(self.groups)
        if count >= 2 and len(order) >= 2:
            self.mode = 'groups'
            self._use_native_scroll()
            self._build_groups(order, buckets)
            return
        if count >= VIRTUAL_MIN:
            self.mode = 'virtual'
            self._use_virtual_scroll()
            self._refresh_virtual()
            return
        self.mode = 'flat'
        self._use_native_scroll()
        self._fill_flat(0, self._rebuild_gen)

    def _build_groups(self, order, buckets):
        self._group_items = {}
        for offset, name in enumerate(order):
            gid = f'g:{offset}'
            indices = buckets[name]
            self._group_items[gid] = indices
            label = f'{name} ({len(indices)})'
            self.tree.insert('', 'end', iid=gid, text=label, tags=('group',), open=False)
            self.tree.insert(gid, 'end', iid=f'{gid}:ph', text='…')

    def _fill_flat(self, start, gen):
        if gen != self._rebuild_gen:
            return
        end = min(len(self.channels), start + CHUNK)
        for index in range(start, end):
            name = self.channels[index][0]
            try:
                self.tree.insert('', 'end', iid=f'c:{index}', text=name)
            except tk.TclError:
                return
        if end < len(self.channels):
            self._fill_job = self.tree.after(1, lambda: self._fill_flat(end, gen))
        else:
            self._fill_job = None

    def _group_iid(self, iid):
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

    def _on_select(self, event=None):
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
        iid = self._group_iid(self.tree.focus())
        if not iid or iid in self._loaded_groups:
            return
        self._load_group(iid)

    def _on_close(self, event=None):
        iid = self._group_iid(self.tree.focus())
        if not iid:
            return
        self.tree.after_idle(lambda group=iid: self._unload_group(group))

    def _load_group(self, gid):
        indices = self._group_items.get(gid) or []
        try:
            for child in self.tree.get_children(gid):
                self.tree.delete(child)
        except tk.TclError:
            return
        self._loaded_groups.add(gid)
        self._fill_group(gid, indices, 0, self._rebuild_gen)

    def _unload_group(self, gid):
        if gid not in self._loaded_groups:
            return
        try:
            if not self.tree.exists(gid) or self.tree.item(gid, 'open'):
                return
            for child in self.tree.get_children(gid):
                self.tree.delete(child)
            self.tree.insert(gid, 'end', iid=f'{gid}:ph', text='…')
        except tk.TclError:
            return
        self._loaded_groups.discard(gid)

    def _fill_group(self, gid, indices, start, gen):
        if gen != self._rebuild_gen or gid not in self._loaded_groups:
            return
        end = min(len(indices), start + CHUNK)
        for pos in range(start, end):
            index = indices[pos]
            name = self.channels[index][0]
            try:
                self.tree.insert(gid, 'end', iid=f'c:{index}', text=name)
            except tk.TclError:
                return
        if end < len(indices):
            self._fill_job = self.tree.after(1, lambda: self._fill_group(gid, indices, end, gen))
        else:
            self._fill_job = None

    def toggle_group(self, gid):
        if not gid or not self.tree.exists(gid):
            return
        opened = bool(self.tree.item(gid, 'open'))
        if opened:
            self.tree.item(gid, open=False)
            self._unload_group(gid)
            return
        self.tree.item(gid, open=True)
        self._load_group(gid)

    def _visible_rows(self):
        try:
            height = max(ROW_HEIGHT, int(self.tree.winfo_height() or 0))
        except tk.TclError:
            height = ROW_HEIGHT * 12
        return max(8, height // ROW_HEIGHT + 1)

    def _on_configure(self, event=None):
        if self.mode == 'virtual':
            self._refresh_virtual()

    def _on_wheel(self, event):
        if self.mode != 'virtual':
            return
        delta = -3
        if getattr(event, 'num', None) == 5 or getattr(event, 'delta', 0) < 0:
            delta = 3
        self._move_virtual(delta)
        return 'break'

    def _virtual_scroll(self, *args):
        n = len(self.channels)
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
        n = len(self.channels)
        vis = self._visible_rows()
        max_start = max(0, n - vis)
        self._virtual_start = max(0, min(max_start, self._virtual_start + delta))
        self._refresh_virtual()

    def _sync_virtual_scrollbar(self):
        n = max(1, len(self.channels))
        vis = min(self._visible_rows(), n)
        start = self._virtual_start / n
        end = (self._virtual_start + vis) / n
        try:
            self.scrollbar.set(start, min(1.0, end))
        except tk.TclError:
            pass

    def _refresh_virtual(self):
        n = len(self.channels)
        vis = self._visible_rows()
        max_start = max(0, n - vis)
        self._virtual_start = max(0, min(max_start, self._virtual_start))
        need = vis if n else 0
        for row in range(need):
            index = self._virtual_start + row
            text = self.channels[index][0] if index < n else ''
            iid = f'v:{row}'
            try:
                if self.tree.exists(iid):
                    self.tree.item(iid, text=text)
                else:
                    self.tree.insert('', 'end', iid=iid, text=text)
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
        if self._selected is None:
            try:
                self.tree.selection_remove(self.tree.selection())
            except tk.TclError:
                pass
            return
        row = self._selected - self._virtual_start
        iid = f'v:{row}'
        try:
            if 0 <= row < self._pool and self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.focus(iid)
            else:
                self.tree.selection_remove(self.tree.selection())
        except tk.TclError:
            pass

    def _index_from_iid(self, iid):
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
            index = self._virtual_start + row
            if 0 <= index < len(self.channels):
                return index
        return None

    def index_at(self, event):
        try:
            iid = self.tree.identify_row(event.y)
        except tk.TclError:
            return None
        return self._index_from_iid(iid)

    def group_at(self, event):
        try:
            iid = self.tree.identify_row(event.y)
        except tk.TclError:
            return None
        return self._group_iid(iid)

    def name_at(self, event):
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
        try:
            return self.tree.item(iid, 'text') or None
        except tk.TclError:
            return None

    def selected_index(self):
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
        if index is None or not (0 <= index < len(self.channels)):
            self._selected = None
            try:
                self.tree.selection_remove(self.tree.selection())
            except tk.TclError:
                pass
            return
        self._selected = index
        if self.mode == 'virtual':
            self.see(index)
            self._paint_virtual_selection()
            return
        iid = f'c:{index}'
        if self.mode == 'groups' and not self.tree.exists(iid):
            self._expand_for_index(index)
        try:
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.tree.see(iid)
        except tk.TclError:
            pass

    def see(self, index):
        if index is None or not (0 <= index < len(self.channels)):
            return
        if self.mode == 'virtual':
            vis = self._visible_rows()
            if index < self._virtual_start:
                self._virtual_start = index
            elif index >= self._virtual_start + vis:
                self._virtual_start = index - vis + 1
            self._refresh_virtual()
            return
        iid = f'c:{index}'
        if self.mode == 'groups' and not self.tree.exists(iid):
            self._expand_for_index(index)
        try:
            if self.tree.exists(iid):
                self.tree.see(iid)
        except tk.TclError:
            pass

    def _expand_for_index(self, index):
        for gid, indices in self._group_items.items():
            if index not in indices:
                continue
            try:
                self.tree.item(gid, open=True)
            except tk.TclError:
                return
            if gid not in self._loaded_groups:
                self._load_group(gid)
            return

    def set_item_name(self, index, name):
        if not (0 <= index < len(self.channels)):
            return
        self.channels[index] = (name, self.channels[index][1])
        iid = f'c:{index}'
        try:
            if self.tree.exists(iid):
                self.tree.item(iid, text=name)
                return
        except tk.TclError:
            return
        if self.mode == 'virtual':
            row = index - self._virtual_start
            if 0 <= row < self._pool:
                try:
                    self.tree.item(f'v:{row}', text=name)
                except tk.TclError:
                    pass

    def clear(self):
        self.channels = []
        self.groups = []
        self._selected = None
        self._virtual_start = 0
        self.mode = 'flat'
        self._clear_tree()
        self._use_native_scroll()
