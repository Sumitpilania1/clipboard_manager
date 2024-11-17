#!/bin/bash
cd "$(dirname "$0")"
export PYTHONPATH="$(dirname "$0")"
python3 clipboard_manager_ui_v2.py
