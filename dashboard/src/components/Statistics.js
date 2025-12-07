import React from "react";

function Statistics({ statistics }) {
  return (
    <div className="stats-card">
      <div className="card-header">
        <h6 className="card-title">📈 Statistics</h6>
      </div>

      <div className="card-content">
        <div className="stat-row">
          <span className="stat-icon">🎯</span>
          <div className="stat-info">
            <span className="stat-label">Inspected Today</span>
            <span className="stat-big">{statistics.totalInspected}</span>
          </div>
        </div>

        <div className="stat-row">
          <span className="stat-icon">❌</span>
          <div className="stat-info">
            <span className="stat-label">Defects Found</span>
            <span className="stat-big" style={{ color: "#ff6b6b" }}>
              {statistics.defectsFound}
            </span>
          </div>
        </div>

        <div className="stat-row">
          <span className="stat-icon">📊</span>
          <div className="stat-info">
            <span className="stat-label">Defect Rate</span>
            <span className="stat-big">{statistics.defectRate}%</span>
          </div>
        </div>

        <div className="stat-row">
          <span className="stat-icon">⏱️</span>
          <div className="stat-info">
            <span className="stat-label">Avg Time</span>
            <span className="stat-big">{statistics.averageProcessTime}s</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Statistics;
