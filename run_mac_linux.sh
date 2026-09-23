#!/bin/bash
set -e
PYTHON_BIN="python3"
if command -v python3.12 >/dev/null 2>&1; then PYTHON_BIN="python3.12"; fi
if [ ! -d ".venv" ]; then "$PYTHON_BIN" -m venv .venv; fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python ml/train_model.py
python ml/compare_models.py
python app.py
