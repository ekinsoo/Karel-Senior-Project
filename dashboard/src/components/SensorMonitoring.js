import React from "react";

function SensorMonitoring({ sensorData }) {
  const getTempColor = () => {
    if (sensorData.temperature === null) return "#999999";
    switch (sensorData.temperatureStatus) {
      case "critical":
        return "#ff3333";
      case "warning":
        return "#ffaa00";
      default:
        return "#00ff00";
    }
  };

  const getTempStatus = () => {
    if (sensorData.temperature === null) return "NO DATA";
    switch (sensorData.temperatureStatus) {
      case "critical":
        return "CRITICAL";
      case "warning":
        return "WARNING";
      default:
        return "NORMAL";
    }
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
        <h6 className="card-title">📊 Sensors</h6>
      </div>

      <div className="card-content">
        {/* Temperature Sensor */}
        <div className="sensor-item">
          <div className="sensor-icon">🌡️</div>
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
          <div className="sensor-icon">💧</div>
          <div className="sensor-data">
            <span className="sensor-label">Humidity</span>
            <span className="sensor-value">{getHumidityDisplay()}</span>
            <div className="sensor-bar">
              <div
                className="sensor-bar-fill"
                style={{
                  width: sensorData.humidity !== null ? `${sensorData.humidity}%` : "0%",
                  backgroundColor: "#00aaff",
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
          <div className="sensor-icon">📱</div>
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
