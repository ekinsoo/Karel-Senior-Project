import os
from pathlib import Path
from datetime import datetime
from collections import deque
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import threading
import time
import numpy as np
import cv2
import json
import paho.mqtt.client as mqtt

from qr.pcb_center_layout import decode_edge_panel_codes
from queue import Queue, Empty

_qr_frame_queue = Queue(maxsize=1)



MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
QR_MULTI_BUDGET_MS = float(os.getenv("QR_MULTI_BUDGET_MS", "5000"))
TOPIC_CAMERA  = "jetson/camera/image/jpeg"
TOPIC_COMMAND  = "jetson/camera/command"
TOPIC_STATUS   = "jetson/camera/status"
TOPIC_BME280 = os.getenv("MQTT_TOPIC_BME280", "karel/telemetry/env/#")

app = FastAPI()
static_dir = Path("./static")
static_dir.mkdir(exist_ok=True)
latest_path = static_dir / "latest.jpg"

# ── QR result store (thread-safe) ────────────────────────────────────────────
_qr_lock = threading.Lock()
_qr_latest: dict | None = None          # most recent decode result
_qr_history: deque = deque(maxlen=50)    # last 50 results for the dashboard
_qr_last_signature: tuple[str, ...] | None = None  # dedup: last decoded bundle
_QR_COOLDOWN_S = 5                       # same code re-accepted after N seconds
_qr_last_time: float = 0.0              # timestamp of last accepted decode

# ── BME280 environmental store (thread-safe) ─────────────────────────────────
_env_lock = threading.Lock()
_env_latest: dict | None = None           # most recent reading (any device)
_env_by_device: dict = {}                 # device_id → latest reading
_env_history: deque = deque(maxlen=200)   # last 200 readings for charts

# ── Camera mode state ────────────────────────────────────────────────────────
_mode_lock = threading.Lock()
_camera_mode: str = "live"                # "live" | "capture"

# ── MQTT publisher client (sends commands to Jetson) ─────────────────────────
_mqtt_pub: mqtt.Client | None = None


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # local network access from any device
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MQTT subscriber running in a background thread ---
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ Connected to MQTT Broker at {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(TOPIC_CAMERA, qos=1)
        client.subscribe(TOPIC_BME280, qos=1)
        client.subscribe(TOPIC_STATUS, qos=1)
        print(f"📡 Subscribed to: {TOPIC_CAMERA}")
        print(f"📡 Subscribed to: {TOPIC_BME280}")
        print(f"📡 Subscribed to: {TOPIC_STATUS}")
    else:
        print(f"❌ Failed to connect, return code {rc}")

def _handle_camera(payload: bytes):
    """Save latest frame and push decoded frame to QR worker."""
    tmp_path = static_dir / "latest.tmp"
    with open(tmp_path, "wb") as f:
        f.write(payload)
    os.replace(tmp_path, latest_path)   # atomic replace

    arr = np.frombuffer(payload, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is not None:
        try:
            while not _qr_frame_queue.empty():
                _qr_frame_queue.get_nowait()
        except Exception:
            pass
        try:
            _qr_frame_queue.put_nowait(frame)
        except Exception:
            pass


def _process_qr(frame):
    """Run edge DataMatrix multi-decode and store sorted results."""
    global _qr_latest, _qr_last_signature, _qr_last_time

    result = decode_edge_panel_codes(frame, time_budget_ms=QR_MULTI_BUDGET_MS)
    if not result.codes:
        print(f"❌ Edge DataMatrix not detected ({result.elapsed_ms} ms)")
        return

    codes = []
    for c in result.codes:
        codes.append(
            {
                "panel_index": c.panel_index,
                "row": c.row,
                "side": c.side,
                "data": c.data,
                "code_type": c.code_type,
                "method": c.method,
            }
        )

    signature = tuple(
        f"{c['panel_index'] if c['panel_index'] is not None else 'x'}:{c['data']}"
        for c in codes
    )
    now = time.monotonic()
    if signature == _qr_last_signature and (now - _qr_last_time) < _QR_COOLDOWN_S:
        return

    _qr_last_signature = signature
    _qr_last_time = now

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        # Keep first code in `data` for backward compatibility with existing UI.
        "data": codes[0]["data"],
        "code_type": codes[0]["code_type"],
        "method": "edge_layout_multi",
        "elapsed_ms": result.elapsed_ms,
        "decoded_count": len(codes),
        "codes": codes,
        "timestamp": ts,
        "status": "OK",
    }

    with _qr_lock:
        _qr_latest = entry
        _qr_history.appendleft(entry)

    vis = frame.copy()
    for c in result.codes:
        pts_i = c.points.astype(np.int32)
        cv2.polylines(vis, [pts_i], isClosed=True, color=(0, 0, 255), thickness=3)
        if c.panel_index is not None:
            x = int(pts_i[:, 0].min())
            y = int(pts_i[:, 1].min()) - 8
            cv2.putText(
                vis,
                str(c.panel_index),
                (x, max(15, y)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
    cv2.imwrite("debug_detected_live.jpg", vis)

    print(
        f"🔍 DataMatrix decoded: {len(codes)} code(s) "
        f"({entry['method']}, {entry['elapsed_ms']} ms)"
    )


def _qr_scanner_loop():
    """Background thread: scan newest frame from memory."""
    print("🔍 QR scanner thread started")
    while True:
        try:
            frame = _qr_frame_queue.get(timeout=1.0)
            _process_qr(frame)
        except Empty:
            continue
        except Exception as e:
            print(f"QR scanner error: {e}")

threading.Thread(target=_qr_scanner_loop, daemon=True, name="qr-scanner").start()


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
    global _camera_mode
    try:
        topic = msg.topic
        if topic.startswith("karel/telemetry/env"):
            _handle_bme280(msg.payload)
        elif topic == TOPIC_STATUS:
            data = json.loads(msg.payload)
            with _mode_lock:
                _camera_mode = data.get("mode", "live")
            print(f"📷 Camera mode synced: {_camera_mode}")
        else:
            _handle_camera(msg.payload)
    except Exception as e:
        print(f"Message processing error ({msg.topic}): {e}")

def mqtt_thread():
    global _mqtt_pub
    print(f"🔄 Attempting to connect to MQTT Broker at {MQTT_HOST}:{MQTT_PORT}...")
    try:
        # Subscriber client
        try:
            from paho.mqtt.enums import CallbackAPIVersion
            c = mqtt.Client(client_id="server-sub", clean_session=True, callback_api_version=CallbackAPIVersion.VERSION2)
        except ImportError:
            c = mqtt.Client(client_id="server-sub", clean_session=True)

        c.on_connect = on_connect
        c.on_message = on_message
        c.connect(MQTT_HOST, MQTT_PORT, keepalive=30)

        # Publisher client (for sending commands to Jetson)
        try:
            pub = mqtt.Client(client_id="server-pub", clean_session=True, callback_api_version=CallbackAPIVersion.VERSION2)
        except Exception:
            pub = mqtt.Client(client_id="server-pub", clean_session=True)
        pub.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
        pub.loop_start()
        _mqtt_pub = pub

        c.loop_forever()
    except Exception as e:
        print(f"❌ MQTT Connection Error: {e}")
        print("   Make sure Mosquitto is running and accessible.")

threading.Thread(target=mqtt_thread, daemon=True).start()

# --- Serve React dashboard build + camera images ---
REACT_BUILD = Path("./dashboard/build")

# Camera images saved here (latest.jpg)
app.mount("/cam-static", StaticFiles(directory=str(static_dir)), name="cam-static")

# React build's /static (JS, CSS bundles)
app.mount("/static", StaticFiles(directory=str(REACT_BUILD / "static")), name="react-static")

@app.get("/", response_class=HTMLResponse)
def index():
    return (REACT_BUILD / "index.html").read_text()

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


# ── Camera mode endpoints ────────────────────────────────────────────────────

@app.get("/api/camera/mode")
def camera_mode():
    """Return current camera mode."""
    with _mode_lock:
        return JSONResponse({"mode": _camera_mode})


@app.post("/api/camera/mode")
async def set_camera_mode(request: Request):
    """Switch between 'live' and 'capture' modes."""
    global _camera_mode
    body = await request.json()
    new_mode = body.get("mode", "live")
    if new_mode not in ("live", "capture"):
        return JSONResponse({"error": "Invalid mode"}, status_code=400)

    with _mode_lock:
        _camera_mode = new_mode

    if _mqtt_pub:
        _mqtt_pub.publish(
            TOPIC_COMMAND,
            json.dumps({"command": "set_mode", "mode": new_mode}),
            qos=1,
        )
    print(f"📷 Mode set to: {new_mode}")
    return JSONResponse({"mode": new_mode})


@app.post("/api/camera/capture")
def camera_capture():
    """Trigger a single frame capture (only works in capture mode)."""
    if _mqtt_pub:
        _mqtt_pub.publish(
            TOPIC_COMMAND,
            json.dumps({"command": "capture"}),
            qos=1,
        )
    print("📸 Capture command sent")
    return JSONResponse({"status": "capture_requested"})


# ── Catch-all: serve React root assets & SPA fallback (MUST be last) ─────────
@app.get("/{filename:path}")
def react_assets(filename: str):
    filepath = REACT_BUILD / filename
    if filepath.is_file():
        return FileResponse(str(filepath))
    return HTMLResponse((REACT_BUILD / "index.html").read_text())
