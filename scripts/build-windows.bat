@echo off
echo ============================================
echo  AngryREST Windows Build Script
echo ============================================

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing dependencies...
pip install -e .[dev]
pip install pyinstaller

echo Building standalone executable...
pyinstaller angryrest.spec

echo ============================================
echo  Build complete!
echo  Output: dist\AngryREST.exe
echo ============================================