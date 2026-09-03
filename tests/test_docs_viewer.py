"""Módulo de test docs viewer."""

from pathlib import Path

import pytest

from docs_viewer import (
    html_img_to_markdown,
    image_markdown_from_line,
    is_html_wrapper_line,
    local_doc_image_bytes,
    normalize_doc_markup,
)


def test_html_wrapper_lines_are_skipped():
    """Prueba html wrapper lines are skipped."""
    assert is_html_wrapper_line('<p align="center">')
    assert is_html_wrapper_line('</p>')
    assert not is_html_wrapper_line('![interfaz-kidneys](https://example.com/a.png)')


def test_image_markdown_from_html_line():
    """Prueba image markdown from html line."""
    line = (
        '<img width="899" height="684" alt="interfaz-kidneys" '
        'src="https://github.com/user-attachments/assets/88366f48-e059-46d8-9169-a94aec31a738" />'
    )
    converted = image_markdown_from_line(line)
    assert converted.startswith('![interfaz-kidneys](https://github.com/user-attachments/assets/')


def test_html_img_to_markdown():
    """Prueba html img to markdown."""
    tag = (
        '<img width="899" height="684" alt="interfaz-kidneys" '
        'src="https://github.com/user-attachments/assets/88366f48-e059-46d8-9169-a94aec31a738" />'
    )
    converted = html_img_to_markdown(tag)
    assert converted.startswith('![interfaz-kidneys](https://github.com/user-attachments/assets/')
    assert '88366f48-e059-46d8-9169-a94aec31a738' in converted


def test_normalize_doc_markup_strips_center_and_converts_img():
    """Prueba normalize doc markup strips center and converts img."""
    source = (
        '<p align="center">\n'
        '<img width="1916" alt="cargando-video-youtube" '
        'src="https://github.com/user-attachments/assets/a9405356-8fa6-456e-8e65-f14326124ead" />\n'
        '</p>\n'
    )
    out = normalize_doc_markup(source)
    assert '<img' not in out.lower()
    assert '<p' not in out.lower()
    assert '![cargando-video-youtube](https://github.com/user-attachments/assets/' in out


def test_normalize_keeps_markdown_images():
    """Prueba normalize keeps markdown images."""
    source = '![reproduccion-m3u](https://github.com/user-attachments/assets/fa30375b-b0bf-4468-857c-07bd939968dd)\n'
    assert normalize_doc_markup(source) == source


def test_local_doc_image_bytes_logo():
    """Prueba local doc image bytes logo."""
    raw = local_doc_image_bytes('img/logo.png')
    assert raw
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'


def test_local_doc_image_bytes_rejects_outside_root(tmp_path):
    """Prueba local doc image bytes rejects outside root."""
    outsider = tmp_path / 'secret.png'
    outsider.write_bytes(b'not-from-project')
    assert local_doc_image_bytes(str(outsider)) is None
    assert local_doc_image_bytes('../' + Path(tmp_path).name + '/secret.png') is None


@pytest.mark.gui
def test_render_markdown_does_not_show_html_img():
    """Prueba render markdown does not show html img."""
    import tkinter as tk
    from docs_viewer import render_markdown

    source = (
        '# Título\n\n'
        '<p align="center">\n'
        '<img width="899" height="684" alt="interfaz-kidneys" '
        'src="https://github.com/user-attachments/assets/88366f48-e059-46d8-9169-a94aec31a738" />\n'
        '</p>\n'
    )
    root = tk.Tk()
    root.withdraw()
    widget = tk.Text(root)
    try:
        render_markdown(widget, source, lambda _href: None)
        shown = widget.get('1.0', 'end')
    finally:
        root.destroy()
    assert '<p align' not in shown.lower()
    assert '<img' not in shown.lower()
    assert 'interfaz-kidneys' in shown
