import React from "react";

function Header({ systemStatus }) {
  const getConnectionStatus = () => {
    const connected = [
      systemStatus.esp32Connected,
      systemStatus.cameraOnline,
    ].filter((status) => status).length;
    const total = 2;
    return { connected, total };
  };

  const connectionStatus = getConnectionStatus();
  const isSystemHealthy =
    systemStatus.esp32Connected && systemStatus.cameraOnline;

  return (
    <header className="iot-header">
      <div className="header-container">
        <div className="header-brand">
          <div className="brand-logo">
            <img src="/karel_logo-01-1.png" alt="Karel Logo" />
          </div>
          <div className="brand-info">
            <h1>Karel SmartHub</h1>
            <p>PCB Defect Detection System</p>
          </div>
        </div>

        <div className="header-status">
          <div className={`system-health ${isSystemHealthy ? "healthy" : "unhealthy"}`}>
            <div className="health-indicator"></div>
            <span>{isSystemHealthy ? "System Healthy" : "System Alert"}</span>
          </div>

          <div className="connections-status">
            <span className="connection-count">
              {connectionStatus.connected}/{connectionStatus.total} Connected
            </span>
            <div className="connection-icons">
              <div
                className={`icon-badge ${systemStatus.esp32Connected ? "connected" : "offline"}`}
                title="ESP32"
              >
                ⚙️
              </div>
              <div
                className={`icon-badge ${systemStatus.cameraOnline ? "connected" : "offline"}`}
                title="Camera"
              >
                📷
              </div>
            </div>
          </div>

          <div className="uptime-info">
            <span className="uptime-label">System Status</span>
            <span className="uptime-value">{systemStatus.uptime}</span>
          </div>
        </div>
      </div>
    </header>
  );
}

export default Header;
