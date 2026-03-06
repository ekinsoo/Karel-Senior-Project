import os
from pathlib import Path
from datetime import datetime
from collections import deque
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import threading
import time
import numpy as np
import cv2
import paho.mqtt.client as mqtt

from qr.qr_pipeline import decode_frame
from output.log_writer import append_result



MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC_CAMERA = "jetson/camera/image/jpeg"
TOPIC_BME280 = os.getenv("MQTT_TOPIC_BME280", "karel/telemetry/env/#")
import json

app = FastAPI()
static_dir = Path("./static")
static_dir.mkdir(exist_ok=True)
latest_path = static_dir / "latest.jpg"

# ── QR result store (thread-safe) ────────────────────────────────────────────
_qr_lock = threading.Lock()
_qr_latest: dict | None = None          # most recent decode result
_qr_history: deque = deque(maxlen=50)    # last 50 results for the dashboard
_qr_last_data: str | None = None        # dedup: last decoded string
_QR_COOLDOWN_S = 5                       # same code re-accepted after N seconds
_qr_last_time: float = 0.0              # timestamp of last accepted decode

# ── BME280 environmental store (thread-safe) ─────────────────────────────────
_env_lock = threading.Lock()
_env_latest: dict | None = None           # most recent reading (any device)
_env_by_device: dict = {}                 # device_id → latest reading
_env_history: deque = deque(maxlen=200)   # last 200 readings for charts


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MQTT subscriber running in a background thread ---
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ Connected to MQTT Broker at {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(TOPIC_CAMERA, qos=1)
        client.subscribe(TOPIC_BME280, qos=1)
        print(f"📡 Subscribed to: {TOPIC_CAMERA}")
        print(f"📡 Subscribed to: {TOPIC_BME280}")
    else:
        print(f"❌ Failed to connect, return code {rc}")

def _handle_camera(payload: bytes):
    """Save latest frame + run QR pipeline."""
    global _qr_latest, _qr_last_data, _qr_last_time
    with open(latest_path, "wb") as f:
        f.write(payload)

    buf = np.frombuffer(payload, dtype=np.uint8)
    frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if frame is not None:
        qr = decode_frame(frame, time_budget_ms=200)
        if qr.decoded:
            now = time.monotonic()
            if qr.data == _qr_last_data and (now - _qr_last_time) < _QR_COOLDOWN_S:
                return
            _qr_last_data = qr.data
            _qr_last_time = now

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = {
                "data": qr.data,
                "code_type": qr.code_type,
                "method": qr.method,
                "elapsed_ms": qr.elapsed_ms,
                "timestamp": ts,
                "status": "OK",
            }
            with _qr_lock:
                _qr_latest = entry
                _qr_history.appendleft(entry)
            append_result(qr)


def _handle_bme280(payload: bytes):
    """Parse BME280 JSON and store latest + history."""
    global _env_latest
    raw = json.loads(payload)
    # Validate required fields
    required = ("temp_c", "hum_pct", "press_hpa")
    if not all(k in raw for k in required):
        print(f"BME280: missing fields in {raw}")
        return

    device_id = raw.get("device_id", "unknown")
    entry = {
        "device_id":  device_id,
        "temp_c":     round(float(raw["temp_c"]), 2),
        "hum_pct":    round(float(raw["hum_pct"]), 2),
        "press_hpa":  round(float(raw["press_hpa"]), 2),
        "seq":        raw.get("seq"),
        "t_iso":      raw.get("t_iso", datetime.now().isoformat()),
        "received":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with _env_lock:
        _env_latest = entry
        _env_by_device[device_id] = entry
        _env_history.appendleft(entry)
    print(f"BME280 [{device_id}] T={entry['temp_c']}°C  H={entry['hum_pct']}%  P={entry['press_hpa']} hPa")


def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        if topic.startswith("karel/telemetry/env"):
            _handle_bme280(msg.payload)
        else:
            _handle_camera(msg.payload)
    except Exception as e:
        print(f"Message processing error ({msg.topic}): {e}")

def mqtt_thread():
    print(f"🔄 Attempting to connect to MQTT Broker at {MQTT_HOST}:{MQTT_PORT}...")
    try:
        # Try using the newer API version if available
        try:
            from paho.mqtt.enums import CallbackAPIVersion
            c = mqtt.Client(client_id="server-sub", clean_session=True, callback_api_version=CallbackAPIVersion.VERSION2)
        except ImportError:
            c = mqtt.Client(client_id="server-sub", clean_session=True)

        c.on_connect = on_connect
        c.on_message = on_message
        c.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
        c.loop_forever()
    except Exception as e:
        print(f"❌ MQTT Connection Error: {e}")
        print("   Make sure EMQX is running and accessible.")

threading.Thread(target=mqtt_thread, daemon=True).start()

# --- Static + simple HTML dashboard ---
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Jetson Camera Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {
      background-color: #121212;
      color: #eaeaea;
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      text-align: center;
      padding-top: 40px;
    }
    h1 {
      font-weight: 600;
      color: #00b4d8;
      margin-bottom: 20px;
    }
    .card {
      background-color: #1e1e1e;
      border: 1px solid #333;
      border-radius: 10px;
      margin: 0 auto;
      width: 80%;
      max-width: 900px;
      padding: 20px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    img {
      width: 100%;
      height: auto;
      border-radius: 8px;
      border: 1px solid #444;
    }
    .timestamp {
      font-size: 0.9em;
      color: #888;
      margin-top: 10px;
    }
  </style>
</head>
<body>
  <h1>📸 Jetson Nano Live Camera Feed</h1>
  <div class="card">
    <img id="frame" src="/static/latest.jpg?ts=0" alt="Waiting for image...">
    <div class="timestamp" id="timestamp">Last updated: never</div>
  </div>

  <script>
    function updateFrame() {
      const img = document.getElementById('frame');
      const ts = Date.now();
      img.src = `/static/latest.jpg?ts=${ts}`;

      // update timestamp display
      const time = new Date().toLocaleTimeString();
      document.getElementById('timestamp').textContent = `Last updated: ${time}`;
    }

    setInterval(updateFrame, 2000); // refresh every 2s
  </script>
</body>
</html>
    """

# Run: uvicorn server_dashboard:app --reload --host 0.0.0.0 --port 8000
#MQTT_HOST=localhost uvicorn server_dashboard:app --reload --host 0.0.0.0 --port 8000


# ── API endpoints ────────────────────────────────────────────────────────────

@app.get("/api/latest-image")
def latest_image():
    return FileResponse("static/latest.jpg", media_type="image/jpeg")


@app.get("/api/qr-latest")
def qr_latest():
    """Return the most recent successful QR decode result."""
    with _qr_lock:
        if _qr_latest:
            return JSONResponse(_qr_latest)
    return JSONResponse({"data": None, "status": "NO_DATA"})


@app.get("/api/qr-history")
def qr_history():
    """Return the last N successful QR decode results (newest first)."""
    with _qr_lock:
        return JSONResponse(list(_qr_history))


@app.get("/api/env/latest")
def env_latest():
    """Return the most recent BME280 reading."""
    with _env_lock:
        if _env_latest:
            return JSONResponse(_env_latest)
    return JSONResponse({"status": "NO_DATA"})


@app.get("/api/env/history")
def env_history():
    """Return the last N BME280 readings (newest first)."""
    with _env_lock:
        return JSONResponse(list(_env_history))
