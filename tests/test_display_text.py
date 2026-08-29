from display_text import plain_display_text, plain_ui_line, busy_status_text


def test_plain_display_text_strips_emoji_and_replacement():
    assert plain_display_text('Canal 🔴 EN DIRECTO') == 'Canal EN DIRECTO'
    assert plain_display_text('Película 🎬 HD') == 'Película HD'
    assert plain_display_text('a\ufffdb') == 'ab'
    assert plain_display_text('   ') == ''
    assert plain_display_text('', 'Sin nombre') == 'Sin nombre'


def test_plain_display_text_keeps_spanish_accents():
    assert plain_display_text('La 1 HD · España') == 'La 1 HD · España'
    assert plain_display_text('Niño ñandú') == 'Niño ñandú'


def test_plain_display_text_collapses_whitespace():
    assert plain_display_text('Canal   extra') == 'Canal extra'


def test_plain_ui_line_uses_ascii_ellipsis():
    assert plain_ui_line('Leyendo canales…') == 'Leyendo canales...'


def test_busy_status_text_shows_percent():
    assert busy_status_text('Leyendo canales...', 45) == 'Leyendo canales...  45 %'
    assert busy_status_text('Descargando lista...') == 'Descargando lista...'
