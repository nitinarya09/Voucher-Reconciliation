# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

added_files = [
    ('ui', 'ui'),
    ('config', 'config'),
    ('vallabh bhawan', 'vallabh bhawan'),
    ('TEST DATA', 'TEST DATA'),
    ('COMPAY_DATA_VAL_10_2025.XLS', '.'),
    ('analysis.ico', '.'),
]

hidden_imports = [
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'pythonnet',
    'openpyxl',
    'openpyxl.styles',
    'openpyxl.utils',
    'pandas',
    'reportlab',
    'reportlab.lib',
    'reportlab.platypus',
    'reportlab.pdfgen',
    'tkinter',
    'tkinter.filedialog',
    'decimal',
    'json',
    'csv',
    'uuid',
    'datetime',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'torch', 'torchvision', 'scipy', 'cv2', 'PIL.ImageQt',
        'IPython', 'jupyter', 'llama_cpp', 'paddleocr', 'paddlex', 'onnxruntime'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_path = 'analysis.ico' if os.path.exists('analysis.ico') else ('app_icon.ico' if os.path.exists('app_icon.ico') else None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='IFMIS_VLC_Voucher_Reconciliation_Suite_v1.0_Portable',
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
    icon=icon_path,
)
