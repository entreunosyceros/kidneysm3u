# -*- mode: python ; coding: utf-8 -*-
# PyInstaller onedir: dist/kidneysm3u/kidneysm3u.exe (PE de Windows) + DLLs.
# Hay que generar con Python de Windows o con Docker/Wine (build-windows.sh).

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH)
IS_WIN = sys.platform == 'win32'

datas = [
    (str(ROOT / 'img'), 'img'),
    (str(ROOT / 'docs'), 'docs'),
    (str(ROOT / 'README.md'), '.'),
    (str(ROOT / 'LICENSE'), '.'),
]
binaries = []
hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.simpledialog',
    'tkinterdnd2',
    'pystray',
    'PIL',
    'vlc',
    'yt_dlp',
    'app_update',
    'app_version',
    'browser_cookie3',
    'Cryptodome',
    'numpy',
    'psutil',
    'requests',
    'vlc_check',
    'usage_profiles',
    'onboarding',
    'player_status',
    'light_mode_auto',
    'cache_cleanup',
    'kick_player',
]

for pkg in ('tkinterdnd2', 'pystray', 'curl_cffi'):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    except Exception:
        pkg_datas, pkg_binaries, pkg_hidden = [], [], []
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

if IS_WIN:
    for pkg in ('pywebview', 'pythonnet', 'clr_loader'):
        try:
            pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        except Exception:
            pkg_datas, pkg_binaries, pkg_hidden = [], [], []
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    hiddenimports += ['webview', 'webview.platforms.winforms', 'twitch_chat', 'twitch_player']

icon = None
png = ROOT / 'img' / 'icono.png'
ico = ROOT / 'img' / 'icono.ico'
if IS_WIN and png.is_file():
    try:
        from PIL import Image
        img = Image.open(png)
        img.save(ico, format='ICO', sizes=[(256, 256), (48, 48), (32, 32), (16, 16)])
        icon = str(ico)
    except Exception:
        icon = str(png)
elif ico.is_file():
    icon = str(ico)

version_file = ROOT / 'file_version_info.txt'
version = str(version_file) if IS_WIN and version_file.is_file() else None

a = Analysis(
    ['main.py'],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'tests'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='kidneysm3u',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    version=version,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='kidneysm3u',
)
