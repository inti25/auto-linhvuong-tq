# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ('linhvuong/web/static', 'linhvuong/web/static'),
    ('linhvuong.png', '.'),
    ('linhvuong_menu.png', '.'),
    ('qrcode.png', '.'),
]
binaries = []
hiddenimports = []

for pkg in ('linhvuong', 'uvicorn', 'fastapi', 'starlette', 'websockets', 'cryptography', 'anyio'):
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

hiddenimports += collect_submodules('pydantic')
hiddenimports += collect_submodules('pydantic_core')
hiddenimports += ['httptools', 'h11', 'socks']

a = Analysis(
    ['LinhVuongWeb.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter', 'PIL', 'Pillow', 'numpy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

icon_path = ['linhvuong.ico'] if sys.platform.startswith('win') else None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LinhVuongWeb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
