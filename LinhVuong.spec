# -*- mode: python ; coding: utf-8 -*-

datas = [('linhvuong.ico', '.'), ('linhvuong.png', '.'), ('linhvuong_menu.png', '.'), ('qrcode.png', '.')]
binaries = []
hiddenimports = []


a = Analysis(
    ['LinhVuong.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PIL',
        'Pillow',
        'numpy',
        'linhvuong.web',
        'linhvuong.security',
        'linhvuong.runtime',
        'linhvuong.cli',
        'fastapi',
        'uvicorn',
        'starlette',
        'pydantic',
        'pydantic_core',
        'cryptography',
        'anyio',
        'httptools',
        'h11',
        'websockets',
        'setuptools',
    ],
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
    name='LinhVuong',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['linhvuong.ico'],
)
