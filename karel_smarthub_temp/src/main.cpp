#include <Arduino.h>
#include <WiFi.h>
#include <time.h>
#include <PubSubClient.h>
#include "sensor_bme280.h"

/* =========================
   CONFIG
   ========================= */

// ---- Device identity (used in topic + payload) ----
const char *DEVICE_ID = "esp32s3-01";

/* =========================
   WIFI PROFILES (OPEN + PRIVATE)
   ========================= */

struct WifiProfile {
  const char* ssid;
  const char* pass;   // "" => OPEN network
};

// 0 = OPEN (public), 1 = PRIVATE
WifiProfile WIFI_PROFILES[] = {
  {"bilkent-EEE", ""},                    // open network
  {"cmlbrk", "gelipcokeryalnizliklar"}     // private hotspot (example)
};

static int wifi_profile_idx = 0;  // which one we are using

/* =========================
   MQTT
   ========================= */

// ---- MQTT broker (Jetson Nano on the same network) ----
const char *MQTT_SERVER = "139.179.55.211";   // Jetson Nano IP
const int   MQTT_PORT   = 1883;

// Topic base (final topic becomes: karel/telemetry/env/<DEVICE_ID>)
const char *MQTT_TOPIC_BASE = "karel/telemetry/env";

/* =========================
   NTP time (UTC recommended)
   ========================= */

const long GMT_OFFSET_SEC = 0;
const int  DAYLIGHT_OFFSET_SEC = 0;

/* =========================
   GLOBALS
   ========================= */

WiFiClient espClient;
PubSubClient mqtt(espClient);

static time_t start_epoch = 0;     // epoch at boot after NTP sync
static uint32_t seq = 0;           // increments each sample

bool sensor_ok = false;

/* =========================
   WIFI SELECTOR (SERIAL)
   ========================= */

int choose_wifi_profile_serial(uint32_t timeout_ms = 5000) {
  Serial.println();
  Serial.println("Choose WiFi profile:");
  Serial.println("  [0] OPEN   (bilkent-wifi)");
  Serial.println("  [1] PRIVATE(cmlbrk hotspot)");
  Serial.println("Type 0 or 1 within 5 seconds...");

  uint32_t t0 = millis();
  while (millis() - t0 < timeout_ms) {
    if (Serial.available()) {
      char c = Serial.read();
      if (c == '0') return 0;
      if (c == '1') return 1;
    }
    delay(10);
  }

  Serial.println("No input. Using default profile 0.");
  return 0;
}

/* =========================
   WIFI CONNECT
   ========================= */

void wifi_connect_secure() {
  const WifiProfile &wp = WIFI_PROFILES[wifi_profile_idx];

  Serial.print("Connecting to WiFi: ");
  Serial.println(wp.ssid);

  WiFi.mode(WIFI_STA);

  // Clean start helps with flaky networks
  WiFi.disconnect(true);
  delay(300);

  // If pass is empty => OPEN network => WiFi.begin(ssid)
  if (wp.pass == nullptr || strlen(wp.pass) == 0) {
    WiFi.begin(wp.ssid);
  } else {
    WiFi.begin(wp.ssid, wp.pass);
  }

  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi connected. IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("RSSI: ");
    Serial.println(WiFi.RSSI());
  } else {
    Serial.println("WiFi NOT connected.");
  }
}

/* =========================
   NTP TIME
   ========================= */

bool ntp_sync() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Skipping NTP (no WiFi).");
    return false;
  }

  Serial.println("Syncing time via NTP...");
  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC,
             "pool.ntp.org", "time.nist.gov");

  struct tm timeinfo;
  int tries = 0;
  while (!getLocalTime(&timeinfo) && tries < 20) {
    delay(500);
    Serial.print("#");
    tries++;
  }
  Serial.println();

  if (tries >= 20) {
    Serial.println("NTP sync FAILED.");
    return false;
  }

  time(&start_epoch);

  char buf[32];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  Serial.print("NTP OK. Start time: ");
  Serial.println(buf);

  return true;
}

/* =========================
   MQTT
   ========================= */

String buildTopic() {
  // karel/telemetry/env/<device_id>
  String t = String(MQTT_TOPIC_BASE);
  t += "/";
  t += DEVICE_ID;
  return t;
}

void mqtt_connect() {
  // set server each time is fine (simple + safe)
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);

  while (!mqtt.connected()) {
    Serial.print("Connecting to MQTT broker... ");

    // Unique client id
    String clientId = "esp32s3-";
    clientId += String((uint32_t)ESP.getEfuseMac(), HEX);

    bool ok = mqtt.connect(clientId.c_str());

    if (ok) {
      Serial.println("OK");
      Serial.print("Publishing topic: ");
      Serial.println(buildTopic());
    } else {
      Serial.print("FAILED, rc=");
      Serial.print(mqtt.state());
      Serial.println(" (retrying in 2s)");
      delay(2000);
    }
  }
}

/* =========================
   JSON BUILDER
   ========================= */

String buildMeasurementJson(const Bme280Data &data) {
  unsigned long elapsed_sec = millis() / 1000;
  seq++;

  time_t t_epoch = 0;
  String t_iso = "unknown";

  if (start_epoch > 0) {
    t_epoch = start_epoch + (time_t)elapsed_sec;

    struct tm tm_utc;
    gmtime_r(&t_epoch, &tm_utc);

    char buf[32];
    strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm_utc);
    t_iso = String(buf);
  }

  String json = "{";
  json += "\"device_id\":\""; json += DEVICE_ID; json += "\"";
  json += ",\"sensor\":\"bme280\"";
  json += ",\"seq\":";        json += String(seq);
  json += ",\"temp_c\":";     json += String(data.temperature_c, 2);
  json += ",\"hum_pct\":";    json += String(data.humidity_pct, 2);
  json += ",\"press_hpa\":";  json += String(data.pressure_hpa, 2);
  json += ",\"t_epoch\":";    json += String((long)t_epoch);
  json += ",\"t_iso\":\"";    json += t_iso; json += "\"";
  json += "}";

  return json;
}

/* =========================
   SETUP / LOOP
   ========================= */

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("Booting ESP32-S3...");

  // 1) Sensor init
  sensor_ok = bme280_init();
  Serial.println(sensor_ok ? "BME280 init OK." : "BME280 init FAILED.");

  // 2) Choose Wi-Fi profile (Serial) + connect
  wifi_profile_idx = choose_wifi_profile_serial(5000);
  wifi_connect_secure();

  // 3) NTP
  ntp_sync();

  // 4) MQTT
  mqtt_connect();
}

void loop() {
  // Keep connections alive / recover if needed
  if (WiFi.status() != WL_CONNECTED) {
    wifi_connect_secure();
    // If Wi-Fi comes back, refresh NTP once
    ntp_sync();
  }

  if (!mqtt.connected()) {
    mqtt_connect();
  }
  mqtt.loop();

  // Read sensor
  Bme280Data data;
  if (bme280_read(data)) {
    String payload = buildMeasurementJson(data);
    String topic = buildTopic();

    // Publish (retain=false)
    bool ok = mqtt.publish(topic.c_str(), payload.c_str(), false);

    Serial.print("Publish: ");
    Serial.println(ok ? "OK" : "FAILED");
    Serial.println(payload);
  } else {
    Serial.println("Failed to read BME280.");
  }

  delay(1000); // 1 Hz
}