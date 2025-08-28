# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import sysconfig

here = os.getcwd()
site_packages = sysconfig.get_paths()['purelib']

block_cipher = None

a = Analysis(
    ['helper.py'],
    pathex=[here, site_packages],
    binaries=[],
    datas=[
        ('skills.json', '.'),
        ('effects.json', '.'),
        ('traineeEvents.json', '.'),
        ('costumeEvents.json', '.'),
        ('costumes.json', '.'),
        ('races.json', '.'),
        ('scenarioEvents.json', '.'),
        ('supports', 'supports'),
        (os.path.join(site_packages, 'openocr'), 'openocr'),
    ],
    hiddenimports=[
        'tools.infer_e2e',
        'tools.OpenDetector',
        'tools.OpenRecognizer',
        'shapely',
        'pyclipper',
        'rapidfuzz',
        'tqdm',
        'yaml',
        'onnxruntime',
        'PIL.ImageDraw',
        'cv2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Key change: exclude_binaries=True and do NOT pass a.binaries/a.datas into EXE
exe = EXE(
    pyz,
    a.scripts,
    [],
    [],
    [],
    name='umatrain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,   # fine to keep; unused in onedir
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    exclude_binaries=True,  # <-- makes this an onedir-style EXE
)

# New: collect everything into a persistently unpacked folder in dist/umatrain
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='umatrain',
    # Optionally set custom output paths:
    # distpath=os.path.join(here, 'dist'),
    # workpath=os.path.join(here, 'build'),
)
