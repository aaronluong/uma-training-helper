# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['helper.py'],
    pathex=['.',r'C:\Anaconda\envs\helper\Lib\site-packages'],
    binaries=[],
    datas=[('skills.json', '.'),
    ('effects.json', '.'),
    ('traineeEvents.json', '.'),
    ('costumeEvents.json', '.'),
    ('costumes.json', '.'),
    ('supports', 'supports'),
    (r'C:\Anaconda\envs\helper\Lib\site-packages\openocr','openocr')
    ],
    hiddenimports=[
        'tools.infer_e2e',
        'tools.OpenDetector',
        'tools.OpenRecognizer',
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
