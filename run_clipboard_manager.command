#!/bin/bash

# Change to the script's directory
cd "$(dirname "$0")"

# Set the application name
export PYQT_MAC_NO_NATIVE_MENUBAR=1
export DISPLAY_NAME="Clipboard Manager V2"

# Run the application
exec python3 clipboard_manager_ui_v2.py
