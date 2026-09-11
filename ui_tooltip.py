"""Tooltip flotante reutilizable (controles, listas, etc.)."""

import tkinter as tk

from display_text import plain_display_text
from ui_theme import get_colors, get_font


class Tooltip:
    """Tooltip cerca del puntero del ratón."""

    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self._text = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text, x=None, y=None, wraplength=0):
        """Muestra el tooltip con el texto dado."""
        text = plain_display_text(text)
        if not text:
            self.hidetip()
            return
        if self.tipwindow and self._text == text:
            return
        self.hidetip()
        if x is None or y is None:
            x = self.widget.winfo_pointerx() + 16
            y = self.widget.winfo_pointery() + 12
        self._text = text
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{int(x)}+{int(y)}")
        try:
            tw.attributes('-topmost', True)
        except tk.TclError:
            pass
        colors = get_colors()
        label = tk.Label(
            tw,
            text=text,
            justify=tk.LEFT,
            background=colors['tooltip_bg'],
            foreground=colors['tooltip_fg'],
            relief=tk.FLAT,
            borderwidth=0,
            font=get_font(9),
            padx=8,
            pady=5,
            wraplength=wraplength,
        )
        label.pack()

    def hidetip(self):
        """Oculta el tooltip."""
        tw = self.tipwindow
        self.tipwindow = None
        self._text = None
        if tw:
            try:
                tw.destroy()
            except tk.TclError:
                pass
