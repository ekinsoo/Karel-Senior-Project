import sys
import os
import time
import json
import threading
import paho.mqtt.client as mqtt
import cv2
import numpy as np
from gi import require_version
require_version('Gst', '1.0')
from gi.repository import Gst

BROKER = sys.argv[1] if len(sys.argv) > 1 else "localhost"
PORT   = int(os.getenv("MQTT_PORT", "1883"))

TOPIC_IMAGE   = "jetson/camera/image/jpeg"
TOPIC_COMMAND  = "jetson/camera/command"
TOPIC_STATUS   = "jetson/camera/status"

FPS               = int(os.getenv("FPS", "1"))
WIDTH             = 1920
HEIGHT            = 1080
JPEG_QUALITY_LIVE = 75
JPEG_QUALITY_CAP  = 75  # maximum quality for single capture

_mode = "live"
_capture_requested = False
_lock = threading.Lock()

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[INFO] Connected to MQTT broker {BROKER}:{PORT}")
        client.subscribe(TOPIC_COMMAND, qos=1)
        print(f"[INFO] Listening for commands on {TOPIC_COMMAND}")
        _publish_status(client)
    else:
        print(f"[ERROR] Failed to connect, return code {rc}")

def _publish_status(c):
    c.publish(TOPIC_STATUS, json.dumps({"mode": _mode}), qos=1, retain=True)

def on_message(client, userdata, msg):
    global _mode, _capture_requested
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        cmd = data.get("command", "")

        with _lock:
            if cmd == "set_mode":
                new_mode = data.get("mode", "live")
                if new_mode in ("live", "capture"):
                    _mode = new_mode
                    print(f"[MODE] Switched to {_mode}")
                    _publish_status(client)
            elif cmd == "capture":
                _capture_requested = True
                print("[CAPTURE] Single frame requested")
    except Exception as e:
        print(f"[WARN] Bad command: {e}")

client = mqtt.Client(client_id="jetson-csi-gst-pub", clean_session=True)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, keepalive=30)
client.loop_start()

Gst.init(None)

pipeline_str = (
    "nvarguscamerasrc sensor-id=0 ! "
    f"video/x-raw(memory:NVMM), width={WIDTH}, height={HEIGHT}, framerate=30/1 ! "
    "nvvidconv ! "
    "video/x-raw, format=BGRx ! "
    "videoconvert ! "
    "video/x-raw, format=BGR ! "
    "appsink name=appsink emit-signals=true max-buffers=1 drop=true"
)

print("[INFO] Pipeline:")
print(pipeline_str)

pipeline = Gst.parse_launch(pipeline_str)
appsink  = pipeline.get_by_name("appsink")

if appsink is None:
    raise RuntimeError("Could not get appsink from pipeline")

pipeline.set_state(Gst.State.PLAYING)
print(f"[INFO] Starting in LIVE mode at {FPS} FPS → {BROKER}:{PORT}")

try:
    last_time = 0.0
    interval  = 1.0 / FPS

    while True:
        sample = appsink.emit("pull-sample")
        if sample is None:
            time.sleep(0.01)
            continue

        buf       = sample.get_buffer()
        caps      = sample.get_caps()
        structure = caps.get_structure(0)
        w         = structure.get_value("width")
        h         = structure.get_value("height")

        success, map_info = buf.map(Gst.MapFlags.READ)
        if not success:
            continue

        try:
            arr   = np.frombuffer(map_info.data, dtype=np.uint8)
            frame = arr.reshape((h, w, 3)).copy()
        finally:
            buf.unmap(map_info)

        with _lock:
            current_mode = _mode
            do_capture   = _capture_requested
            _capture_requested = False

        if current_mode == "capture":
            if not do_capture:
                continue
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, ts, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (0, 255, 0), 2, cv2.LINE_AA)
            ok, jpeg = cv2.imencode(".jpg", frame,
                                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY_CAP])
            if ok:
                client.publish(TOPIC_IMAGE, payload=jpeg.tobytes(), qos=1)
                print(f"[CAPTURE] Sent frame ({len(jpeg.tobytes())} bytes)")
            continue

        now = time.time()
        if now - last_time < interval:
            continue
        last_time = now

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, ts, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (0, 255, 0), 2, cv2.LINE_AA)
        ok, jpeg = cv2.imencode(".jpg", frame,
                                [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY_LIVE])
        if ok:
            client.publish(TOPIC_IMAGE, payload=jpeg.tobytes(), qos=1)

except KeyboardInterrupt:
    print("\n[INFO] Stopping...")

finally:
    pipeline.set_state(Gst.State.NULL)
    client.loop_stop()
    client.disconnect()
    print("[INFO] Clean exit.")