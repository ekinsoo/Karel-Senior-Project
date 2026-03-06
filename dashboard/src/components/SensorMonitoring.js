import React from "react";

function SensorMonitoring({ sensorData }) {
  const getTempColor = () => {
    if (sensorData.temperature === null) return "#6b7280";
    const t = sensorData.temperature;
    if (t <= 25) return "#47b881";
    if (t <= 30) {
      const ratio = (t - 25) / 5;
      const r = Math.round(0x47 + (0xe8 - 0x47) * ratio);
      const g = Math.round(0xb8 + (0xa8 - 0xb8) * ratio);
      const b = Math.round(0x81 + (0x38 - 0x81) * ratio);
      return `rgb(${r},${g},${b})`;
    }
    if (t <= 40) {
      const ratio = (t - 30) / 10;
      const r = Math.round(0xe8 + (0xd9 - 0xe8) * ratio);
      const g = Math.round(0xa8 + (0x53 - 0xa8) * ratio);
      const b = Math.round(0x38 + (0x4f - 0x38) * ratio);
      return `rgb(${r},${g},${b})`;
    }
    return "#d9534f";
  };

  const getTempStatus = () => {
    if (sensorData.temperature === null) return "NO DATA";
    const t = sensorData.temperature;
    if (t > 35) return "CRITICAL";
    if (t > 25) return "WARNING";
    return "NORMAL";
  };

  const getTempDisplay = () => {
    return sensorData.temperature !== null ? `${sensorData.temperature}°C` : "-- °C";
  };

  const getHumidityDisplay = () => {
    return sensorData.humidity !== null ? `${sensorData.humidity}%` : "-- %";
  };

  return (
    <div className="sensor-card">
      <div className="card-header">
        <h6 className="card-title">Sensors</h6>
      </div>

      <div className="card-content">
        {/* Temperature Sensor */}
        <div className="sensor-item">
          <div className="sensor-data">
            <span className="sensor-label">Temperature</span>
            <span className="sensor-value">{getTempDisplay()}</span>
            <div className="sensor-bar">
              <div
                className="sensor-bar-fill"
                style={{
                  width: sensorData.temperature !== null
                    ? `${((sensorData.temperature - 18) / (35 - 18)) * 100}%`
                    : "0%",
                  backgroundColor: getTempColor(),
                }}
              ></div>
            </div>
            <span className="sensor-status" style={{ color: getTempColor() }}>
              {getTempStatus()}
            </span>
          </div>
        </div>

        {/* Humidity Sensor */}
        <div className="sensor-item">
          <div className="sensor-data">
            <span className="sensor-label">Humidity</span>
            <span className="sensor-value">{getHumidityDisplay()}</span>
            <div className="sensor-bar">
              <div
                className="sensor-bar-fill"
                style={{
                  width: sensorData.humidity !== null ? `${sensorData.humidity}%` : "0%",
                  backgroundColor: "#5bbfcf",
                }}
              ></div>
            </div>
            <span className="sensor-status">
              {sensorData.humidity !== null ? "Optimal" : "NO DATA"}
            </span>
          </div>
        </div>

        {/* QR Code */}
        <div className="sensor-item">
          <div className="sensor-data">
            <span className="sensor-label">Last QR Code</span>
            <span className="sensor-value qr-value">{sensorData.qrCode}</span>
            <span className="sensor-timestamp">
              {sensorData.qrScannedTime}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SensorMonitoring;
