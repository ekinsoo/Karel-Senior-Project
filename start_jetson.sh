#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  Jetson Nano — Start All Services
#  Usage: bash start_jetson.sh
# ─────────────────────────────────────────────────────────────────
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

VENV_PYTHON="$PROJECT_DIR/.venv/bin/python3"
VENV_UVICORN="$PROJECT_DIR/.venv/bin/uvicorn"

# 1. Mosquitto MQTT broker
echo "[1/3] Starting Mosquitto MQTT broker..."
if ! systemctl is-active --quiet mosquitto; then
    sudo systemctl start mosquitto
fi
echo "      Mosquitto running on port 1883"

# 2. FastAPI server (background)
echo "[2/3] Starting FastAPI server on port 8000..."
MQTT_HOST=localhost MQTT_PORT=1883 \
    "$VENV_UVICORN" server_dashboard:app --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!
echo "      FastAPI PID=$FASTAPI_PID"

# 3. Camera publisher
echo "[3/3] Starting Jetson CSI camera publisher (FPS=1)..."
sleep 2   # wait for FastAPI + broker to be ready
"$VENV_PYTHON" jetson_publisher.py localhost

# Cleanup on Ctrl+C
trap "echo 'Stopping...'; kill $FASTAPI_PID 2>/dev/null; exit 0" INT TERM
wait $FASTAPI_PID
