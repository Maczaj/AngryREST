#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo " AngryREST Linux Build Script"
echo "============================================"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies..."
pip install -e '.[dev]'
pip install pyinstaller

echo "Building standalone executable..."
pyinstaller angryrest.spec

echo "============================================"
echo " Build complete!"
echo " Output: dist/AngryREST"
echo "============================================"