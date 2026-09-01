"""Pegar y menú contextual en campos de texto (Ctrl+V y clic derecho)."""

import tkinter as tk
from tkinter import ttk


def clipboard_text(widget):
    """Clipboard text."""
    try:
        return widget.clipboard_get()
    except tk.TclError:
        return ''


def insert_clipboard_text(widget, text):
    """Sustituye la selección o inserta en el cursor. Usa el portapapeles del sistema (CLIPBOARD)."""
    if text is None:
        return
    try:
        state = str(widget.cget('state'))
    except tk.TclError:
        state = 'normal'
    if state in ('disabled', 'readonly'):
        return
    try:
        widget.delete('sel.first', 'sel.last')
    except tk.TclError:
        pass
    try:
        widget.insert('insert', text)
    except tk.TclError:
        try:
            widget.insert(tk.END, text)
        except tk.TclError:
            pass


def paste_clipboard(widget):
    """Paste clipboard."""
    insert_clipboard_text(widget, clipboard_text(widget))


def _on_paste(event):
    """Callback interno para paste."""
    paste_clipboard(event.widget)
    return 'break'


def _on_cut(event):
    """Callback interno para cut."""
    widget = event.widget
    try:
        selected = widget.selection_get()
    except tk.TclError:
        return 'break'
    try:
        widget.clipboard_clear()
        widget.clipboard_append(selected)
        widget.delete('sel.first', 'sel.last')
    except tk.TclError:
        pass
    return 'break'


def _on_copy(event):
    """Callback interno para copy."""
    widget = event.widget
    try:
        selected = widget.selection_get()
    except tk.TclError:
        return 'break'
    try:
        widget.clipboard_clear()
        widget.clipboard_append(selected)
    except tk.TclError:
        pass
    return 'break'


def _on_select_all(event):
    """Callback interno para select all."""
    widget = event.widget
    try:
        widget.selection_range(0, tk.END)
        widget.icursor(tk.END)
    except tk.TclError:
        pass
    return 'break'


def _show_entry_menu(event):
    """Uso interno: show entry menu."""
    widget = event.widget
    from ui_theme import style_menu_tree

    menu = tk.Menu(widget, tearoff=0)
    style_menu_tree(menu)
    menu.add_command(label='Cortar', command=lambda: _on_cut(event))
    menu.add_command(label='Copiar', command=lambda: _on_copy(event))
    menu.add_command(label='Pegar', command=lambda: _on_paste(event))
    menu.add_separator()
    menu.add_command(label='Seleccionar todo', command=lambda: _on_select_all(event))
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        try:
            menu.grab_release()
        except tk.TclError:
            pass
    return 'break'


_ENTRY_CLASSES = ('Entry', 'TEntry', 'TCombobox')
_PASTE_SEQS = ('<Control-v>', '<Control-V>', '<Shift-Insert>')
_CUT_SEQS = ('<Control-x>', '<Control-X>', '<Shift-Delete>')
_COPY_SEQS = ('<Control-c>', '<Control-C>', '<Control-Insert>')
_SELECT_SEQS = ('<Control-a>', '<Control-A>')
_MENU_SEQS = ('<Button-3>', '<Shift-F10>')


def bind_entry_clipboard(widget):
    """Atajos y menú contextual en un Entry/Combobox concreto."""
    for seq in _PASTE_SEQS:
        widget.bind(seq, _on_paste)
    for seq in _CUT_SEQS:
        widget.bind(seq, _on_cut)
    for seq in _COPY_SEQS:
        widget.bind(seq, _on_copy)
    for seq in _SELECT_SEQS:
        widget.bind(seq, _on_select_all)
    for seq in _MENU_SEQS:
        widget.bind(seq, _show_entry_menu)


def install_entry_clipboard(root):
    """Activa pegar (CLIPBOARD) y clic derecho en todos los campos de texto de esta app."""
    if getattr(root, '_kidneys_clipboard', False):
        return
    root._kidneys_clipboard = True
    for cls in _ENTRY_CLASSES:
        for seq in _PASTE_SEQS:
            root.bind_class(cls, seq, _on_paste, add=False)
        for seq in _CUT_SEQS:
            root.bind_class(cls, seq, _on_cut, add=False)
        for seq in _COPY_SEQS:
            root.bind_class(cls, seq, _on_copy, add=False)
        for seq in _SELECT_SEQS:
            root.bind_class(cls, seq, _on_select_all, add=False)
        for seq in _MENU_SEQS:
            root.bind_class(cls, seq, _show_entry_menu, add=False)


def ask_string(parent, title, prompt, initialvalue='', width=64):
    """Diálogo de una línea con Ctrl+V y clic derecho para pegar."""
    from ui_theme import center_window, set_window_icon, style_window

    result = {'value': None}
    window = tk.Toplevel(parent)
    window.title(title)
    window.transient(parent)
    window.resizable(True, True)
    style_window(window)
    set_window_icon(window)

    shell = ttk.Frame(window, padding=16)
    shell.pack(fill=tk.BOTH, expand=True)
    prompt_label = ttk.Label(shell, text=prompt, wraplength=480)
    prompt_label.pack(anchor=tk.W, pady=(0, 8))
    from ui_layout import bind_wraplength
    bind_wraplength(shell, padding=32)
    entry = ttk.Entry(shell, width=width)
    entry.pack(fill=tk.X)
    bind_entry_clipboard(entry)
    if initialvalue:
        entry.insert(0, initialvalue)
        entry.selection_range(0, tk.END)
    entry.focus_set()

    buttons = ttk.Frame(shell)
    buttons.pack(fill=tk.X, pady=(14, 0))

    def accept(_event=None):
        """Accept."""
        result['value'] = entry.get()
        window.destroy()

    def cancel(_event=None):
        """Cancel."""
        result['value'] = None
        window.destroy()

    ttk.Button(buttons, text='Cancelar', command=cancel).pack(side=tk.RIGHT)
    ttk.Button(buttons, text='Aceptar', style='Accent.TButton', command=accept).pack(
        side=tk.RIGHT, padx=(0, 8)
    )
    window.bind('<Return>', accept)
    window.bind('<Escape>', cancel)
    window.protocol('WM_DELETE_WINDOW', cancel)
    try:
        window.grab_set()
    except tk.TclError:
        pass
    center_window(window, 520, 160)
    parent.wait_window(window)
    return result['value']
