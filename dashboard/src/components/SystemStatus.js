import React from "react";

function SystemStatus({ systemStatus }) {
  const StatusItem = ({ icon, label, status }) => (
    <div className="status-item">
      <span className="status-icon">{icon}</span>
      <div className="status-info">
        <span className="status-label">{label}</span>
        <div className="status-indicator">
          <span
            className="status-dot"
            style={{
              backgroundColor: status ? "#00ff00" : "#ff3333",
            }}
          ></span>
          <span className="status-text">{status ? "Online" : "Offline"}</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="system-card">
      <div className="card-header">
        <h6 className="card-title">🔧 System Status</h6>
      </div>

      <div className="card-content">
        <StatusItem
          icon="⚙️"
          label="ESP32 Board"
          status={systemStatus.esp32Connected}
        />
        <StatusItem
          icon="📷"
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
