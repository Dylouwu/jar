# client_base.spec
# This file serves as a template for PyInstaller's spec file.
# Placeholders will be replaced by the build script.

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['{{OBFUSCATED_CLIENT_PATH}}'], # Placeholder for the path to the obfuscated client.py
    pathex=[],
    binaries=[],
    datas=[
        # Placeholder for PyArmor runtime files: (source_path, destination_name_in_bundle)
        ('{{PYARMOR_DATA_SOURCE}}', '{{PYARMOR_RUNTIME_DEST_DIR_NAME}}'),
    ],
    hiddenimports=['socket', 'requests', 'uuid'], # Added uuid just to be safe, though often not needed
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'test', 'unittest', 'pydoc', 'distutils', 'setuptools',
        '__pycache__', 'idlelib', 'html', 'xml', 
        'asyncio', 'concurrent', 
    ],
    noarchive=False,
    optimize=0, 
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='client_obf', # Placeholder, will be replaced by build.sh
    debug=False,
    bootloader_ignore_signals=False,
    strip=False, 
    upx=True,   
    upx_exclude=[], 
    runtime_tmpdir=None, 
    console=False, # CRUCIAL: Prevents a console window from appearing
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None, 
    codesign_identity=None, 
    entitlements_file=None, 
)

