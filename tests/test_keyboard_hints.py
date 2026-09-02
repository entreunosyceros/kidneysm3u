"""Pruebas del overlay de atajos descubribles."""

import json

import app_config
import keyboard


def _isolate_config(tmp_path, monkeypatch):
    previous = app_config._cache
    cfg = tmp_path / 'config.json'
    monkeypatch.setattr(app_config, 'CONFIG_PATH', str(cfg))
    app_config._cache = None
    return previous


def test_player_quick_hints_include_help_keys():
    """Los atajos rápidos incluyen F1 y pantalla completa."""
    keys = [item[0] for item in keyboard.PLAYER_QUICK_HINTS]
    assert 'F1 / ?' in keys
    assert 'F11' in keys


def test_shortcut_categories_document_f1_and_f11():
    """El diálogo completo documenta F1 (ayuda) y F11 (pantalla completa)."""
    flat = []
    for _category, items in keyboard.SHORTCUT_CATEGORIES:
        flat.extend(items)
    mapping = dict(flat)
    assert 'Atajos rápidos en el reproductor' in mapping['F1']
    assert 'Pantalla completa' in mapping['F11']


def test_needs_player_shortcuts_hint_without_config(tmp_path, monkeypatch):
    """Sin config.json debe mostrar el overlay la primera vez."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        assert app_config.needs_player_shortcuts_hint() is True
    finally:
        app_config._cache = previous


def test_needs_player_shortcuts_hint_legacy_config(tmp_path, monkeypatch):
    """Config antigua sin la clave no fuerza el overlay."""
    previous = _isolate_config(tmp_path, monkeypatch)
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps({'theme': 'dark'}), encoding='utf-8')
    try:
        assert app_config.needs_player_shortcuts_hint() is False
    finally:
        app_config._cache = previous


def test_bind_question_mark_help_skips_invalid_sequences():
    """No debe fallar si una secuencia no es válida en Tk."""
    import tkinter as tk
    from keyboard import bind_question_mark_help

    root = tk.Tk()
    root.withdraw()
    bind_question_mark_help(root, lambda e: 'break')
    root.destroy()


def test_set_player_shortcuts_hint_shown(tmp_path, monkeypatch):
    """Marcar visto persiste en config.json."""
    previous = _isolate_config(tmp_path, monkeypatch)
    try:
        app_config.set_player_shortcuts_hint_shown(True)
        raw = json.loads((tmp_path / 'config.json').read_text(encoding='utf-8'))
        assert raw['player_shortcuts_hint_shown'] is True
        assert app_config.needs_player_shortcuts_hint() is False
    finally:
        app_config._cache = previous
