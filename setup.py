"""
py2app setup file for Pixel Art Converter.

Build:
    python3 setup.py py2app

Output:
    dist/Pixel Art Converter.app
"""
import sys
# py2app's modulegraph recurses deeply through the AST of imported packages.
# Default 1000 isn't enough for scipy/scikit-image on Python 3.14.
sys.setrecursionlimit(8000)

from setuptools import setup

APP = ['pixel_art_converter.py']

DATA_FILES = [
    # Bundled at YourApp.app/Contents/Resources/docs/
    ('docs', [
        'docs/icon.png',
        'docs/icon-dark.png',
        'docs/logo.png',
        'docs/logo-dark.png',
    ]),
]

OPTIONS = {
    'argv_emulation': False,
    # iconfile points at a .icns for pre-Tahoe macOS. The Tahoe layered .icon
    # is copied in post-build (py2app doesn't grok the .icon directory format).
    'iconfile': 'build/AppIcon.icns',
    'plist': {
        'CFBundleName':                 'Pixel Art Converter',
        'CFBundleDisplayName':          'Pixel Art Converter',
        'CFBundleIdentifier':           'com.ahmetolcum.PixelArtConverter',
        'CFBundleVersion':              '1.1.1',
        'CFBundleShortVersionString':   '1.1.1',
        # No extension — macOS Tahoe looks for AppIcon.icon first, falls back
        # to AppIcon.icns on older systems.
        'CFBundleIconFile':             'AppIcon',
        'CFBundleIconName':             'AppIcon',
        'NSHighResolutionCapable':      True,
        'LSMinimumSystemVersion':       '11.0',
        'NSHumanReadableCopyright':     '© 2026 Ahmet Olcum. MIT licensed.',
        # Drag-and-drop document types so users can drop PNGs onto the dock icon
        'CFBundleDocumentTypes': [{
            'CFBundleTypeName':         'PNG image',
            'CFBundleTypeExtensions':   ['png', 'PNG'],
            'CFBundleTypeRole':         'Viewer',
            'LSItemContentTypes':       ['public.png'],
        }],
    },

    # Top-level packages: py2app recursively picks up all submodules.
    'packages': [
        'PIL',
        'numpy',
        'sklearn',
        'skimage',
        'scipy',
    ],

    # Modules py2app's auto-detection sometimes misses.
    'includes': [
        'objc', 'AppKit', 'Foundation',
    ],

    # Heavy / unused stuff — keeps bundle smaller AND avoids modulegraph
    # following dead-end import chains.
    # NOTE: do NOT exclude 'unittest' — it's stdlib and scipy/sklearn/skimage
    # import unittest.mock internally for compatibility shims at runtime.
    'excludes': [
        'tkinter',
        'matplotlib', 'pandas',          # ~150MB combined, none used
        'IPython', 'jupyter',
        'PyInstaller', 'PySide2', 'PySide6', 'PyQt5', 'PyQt6',  # GUI rivals
        'wx',
        'sphinx', 'pytest', 'mypy',
    ],

    # Platform-native libraries; avoid signing issues with embedded duplicates.
    'frameworks': [],

    # Avoid the strict-aliasing crash in py2app's bundle builder for dylibs
    'no_strip':         True,
    'optimize':         0,
    'compressed':       True,
    'semi_standalone':  False,   # full standalone — embed Python interpreter
    'site_packages':    True,
}

setup(
    app=APP,
    name='Pixel Art Converter',
    version='1.0.0',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
