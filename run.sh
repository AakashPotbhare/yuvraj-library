#!/bin/bash
cd "$(dirname "$0")"
echo "Starting Yuvraj Library..."
if [ ! -d "venv" ]; then
    echo "Setting up Python environment (first time only)..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt -q
echo "Library is ready! Opening in your browser..."
python3 app.py &
APP_PID=$!
sleep 2
xdg-open http://localhost:5000 2>/dev/null || open http://localhost:5000 2>/dev/null || true
wait $APP_PID
