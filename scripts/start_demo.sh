#!/bin/bash
# ProtoAnalyzer Demo Startup Script
# Usage: bash scripts/start_demo.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "╔══════════════════════════════════════╗"
echo "║   ProtoAnalyzer — Protocol Analysis  ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Backend ─────────────────────────────────────────────────────────────────
cd "$PROJECT_ROOT/backend"

if [ ! -d "venv" ]; then
  echo "→ Creating Python virtual environment..."
  python3 -m venv venv
fi

echo "→ Installing Python dependencies..."
source venv/bin/activate
pip install -r requirements.txt -q

# Copy .env if missing
if [ ! -f "$PROJECT_ROOT/.env" ]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
  echo "→ Created .env from .env.example (add your API key there)"
fi

# Import demo data if DB is empty
DB_PATH="$PROJECT_ROOT/data/protocol_analysis.db"
if [ ! -f "$DB_PATH" ]; then
  echo "→ Importing demo data..."
  python "$PROJECT_ROOT/scripts/import_demo_data.py"
fi

echo "→ Starting backend server on http://localhost:8000 ..."
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
sleep 2

# Run full pipeline automatically
echo "→ Running analysis pipeline..."
curl -s -X POST http://localhost:8000/projects/1/run/full-pipeline > /dev/null
echo "   Pipeline complete!"

# ── Frontend ─────────────────────────────────────────────────────────────────
cd "$PROJECT_ROOT/frontend"

if [ ! -d "node_modules" ]; then
  echo "→ Installing npm dependencies..."
  npm install -q
fi

echo "→ Starting frontend on http://localhost:5173 ..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ System running!"
echo "   Frontend : http://localhost:5173"
echo "   Backend  : http://localhost:8000"
echo "   API Docs : http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers."

# Wait and cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait
