import React from "react";

function AlertPanel({ alerts }) {
  const getSeverityColor = (severity) => {
    switch (severity) {
      case "high":
        return "#d9534f";
      case "medium":
        return "#e8a838";
      case "low":
        return "#4a90d9";
      default:
        return "#47b881";
    }
  };

  return (
    <div className="alert-panel-card">
      <div className="card-header">
        <h6 className="card-title">Alert History</h6>
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
