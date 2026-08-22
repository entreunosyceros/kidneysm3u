"""Visor de la documentación Markdown dentro de la aplicación."""

import os
import re
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ui_theme import (
    style_window, set_window_icon, center_window, get_colors, get_font, style_listbox,
)

DOC_PAGES = (
    ('Inicio', 'README.md', 'Puerta de entrada al manual'),
    ('Índice', 'docs/README.md', 'Mapa de toda la documentación'),
    ('Instalación', 'docs/instalacion.md', 'Requisitos, Ubuntu, Windows y entorno virtual'),
    ('Uso', 'docs/uso.md', 'Cargar una lista y empezar a reproducir'),
    ('Listas M3U', 'docs/listas-m3u.md', 'Filtro, IPTV y ordenación de listas'),
    ('YouTube', 'docs/youtube.md', 'Búsqueda, Shorts, cookies y descargas'),
    ('Reproductor', 'docs/reproductor.md', 'Controles, atajos, favoritos y bandeja'),
    ('Notas', 'docs/notas.md', 'Detalles técnicos y problemas conocidos'),
)

_INLINE_RE = re.compile(
    r'(!\[([^\]]*)\]\(([^)]+)\)|\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*)'
)


def _project_root():
    return Path(__file__).resolve().parent


def _normalize_doc_path(relative):
    path = os.path.normpath(relative or '').replace('\\', '/')
    if path.startswith('./'):
        path = path[2:]
    return path


def resolve_doc_href(current_rel, href):
    href = (href or '').strip()
    if href.startswith(('http://', 'https://', 'mailto:')):
        return ('url', href)
    path_part, _, _anchor = href.partition('#')
    if not path_part:
        return ('doc', _normalize_doc_path(current_rel))
    current = Path(_normalize_doc_path(current_rel))
    target = _normalize_doc_path(str(current.parent / path_part))
    return ('doc', target)


def _configure_tags(widget, colors):
    widget.configure(
        bg=colors['list_bg'],
        fg=colors['list_fg'],
        insertbackground=colors['text'],
        selectbackground=colors['select_bg'],
        selectforeground=colors['select_fg'],
        relief=tk.FLAT,
        borderwidth=0,
        highlightthickness=0,
        padx=14,
        pady=12,
        wrap=tk.WORD,
        font=get_font(10),
        cursor='arrow',
    )
    widget.tag_configure('h1', font=get_font(18, 'bold'), foreground=colors['text'], spacing1=8, spacing3=10)
    widget.tag_configure('h2', font=get_font(14, 'bold'), foreground=colors['text'], spacing1=14, spacing3=6)
    widget.tag_configure('h3', font=get_font(11, 'bold'), foreground=colors['accent'], spacing1=10, spacing3=4)
    widget.tag_configure('body', font=get_font(10), foreground=colors['text'], spacing3=6)
    widget.tag_configure('muted', font=get_font(10), foreground=colors['text_muted'], spacing3=6)
    widget.tag_configure('bold', font=get_font(10, 'bold'), foreground=colors['text'])
    widget.tag_configure('code', font=('monospace', 9), foreground=colors['accent'], background=colors['surface_alt'])
    widget.tag_configure(
        'codeblock',
        font=('monospace', 9),
        foreground=colors['text'],
        background=colors['surface_alt'],
        spacing1=4,
        spacing3=8,
        lmargin1=12,
        lmargin2=12,
    )
    widget.tag_configure('quote', font=get_font(10), foreground=colors['text_muted'], lmargin1=16, lmargin2=16, spacing3=6)
    widget.tag_configure('bullet', font=get_font(10), foreground=colors['text'], lmargin1=18, lmargin2=28, spacing3=3)
    widget.tag_configure('table', font=get_font(9), foreground=colors['text'], spacing3=2)
    widget.tag_configure('hr', foreground=colors['border'])
    widget.tag_configure('link', font=get_font(10), foreground=colors['accent'], underline=True)


def _insert_inline(widget, text, on_link, base_tags=('body',)):
    pos = 0
    for match in _INLINE_RE.finditer(text):
        if match.start() > pos:
            widget.insert(tk.END, text[pos:match.start()], base_tags)
        if match.group(1) and match.group(1).startswith('!['):
            alt = match.group(2) or 'imagen'
            widget.insert(tk.END, f'[{alt}]', ('muted',) + tuple(t for t in base_tags if t != 'body'))
        elif match.group(4) is not None:
            label, href = match.group(4), match.group(5)
            tag = f'link_{id(href)}_{widget.index(tk.END)}'
            widget.insert(tk.END, label, ('link', tag) + tuple(t for t in base_tags if t not in ('body', 'link')))
            widget.tag_bind(tag, '<Button-1>', lambda _e, target=href: on_link(target))
            widget.tag_bind(tag, '<Enter>', lambda _e: widget.configure(cursor='hand2'))
            widget.tag_bind(tag, '<Leave>', lambda _e: widget.configure(cursor='arrow'))
        elif match.group(6) is not None:
            widget.insert(tk.END, match.group(6), ('code',))
        else:
            widget.insert(tk.END, match.group(7), ('bold',))
        pos = match.end()
    if pos < len(text):
        widget.insert(tk.END, text[pos:], base_tags)


def render_markdown(widget, source, on_link):
    widget.configure(state=tk.NORMAL)
    widget.delete('1.0', tk.END)
    lines = source.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    i = 0
    in_code = False
    code_lines = []

    def flush_code():
        block = '\n'.join(code_lines).rstrip() + '\n'
        widget.insert(tk.END, block + '\n', ('codeblock',))
        code_lines.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('```'):
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_lines.append(line)
            i += 1
            continue
        if stripped in ('---', '***'):
            widget.insert(tk.END, '─' * 42 + '\n', ('hr', 'muted'))
            i += 1
            continue
        if stripped.startswith('|') and i + 1 < len(lines) and re.match(r'^\|[\s:|-]+\|', lines[i + 1].strip()):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [cell.strip() for cell in lines[i].strip().strip('|').split('|')]
                if not re.match(r'^[\s:|-]+$', ''.join(cells)):
                    rows.append(cells)
                i += 1
            for row in rows:
                widget.insert(tk.END, '  ·  '.join(row) + '\n', ('table',))
            widget.insert(tk.END, '\n')
            continue
        if stripped.startswith('# '):
            _insert_inline(widget, stripped[2:], on_link, ('h1',))
            widget.insert(tk.END, '\n')
        elif stripped.startswith('## '):
            _insert_inline(widget, stripped[3:], on_link, ('h2',))
            widget.insert(tk.END, '\n')
        elif stripped.startswith('### '):
            _insert_inline(widget, stripped[4:], on_link, ('h3',))
            widget.insert(tk.END, '\n')
        elif stripped.startswith('- '):
            widget.insert(tk.END, '• ', ('bullet',))
            _insert_inline(widget, stripped[2:], on_link, ('bullet',))
            widget.insert(tk.END, '\n')
        elif stripped.startswith('>'):
            quote = re.sub(r'^>\s*(\[![A-Z]+\]\s*)?', '', stripped)
            _insert_inline(widget, quote, on_link, ('quote',))
            widget.insert(tk.END, '\n')
        elif stripped:
            _insert_inline(widget, stripped, on_link, ('body',))
            widget.insert(tk.END, '\n')
        else:
            widget.insert(tk.END, '\n')
        i += 1

    widget.configure(state=tk.DISABLED)
    widget.see('1.0')


def show_documentation(root):
    window = tk.Toplevel(root)
    window.title('Documentación')
    window.geometry('920x640')
    window.minsize(720, 480)
    window.transient(root)
    style_window(window)
    set_window_icon(window)
    center_window(window, 920, 640)

    colors = get_colors()
    current = {'path': 'docs/README.md'}

    main = ttk.Frame(window, padding=16)
    main.pack(fill=tk.BOTH, expand=True)
    main.columnconfigure(1, weight=1)
    main.rowconfigure(1, weight=1)

    ttk.Label(main, text='Documentación', style='PageTitle.TLabel').grid(
        row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
    )

    side = ttk.Frame(main)
    side.grid(row=1, column=0, sticky='nsw', padx=(0, 12))
    ttk.Label(side, text='Temas', style='Muted.TLabel').pack(anchor=tk.W, pady=(0, 6))
    topics = tk.Listbox(side, width=22, height=22, exportselection=False)
    topics.pack(fill=tk.Y, expand=True)
    style_listbox(topics)
    for title, _path, _summary in DOC_PAGES:
        topics.insert(tk.END, title)

    body = ttk.Frame(main)
    body.grid(row=1, column=1, sticky='nsew')
    body.rowconfigure(0, weight=1)
    body.columnconfigure(0, weight=1)

    scroll = ttk.Scrollbar(body)
    scroll.grid(row=0, column=1, sticky='ns')
    viewer = tk.Text(body, yscrollcommand=scroll.set)
    viewer.grid(row=0, column=0, sticky='nsew')
    scroll.config(command=viewer.yview)
    _configure_tags(viewer, colors)

    def load_page(relative_path):
        relative_path = _normalize_doc_path(relative_path)
        path = _project_root() / relative_path
        current['path'] = relative_path
        for index, (_title, page_path, _summary) in enumerate(DOC_PAGES):
            if page_path == relative_path:
                topics.selection_clear(0, tk.END)
                topics.selection_set(index)
                topics.activate(index)
                topics.see(index)
                break
        if not path.is_file():
            render_markdown(viewer, f'# No encontrado\n\nNo está el archivo `{relative_path}`.', on_link)
            return
        try:
            source = path.read_text(encoding='utf-8')
        except OSError as err:
            render_markdown(viewer, f'# Error\n\nNo se pudo leer `{relative_path}`: {err}', on_link)
            return
        render_markdown(viewer, source, on_link)

    def on_link(href):
        kind, target = resolve_doc_href(current['path'], href)
        if kind == 'url':
            webbrowser.open(target)
            return
        load_page(target)

    def on_topic(_event=None):
        selection = topics.curselection()
        if selection:
            load_page(DOC_PAGES[selection[0]][1])

    topics.bind('<<ListboxSelect>>', on_topic)
    buttons = ttk.Frame(main)
    buttons.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(12, 0))
    ttk.Button(buttons, text='Índice', command=lambda: load_page('docs/README.md')).pack(side=tk.LEFT)
    ttk.Button(buttons, text='Inicio', command=lambda: load_page('README.md')).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(buttons, text='Cerrar', command=window.destroy).pack(side=tk.RIGHT)

    topics.selection_set(1)
    load_page('docs/README.md')
