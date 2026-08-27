from pathlib import Path

from docs_viewer import html_img_to_markdown, local_doc_image_bytes, normalize_doc_markup


def test_html_img_to_markdown():
    tag = (
        '<img width="899" height="684" alt="interfaz-kidneys" '
        'src="https://github.com/user-attachments/assets/88366f48-e059-46d8-9169-a94aec31a738" />'
    )
    converted = html_img_to_markdown(tag)
    assert converted.startswith('![interfaz-kidneys](https://github.com/user-attachments/assets/')
    assert '88366f48-e059-46d8-9169-a94aec31a738' in converted


def test_normalize_doc_markup_strips_center_and_converts_img():
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
    source = '![reproduccion-m3u](https://github.com/user-attachments/assets/fa30375b-b0bf-4468-857c-07bd939968dd)\n'
    assert normalize_doc_markup(source) == source


def test_local_doc_image_bytes_logo():
    raw = local_doc_image_bytes('img/logo.png')
    assert raw
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'


def test_local_doc_image_bytes_rejects_outside_root(tmp_path):
    outsider = tmp_path / 'secret.png'
    outsider.write_bytes(b'not-from-project')
    assert local_doc_image_bytes(str(outsider)) is None
    assert local_doc_image_bytes('../' + Path(tmp_path).name + '/secret.png') is None
