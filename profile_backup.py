"""Exportar / importar perfil de usuario (config, favoritos, cookies)."""

import json
import os
import zipfile

from app_paths import data_dir

PROFILE_FILES = (
    'config.json',
    'favoritos.json',
    'enlaces.json',
    'cookies.txt',
    'twitch_cookies.txt',
    'kick_cookies.txt',
)


def profile_export_paths(base=None):
    """Rutas de archivos de perfil que existen bajo data_dir."""
    root = base or data_dir()
    found = []
    for name in PROFILE_FILES:
        path = os.path.join(root, name)
        if os.path.isfile(path):
            found.append(path)
    return found


def export_profile_zip(dest_path, base=None):
    """Escribe un zip con el perfil. Devuelve (n_archivos, ruta)."""
    root = base or data_dir()
    paths = profile_export_paths(root)
    if not paths:
        raise FileNotFoundError('No hay archivos de perfil para exportar.')
    dest_path = os.path.abspath(dest_path)
    os.makedirs(os.path.dirname(dest_path) or '.', exist_ok=True)
    with zipfile.ZipFile(dest_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            zf.write(path, arcname=os.path.basename(path))
        meta = {'files': [os.path.basename(p) for p in paths], 'version': 1}
        zf.writestr('profile_meta.json', json.dumps(meta, ensure_ascii=False, indent=2))
    return len(paths), dest_path


def import_profile_zip(src_path, base=None, *, reload_config=True):
    """Restaura archivos del zip en data_dir. Devuelve lista de nombres escritos."""
    root = base or data_dir()
    os.makedirs(root, exist_ok=True)
    src_path = os.path.abspath(src_path)
    written = []
    with zipfile.ZipFile(src_path, 'r') as zf:
        names = set(zf.namelist())
        for name in PROFILE_FILES:
            if name not in names:
                continue
            target = os.path.join(root, name)
            with zf.open(name) as src, open(target, 'wb') as out:
                out.write(src.read())
            written.append(name)
    if not written:
        raise ValueError('El ZIP no contiene archivos de perfil reconocidos.')
    if reload_config and 'config.json' in written:
        import app_config
        app_config._cache = None
        app_config.load()
    return written
