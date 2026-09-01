"""Módulo de test window identity."""

from ui_theme import APP_WM_CLASS


def test_wm_class_matches_gnome_launcher():
    """GNOME agrupa por este nombre; el .desktop usa StartupWMClass=Kidneysm3u."""
    assert APP_WM_CLASS == 'Kidneysm3u'
