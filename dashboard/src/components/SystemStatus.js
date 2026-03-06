import React from "react";

function SystemStatus({ systemStatus }) {
  const StatusItem = ({ label, status }) => (
    <div className="status-item">
      <div className="status-info">
        <span className="status-label">{label}</span>
        <div className="status-indicator">
          <span
            className="status-dot"
            style={{
              backgroundColor: status ? "#47b881" : "#d9534f",
            }}
          ></span>
          <span style={{ color: status ? "#47b881" : "#d9534f" }}>{status ? "Online" : "Offline"}</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="system-card">
      <div className="card-header">
        <h6 className="card-title">System Status</h6>
      </div>

      <div className="card-content">
        <StatusItem
          label="ESP32 Board"
          status={systemStatus.esp32Connected}
        />
        <StatusItem
          label="Camera"
          status={systemStatus.cameraOnline}
        />

        <div className="uptime-section">
          <span className="uptime-label">System Status</span>
          <span className="uptime-value">{systemStatus.uptime}</span>
        </div>
      </div>
    </div>
  );
}

export default SystemStatus;
