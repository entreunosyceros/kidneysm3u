# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: genera dist/kidneysm3u.exe desde Linux o desde Windows.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH)

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
    'browser_cookie3',
    'Cryptodome',
    'numpy',
    'psutil',
    'requests',
    'ffmpeg',
]

for pkg in ('yt_dlp', 'browser_cookie3', 'tkinterdnd2', 'pystray'):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    except Exception:
        pkg_datas, pkg_binaries, pkg_hidden = [], [], collect_submodules(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

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
    a.binaries,
    a.datas,
    [],
    name='kidneysm3u.exe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'img' / 'logo.png') if (ROOT / 'img' / 'logo.png').is_file() else None,
)
