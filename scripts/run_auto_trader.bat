@echo off
REM Auto-Trader Windows Startup Script
REM This script runs the Auto-Trader system on Windows

setlocal EnableDelayedExpansion

echo ============================================================
echo Auto-Trader Automated Trading System
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11 or higher
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found. Creating one...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    
    echo Installing dependencies...
    call .venv\Scripts\activate.bat
    pip install -U pip
    pip install uv
    uv sync
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
) else (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Check for .env file
if not exist ".env" (
    if exist ".env.example" (
        echo WARNING: .env file not found. Copying from .env.example
        copy .env.example .env
        echo Please edit .env file with your configuration
        notepad .env
        pause
    ) else (
        echo ERROR: .env file not found
        pause
        exit /b 1
    )
)

REM Parse command line arguments
set "LIVE_MODE="
set "DEBUG_MODE="
set "CHECK_CONFIG="

:parse_args
if "%~1"=="" goto :end_parse
if /i "%~1"=="--live" set "LIVE_MODE=--live"
if /i "%~1"=="--debug" set "DEBUG_MODE=--debug"
if /i "%~1"=="--check-config" set "CHECK_CONFIG=--check-config"
shift
goto :parse_args
:end_parse

REM Run the application
echo.
echo Starting Auto-Trader...
echo ============================================================

if defined CHECK_CONFIG (
    python run_auto_trader.py --check-config
) else if defined LIVE_MODE (
    echo.
    echo ############################################################
    echo WARNING: LIVE TRADING MODE
    echo Real money trades will be executed!
    echo ############################################################
    echo.
    set /p "CONFIRM=Type 'YES' to confirm live trading mode: "
    if "!CONFIRM!"=="YES" (
        python run_auto_trader.py --live %DEBUG_MODE%
    ) else (
        echo Live trading cancelled.
    )
) else (
    echo Running in SIMULATION MODE (no real trades)
    python run_auto_trader.py %DEBUG_MODE%
)

REM Check exit code
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Auto-Trader exited with error code %errorlevel%
    pause
)

endlocal