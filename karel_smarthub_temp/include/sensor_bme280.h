#ifndef SENSOR_BME280_H
#define SENSOR_BME280_H

struct Bme280Data {
    float temperature_c;
    float humidity_pct;
    float pressure_hpa;
};

// Initialize the sensor (returns true if OK)
bool bme280_init();

// Read one measurement (returns true if OK)
bool bme280_read(Bme280Data &out);

#endif
