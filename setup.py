"""
Setup script for building macOS app bundle
"""
from setuptools import setup

APP = ['clipboard_manager_ui_v2.py']
DATA_FILES = [
    ('icons', ['icons/clipboard_icon.png']),
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icons/clipboard_icon.png',
    'plist': {
        'CFBundleName': 'Clipboard Manager V2',
        'CFBundleDisplayName': 'Clipboard Manager V2',
        'CFBundleIdentifier': 'com.clipboardmanager.v2',
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '10.10',
        'NSHighResolutionCapable': True,
        'LSApplicationCategoryType': 'public.app-category.productivity',
        'LSEnvironment': {
            'LANG': 'en_US.UTF-8',
            'PATH': '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'
        },
        'NSRequiresAquaSystemAppearance': False,
        'LSBackgroundOnly': False,
        'NSAppleScriptEnabled': False,
    },
    'packages': ['PyQt5'],
    'includes': [
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'sqlite3',
    ],
    'excludes': ['tkinter', 'matplotlib', 'numpy'],
}

setup(
    name='Clipboard Manager V2',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    install_requires=['PyQt5'],
)
