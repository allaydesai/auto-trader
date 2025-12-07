# Auto-Trader PowerShell Startup Script
# This script runs the Auto-Trader system on Windows using PowerShell

param(
    [switch]$Live,
    [switch]$Debug,
    [switch]$CheckConfig,
    [string]$Config
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Auto-Trader Automated Trading System" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.11 or higher" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Virtual environment not found. Creating one..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    & ".venv\Scripts\Activate.ps1"
    pip install -U pip
    pip install uv
    uv sync
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & ".venv\Scripts\Activate.ps1"
}

# Check for .env file
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "WARNING: .env file not found. Copying from .env.example" -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
        Write-Host "Please edit .env file with your configuration" -ForegroundColor Yellow
        notepad ".env"
        Read-Host "Press Enter to continue"
    } else {
        Write-Host "ERROR: .env file not found" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Build command arguments
$args = @()

if ($CheckConfig) {
    $args += "--check-config"
}

if ($Live) {
    $args += "--live"
}

if ($Debug) {
    $args += "--debug"
}

if ($Config) {
    $args += "--config"
    $args += $Config
}

# Run the application
Write-Host ""
Write-Host "Starting Auto-Trader..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if ($CheckConfig) {
    python run_auto_trader.py @args
} elseif ($Live) {
    Write-Host ""
    Write-Host "############################################################" -ForegroundColor Red
    Write-Host "WARNING: LIVE TRADING MODE" -ForegroundColor Red
    Write-Host "Real money trades will be executed!" -ForegroundColor Red
    Write-Host "############################################################" -ForegroundColor Red
    Write-Host ""
    
    $confirmation = Read-Host "Type 'YES' to confirm live trading mode"
    if ($confirmation -eq "YES") {
        python run_auto_trader.py @args
    } else {
        Write-Host "Live trading cancelled." -ForegroundColor Yellow
    }
} else {
    Write-Host "Running in SIMULATION MODE (no real trades)" -ForegroundColor Green
    python run_auto_trader.py @args
}

# Check exit code
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Auto-Trader exited with error code $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}