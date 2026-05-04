# PyInstaller spec for the cross-platform PySide6 GUI.
# Build:  pyinstaller pixel_art_converter_qt.spec
#
# Heavy ML deps (onnxruntime, scikit-image, scikit-learn, scipy) and the
# Qt runtime are bundled. rembg model weights (~700 MB) are NOT bundled —
# they download to ~/.u2net on first use of each model.

import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas, binaries, hiddenimports = [], [], []

for pkg in ("PySide6", "rembg", "onnxruntime"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

for pkg in ("sklearn", "skimage", "scipy"):
    datas += collect_data_files(pkg)

# Bundle the icon so the exe / Linux binary has the same window icon
# as the cloned-source run.
datas += [("docs/icon.png", "docs")]

block_cipher = None

a = Analysis(
    ["pixel_art_converter_qt.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="PixelArtConverter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon="docs/icon.png" if sys.platform != "linux" else None,
)
