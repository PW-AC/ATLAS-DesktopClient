@echo off
setlocal

:: Change to the script's directory to ensure relative paths work correctly
cd /d "%~dp0"

:: Set the window title
title Acencia Hub Launcher

:: --- Configuration ---
set VENV_DIR=venv
set REQUIREMENTS_FILE=requirements.txt

:: --- Virtual Environment Check ---
echo.
echo [INFO] Checking for Python virtual environment in '%VENV_DIR%'...
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo [ERROR] Please run the following commands first:
    echo.
    echo   python -m venv %VENV_DIR%
    echo.
    pause
    exit /b 1
)

:: --- Activate Virtual Environment ---
echo [INFO] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

:: --- Install/Update Dependencies ---
echo.
echo [INFO] Installing/updating dependencies from '%REQUIREMENTS_FILE%'...
python -m pip install -r "%REQUIREMENTS_FILE%"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies. Please check the console output.
    pause
    exit /b 1
)

:: --- Start the Application in a loop ---
:start_server
echo.
echo [INFO] Starting Acencia Hub... (%time%)
python -u run.py

echo.
echo [WARN] Server process exited. Restarting in 3 seconds...
timeout /t 3 /nobreak >nul
goto start_server

endlocal
pause