#!/usr/bin/env bash
# Render build command for the ReuseHub backend.
# Installs Python dependencies for the Django REST API.
set -euo pipefail

pip install --upgrade pip
pip install -r requirements.txt
