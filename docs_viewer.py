"""Visor de la documentación Markdown dentro de la aplicación."""

import hashlib
import os
import re
import ssl
import tempfile
import threading
import webbrowser
import tkinter as tk
from collections import deque
from io import BytesIO
from pathlib import Path
from tkinter import ttk
from urllib.request import Request, urlopen

from ui_theme import (
    style_window, set_window_icon, center_window, get_colors, get_font, style_listbox,
)

from app_paths import resource_dir

DOC_PAGES = (
    ('Inicio', 'README.md', 'Puerta de entrada al manual'),
    ('Índice', 'docs/README.md', 'Mapa de toda la documentación'),
    ('Instalación', 'docs/instalacion.md', 'Requisitos, Ubuntu, Windows y entorno virtual'),
    ('Uso', 'docs/uso.md', 'Cargar una lista, reproducir y preferencias'),
    ('Listas M3U', 'docs/listas-m3u.md', 'Filtro, IPTV, buffer y ordenación de listas'),
    ('YouTube', 'docs/youtube.md', 'Búsqueda, Shorts, cookies y descargas'),
    ('Reproductor', 'docs/reproductor.md', 'Controles, PiP, grabación, pantalla completa y bandeja'),
    ('Notas', 'docs/notas.md', 'Detalles técnicos y problemas conocidos'),
)

_INLINE_RE = re.compile(
    r'(!\[([^\]]*)\]\(([^)]+)\)|\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*)'
)
_IMG_HTML_RE = re.compile(r'<img\b[^>]*>', re.IGNORECASE)
_P_TAG_RE = re.compile(r'</?p\b[^>]*>', re.IGNORECASE)
_SRC_RE = re.compile(r'''\bsrc\s*=\s*["']([^"']+)["']''', re.IGNORECASE)
_ALT_RE = re.compile(r'''\balt\s*=\s*["']([^"']*)["']''', re.IGNORECASE)
_DOC_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) '
    'Gecko/20100101 Firefox/125.0'
)
_DOC_IMG_MAX_BYTES = 5 * 1024 * 1024
_DOC_IMG_MAX_W = 640
_DOC_IMG_MAX_H = 420


def _project_root():
    """Uso interno: project root."""
    return Path(resource_dir())


def html_img_to_markdown(tag):
    """Html img to markdown."""
    src_match = _SRC_RE.search(tag or '')
    if not src_match:
        return ''
    alt_match = _ALT_RE.search(tag)
    alt = (alt_match.group(1) if alt_match else '').strip() or 'imagen'
    return f'![{alt}]({src_match.group(1).strip()})'


def is_html_wrapper_line(stripped):
    """Indica si html wrapper line."""
    return bool(re.match(r'^</?(p|div|span|center)\b[^>]*>$', stripped or '', re.I))


def image_markdown_from_line(stripped):
    """Image markdown from line."""
    match = _IMG_HTML_RE.search(stripped or '')
    if not match:
        return None
    converted = html_img_to_markdown(match.group(0))
    return converted or None


def normalize_doc_markup(source):
    """Convierte <img> HTML (capturas de GitHub) a Markdown y quita <p align=center>."""
    text = source or ''
    text = _P_TAG_RE.sub('', text)
    return _IMG_HTML_RE.sub(lambda match: html_img_to_markdown(match.group(0)), text)


def _doc_image_cache_dir():
    """Uso interno: doc image cache dir."""
    path = os.path.join(tempfile.gettempdir(), 'kidneysm3u_docs_img')
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def _doc_cache_path(url):
    """Uso interno: doc cache path."""
    digest = hashlib.sha1((url or '').encode('utf-8', errors='replace')).hexdigest()
    return os.path.join(_doc_image_cache_dir(), digest)


def fetch_doc_image_bytes(url):
    """Obtiene doc image bytes desde la red o el disco."""
    url = (url or '').strip()
    if not url.startswith(('http://', 'https://')):
        return None
    cached = _doc_cache_path(url)
    try:
        if os.path.isfile(cached) and 0 < os.path.getsize(cached) <= _DOC_IMG_MAX_BYTES:
            with open(cached, 'rb') as handle:
                return handle.read()
    except OSError:
        pass
    request = Request(url, headers={'User-Agent': _DOC_UA, 'Accept': 'image/*,*/*'})
    raw = None
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read(_DOC_IMG_MAX_BYTES + 1)
    except Exception:
        try:
            ctx = ssl._create_unverified_context()
            with urlopen(request, timeout=15, context=ctx) as response:
                raw = response.read(_DOC_IMG_MAX_BYTES + 1)
        except Exception:
            return None
    if not raw or len(raw) > _DOC_IMG_MAX_BYTES:
        return None
    try:
        with open(cached, 'wb') as handle:
            handle.write(raw)
    except OSError:
        pass
    return raw


def local_doc_image_bytes(url):
    """Local doc image bytes."""
    url = (url or '').strip()
    if not url or url.startswith(('http://', 'https://', 'mailto:')):
        return None
    path_part = url.split('#', 1)[0].split('?', 1)[0]
    root = _project_root().resolve()
    path = Path(path_part)
    candidate = path if path.is_absolute() else (root / path_part)
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    if not resolved.is_file():
        return None
    try:
        if resolved.stat().st_size > _DOC_IMG_MAX_BYTES:
            return None
        return resolved.read_bytes()
    except OSError:
        return None


def photo_from_image_bytes(raw, max_width=_DOC_IMG_MAX_W, max_height=_DOC_IMG_MAX_H, master=None):
    """Photo from image bytes."""
    if not raw:
        return None
    try:
        from PIL import Image, ImageTk
    except Exception:
        return None
    try:
        image = Image.open(BytesIO(raw))
        image.load()
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
    except Exception:
        return None
    width, height = image.size
    if width < 1 or height < 1:
        return None
    scale = min(max_width / width, max_height / height, 1.0)
    if scale < 1:
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )
    try:
        if master is not None:
            return ImageTk.PhotoImage(image, master=master)
        return ImageTk.PhotoImage(image)
    except Exception:
        return None


def load_doc_photo(url, master=None):
    """Carga doc photo."""
    raw = fetch_doc_image_bytes(url) if (url or '').startswith(('http://', 'https://')) else local_doc_image_bytes(url)
    return photo_from_image_bytes(raw, master=master)


def _apply_doc_image(widget, gen, mark, label, raw):
    """Uso interno: apply doc image."""
    if getattr(widget, '_doc_gen', None) != gen:
        return
    photo = photo_from_image_bytes(raw, master=widget)
    try:
        widget.configure(state=tk.NORMAL)
        line_end = widget.index(f'{mark} lineend')
        widget.delete(mark, line_end)
        if photo is not None:
            widget.image_create(mark, image=photo)
            widget._doc_images.append(photo)
        else:
            widget.insert(mark, f'[{label}]', ('muted',))
        widget.configure(state=tk.DISABLED)
    except tk.TclError:
        return


def _pump_doc_images(widget, gen):
    """Uso interno: pump doc images."""
    if getattr(widget, '_doc_gen', None) != gen:
        return
    ready = getattr(widget, '_doc_ready', None)
    while ready:
        try:
            item = ready.popleft()
        except IndexError:
            break
        _apply_doc_image(widget, *item)
    if getattr(widget, '_doc_pending', 0) > 0:
        try:
            widget.after(80, lambda: _pump_doc_images(widget, gen))
        except tk.TclError:
            pass


def _schedule_doc_image(widget, url, alt, gen):
    """Uso interno: schedule doc image."""
    mark = f'docimg{getattr(widget, "_doc_img_n", 0)}'
    widget._doc_img_n = getattr(widget, '_doc_img_n', 0) + 1
    widget.mark_set(mark, tk.END)
    widget.mark_gravity(mark, tk.LEFT)
    label = (alt or 'imagen').strip() or 'imagen'
    widget.insert(tk.END, f'[{label}]', ('muted',))
    widget._doc_pending = getattr(widget, '_doc_pending', 0) + 1

    def work():
        """Work."""
        try:
            if (url or '').startswith(('http://', 'https://')):
                raw = fetch_doc_image_bytes(url)
            else:
                raw = local_doc_image_bytes(url)
            getattr(widget, '_doc_ready', deque()).append((gen, mark, label, raw))
        finally:
            widget._doc_pending = max(0, getattr(widget, '_doc_pending', 1) - 1)

    threading.Thread(target=work, daemon=True).start()


def _normalize_doc_path(relative):
    """Uso interno: normalize doc path."""
    path = os.path.normpath(relative or '').replace('\\', '/')
    if path.startswith('./'):
        path = path[2:]
    return path


def resolve_doc_href(current_rel, href):
    """Resolve doc href."""
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
    """Uso interno: configure tags."""
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


def _insert_inline(widget, text, on_link, base_tags=('body',), schedule_image=None):
    """Uso interno: insert inline."""
    pos = 0
    for match in _INLINE_RE.finditer(text):
        if match.start() > pos:
            widget.insert(tk.END, text[pos:match.start()], base_tags)
        if match.group(1) and match.group(1).startswith('!['):
            alt = match.group(2) or 'imagen'
            href = (match.group(3) or '').strip()
            if schedule_image and href:
                schedule_image(href, alt)
            else:
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
    """Renderiza markdown."""
    widget.configure(state=tk.NORMAL)
    widget.delete('1.0', tk.END)
    widget._doc_gen = getattr(widget, '_doc_gen', 0) + 1
    gen = widget._doc_gen
    widget._doc_images = []
    widget._doc_img_n = 0
    widget._doc_ready = deque()
    widget._doc_pending = 0
    source = normalize_doc_markup(source)
    lines = source.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    i = 0
    in_code = False
    code_lines = []

    def schedule_image(url, alt):
        """Programa image."""
        _schedule_doc_image(widget, url, alt, gen)

    def flush_code():
        """Flush code."""
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
        if is_html_wrapper_line(stripped):
            i += 1
            continue
        img_md = image_markdown_from_line(stripped)
        if img_md:
            _insert_inline(widget, img_md, on_link, ('body',), schedule_image)
            widget.insert(tk.END, '\n')
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
            _insert_inline(widget, stripped[2:], on_link, ('h1',), schedule_image)
            widget.insert(tk.END, '\n')
        elif stripped.startswith('## '):
            _insert_inline(widget, stripped[3:], on_link, ('h2',), schedule_image)
            widget.insert(tk.END, '\n')
        elif stripped.startswith('### '):
            _insert_inline(widget, stripped[4:], on_link, ('h3',), schedule_image)
            widget.insert(tk.END, '\n')
        elif stripped.startswith('- '):
            widget.insert(tk.END, '• ', ('bullet',))
            _insert_inline(widget, stripped[2:], on_link, ('bullet',), schedule_image)
            widget.insert(tk.END, '\n')
        elif stripped.startswith('>'):
            quote = re.sub(r'^>\s*(\[![A-Z]+\]\s*)?', '', stripped)
            _insert_inline(widget, quote, on_link, ('quote',), schedule_image)
            widget.insert(tk.END, '\n')
        elif stripped:
            _insert_inline(widget, stripped, on_link, ('body',), schedule_image)
            widget.insert(tk.END, '\n')
        else:
            widget.insert(tk.END, '\n')
        i += 1

    widget.configure(state=tk.DISABLED)
    widget.see('1.0')
    if widget._doc_img_n:
        widget.after(50, lambda: _pump_doc_images(widget, gen))


def show_documentation(root):
    """Muestra documentation."""
    window = tk.Toplevel(root)
    window.title('Documentación')
    from ui_layout import setup_resizable_dialog
    setup_resizable_dialog(window, 920, 640, 720, 480)
    window.transient(root)
    style_window(window)
    set_window_icon(window)

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
    side.grid(row=1, column=0, sticky='nsew', padx=(0, 12))
    side.rowconfigure(1, weight=1)
    ttk.Label(side, text='Temas', style='Muted.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 6))
    topics = tk.Listbox(side, exportselection=False)
    topics.grid(row=1, column=0, sticky='nsew')
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
        """Carga page."""
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
        """Responde al evento link."""
        kind, target = resolve_doc_href(current['path'], href)
        if kind == 'url':
            webbrowser.open(target)
            return
        load_page(target)

    def on_topic(_event=None):
        """Responde al evento topic."""
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
