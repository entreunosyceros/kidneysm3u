"""Módulo de test ui layout."""

import tkinter as tk
from tkinter import ttk

from ui_layout import bind_wraplength, make_vertical_scroll, walk_wraplength


def test_walk_wraplength_updates_descendants():
    """Prueba walk wraplength updates descendants."""
    root = tk.Tk()
    root.withdraw()
    frame = ttk.Frame(root)
    label = ttk.Label(frame, text='Texto largo de prueba', wraplength=400)
    label.pack()
    walk_wraplength(frame, 280)
    assert int(label.cget('wraplength')) == 280
    root.destroy()


def test_bind_wraplength_on_configure():
    """Prueba bind wraplength on configure."""
    root = tk.Tk()
    root.withdraw()
    root.geometry('420x120')
    label = ttk.Label(root, text='Contenido adaptable', wraplength=360)
    label.pack(fill=tk.X)
    bind_wraplength(root, padding=40)
    root.update_idletasks()
    root.geometry('300x120')
    root.update_idletasks()
    assert int(label.cget('wraplength')) == 260
    root.destroy()


def test_make_vertical_scroll_syncs_inner_width():
    """Prueba make vertical scroll syncs inner width."""
    root = tk.Tk()
    root.withdraw()
    shell = ttk.Frame(root)
    shell.pack(fill=tk.BOTH, expand=True)
    shell.configure(width=360, height=200)
    canvas, inner, sync = make_vertical_scroll(shell, wrap_padding=24)
    ttk.Label(inner, text='Dentro del scroll', wraplength=300).pack()
    root.update_idletasks()
    sync()
    inner_w = int(canvas.itemcget(canvas.find_withtag('all')[0], 'width'))
    assert inner_w >= 1
    root.destroy()
