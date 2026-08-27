from ui_clipboard import insert_clipboard_text


class _FakeEntry:
    def __init__(self, state='normal'):
        self.state = state
        self.deleted_sel = False
        self.inserted = None

    def cget(self, key):
        if key == 'state':
            return self.state
        raise RuntimeError(key)

    def delete(self, start, end=None):
        self.deleted_sel = True

    def insert(self, index, text):
        self.inserted = (index, text)


def test_insert_clipboard_replaces_selection():
    widget = _FakeEntry()
    insert_clipboard_text(widget, 'https://ejemplo/lista.m3u')
    assert widget.deleted_sel is True
    assert widget.inserted == ('insert', 'https://ejemplo/lista.m3u')


def test_insert_clipboard_skips_readonly():
    widget = _FakeEntry(state='readonly')
    insert_clipboard_text(widget, 'https://ejemplo/lista.m3u')
    assert widget.inserted is None
