"""Rutas de recursos empaquetados y de datos del usuario (PyInstaller incluido)."""

import os
import sys


def resource_dir():
    """Código, img/ y docs/. Con PyInstaller onefile es la carpeta temporal _MEIPASS."""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """config.json, cookies, favoritos: al lado del .exe si está empaquetado."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
