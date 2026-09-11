"""Toasts no bloqueantes (avisos temporales sobre la ventana)."""

import tkinter as tk

from ui_theme import get_colors, get_font

_ACTIVE = []


def show_toast(parent, text, *, duration_ms=3200, kind='info'):
    """Muestra un aviso flotante que se desvanece solo."""
    text = (text or '').strip()
    if not text or parent is None:
        return None
    try:
        if not parent.winfo_exists():
            return None
    except tk.TclError:
        return None

    colors = get_colors()
    if kind == 'ok':
        bg, fg = colors['accent'], colors['accent_text']
    elif kind == 'error':
        bg, fg = colors['danger'], colors['danger_text']
    else:
        bg, fg = colors['surface_alt'], colors['text']

    toast = tk.Toplevel(parent)
    try:
        toast.overrideredirect(True)
    except tk.TclError:
        pass
    try:
        toast.attributes('-topmost', True)
    except tk.TclError:
        pass
    try:
        toast.wm_attributes('-type', 'notification')
    except tk.TclError:
        pass
    toast.configure(bg=bg)
    label = tk.Label(
        toast,
        text=text,
        bg=bg,
        fg=fg,
        font=get_font(10),
        padx=14,
        pady=10,
        wraplength=360,
        justify=tk.LEFT,
    )
    label.pack()

    def _place():
        try:
            parent.update_idletasks()
            toast.update_idletasks()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            tw = toast.winfo_reqwidth()
            th = toast.winfo_reqheight()
            x = px + max(12, pw - tw - 18)
            y = py + max(12, ph - th - 24)
            toast.geometry(f'+{int(x)}+{int(y)}')
        except tk.TclError:
            pass

    def _fade(step=0):
        try:
            if not toast.winfo_exists():
                return
            alpha = max(0.0, 1.0 - (step / 8.0))
            try:
                toast.attributes('-alpha', alpha)
            except tk.TclError:
                pass
            if alpha <= 0.05:
                _close()
                return
            toast.after(40, lambda: _fade(step + 1))
        except tk.TclError:
            pass

    def _close():
        try:
            if toast in _ACTIVE:
                _ACTIVE.remove(toast)
        except ValueError:
            pass
        try:
            toast.destroy()
        except tk.TclError:
            pass

    _ACTIVE.append(toast)
    _place()
    try:
        toast.attributes('-alpha', 0.0)
        for i in range(1, 6):
            toast.after(i * 25, lambda a=i / 5.0: toast.attributes('-alpha', a))
    except tk.TclError:
        pass
    toast.after(max(800, int(duration_ms)), lambda: _fade(0))
    toast.bind('<Button-1>', lambda _e: _close())
    return toast
