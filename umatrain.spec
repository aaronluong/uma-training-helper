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
    datas=[('skills.json', '.'),
    ('effects.json', '.'),
    ('traineeEvents.json', '.'),
    ('costumeEvents.json', '.'),
    ('costumes.json', '.'),
    ('races.json','.'),
    ('scenarioEvents.json','.'),
    ('supports', 'supports'),
    (os.path.join(site_packages,'openocr'),'openocr')
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
        'cv2'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure,a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='umatrain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
