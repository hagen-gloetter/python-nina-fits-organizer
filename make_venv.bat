@echo off
setlocal
cd /d "%~dp0"

set "VENV_DIR=astro_env_win"

echo Setting up Python virtual environment in '%VENV_DIR%'...

rem A previous run may have been interrupted, leaving python.exe without the
rem activation scripts. Detect that and rebuild the venv from scratch.
if exist "%VENV_DIR%\Scripts\python.exe" if not exist "%VENV_DIR%\Scripts\Activate.ps1" (
    echo Found incomplete virtual environment, removing it first...
    rmdir /s /q "%VENV_DIR%"
)

where py >nul 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: The Python launcher 'py' was not found on PATH.
    echo Install Python 3.13 from https://www.python.org/downloads/ and ensure
    echo "Add python.exe to PATH" / the py launcher is enabled, then retry.
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    py -3.13 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to create the virtual environment with Python 3.13.
        echo Make sure Python 3.13 is installed ^(py -0p lists available versions^).
        exit /b 1
    )
)

"%VENV_DIR%\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 (
    echo.
    echo ERROR: Could not bootstrap pip into the virtual environment.
    echo Delete the '%VENV_DIR%' folder and re-run this script.
    exit /b 1
)

"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo ERROR: Failed to upgrade pip. Check your internet connection and retry.
    exit /b 1
)

"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies from requirements.txt.
    exit /b 1
)

echo.
echo Setup completed.
echo Activate with ^(cmd^):        %VENV_DIR%\Scripts\activate.bat
echo Activate with ^(PowerShell^): .\%VENV_DIR%\Scripts\Activate.ps1

endlocal