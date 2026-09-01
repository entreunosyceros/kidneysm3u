"""Módulo de test display text."""

from display_text import plain_display_text, plain_ui_line, busy_status_text, truncate_ui_text


def test_plain_display_text_strips_emoji_and_replacement():
    """Prueba plain display text strips emoji and replacement."""
    assert plain_display_text('Canal 🔴 EN DIRECTO') == 'Canal EN DIRECTO'
    assert plain_display_text('Película 🎬 HD') == 'Película HD'
    assert plain_display_text('a\ufffdb') == 'ab'
    assert plain_display_text('   ') == ''
    assert plain_display_text('', 'Sin nombre') == 'Sin nombre'


def test_plain_display_text_keeps_spanish_accents():
    """Prueba plain display text keeps spanish accents."""
    assert plain_display_text('La 1 HD · España') == 'La 1 HD · España'
    assert plain_display_text('Niño ñandú') == 'Niño ñandú'


def test_plain_display_text_collapses_whitespace():
    """Prueba plain display text collapses whitespace."""
    assert plain_display_text('Canal   extra') == 'Canal extra'


def test_plain_ui_line_uses_ascii_ellipsis():
    """Prueba plain interfaz line uses ascii ellipsis."""
    assert plain_ui_line('Leyendo canales…') == 'Leyendo canales...'


def test_truncate_ui_text_uses_ascii_ellipsis():
    """Prueba truncate interfaz text uses ascii ellipsis."""
    assert truncate_ui_text('abcdefghij', 7) == 'abcd...'
    assert truncate_ui_text('abc', 7) == 'abc'


def test_busy_status_text_shows_percent():
    """Prueba busy status text shows percent."""
    assert busy_status_text('Leyendo canales...', 45) == 'Leyendo canales...  45 %'
    assert busy_status_text('Descargando lista...') == 'Descargando lista...'
