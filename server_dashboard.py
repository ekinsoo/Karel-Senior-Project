import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import threading
import paho.mqtt.client as mqtt



MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC = "jetson/camera/image/jpeg"

app = FastAPI()
static_dir = Path("./static")
static_dir.mkdir(exist_ok=True)
latest_path = static_dir / "latest.jpg"


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
    client.subscribe(TOPIC, qos=1)

def on_message(client, userdata, msg):
    try:
        with open(latest_path, "wb") as f:
            f.write(msg.payload)
    except Exception as e:
        print("Write error:", e)

def mqtt_thread():
    c = mqtt.Client(client_id="server-sub", clean_session=True)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    c.loop_forever()

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


# New: send the latest image to React
from fastapi.responses import FileResponse

@app.get("/api/latest-image")
def latest_image():
    return FileResponse("static/latest.jpg", media_type="image/jpeg")
