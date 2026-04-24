@echo off
SETLOCAL EnableDelayedExpansion

echo.
echo   Reel Analyser - Windows Launcher
echo   ==================================
echo.

:: Check for ffmpeg
where ffmpeg >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Error: ffmpeg is not installed or not in PATH.
    echo Please install it from https://ffmpeg.org/download.html
    exit /b 1
)

:: Check for Python venv
if not exist "venv" (
    echo [!] Python venv not found. Creating...
    python -m venv venv
)

:: Install dependencies
echo [->] Installing Python dependencies (Windows)...
call venv\Scripts\activate
pip install -r requirements-windows.txt

:: Check Node modules
if not exist "frontend\node_modules" (
    echo [→] Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

:: Run migration
echo [->] Running database migration...
python migrate.py

echo.
echo [OK] Starting servers...
echo.

:: Start Backend in a new window
start "Reel Analyser Backend" cmd /k "call venv\Scripts\activate && uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload"

:: Start Frontend in a new window
cd frontend
start "Reel Analyser Frontend" cmd /k "npm run dev"
cd ..

echo.
echo   ========================================
echo   [OK] Backend:  http://localhost:8080
echo   [OK] Frontend: http://localhost:5173
echo   [OK] API Docs: http://localhost:8080/docs
echo   ========================================
echo.
echo   Check the separate windows for logs.
echo.
pause
