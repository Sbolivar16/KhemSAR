@echo off
setlocal enabledelayedexpansion
echo ==========================================
echo    KhemSAR - Setup ^& Launcher (Windows)
echo ==========================================

cd /d "%~dp0"

where conda >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [KhemSAR] Conda detected.
    conda env list | findstr /R "^khemsar " >nul
    if !ERRORLEVEL! NEQ 0 (
        echo [KhemSAR] Creating conda environment 'khemsar'...
        conda env create -f environment.yml
    )
    echo [KhemSAR] Launching KhemSAR at http://127.0.0.1:8765 ...
    conda run --no-capture-output -n khemsar python -m khemsar.main
    goto :eof
)

where uv >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [KhemSAR] uv detected.
    if not exist ".venv" (
        uv venv --python 3.11 .venv
    )
    call .venv\Scripts\activate.bat
    uv pip install -e ".[ml,dev]" || uv pip install -e ".[dev]"
    echo [KhemSAR] Launching KhemSAR at http://127.0.0.1:8765 ...
    python -m khemsar.main
    goto :eof
)

echo [KhemSAR] Using system Python...
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e ".[ml,dev]" || pip install -e ".[dev]"
echo [KhemSAR] Launching KhemSAR at http://127.0.0.1:8765 ...
python -m khemsar.main
