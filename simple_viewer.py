import cv2
import numpy as np
import paho.mqtt.client as mqtt
import sys

# Settings
BROKER = "localhost"
PORT = 1883
TOPIC = "jetson/camera/image/jpeg"

print(f"--- Simple MQTT Image Viewer ---")
print(f"Broker: {BROKER}:{PORT}")
print(f"Topic:  {TOPIC}")
print("Waiting for images... (Press 'q' to quit)")

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        
        print("✅ Connected successfully!")
        client.subscribe(TOPIC)
        print("📡 Subscribed.")
    else:
        print(f"❌ Connection failed with code {rc}")

def on_message(client, userdata, msg):
    try:
        # Convert bytes to numpy array
        nparr = np.frombuffer(msg.payload, np.uint8)
        # Decode image
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is not None:
            cv2.imshow("Live Feed (MQTT)", img)
            print(f"🖼️ Received frame: {img.shape} - {len(msg.payload)} bytes", end="\r")
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\nExiting...")
                client.disconnect()
                sys.exit(0)
        else:
            print("⚠️ Received data but could not decode image.")
            
    except Exception as e:
        print(f"Error processing image: {e}")

# Setup Client
try:
    from paho.mqtt.enums import CallbackAPIVersion
    client = mqtt.Client(client_id="simple-viewer", clean_session=True, callback_api_version=CallbackAPIVersion.VERSION2)
except ImportError:
    client = mqtt.Client(client_id="simple-viewer", clean_session=True)

client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(BROKER, PORT, 60)
    client.loop_forever()
except KeyboardInterrupt:
    print("\nStopped by user.")
except Exception as e:
    print(f"\n❌ Error: {e}")
