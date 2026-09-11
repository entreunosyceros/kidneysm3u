"""Módulo de m3u sorter."""

import copy
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from ui_theme import style_window, style_listbox, style_text, set_window_icon
from ui_layout import bind_wraplength, setup_resizable_dialog
from ui_toast import show_toast


class M3USorter:
    """Clase que representa m3usorter."""

    def __init__(self, root, input_file):
        """Inicializa M3USorter."""
        self.window = tk.Toplevel(root)
        self.window.title('Ordenar Lista M3U')
        setup_resizable_dialog(self.window, 860, 640, 640, 420)
        style_window(self.window)
        set_window_icon(self.window)

        self.input_file = input_file
        self.channels = []
        self.clipboard = []
        self.last_selection = None
        self.drag_start_index = None
        self._visible = []
        self._undo_stack = []
        self._redo_stack = []
        self._max_history = 40

        self.create_widgets()
        self.load_channels()

    def create_widgets(self):
        """Crea widgets."""
        main_frame = ttk.Frame(self.window, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text='Ordenar lista M3U', style='PageTitle.TLabel').pack(anchor=tk.W)
        ttk.Label(
            main_frame,
            text='Busca, edita y reordena canales antes de guardar',
            style='Muted.TLabel',
        ).pack(anchor=tk.W, pady=(0, 12))

        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text='Buscar', style='Muted.TLabel').pack(side=tk.LEFT, padx=(0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', self.filter_channels)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.selection_bar = ttk.Frame(main_frame)
        self.selection_bar.pack(fill=tk.X, pady=(0, 8))
        self.selection_var = tk.StringVar(value='Ningún canal seleccionado')
        ttk.Label(self.selection_bar, textvariable=self.selection_var, style='Muted.TLabel').pack(
            side=tk.LEFT, padx=(0, 12),
        )
        ttk.Button(
            self.selection_bar, text='Cambiar grupo…', command=self.change_group,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            self.selection_bar, text='Deshacer', command=self.undo,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            self.selection_bar, text='Rehacer', command=self.redo,
        ).pack(side=tk.LEFT)

        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.channels_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, exportselection=False)
        self.channels_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        style_listbox(self.channels_listbox)
        self.channels_listbox.bind('<<ListboxSelect>>', self._on_selection_changed)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.channels_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.channels_listbox.config(yscrollcommand=scrollbar.set)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)
        for col in range(4):
            buttons_frame.columnconfigure(col, weight=1 if col == 3 else 0)

        self.drag_enabled = tk.BooleanVar(value=False)

        ttk.Button(buttons_frame, text='Cortar', command=self.cut_channels).grid(
            row=0, column=0, padx=(0, 6), pady=(0, 6), sticky=tk.W,
        )
        ttk.Button(buttons_frame, text='Copiar', command=self.copy_channels).grid(
            row=0, column=1, padx=(0, 6), pady=(0, 6), sticky=tk.W,
        )
        ttk.Button(buttons_frame, text='Pegar', command=self.paste_channels).grid(
            row=0, column=2, padx=(0, 6), pady=(0, 6), sticky=tk.W,
        )
        ttk.Button(buttons_frame, text='Eliminar', command=self.delete_channels).grid(
            row=0, column=3, padx=(0, 6), pady=(0, 6), sticky=tk.W,
        )
        ttk.Button(buttons_frame, text='Editar canal', command=self.edit_channel).grid(
            row=1, column=0, padx=(0, 6), sticky=tk.W,
        )
        ttk.Button(buttons_frame, text='Cambiar grupo', command=self.change_group).grid(
            row=1, column=1, padx=(0, 6), sticky=tk.W,
        )
        ttk.Checkbutton(
            buttons_frame,
            text='Drag & drop',
            variable=self.drag_enabled,
            command=self.toggle_drag_drop,
        ).grid(row=1, column=2, padx=(8, 0), sticky=tk.W)
        ttk.Button(
            buttons_frame, text='Guardar', style='Accent.TButton', command=self.save_channels,
        ).grid(row=1, column=3, sticky=tk.E)

        self.window.bind('<Control-x>', lambda e: self.cut_channels())
        self.window.bind('<Control-c>', lambda e: self.copy_channels())
        self.window.bind('<Control-v>', lambda e: self.paste_channels())
        self.window.bind('<Delete>', lambda e: self.delete_channels())
        self.window.bind('<Control-a>', lambda e: self.select_all())
        self.window.bind('<Control-z>', lambda e: self.undo())
        self.window.bind('<Control-y>', lambda e: self.redo())
        self.window.bind('<Control-Z>', lambda e: self.undo())
        self.window.bind('<Control-Y>', lambda e: self.redo())

    def _snapshot(self):
        """Copia profunda del estado de canales."""
        return copy.deepcopy(self.channels)

    def _push_undo(self):
        """Guarda estado actual en la pila de deshacer."""
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_history_hint()

    def _update_history_hint(self):
        """Actualiza el texto de selección incluyendo historial."""
        count = len(self._selected_channel_indices())
        parts = []
        if count:
            parts.append(f'{count} seleccionado{"s" if count != 1 else ""}')
        else:
            parts.append('Ningún canal seleccionado')
        if self._undo_stack or self._redo_stack:
            parts.append(
                f'Deshacer {len(self._undo_stack)} · Rehacer {len(self._redo_stack)}'
            )
        self.selection_var.set('  ·  '.join(parts))

    def _on_selection_changed(self, event=None):
        """Actualiza la barra de multi-selección."""
        self._update_history_hint()

    def undo(self, event=None):
        """Deshace el último cambio."""
        if not self._undo_stack:
            return 'break'
        self._redo_stack.append(self._snapshot())
        self.channels = self._undo_stack.pop()
        self._rebuild_listbox()
        self._update_history_hint()
        show_toast(self.window, 'Deshecho', duration_ms=1600)
        return 'break'

    def redo(self, event=None):
        """Rehace el último cambio deshecho."""
        if not self._redo_stack:
            return 'break'
        self._undo_stack.append(self._snapshot())
        self.channels = self._redo_stack.pop()
        self._rebuild_listbox()
        self._update_history_hint()
        show_toast(self.window, 'Rehecho', duration_ms=1600)
        return 'break'

    def _selected_listbox_indices(self):
        """Índices de la listbox (vista filtrada)."""
        return list(self.channels_listbox.curselection())

    def _selected_channel_indices(self):
        """Índices reales en self.channels."""
        out = []
        for i in self._selected_listbox_indices():
            if 0 <= i < len(self._visible):
                out.append(self._visible[i])
        return out

    def _rebuild_listbox(self, keep_selection=None):
        """Vuelve a pintar la lista según el filtro."""
        term = (self.search_var.get() or '').strip().lower()
        self.channels_listbox.delete(0, tk.END)
        self._visible = []
        for i, (extinf_line, _) in enumerate(self.channels):
            name = self.get_channel_name(extinf_line)
            if term and term not in name.lower():
                continue
            self._visible.append(i)
            self.channels_listbox.insert(tk.END, name)
        if keep_selection:
            wanted = set(keep_selection)
            for list_i, ch_i in enumerate(self._visible):
                if ch_i in wanted:
                    self.channels_listbox.selection_set(list_i)

    def select_all(self, event=None):
        """Select all."""
        self.channels_listbox.select_set(0, tk.END)
        self._on_selection_changed()
        return 'break'

    def copy_channels(self, event=None):
        """Copia canales."""
        selected = self._selected_channel_indices()
        if not selected:
            return
        self.clipboard = [self.channels[i] for i in selected]

    def paste_channels(self):
        """Paste canales."""
        if not self.clipboard:
            return
        self._push_undo()
        selected = self._selected_channel_indices()
        insert_index = selected[0] if selected else len(self.channels)
        for offset, channel in enumerate(self.clipboard):
            self.channels.insert(insert_index + offset, copy.deepcopy(channel))
        self._rebuild_listbox(keep_selection=list(range(insert_index, insert_index + len(self.clipboard))))

    def delete_channels(self, event=None):
        """Elimina canales."""
        selected = self._selected_channel_indices()
        if not selected:
            return
        self._push_undo()
        for i in reversed(selected):
            self.channels.pop(i)
        self._rebuild_listbox()
        self._update_history_hint()

    def load_channels(self):
        """Carga canales."""
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            i = 0
            while i < len(lines):
                if lines[i].startswith('#EXTINF:'):
                    if i + 1 < len(lines):
                        self.channels.append((lines[i], lines[i + 1]))
                        i += 2
                    else:
                        i += 1
                else:
                    i += 1
            self._rebuild_listbox()
            self._update_history_hint()

        except Exception as e:
            messagebox.showerror('Error', f'Error al cargar el archivo: {str(e)}')

    def get_channel_name(self, extinf_line):
        """Obtiene canal name."""
        try:
            return extinf_line.split(',')[-1].strip()
        except Exception:
            return 'Canal sin nombre'

    def edit_channel(self):
        """Edit canal."""
        selected = self._selected_channel_indices()
        if not selected:
            return

        index = selected[0]
        extinf_line, url_line = self.channels[index]

        edit_window = tk.Toplevel(self.window)
        edit_window.title('Editar Canal')
        setup_resizable_dialog(edit_window, 640, 340, 480, 280)
        style_window(edit_window)
        set_window_icon(edit_window)

        edit_frame = ttk.Frame(edit_window, padding=16)
        edit_frame.pack(fill=tk.BOTH, expand=True)
        edit_frame.rowconfigure(1, weight=1)
        edit_frame.rowconfigure(3, weight=1)
        edit_frame.columnconfigure(0, weight=1)

        ttk.Label(edit_frame, text='Información del canal', style='Muted.TLabel').grid(
            row=0, column=0, sticky=tk.W, pady=(0, 6),
        )
        info_text = tk.Text(edit_frame, height=5)
        info_text.insert('1.0', extinf_line)
        info_text.grid(row=1, column=0, sticky='nsew', pady=(0, 12))
        style_text(info_text)

        ttk.Label(edit_frame, text='URL', style='Muted.TLabel').grid(
            row=2, column=0, sticky=tk.W, pady=(0, 6),
        )
        url_text = tk.Text(edit_frame, height=2)
        url_text.insert('1.0', url_line)
        url_text.grid(row=3, column=0, sticky='nsew', pady=(0, 16))
        style_text(url_text)

        def save_changes():
            """Guarda changes."""
            self._push_undo()
            new_extinf = info_text.get('1.0', 'end-1c')
            new_url = url_text.get('1.0', 'end-1c')
            self.channels[index] = (new_extinf + '\n', new_url + '\n')
            self._rebuild_listbox(keep_selection=[index])
            edit_window.destroy()

        ttk.Button(edit_frame, text='Guardar', style='Accent.TButton', command=save_changes).grid(
            row=4, column=0, sticky=tk.E,
        )
        bind_wraplength(edit_window, padding=32)

    def save_channels(self):
        """Guarda canales."""
        output_file = filedialog.asksaveasfilename(
            defaultextension='.m3u',
            filetypes=[('Archivos M3U', '*.m3u')],
            initialfile='lista_ordenada.m3u'
        )

        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('#EXTM3U\n')
                    for extinf_line, url_line in self.channels:
                        f.write(extinf_line)
                        f.write(url_line)
                show_toast(self.window, 'Lista guardada correctamente', kind='ok')
                self.window.after(900, self.window.destroy)
            except Exception as e:
                messagebox.showerror('Error', f'Error al guardar el archivo: {str(e)}')

    def toggle_drag_drop(self):
        """Alterna drag drop."""
        if self.drag_enabled.get():
            self.channels_listbox.bind('<Button-1>', self.on_click)
            self.channels_listbox.bind('<B1-Motion>', self.on_drag)
            self.channels_listbox.bind('<ButtonRelease-1>', self.on_drop)
        else:
            self.channels_listbox.unbind('<Button-1>')
            self.channels_listbox.unbind('<B1-Motion>')
            self.channels_listbox.unbind('<ButtonRelease-1>')

    def on_click(self, event):
        """Responde al evento click."""
        self.drag_start_index = self.channels_listbox.nearest(event.y)
        self._drag_undo_ready = True

    def on_drag(self, event):
        """Responde al evento drag."""
        drag_index = self.channels_listbox.nearest(event.y)
        if drag_index != self.drag_start_index:
            self.move_channels(self.drag_start_index, drag_index, push_undo=self._drag_undo_ready)
            self._drag_undo_ready = False
            self.drag_start_index = drag_index

    def on_drop(self, event):
        """Responde al evento drop."""
        self._drag_undo_ready = False

    def move_channels(self, from_index, to_index, push_undo=True):
        """Mueve canales (índices de listbox)."""
        if from_index is None or to_index is None:
            return
        if not (0 <= from_index < len(self._visible) and 0 <= to_index < len(self._visible)):
            return
        if push_undo:
            self._push_undo()
        selected_list = self._selected_listbox_indices() or [from_index]
        channel_indices = [self._visible[i] for i in selected_list if 0 <= i < len(self._visible)]
        if not channel_indices:
            return
        selected_channels = [self.channels[i] for i in channel_indices]
        for i in reversed(sorted(set(channel_indices))):
            self.channels.pop(i)
        target_channel = self._visible[to_index]
        removed_before = sum(1 for i in channel_indices if i < target_channel)
        insert_at = max(0, target_channel - removed_before)
        if to_index > from_index:
            insert_at = max(0, insert_at - len(selected_channels) + 1)
        for offset, channel in enumerate(selected_channels):
            self.channels.insert(insert_at + offset, channel)
        keep = list(range(insert_at, insert_at + len(selected_channels)))
        self._rebuild_listbox(keep_selection=keep)

    def cut_channels(self):
        """Cut canales."""
        self.copy_channels()
        self.delete_channels()

    def change_group(self):
        """Change group."""
        selected = self._selected_channel_indices()
        if not selected:
            return

        count = len(selected)
        prompt = f'Nuevo grupo para {count} canal{"es" if count != 1 else ""}:'
        new_group = simpledialog.askstring('Cambiar grupo', prompt, parent=self.window)
        if not new_group:
            return
        self._push_undo()
        for i in selected:
            extinf_line, url = self.channels[i]
            updated_line = re.sub(
                r'(group-title=")[^"]*(")',
                f'\\1{new_group}\\2',
                extinf_line,
                flags=re.IGNORECASE
            )
            if 'group-title=' not in updated_line.lower():
                updated_line = extinf_line.replace(
                    '#EXTINF:', f'#EXTINF: group-title="{new_group}",', 1,
                )
            self.channels[i] = (updated_line, url)
        self._rebuild_listbox(keep_selection=selected)
        self._update_history_hint()
        show_toast(self.window, f'Grupo «{new_group}» aplicado a {count}', kind='ok')

    def filter_channels(self, *args):
        """Filtra canales."""
        keep = self._selected_channel_indices()
        self._rebuild_listbox(keep_selection=keep)
        self._update_history_hint()
