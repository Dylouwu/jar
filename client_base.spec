# client_base.spec
# This file serves as a template for PyInstaller's spec file.
# Placeholders like {{OBFUSCATED_CLIENT_PATH}} will be replaced by the build script.

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None # You can define a cipher here if needed, otherwise leave None

a = Analysis(
    ['{{OBFUSCATED_CLIENT_PATH}}'], # Placeholder for the path to the obfuscated client.py
    pathex=[],
    binaries=[],
    datas=[
        # Placeholder for PyArmor runtime files: (source_path, destination_name_in_bundle)
        ('{{PYARMOR_DATA_SOURCE}}', '{{PYARMOR_DATA_DEST}}'),
    ],
    hiddenimports=[], # Add any modules PyInstaller might miss, e.g., 'gevent.hub'
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Common modules to exclude for smaller size and reduced noise
        'tkinter', 'test', 'unittest', 'pydoc', 'distutils', 'setuptools',
        '__pycache__', 'idlelib', 'html', 'xml', 'email', 'http',
        'asyncio', 'concurrent', # Often included but might not be essential
    ],
    noarchive=False,
    optimize=0, # 0=no optimization, 1=basic, 2=aggressive (might affect debugging)
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    # Name of the output executable
    name='client_obf',
    debug=False, # Set to True for debugging PyInstaller issues (makes it larger)
    bootloader_ignore_signals=False,
    strip=False, # Set to True to strip debug info from binaries (reduces size slightly)
    upx=True,    # Set to True to compress the final executable with UPX (if installed)
    upx_exclude=[], # List of files to exclude from UPX compression (e.g., if it causes issues)
    runtime_tmpdir=None, # Directory where the executable unpacks at runtime (None = system temp)
    console=False, # <-- CRUCIAL: Prevents a console window from appearing
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None, # e.g., 'x86_64', 'arm64' (usually auto-detected)
    codesign_identity=None, # For macOS code signing
    entitlements_file=None, # For macOS entitlements
)
