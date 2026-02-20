@echo off
REM Shortlist - Unified Startup Script for Windows
REM This script checks dependencies, starts the backend and frontend, and opens your browser

setlocal enabledelayedexpansion

echo.
echo ╔═══════════════════════════════╗
echo ║      Shortlist Startup      ║
echo ╚═══════════════════════════════╝
echo.

echo → Checking dependencies...
echo.

REM Check Python (handle Windows Store alias issue)
set PYTHON_CMD=python
python --version >nul 2>&1
if errorlevel 1 (
    REM Try python3 as fallback
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo ✗ Python is not installed or not accessible
        echo.
        echo   Common issue on Windows: The Microsoft Store Python alias may be interfering.
        echo.
        echo   To fix:
        echo   1. Open Settings → Apps → Advanced app settings → App execution aliases
        echo   2. Turn OFF both python.exe and python3.exe
        echo   3. Install Python from: https://www.python.org/downloads/
        echo   4. Make sure to check "Add Python to PATH" during installation
        echo.
        echo   OR try running this script with python3 instead:
        echo   python3 start.bat
        echo.
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=python3
    )
)

for /f "tokens=2" %%i in ('!PYTHON_CMD! --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✓ Python %PYTHON_VERSION% (using !PYTHON_CMD!)

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Node.js is not installed
    echo   Please install Node.js 18 or higher from:
    echo   https://nodejs.org/
    pause
    exit /b 1
)

for /f "tokens=1" %%i in ('node --version') do set NODE_VERSION=%%i
echo ✓ Node.js %NODE_VERSION%

REM Check uv (handle PATH issues on Windows)
set UV_CMD=uv
uv --version >nul 2>&1
if errorlevel 1 (
    echo ✗ uv is not installed
    echo   Installing uv...
    !PYTHON_CMD! -m pip install uv
    if errorlevel 1 (
        echo   Failed to install uv. Please install manually:
        echo   !PYTHON_CMD! -m pip install uv
        pause
        exit /b 1
    )

    REM Check if uv is now accessible
    uv --version >nul 2>&1
    if errorlevel 1 (
        REM uv command not in PATH yet, use python -m uv instead
        !PYTHON_CMD! -m uv --version >nul 2>&1
        if errorlevel 1 (
            echo   Failed to run uv. Please restart your terminal and try again.
            pause
            exit /b 1
        )
        set UV_CMD=!PYTHON_CMD! -m uv
        echo   ✓ uv installed (using !PYTHON_CMD! -m uv)
        echo.
        echo   Note: Restart your terminal to use 'uv' command directly.
        echo.
    ) else (
        echo   ✓ uv installed
    )
) else (
    echo ✓ uv
)
echo.

REM Check if dependencies are installed
echo → Checking if dependencies are installed...
echo.

if not exist ".venv" (
    echo   Installing Python dependencies ^(this may take a minute^)...
    !UV_CMD! sync
    if errorlevel 1 (
        echo   Failed to install Python dependencies
        pause
        exit /b 1
    )
    echo   ✓ Python dependencies installed
) else (
    echo   ✓ Python dependencies already installed
)

if not exist "frontend\node_modules" (
    echo   Installing Node dependencies ^(this may take a minute^)...
    cd frontend
    call npm install
    cd ..
    if errorlevel 1 (
        echo   Failed to install Node dependencies
        pause
        exit /b 1
    )
    echo   ✓ Node dependencies installed
) else (
    echo   ✓ Node dependencies already installed
)

echo.

REM Check configuration
if not exist "config.json" (
    if "%LLM_API_KEY%"=="" (
        echo ⚠ No configuration found
        echo   The app will start, but you'll need to configure your LLM API key
        echo   in the Settings panel ^(gear icon in the top right^).
        echo.
    )
)

echo → Starting Shortlist...
echo.

REM Start backend in a new window
echo   Starting backend server...
start "Shortlist - Backend" cmd /c "!UV_CMD! run python main.py"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend in a new window
echo   Starting frontend dev server...
start "Shortlist - Frontend" cmd /c "cd frontend && npm run dev"

REM Wait for frontend to start
timeout /t 3 /nobreak >nul

echo.
echo ╔═══════════════════════════════════════╗
echo ║          🚀 App is running!          ║
echo ╚═══════════════════════════════════════╝
echo.
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:5000
echo.
echo   Close the backend and frontend windows to stop the app
echo.

REM Open browser
timeout /t 2 /nobreak >nul
start http://localhost:3000

echo Press any key to exit this window...
pause >nul
