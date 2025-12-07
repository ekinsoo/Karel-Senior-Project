import React from "react";

function AlertPanel({ alerts }) {
  const getSeverityColor = (severity) => {
    switch (severity) {
      case "high":
        return "#ff3333";
      case "medium":
        return "#ffaa00";
      case "low":
        return "#00aaff";
      default:
        return "#00ff00";
    }
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case "high":
        return "🔴";
      case "medium":
        return "🟠";
      case "low":
        return "🔵";
      default:
        return "🟢";
    }
  };

  return (
    <div className="alert-panel-card">
      <div className="card-header">
        <h6 className="card-title">🚨 Alert History</h6>
        <span className="alert-count">{alerts.length}</span>
      </div>

      <div className="card-content">
        {alerts.length === 0 ? (
          <div className="no-alerts">
            <span className="no-alerts-icon">✓</span>
            <span className="no-alerts-text">No alerts</span>
          </div>
        ) : (
          <div className="alerts-list">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className="alert-item"
                style={{ borderLeftColor: getSeverityColor(alert.severity) }}
              >
                <div className="alert-icon">
                  {getSeverityIcon(alert.severity)}
                </div>
                <div className="alert-content">
                  <p className="alert-message">{alert.message}</p>
                  <span className="alert-time">{alert.timestamp}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default AlertPanel;
