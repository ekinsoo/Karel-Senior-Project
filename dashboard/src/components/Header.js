import React from "react";

function Header({ systemStatus }) {
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

          <div className="device-status-group">
            <div className="device-badge">
              <span className={`device-dot ${systemStatus.esp32Connected ? "online" : "offline"}`}></span>
              ESP32
            </div>
            <div className="device-badge">
              <span className={`device-dot ${systemStatus.cameraOnline ? "online" : "offline"}`}></span>
              Camera
            </div>
          </div>

          <div className="header-uptime">{systemStatus.uptime}</div>
        </div>
      </div>
    </header>
  );
}

export default Header;
