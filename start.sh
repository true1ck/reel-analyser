#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  🎬 Reel Analyser — One-Command Launcher
# ═══════════════════════════════════════════════════════════

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  🎬 Reel Analyser"
echo "  ═══════════════════════"
echo ""

# Check system dependencies
command -v ffmpeg >/dev/null 2>&1 || { echo "[!] Error: ffmpeg is not installed. Please run 'brew install ffmpeg'"; exit 1; }
command -v yt-dlp >/dev/null 2>&1 || { echo "[!] Error: yt-dlp is not installed. Please run 'brew install yt-dlp'"; exit 1; }

# Check Python venv
if [ ! -d "venv" ]; then
    echo "[!] Python venv not found. Creating..."
    python3 -m venv venv
fi

# Install Python deps
echo "[→] Skipping pip install to avoid dependency resolver hang..."
# ./venv/bin/pip install -q -r requirements.txt 2>/dev/null

# Check Node
if [ ! -d "frontend/node_modules" ]; then
    echo "[→] Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# Run migration
echo "[→] Running migration..."
./venv/bin/python migrate.py

echo ""
echo "[✓] Starting servers..."
echo ""

# Start backend
./venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "  ════════════════════════════════════════"
echo "  ✅ Backend:  http://localhost:8000"
echo "  ✅ Frontend: http://localhost:5173"
echo "  ✅ API Docs: http://localhost:8000/docs"
echo "  ════════════════════════════════════════"
echo ""
echo "  Press Ctrl+C to stop both servers"
echo ""

cleanup() {
    echo ""
    echo "[→] Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "[✓] Stopped."
}

trap cleanup EXIT INT TERM
wait
