#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BME280.h>

#include "sensor_bme280.h"

// Create a global BME280 object
static Adafruit_BME280 bme;

// You can change this later if your module uses 0x77
static const uint8_t BME280_I2C_ADDR = 0x76;

bool bme280_init()
{
    // Start I2C (default pins for ESP32-S3 DevKitC will be used)
    Wire.begin();

    // Try to initialize the sensor
    bool status = bme.begin(BME280_I2C_ADDR);

    if (!status) {
        Serial.println("BME280 not found! Check wiring or address.");
        return false;
    }

    Serial.println("BME280 initialized successfully.");
    return true;
}

bool bme280_read(Bme280Data &out)
{
    // It is safe to call readTemperature/readHumidity/readPressure directly.
    out.temperature_c = bme.readTemperature();            // °C
    out.humidity_pct  = bme.readHumidity();               // %
    out.pressure_hpa  = bme.readPressure() / 100.0F;      // Pa → hPa

    // You could add basic sanity checks if you want
    return true;
}