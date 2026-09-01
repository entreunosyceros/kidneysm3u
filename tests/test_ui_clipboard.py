"""Módulo de test ui clipboard."""

from ui_clipboard import insert_clipboard_text


class _FakeEntry:
    """Clase que representa fakeentry."""
    def __init__(self, state='normal'):
        """Inicializa _FakeEntry."""
        self.state = state
        self.deleted_sel = False
        self.inserted = None

    def cget(self, key):
        """Cget."""
        if key == 'state':
            return self.state
        raise RuntimeError(key)

    def delete(self, start, end=None):
        """Delete."""
        self.deleted_sel = True

    def insert(self, index, text):
        """Insert."""
        self.inserted = (index, text)


def test_insert_clipboard_replaces_selection():
    """Prueba insert clipboard replaces selection."""
    widget = _FakeEntry()
    insert_clipboard_text(widget, 'https://ejemplo/lista.m3u')
    assert widget.deleted_sel is True
    assert widget.inserted == ('insert', 'https://ejemplo/lista.m3u')


def test_insert_clipboard_skips_readonly():
    """Prueba insert clipboard skips readonly."""
    widget = _FakeEntry(state='readonly')
    insert_clipboard_text(widget, 'https://ejemplo/lista.m3u')
    assert widget.inserted is None
