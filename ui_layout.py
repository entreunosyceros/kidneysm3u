"""Utilidades de layout adaptable para ventanas Tk."""

import tkinter as tk
from tkinter import ttk

from ui_theme import center_window, get_colors


def walk_wraplength(widget, wrap):
    """Actualiza wraplength en widget y descendientes que lo tengan."""
    for child in widget.winfo_children():
        try:
            if int(child.cget('wraplength') or 0) > 0:
                child.configure(wraplength=wrap)
        except (tk.TclError, TypeError, ValueError):
            pass
        walk_wraplength(child, wrap)


def bind_wraplength(root, padding=36, min_wrap=240):
    """Enlaza <Configure> para reflow de etiquetas con wraplength."""
    last = {'value': 0}

    def _sync(_event=None):
        """Uso interno: sync."""
        try:
            width = max(1, int(root.winfo_width()))
        except tk.TclError:
            return
        wrap = max(min_wrap, width - padding)
        if wrap == last['value']:
            return
        last['value'] = wrap
        walk_wraplength(root, wrap)

    root.bind('<Configure>', _sync, add='+')
    root.after_idle(_sync)
    return _sync


def bind_mousewheel(canvas, *widgets):
    """Rueda del ratón en canvas y widgets del scroll shell."""

    def _on_wheel(event):
        """Callback interno para wheel."""
        if getattr(event, 'num', None) == 5:
            steps = 1
        elif getattr(event, 'num', None) == 4:
            steps = -1
        else:
            delta = getattr(event, 'delta', 0) or 0
            if not delta:
                return
            steps = int(-delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        canvas.yview_scroll(steps, 'units')
        return 'break'

    def _bind_recursive(widget):
        """Uso interno: bind recursive."""
        widget.bind('<MouseWheel>', _on_wheel, add='+')
        widget.bind('<Button-4>', _on_wheel, add='+')
        widget.bind('<Button-5>', _on_wheel, add='+')
        for child in widget.winfo_children():
            _bind_recursive(child)

    _bind_recursive(canvas)
    for widget in widgets:
        if widget is not None:
            _bind_recursive(widget)


def make_vertical_scroll(parent, padding=(0, 0, 8, 4), wrap_padding=36, min_wrap=240):
    """
    Canvas + scrollbar vertical con inner frame expandible.
    Devuelve (canvas, inner_frame, sync_fn).
    """
    colors = get_colors()
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)

    canvas = tk.Canvas(parent, bg=colors['bg'], highlightthickness=0, bd=0)
    scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.grid(row=0, column=0, sticky='nsew')
    scroll.grid(row=0, column=1, sticky='ns', padx=(4, 0))

    inner = ttk.Frame(canvas, padding=padding)
    inner_id = canvas.create_window((0, 0), window=inner, anchor='nw')
    syncing = {'on': False}
    last_wrap = {'value': 0}

    def sync(_event=None):
        """Sync."""
        if syncing['on']:
            return
        syncing['on'] = True
        try:
            width = max(1, int(canvas.winfo_width()))
            canvas.itemconfigure(inner_id, width=width)
            wrap = max(min_wrap, width - wrap_padding)
            if wrap != last_wrap['value']:
                last_wrap['value'] = wrap
                walk_wraplength(inner, wrap)
            canvas.configure(scrollregion=canvas.bbox('all') or (0, 0, 0, 0))
        except tk.TclError:
            pass
        finally:
            syncing['on'] = False

    inner.bind('<Configure>', sync, add='+')
    canvas.bind('<Configure>', sync, add='+')
    bind_mousewheel(canvas, inner)
    return canvas, inner, sync


def wraplength_for(width, padding=28, min_wrap=120, max_wrap=720):
    """Wraplength for."""
    return max(min_wrap, min(int(width) - padding, max_wrap))


def bind_loading_card(overlay, card, labels, thumb_wrap=None, max_thumb=(440, 248)):
    """Ajusta wraplength y miniatura del overlay de carga al tamaño del vídeo."""

    def sync(_event=None):
        """Sync."""
        try:
            width = max(1, int(overlay.winfo_width()))
        except tk.TclError:
            return
        wrap = wraplength_for(width, padding=44, min_wrap=120, max_wrap=max_thumb[0])
        for label in labels:
            if label is None:
                continue
            try:
                if int(label.cget('wraplength') or 0) > 0:
                    label.configure(wraplength=wrap)
            except tk.TclError:
                pass
        if thumb_wrap is not None:
            tw = max(160, min(wrap, max_thumb[0]))
            th = max(90, min(int(tw * 9 / 16), max_thumb[1]))
            try:
                thumb_wrap.configure(width=tw, height=th)
            except tk.TclError:
                pass
        rescale = getattr(overlay, '_thumb_rescale_cb', None)
        if callable(rescale):
            rescale()

    overlay.bind('<Configure>', sync, add='+')
    card.bind('<Configure>', sync, add='+')
    overlay.after_idle(sync)
    return sync


def setup_resizable_dialog(window, width, height, min_width=None, min_height=None):
    """Geometry, minsize, resizable y centrado estándar."""
    window.geometry(f'{width}x{height}')
    if min_width is not None and min_height is not None:
        window.minsize(min_width, min_height)
    window.resizable(True, True)
    center_window(window, width, height)


def bind_tree_stretch(tree, stretch_columns=None):
    """Columnas Treeview que crecen con el ancho de la ventana."""
    if stretch_columns is None:
        stretch_columns = ('#0',)
    for col in stretch_columns:
        try:
            tree.column(col, stretch=True)
        except tk.TclError:
            pass

    def _resize(_event=None):
        """Uso interno: resize."""
        try:
            total = max(tree.winfo_width(), 1)
        except tk.TclError:
            return
        cols = tree['columns'] or ()
        all_cols = ('#0',) + tuple(cols)
        stretch = [c for c in stretch_columns if c in all_cols]
        fixed = [c for c in all_cols if c not in stretch]
        fixed_w = sum(int(tree.column(c, 'width') or 0) for c in fixed)
        remain = max(80, total - fixed_w - 24)
        if stretch:
            each = max(60, remain // len(stretch))
            for col in stretch:
                try:
                    tree.column(col, width=each)
                except tk.TclError:
                    pass

    tree.bind('<Configure>', _resize, add='+')
    return _resize
