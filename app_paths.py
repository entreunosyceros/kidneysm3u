"""Rutas de recursos empaquetados y de datos del usuario (PyInstaller incluido)."""

import os
import sys


def resource_dir():
    """Código, img/ y docs/. Con PyInstaller onefile es la carpeta temporal _MEIPASS."""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def data_dir():
    """config.json, cookies, favoritos. En Windows instalado: %LOCALAPPDATA%\\kidneysm3u."""
    if getattr(sys, 'frozen', False) and sys.platform == 'win32':
        base = (os.environ.get('LOCALAPPDATA') or '').strip() or os.path.expanduser('~')
        path = os.path.join(base, 'kidneysm3u')
        os.makedirs(path, exist_ok=True)
        return path
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
